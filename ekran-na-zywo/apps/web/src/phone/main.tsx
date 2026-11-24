// Telefon uczestnika: jedno wejście z QR, widok zależy od trybu ustawionego przez operatora.
import { render } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import type { PhoneMode, PublicView } from '@shared/types.ts';
import { applyTheme, config } from '../lib/theme.ts';
import { connect } from '../lib/conn.ts';
import { t } from '../lib/i18n.ts';
import { Logos } from '../ui/common.tsx';
import '../themes/base.css';
import '../themes/phone.css';

applyTheme();

// localStorage służy tylko do identyfikatora urządzenia i flagi "zagłosowano". Żadnych ciasteczek ani analityki.
const mem: Record<string, string> = {};
const store = {
  get(k: string): string | null { try { return localStorage.getItem(k); } catch { return mem[k] ?? null; } },
  set(k: string, v: string): void { try { localStorage.setItem(k, v); } catch { mem[k] = v; } },
};

function deviceId(): string {
  let id = store.get('deviceId');
  if (!id || !/^[A-Za-z0-9_-]{8,64}$/.test(id)) {
    const b = new Uint8Array(16);
    crypto.getRandomValues(b);
    id = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
    store.set('deviceId', id);
  }
  return id;
}

function votedList(epoch: number): string[] {
  try { return JSON.parse(store.get(`voted:${epoch}`) ?? '[]'); } catch { return []; }
}

async function post(path: string, body: unknown): Promise<{ ok: boolean; code?: string; message?: string }> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 8000);
  try {
    const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl.signal });
    return await res.json();
  } catch {
    return { ok: false, code: 'network', message: t('phone.error.network') };
  } finally { clearTimeout(timer); }
}

const forced: PhoneMode | null = location.pathname === '/ankieta' ? 'poll' : location.pathname === '/pytania' ? 'questions' : null;

function App() {
  const [view, setView] = useState<PublicView | null>(null);
  const wsOpen = useRef(false);

  useEffect(() => {
    const conn = connect({
      role: 'public',
      pingMs: 20_000,
      onView: (v) => setView(v as PublicView),
      onStatus: (s) => { wsOpen.current = s === 'open'; },
    });
    // Fallback: gdy WebSocket nie wstaje (np. filtr w sieci hotelu), odpytujemy co 2 s.
    const poll = setInterval(async () => {
      if (wsOpen.current || document.hidden) return;
      try {
        const r = (await (await fetch('/api/state', { cache: 'no-store' })).json()) as { ok: boolean; view: PublicView };
        if (r.ok) setView(r.view);
      } catch { /* spróbujemy za 2 s */ }
    }, 2000);
    return () => { conn.close(); clearInterval(poll); };
  }, []);

  if (!view) return <Shell><div class="center"><div class="dots" aria-label={t('phone.loading')}><i /><i /><i /></div></div></Shell>;
  const mode = forced ?? view.phoneMode;
  return (
    <Shell>
      {mode === 'poll' ? <PollScreen view={view} />
        : mode === 'questions' ? <QuestionForm view={view} />
        : mode === 'thanks' ? <Message title={t('phone.thanks.title')} text={t('phone.thanks.text')} />
        : mode === 'closed' ? <Message title={t('phone.closed.title')} text={t('phone.closed.text')} />
        : <Message title={t('phone.waiting.title')} text={t('phone.waiting.text')} waiting />}
    </Shell>
  );
}

function Shell({ children }: { children: preact.ComponentChildren }) {
  return (
    <main class="wrap">
      <header><Logos withFunding={false} /></header>
      <section class="content">{children}</section>
      <footer class="foot">{config.event.title}, {config.event.subtitle}</footer>
    </main>
  );
}

function Message({ title, text, waiting }: { title: string; text?: string; waiting?: boolean }) {
  return (
    <div class="center" role="status">
      {waiting ? <div class="dots"><i /><i /><i /></div> : null}
      <h1>{title}</h1>
      {text ? <p class="lead">{text}</p> : null}
    </div>
  );
}

function PollScreen({ view }: { view: PublicView }) {
  const [voted, setVoted] = useState<string[]>(() => votedList(view.pollEpoch));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { setVoted(votedList(view.pollEpoch)); }, [view.pollEpoch]);

  const next = view.polls.find((p) => !voted.includes(p.id));
  // Powrót na stronę po głosowaniu: samo potwierdzenie, bez ujawniania wyboru.
  if (!next) return <Message title={t('phone.poll.thanks.title')} text={t('phone.poll.thanks.text')} />;
  if (view.pollStatus === 'draft') return <Message title={t('phone.waiting.title')} text={t('phone.waiting.text')} waiting />;
  if (view.pollStatus === 'closed') return <Message title={t('phone.poll.closed.title')} text={t('phone.poll.closed.text')} />;

  const vote = async (optionId: string) => {
    if (busy) return;
    setBusy(true); setErr('');
    try { navigator.vibrate?.(20); } catch { /* brak haptyki */ }
    const r = await post('/api/vote', { pollId: next.id, optionId, deviceId: deviceId() });
    setBusy(false);
    if (r.ok || r.code === 'already_voted') {
      const list = [...new Set([...voted, next.id])];
      store.set(`voted:${view.pollEpoch}`, JSON.stringify(list));
      setVoted(list);
    } else setErr(r.message ?? t('phone.error.generic'));
  };

  return (
    <div class="poll">
      {view.polls.length > 1 ? <p class="step">{t('phone.poll.step', { n: view.polls.indexOf(next) + 1, of: view.polls.length })}</p> : null}
      <h1 class="question">{next.text}</h1>
      <div class="options">
        {next.options.map((o, i) => (
          <button type="button" class={`btn-vote v${i + 1}`} disabled={busy} onClick={() => vote(o.id)}>{o.label}</button>
        ))}
      </div>
      {err ? <p class="error" role="alert">{err}</p> : null}
      <p class="hint">{t('phone.poll.anon')}</p>
    </div>
  );
}

function QuestionForm({ view }: { view: PublicView }) {
  const L = config.limits;
  const [text, setText] = useState('');
  const [name, setName] = useState('');
  const [expert, setExpert] = useState('');
  const [website, setWebsite] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [sent, setSent] = useState(false);
  const clientId = useRef(crypto.randomUUID?.() ?? String(Math.random()));
  const len = text.trim().length;
  const valid = len >= L.questionMin && len <= L.questionMax;

  const submit = async (e: Event) => {
    e.preventDefault();
    if (busy) return;
    if (!valid) { setErr(t('phone.q.error.length', { min: L.questionMin, max: L.questionMax })); return; }
    setBusy(true); setErr('');
    // clientId chroni przed podwójnym kliknięciem: serwer zapisze to pytanie tylko raz.
    const r = await post('/api/question', { text, name, expertId: expert || undefined, website, deviceId: deviceId(), clientId: clientId.current });
    setBusy(false);
    if (r.ok) {
      setSent(true); setText('');
      clientId.current = crypto.randomUUID?.() ?? String(Math.random());
      try { navigator.vibrate?.(20); } catch { /* nic */ }
    } else setErr(r.message ?? t('phone.error.generic'));
  };

  if (sent) {
    return (
      <div class="center" role="status">
        <h1>{t('phone.q.sent.title')}</h1>
        <p class="lead">{t('phone.q.sent.text')}</p>
        <button type="button" class="btn-primary" onClick={() => setSent(false)}>{t('phone.q.another')}</button>
      </div>
    );
  }

  return (
    <form class="qform" onSubmit={submit} noValidate>
      <h1>{t('phone.q.title')}</h1>
      <label for="q-text">{t('phone.q.text.label')}</label>
      <textarea id="q-text" rows={5} maxLength={L.questionMax} value={text} required
        placeholder={t('phone.q.text.placeholder')}
        onInput={(e) => setText((e.target as HTMLTextAreaElement).value)} />
      <div class={`counter ${len > 0 && !valid ? 'bad' : ''}`} aria-live="polite">{len} / {L.questionMax}</div>

      <label for="q-expert">{t('phone.q.expert.label')}</label>
      <select id="q-expert" value={expert} onChange={(e) => setExpert((e.target as HTMLSelectElement).value)}>
        <option value="">{t('q.toAll')}</option>
        {view.experts.map((x) => <option value={x.id}>{x.name}{x.role ? `, ${x.role}` : ''}</option>)}
      </select>

      <label for="q-name">{t('phone.q.name.label')}</label>
      <input id="q-name" type="text" maxLength={L.nameMax} value={name} autocomplete="given-name"
        onInput={(e) => setName((e.target as HTMLInputElement).value)} />
      <p class="hint">{t('phone.q.name.hint')}</p>

      {/* Honeypot: pole niewidoczne dla ludzi. Wypełnia je tylko automat. */}
      <div class="hp" aria-hidden="true">
        <label for="website">Strona www</label>
        <input id="website" name="website" type="text" tabIndex={-1} autocomplete="off" value={website}
          onInput={(e) => setWebsite((e.target as HTMLInputElement).value)} />
      </div>

      {err ? <p class="error" role="alert">{err}</p> : null}
      <button type="submit" class="btn-primary" disabled={busy}>{busy ? t('phone.q.sending') : t('phone.q.send')}</button>
      <p class="notice">{t('phone.q.dataNotice')}</p>
    </form>
  );
}

render(<App />, document.getElementById('app')!);
