// Krok przed buildem: walidacja treści i skopiowanie assetów motywu.
// Z flagą --production build wywala się, jeśli jakikolwiek slajd ma verified: false albo brak źródła lub roku.
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';
import { validateSlides } from '../packages/shared/util.ts';

const root = resolve(import.meta.dirname, '..');
const production = process.argv.includes('--production');
const read = (p: string) => JSON.parse(readFileSync(resolve(root, p), 'utf8'));
const errors: string[] = [];
const warnings: string[] = [];

// 1. Slajdy
const slides = read('content/slides.json');
const structural = validateSlides(slides, false);
for (const i of structural.issues) errors.push(`slides.json, slajd ${i.index + 1} (${i.title}): ${i.problems.join(', ')}`);
const strict = validateSlides(slides, true);
for (const i of strict.issues) {
  const msg = `slides.json, slajd ${i.index + 1} (${i.title}): ${i.problems.join(', ')}`;
  if (production) errors.push(msg); else warnings.push(msg);
}

// 2. Config i teksty
const config = read('content/config.json');
const pl = read('content/i18n/pl.json') as Record<string, string>;
const theme = read('content/theme.json');
if (!Array.isArray(config.polls) || !config.polls.length) errors.push('config.json: brak ankiety (polls).');
for (const p of config.polls ?? []) {
  if (!p.text || !Array.isArray(p.options) || p.options.length < 2) errors.push(`config.json: ankieta ${p.id} wymaga treści i co najmniej 2 odpowiedzi.`);
}
// W tekstach interfejsu nie używamy długich myślników.
const dash = String.fromCharCode(0x2014);
for (const [k, v] of Object.entries(pl)) if (v.includes(dash)) errors.push(`pl.json: klucz ${k} zawiera długi myślnik.`);
for (const p of config.polls ?? []) if (JSON.stringify(p).includes(dash)) errors.push(`config.json: ankieta ${p.id} zawiera długi myślnik.`);

// 3. Klucze tłumaczeń użyte w kodzie
const used = new Set<string>();
const walk = (dir: string) => {
  for (const f of readdirSync(dir, { withFileTypes: true })) {
    const p = resolve(dir, f.name);
    if (f.isDirectory()) walk(p);
    else if (/\.tsx?$/.test(f.name)) for (const m of readFileSync(p, 'utf8').matchAll(/\bt\('([a-zA-Z0-9_.-]+)'/g)) used.add(m[1]);
  }
};
walk(resolve(root, 'apps/web/src'));
for (const k of used) if (!(k in pl)) errors.push(`pl.json: brak klucza ${k}`);

// 4. Assety motywu: content/assets -> apps/web/public/theme
const src = resolve(root, 'content/assets');
const dst = resolve(root, 'apps/web/public/theme');
rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
if (existsSync(src)) cpSync(src, dst, { recursive: true });
const need: string[] = [
  ...Object.values(theme.logos ?? {}).filter(Boolean) as string[],
  ...(theme.fonts?.files ?? []).map((f: { file: string }) => f.file),
  ...(theme.background?.file ? [theme.background.file] : []),
];
for (const f of need) if (!existsSync(resolve(src, f))) errors.push(`theme.json wskazuje plik, którego nie ma w content/assets: ${f}`);
if (production) {
  for (const [slot, file] of Object.entries(theme.logos ?? {})) if (!file) warnings.push(`brak logotypu w slocie logo.${slot} (na ekranie będzie szary prostokąt)`);
  if (theme.placeholder) warnings.push('motyw roboczy (placeholder: true). Podmień content/theme.json po dostarczeniu designu.');
}

for (const w of warnings) console.warn(`UWAGA: ${w}`);
if (errors.length) {
  for (const e of errors) console.error(`BŁĄD: ${e}`);
  console.error(`\nBuild ${production ? 'produkcyjny ' : ''}zatrzymany. Błędów: ${errors.length}.`);
  if (production && strict.issues.length) console.error('Slajdy bez potwierdzonych danych nie mogą trafić na produkcję. Uzupełnij dane albo usuń szablony z content/slides.json.');
  process.exit(1);
}
console.log(`Treści OK (${production ? 'produkcja' : 'tryb roboczy'}). Slajdów: ${(slides.slides ?? []).length}, kluczy tekstów: ${Object.keys(pl).length}.`);
