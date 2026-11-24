// Połączenie WebSocket z automatycznym powrotem (exponential backoff, max 3 s) i komendami z potwierdzeniem.
import type { Role, ServerMsg, View } from '@shared/types.ts';

export type ConnStatus = 'connecting' | 'open' | 'closed' | 'unauthorized';

export interface Conn {
  cmd(type: string, payload?: Record<string, unknown>): Promise<any>;
  setPingData(fn: () => Record<string, unknown>): void;
  close(): void;
}

export class CmdFail extends Error {
  constructor(public code: string, message: string) { super(message); }
}

export function connect(opts: {
  role: Role;
  token?: string;
  preview?: boolean;
  pingMs?: number;
  onView: (v: View) => void;
  onStatus?: (s: ConnStatus) => void;
}): Conn {
  let ws: WebSocket | null = null;
  let closed = false;
  let delay = 300;
  let lastVersion = 0;
  let lastMsgAt = 0;
  let pingData: () => Record<string, unknown> = () => ({});
  const pending = new Map<string, { ok: (d: any) => void; fail: (e: Error) => void; timer: number }>();
  const pingMs = opts.pingMs ?? 5000;

  const open = () => {
    if (closed) return;
    opts.onStatus?.('connecting');
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    let sock: WebSocket;
    try { sock = new WebSocket(`${proto}//${location.host}/ws?role=${opts.role}`); } catch { retry(); return; }
    ws = sock;
    // Uchwyt dla testów odporności (scripts/tests): pozwala ubić gniazdo z zewnątrz.
    ((window as any).__sockets ??= []).push(sock);
    sock.onopen = () => {
      lastMsgAt = Date.now();
      // Token idzie w wiadomości, nie w adresie: nie trafia do logów.
      sock.send(JSON.stringify({ t: 'hello', role: opts.role, token: opts.token, version: lastVersion, preview: opts.preview }));
    };
    sock.onmessage = (ev) => {
      lastMsgAt = Date.now();
      let m: ServerMsg;
      try { m = JSON.parse(ev.data); } catch { return; }
      if (m.t === 'state') {
        delay = 300;
        lastVersion = m.version;
        opts.onStatus?.('open');
        opts.onView(m.view);
      } else if (m.t === 'ack' || (m.t === 'error' && m.id)) {
        const p = pending.get(m.id!);
        if (!p) return;
        pending.delete(m.id!);
        clearTimeout(p.timer);
        if (m.t === 'ack') p.ok(m.data); else p.fail(new CmdFail(m.code, m.message));
      } else if (m.t === 'error' && m.code === 'unauthorized') {
        closed = true;
        opts.onStatus?.('unauthorized');
      }
    };
    sock.onclose = () => { if (ws === sock) { ws = null; if (!closed) { opts.onStatus?.('closed'); retry(); } } };
    sock.onerror = () => { try { sock.close(); } catch { /* nic */ } };
  };

  const retry = () => {
    if (closed) return;
    setTimeout(open, delay);
    delay = Math.min(3000, delay * 1.8);
  };

  // Natychmiastowe zerwanie: nie czekamy na zamknięcie gniazda przez przeglądarkę (bez sieci trwa to długo).
  const drop = () => {
    const dead = ws;
    if (!dead || closed) return;
    ws = null;
    try { dead.close(); } catch { /* nic */ }
    for (const [id, p] of pending) { clearTimeout(p.timer); p.fail(new CmdFail('offline', 'Połączenie zerwane w trakcie akcji. Sprawdź stan i ponów.')); pending.delete(id); }
    opts.onStatus?.('closed');
    retry();
  };

  const beat = setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    // Martwe połączenie (np. zmiana sieci): brak odpowiedzi przez 2,5 cyklu = zrywamy i łączymy od nowa.
    if (Date.now() - lastMsgAt > pingMs * 2.5) { drop(); return; }
    ws.send(JSON.stringify({ t: 'ping', ...pingData() }));
  }, pingMs);
  const onOffline = () => drop();
  const onOnline = () => { if (!ws && !closed) { delay = 300; } };
  window.addEventListener('offline', onOffline);
  window.addEventListener('online', onOnline);

  open();

  return {
    cmd(type, payload = {}) {
      return new Promise((ok, fail) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) { fail(new CmdFail('offline', 'Brak połączenia z serwerem. Akcja nie została wykonana.')); return; }
        const id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
        const timer = window.setTimeout(() => {
          pending.delete(id);
          fail(new CmdFail('timeout', 'Serwer nie potwierdził akcji. Sprawdź połączenie i stan na ekranie.'));
        }, 6000);
        pending.set(id, { ok, fail, timer });
        ws.send(JSON.stringify({ t: 'cmd', id, type, payload }));
      });
    },
    setPingData(fn) { pingData = fn; },
    close() {
      closed = true; clearInterval(beat);
      window.removeEventListener('offline', onOffline); window.removeEventListener('online', onOnline);
      try { ws?.close(); } catch { /* nic */ }
    },
  };
}

/** Token z fragmentu adresu (#t=...) trafia do pamięci przeglądarki i znika z paska adresu. */
export function takeToken(param: string, storageKey: string, persistent = false): string {
  const store = persistent ? localStorage : sessionStorage;
  const fromHash = new URLSearchParams(location.hash.replace(/^#/, '')).get(param);
  const fromQuery = new URLSearchParams(location.search).get(param);
  const tok = fromHash || fromQuery;
  try {
    if (tok) {
      store.setItem(storageKey, tok);
      const q = new URLSearchParams(location.search); q.delete(param);
      const h = new URLSearchParams(location.hash.replace(/^#/, '')); h.delete(param);
      history.replaceState(null, '', location.pathname + (q.size ? `?${q}` : '') + (h.size ? `#${h}` : ''));
      return tok;
    }
    return store.getItem(storageKey) ?? '';
  } catch { return tok ?? ''; }
}
