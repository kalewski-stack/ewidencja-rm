// Wspólne dla /ops i /mod: bramka tokenu, połączenie, komunikaty, eksporty.
import { useEffect, useRef, useState } from 'preact/hooks';
import type { StaffView } from '@shared/types.ts';
import { csvCell, effectiveTally, sum } from '@shared/util.ts';
import { connect, takeToken, type Conn, type ConnStatus } from '../lib/conn.ts';
import { t } from '../lib/i18n.ts';
import { docx, download, zip, type ZipEntry } from '../lib/zip.ts';
import { pollBoard, recsBoard } from '../lib/board.ts';

export interface Staff {
  view: StaffView | null;
  status: ConnStatus;
  online: boolean;
  token: string;
  /** Wysyła komendę. Błąd pokazuje jako komunikat i zwraca undefined. Offline niczego nie gubi po cichu. */
  run: (type: string, payload?: Record<string, unknown>, okMsg?: string) => Promise<any>;
  toast: (msg: string, kind?: 'ok' | 'err') => void;
  toasts: { id: number; msg: string; kind: 'ok' | 'err' }[];
  setToken: (tok: string) => void;
}

export function useStaff(role: 'ops' | 'mod'): Staff {
  const [token, setTok] = useState(() => takeToken('t', `${role}Token`));
  const [view, setView] = useState<StaffView | null>(null);
  const [status, setStatus] = useState<ConnStatus>('connecting');
  const [toasts, setToasts] = useState<Staff['toasts']>([]);
  const conn = useRef<Conn | null>(null);
  const seq = useRef(0);

  const toast: Staff['toast'] = (msg, kind = 'ok') => {
    const id = ++seq.current;
    setToasts((x) => [...x.slice(-3), { id, msg, kind }]);
    setTimeout(() => setToasts((x) => x.filter((y) => y.id !== id)), kind === 'err' ? 7000 : 2500);
  };

  useEffect(() => {
    if (!token) return;
    setStatus('connecting');
    const c = connect({ role, token, onView: (v) => setView(v as StaffView), onStatus: setStatus });
    conn.current = c;
    return () => c.close();
  }, [token]);

  const run: Staff['run'] = async (type, payload, okMsg) => {
    try {
      const r = await conn.current!.cmd(type, payload);
      if (okMsg) toast(okMsg);
      return r ?? true;
    } catch (e) {
      toast((e as Error).message, 'err');
      return undefined;
    }
  };

  return {
    view, status, online: status === 'open', token, run, toast, toasts,
    setToken: (tok) => { try { sessionStorage.setItem(`${role}Token`, tok); } catch { /* nic */ } setTok(tok); },
  };
}

export function Gate({ staff, title }: { staff: Staff; title: string }) {
  const [val, setVal] = useState('');
  return (
    <div class="gate-form">
      <h1>{title}</h1>
      <p>{staff.status === 'unauthorized' ? t('staff.gate.bad') : t('staff.gate.info')}</p>
      <form onSubmit={(e) => { e.preventDefault(); if (val.trim()) { staff.setToken(val.trim()); if (staff.status === 'unauthorized') location.reload(); } }}>
        <input type="password" value={val} placeholder={t('staff.gate.placeholder')} autocomplete="off" onInput={(e) => setVal((e.target as HTMLInputElement).value)} />
        <button class="btn primary" type="submit">{t('staff.gate.enter')}</button>
      </form>
    </div>
  );
}

export function Toasts({ staff }: { staff: Staff }) {
  return <div class="toasts" aria-live="assertive">{staff.toasts.map((x) => <div key={x.id} class={`toast ${x.kind}`}>{x.msg}</div>)}</div>;
}

export function OfflineBanner({ staff }: { staff: Staff }) {
  if (staff.online) return null;
  return <div class="offline" role="alert">{t('staff.offline')}</div>;
}

export function Confirm({ text, onYes, children, cls = '', disabled }: { text: string; onYes: () => void; children: preact.ComponentChildren; cls?: string; disabled?: boolean }) {
  return <button type="button" class={`btn ${cls}`} disabled={disabled} onClick={() => { if (window.confirm(text)) onYes(); }}>{children}</button>;
}

export const hhmm = (iso: string) => new Date(iso).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });

// ---------- eksporty ----------
export function recsMarkdown(v: StaffView): string {
  return `# ${t('screen.recs.title')}\n\n` + v.recommendations.map((r, i) => `${i + 1}. **${r.title}**\n   ${r.text}`).join('\n\n') + '\n';
}

export function recsDocx(v: StaffView): Blob {
  return docx([
    { text: t('screen.recs.title'), bold: true, size: 18 },
    ...v.recommendations.flatMap((r, i) => [{ text: `${i + 1}. ${r.title}`, bold: true, size: 13 }, { text: r.text, size: 11 }]),
  ]);
}

export function votesCsv(v: StaffView): string {
  // Same sumy. W systemie nie ma danych o pojedynczych głosach.
  const rows = [['ankieta', 'pytanie', 'odpowiedz', 'glosy', 'wpis_reczny'].join(';')];
  for (const p of v.polls) {
    const tally = effectiveTally(p, v.pollStatus === 'closed');
    for (const o of p.options) rows.push([p.id, p.text, o.label, tally[o.id], p.manualOverride ? 'tak' : 'nie'].map(csvCell).join(';'));
  }
  return '﻿' + rows.join('\r\n') + '\r\n';
}

export function questionsCsv(v: StaffView): string {
  const ex = (id?: string) => v.experts.find((e) => e.id === id)?.name ?? t('q.toAll');
  const rows = [['id', 'czas', 'status', 'tresc', 'tresc_oryginalna', 'imie', 'do_kogo', 'zrodlo', 'duplikat_pytania', 'flaga_blocklist'].join(';')];
  for (const q of v.questions) {
    rows.push([q.id, q.createdAt, q.status, q.text, q.originalText ?? '', q.name ?? '', ex(q.expertId), q.source, q.duplicateOf ?? '', q.flagged ? 'tak' : ''].map(csvCell).join(';'));
  }
  return '﻿' + rows.join('\r\n') + '\r\n';
}

export async function pollPng(v: StaffView): Promise<Blob> {
  const p = v.polls[v.activePoll] ?? v.polls[0];
  return pollBoard(p, effectiveTally(p, v.pollStatus === 'closed'));
}

export async function exportAll(staff: Staff): Promise<void> {
  const v = staff.view!;
  let results: unknown = { exportedAt: new Date().toISOString(), state: v };
  try {
    const r = await fetch('/api/export', { headers: { Authorization: `Bearer ${staff.token}` }, cache: 'no-store' });
    if (r.ok) results = await r.json();
  } catch { /* offline: eksportujemy to, co mamy w przeglądarce */ }
  const buf = async (b: Blob) => new Uint8Array(await b.arrayBuffer());
  const entries: ZipEntry[] = [
    { name: 'results.json', data: JSON.stringify(results, null, 2) },
    { name: 'votes.csv', data: votesCsv(v) },
    { name: 'questions.csv', data: questionsCsv(v) },
    { name: 'recommendations.md', data: recsMarkdown(v) },
    { name: 'recommendations.docx', data: await buf(recsDocx(v)) },
    { name: 'plansza-ankieta-1920x1080.png', data: await buf(await pollPng(v)) },
    { name: 'plansza-rekomendacje-1920x1080.png', data: await buf(await recsBoard(v.recommendations, 1920, 1080)) },
    { name: 'plansza-rekomendacje-1080x1350.png', data: await buf(await recsBoard(v.recommendations, 1080, 1350)) },
  ];
  download(zip(entries), `ekran-na-zywo-eksport-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')}.zip`);
  staff.toast(t('ops.export.done', { votes: sum(effectiveTally(v.polls[0])), questions: v.questions.length }));
}
