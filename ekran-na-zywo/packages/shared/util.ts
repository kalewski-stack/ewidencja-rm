// Czyste funkcje wspólne dla frontu, workera i skryptów (bez zależności od środowiska).
import type { Poll, Slide } from './types.ts';

/** Sumy z ankiety, które pokazujemy: wpis ręczny ma pierwszeństwo, potem wynik zamrożony. */
export function effectiveTally(p: Pick<Poll, 'tally' | 'manualOverride' | 'frozenResult' | 'options'>, preferFrozen = false): Record<string, number> {
  const src = p.manualOverride ?? (preferFrozen && p.frozenResult ? p.frozenResult.tally : p.tally);
  const out: Record<string, number> = {};
  for (const o of p.options) out[o.id] = Math.max(0, Math.floor(Number(src[o.id]) || 0));
  return out;
}

export function sum(t: Record<string, number>): number {
  return Object.values(t).reduce((a, b) => a + b, 0);
}

/** Procenty zaokrąglone do 1 p.p. tak, by suma wynosiła dokładnie 100 (metoda największych reszt). */
export function percents(tally: Record<string, number>): Record<string, number> {
  const ids = Object.keys(tally);
  const total = sum(tally);
  const out: Record<string, number> = {};
  if (!total) { for (const id of ids) out[id] = 0; return out; }
  const raw = ids.map((id) => ({ id, exact: (tally[id] * 100) / total }));
  let left = 100;
  for (const r of raw) { out[r.id] = Math.floor(r.exact); left -= out[r.id]; }
  raw.sort((a, b) => (b.exact % 1) - (a.exact % 1) || tally[b.id] - tally[a.id]);
  for (let i = 0; i < left; i++) out[raw[i % raw.length].id]++;
  return out;
}

export function winners(tally: Record<string, number>): string[] {
  const max = Math.max(0, ...Object.values(tally));
  if (max === 0) return [];
  return Object.keys(tally).filter((k) => tally[k] === max);
}

/** Normalizacja tekstu: małe litery, bez polskich znaków i interpunkcji. */
export function normalizeText(s: string): string {
  return s
    .toLowerCase()
    .replace(/ł/g, 'l')
    .normalize('NFD')
    .replace(/\p{M}+/gu, '')
    .replace(/[^a-z0-9 ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function trigrams(s: string): Set<string> {
  const n = `  ${normalizeText(s)} `;
  const out = new Set<string>();
  for (let i = 0; i < n.length - 2; i++) out.add(n.slice(i, i + 3));
  return out;
}

/** Podobieństwo Jaccarda na trigramach, 0..1. Powyżej 0.6 podpowiadamy duplikat. */
export function similarity(a: string, b: string): number {
  const A = trigrams(a), B = trigrams(b);
  if (!A.size || !B.size) return 0;
  let inter = 0;
  for (const x of A) if (B.has(x)) inter++;
  return inter / (A.size + B.size - inter);
}
export const DUPLICATE_THRESHOLD = 0.6;

/** Czyszczenie tekstu od użytkownika: bez znaków sterujących, zwinięte spacje. Renderujemy zawsze jako tekst. */
export function cleanText(s: unknown, max: number): string {
  const CTRL = new RegExp('[\\u0000-\\u001f\\u007f\\u200b-\\u200f\\u2028-\\u202f\\ufeff]', 'g');
  return String(s ?? '').replace(CTRL, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
}

export function blocklistHit(text: string, stems: string[]): boolean {
  const words = normalizeText(text).split(' ');
  return stems.some((st) => words.some((w) => w.startsWith(st)));
}

export function parseBlocklist(raw: string): string[] {
  return raw.split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#')).map(normalizeText).filter(Boolean);
}

// ---- walidacja slajdów (schemat) ----
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === 'string';

export interface SlideIssue { index: number; title: string; problems: string[] }

/**
 * Sprawdza strukturę slajdów. Przy `strict` (build produkcyjny, wgrywanie z /ops) każdy slajd musi mieć
 * `verified: true`, źródło, rok i komplet danych. Zakaz zmyślania danych jest pilnowany tutaj.
 */
export function validateSlides(input: unknown, strict: boolean): { slides: Slide[]; issues: SlideIssue[] } {
  const list = Array.isArray(input) ? input : (input as { slides?: unknown })?.slides;
  if (!Array.isArray(list)) return { slides: [], issues: [{ index: -1, title: '', problems: ['Oczekiwano tablicy slajdów lub obiektu { "slides": [...] }.'] }] };
  if (list.length > 60) return { slides: [], issues: [{ index: -1, title: '', problems: ['Za dużo slajdów (max 60).'] }] };
  const issues: SlideIssue[] = [];
  list.forEach((raw, index) => {
    const s = (raw ?? {}) as Record<string, any>;
    const p: string[] = [];
    if (!isStr(s.title) || !s.title.trim()) p.push('brak tytułu (title)');
    if (!isStr(s.notes)) p.push('brak pola notes (może być puste)');
    if (typeof s.verified !== 'boolean') p.push('brak flagi verified');
    if (s.seconds !== undefined && (!isNum(s.seconds) || s.seconds < 2 || s.seconds > 120)) p.push('seconds poza zakresem 2..120');
    let dataOk = true;
    switch (s.type) {
      case 'bigNumber':
        if (!isNum(s.value)) dataOk = false;
        break;
      case 'bar':
        if (!Array.isArray(s.categories) || s.categories.length < 1 || s.categories.length > 8 ||
          !s.categories.every((c: any) => isStr(c?.label) && isNum(c?.value))) dataOk = false;
        break;
      case 'line':
        if (!Array.isArray(s.x) || s.x.length < 2 || !Array.isArray(s.series) || s.series.length < 1 || s.series.length > 4 ||
          !s.series.every((r: any) => isStr(r?.name) && Array.isArray(r?.values) && r.values.length === s.x.length && r.values.every(isNum))) dataOk = false;
        break;
      case 'map':
        if (!s.values || typeof s.values !== 'object' || !Object.keys(s.values).length ||
          !Object.entries(s.values).every(([k, v]) => /^[A-Z]{2}$/.test(k) && isNum(v))) dataOk = false;
        break;
      case 'compare':
        if (![s.left, s.right].every((c: any) => c && isNum(c.value) && isStr(c.label) && c.label.trim())) dataOk = false;
        break;
      default:
        p.push(`nieznany typ slajdu: ${String(s.type)}`);
    }
    if (strict) {
      if (!dataOk) p.push('niekompletne dane slajdu');
      if (s.verified !== true) p.push('verified musi być true (dane potwierdzone u źródła)');
      if (!isStr(s.source) || !s.source.trim()) p.push('brak źródła (source)');
      if (s.year === null || s.year === undefined || String(s.year).trim() === '') p.push('brak roku (year)');
    }
    if (p.length) issues.push({ index, title: isStr(s.title) ? s.title : '', problems: p });
  });
  return { slides: issues.length ? [] : (list as Slide[]), issues };
}

/** Czy slajd ma komplet danych do narysowania (bez względu na verified). */
export function slideHasData(s: Slide): boolean {
  return validateSlides([{ ...s, verified: true, source: 'x', year: 1 }], true).issues.length === 0;
}

export function formatNumber(n: number, decimals = 0): string {
  const fixed = Math.abs(n).toFixed(decimals);
  const [int, frac] = fixed.split('.');
  const grouped = int.length > 4 ? int.replace(/\B(?=(\d{3})+(?!\d))/g, ' ') : int;
  return (n < 0 ? '-' : '') + grouped + (frac ? ',' + frac : '');
}

export function decimalsOf(n: number): number {
  const s = String(n);
  const i = s.indexOf('.');
  return i < 0 ? 0 : Math.min(2, s.length - i - 1);
}

export function csvCell(v: unknown): string {
  let s = String(v ?? '');
  // Ochrona przed wstrzyknięciem formuł po otwarciu w Excelu
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
