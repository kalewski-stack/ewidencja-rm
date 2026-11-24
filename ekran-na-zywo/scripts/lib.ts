// Wspólne dla skryptów: adres serwera, tokeny z .dev.vars lub zmiennych środowiska, klient komend operatora.
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

export const root = resolve(import.meta.dirname, '..');
const vars: Record<string, string> = {};
const devVars = resolve(root, '.dev.vars');
if (existsSync(devVars)) for (const l of readFileSync(devVars, 'utf8').split('\n')) { const m = l.match(/^([A-Z_]+)=(.*)$/); if (m) vars[m[1]] = m[2].trim(); }

export const BASE = (process.env.BASE ?? 'http://localhost:8787').replace(/\/$/, '');
export const OPS_TOKEN = process.env.OPS_TOKEN ?? vars.OPS_TOKEN ?? '';
export const MOD_TOKEN = process.env.MOD_TOKEN ?? vars.MOD_TOKEN ?? '';
export const SCREEN_KEY = process.env.SCREEN_KEY ?? vars.SCREEN_KEY ?? '';
export const WS_BASE = BASE.replace(/^http/, 'ws');

/** Playwright: z projektu albo z instalacji globalnej (NODE_PATH). */
export function playwright(): any {
  const require = createRequire(import.meta.url);
  try { return require('playwright'); } catch { /* niżej */ }
  for (const p of (process.env.NODE_PATH ?? '').split(':').filter(Boolean).concat('/opt/node-tools/node_modules')) {
    try { return createRequire(p + '/')('playwright'); } catch { /* następna ścieżka */ }
  }
  throw new Error('Brak Playwright. Zainstaluj: npm i -D playwright && npx playwright install chromium');
}

export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function post(path: string, body: unknown, headers: Record<string, string> = {}): Promise<{ status: number; body: any }> {
  const r = await fetch(BASE + path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
  return { status: r.status, body: await r.json().catch(() => ({})) };
}

export interface Client { view: any; cmd(type: string, payload?: Record<string, unknown>): Promise<any>; close(): void; waitFor(fn: (v: any) => boolean, ms?: number): Promise<any>; closed: boolean }

/** Klient WebSocket w dowolnej roli. `cmd` odrzuca obietnicę przy błędzie z serwera. */
export async function client(role: 'ops' | 'mod' | 'screen' | 'public', token = '', preview = true): Promise<Client> {
  const ws = new WebSocket(`${WS_BASE}/ws?role=${role}`);
  const pending = new Map<string, { ok: (d: any) => void; fail: (e: Error) => void }>();
  const waiters: { fn: (v: any) => boolean; ok: (v: any) => void }[] = [];
  const c: Client = {
    view: null, closed: false,
    cmd(type, payload = {}) {
      return new Promise((ok, fail) => {
        const id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
        pending.set(id, { ok, fail });
        ws.send(JSON.stringify({ t: 'cmd', id, type, payload }));
      });
    },
    waitFor(fn, ms = 5000) {
      if (c.view && fn(c.view)) return Promise.resolve(c.view);
      return new Promise((ok, fail) => {
        const w = { fn, ok };
        waiters.push(w);
        setTimeout(() => { const i = waiters.indexOf(w); if (i >= 0) { waiters.splice(i, 1); fail(new Error(`waitFor: warunek niespełniony w ${ms} ms (${role})`)); } }, ms);
      });
    },
    close() { ws.close(); },
  };
  ws.onmessage = (e) => {
    const m = JSON.parse(String(e.data));
    if (m.t === 'state') {
      c.view = m.view;
      for (let i = waiters.length - 1; i >= 0; i--) if (waiters[i].fn(m.view)) waiters.splice(i, 1)[0].ok(m.view);
    } else if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id)!; pending.delete(m.id);
      if (m.t === 'ack') p.ok(m.data); else p.fail(Object.assign(new Error(m.message), { code: m.code }));
    }
  };
  ws.onclose = () => { c.closed = true; };
  await new Promise<void>((ok, fail) => { ws.onopen = () => ok(); ws.onerror = () => fail(new Error(`Nie mogę połączyć się z ${WS_BASE}. Czy serwer działa?`)); });
  ws.send(JSON.stringify({ t: 'hello', role, token, preview }));
  if (role === 'public' || token) await Promise.race([c.waitFor(() => true, 4000), new Promise((_, fail) => { ws.addEventListener('close', () => fail(new Error(`Serwer odrzucił połączenie w roli ${role} (token?)`))); })]);
  return c;
}
