// Durable Object: jedno źródło prawdy o wydarzeniu. Stan trwały w DO storage, WebSocket przez Hibernation API.
import { DurableObject } from 'cloudflare:workers';
import type {
  ClientMsg, Expert, Poll, PublicView, Question, Recommendation, Role, SceneId, ScreenQuestion,
  ScreenView, ServerMsg, Slide, StaffView, State,
} from '../../../packages/shared/types.ts';
import { PHONE_MODES, REC_TEXT_MAX, REC_TITLE_MAX, SCENES } from '../../../packages/shared/types.ts';
import { blocklistHit, cleanText, effectiveTally, parseBlocklist, sum, validateSlides } from '../../../packages/shared/util.ts';
import config from '../../../content/config.json';
import seedSlides from '../../../content/slides.json';
import blocklistRaw from '../../../content/blocklist.txt';
import pkg from '../../../package.json';
import type { Env } from './index.ts';
import { bearer, json, safeEqual, sha256Hex } from './http.ts';

const BLOCKLIST = parseBlocklist(blocklistRaw);
const L = config.limits;
const BROADCAST_MS = 250; // max 4 odświeżenia na sekundę
const BACKUP_MS = 5 * 60_000;

class CmdError extends Error {
  constructor(public code: string, message: string, public data?: unknown) { super(message); }
}

interface Attachment { role: Role; authed: boolean; preview?: boolean }

function seedPolls(): Poll[] {
  return config.polls.map((p) => {
    const options = p.options.map((o) => ({ id: o.id, label: o.label }));
    if (p.thirdOption?.enabled) options.push({ id: p.thirdOption.id, label: p.thirdOption.label });
    return { id: p.id, text: p.text, options, tally: Object.fromEntries(options.map((o) => [o.id, 0])) };
  });
}

function freshState(): State {
  return {
    version: 1,
    phoneMode: 'waiting',
    scene: 'idle',
    sceneParams: { slideIndex: 0, slideNonce: 0, revealCount: 0 },
    pollStatus: 'draft',
    pollEpoch: 1,
    polls: seedPolls(),
    activePoll: 0,
    questions: [],
    queue: [],
    experts: (config.experts as Expert[]).map((e, i) => ({ id: e.id ?? `e${i + 1}`, name: e.name, role: e.role })),
    recommendations: Array.from({ length: 5 }, () => ({ title: '', text: '', rev: 0 })),
    counters: { votes: 0, questionsSubmitted: 0 },
    fallbackStatic: false,
    slides: (seedSlides as { slides: Slide[] }).slides,
    slidesPaused: false,
    slidesCustom: false,
    agendaStep: -1,
    lastSavedAt: new Date().toISOString(),
  };
}

export class EventRoom extends DurableObject<Env> {
  private s: State = freshState();
  private voters = new Set<string>(); // hasze urządzeń, bez powiązania z wyborem
  private seenCmd = new Map<string, number>();
  private questionTimes = new Map<string, number[]>();
  private screenBeatAt = 0;
  private screenSlide = 0;
  private lastSent = new Map<string, string>();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private lastFlush = 0;
  private lastBeatBroadcast = 0;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.blockConcurrencyWhile(() => this.load());
  }

  // ---------- trwałość ----------
  private async load(): Promise<void> {
    const core = await this.ctx.storage.get<Omit<State, 'questions' | 'slides'>>('core');
    if (!core) return;
    const fresh = freshState();
    const questions = [...(await this.ctx.storage.list<Question>({ prefix: 'q:' })).values()];
    questions.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    const customSlides = core.slidesCustom ? await this.ctx.storage.get<Slide[]>('slides') : undefined;
    this.s = { ...fresh, ...core, questions, slides: customSlides ?? fresh.slides, slidesCustom: !!customSlides };
    const voters = await this.ctx.storage.list({ prefix: `v:${this.s.pollEpoch}:` });
    this.voters = new Set(voters.keys());
  }

  /** Zapis przy każdej zmianie. `extra` trafia do tej samej, atomowej operacji put. */
  private commit(extra: Record<string, unknown> = {}): void {
    this.s.version++;
    this.s.lastSavedAt = new Date().toISOString();
    const { questions: _q, slides: _s, ...core } = this.s;
    void this.ctx.storage.put({ core, ...extra });
    this.scheduleBroadcast();
    void this.ensureBackupAlarm();
  }

  private qKey(q: Question): Record<string, unknown> { return { [`q:${q.id}`]: q }; }

  private async ensureBackupAlarm(): Promise<void> {
    if ((await this.ctx.storage.getAlarm()) === null) await this.ctx.storage.setAlarm(Date.now() + BACKUP_MS);
  }

  /** Co 5 minut (gdy coś się zmieniało): kopia stanu w storage i, jeśli podpięto, w R2. */
  async alarm(): Promise<void> {
    const snapshot = JSON.stringify({ at: new Date().toISOString(), state: this.s });
    const key = `bk:${Date.now()}`;
    await this.ctx.storage.put(key, snapshot.length < 1_800_000 ? snapshot : snapshot.slice(0, 1_800_000));
    const old = [...(await this.ctx.storage.list({ prefix: 'bk:' })).keys()].sort();
    if (old.length > 12) await this.ctx.storage.delete(old.slice(0, old.length - 12));
    if (this.env.BACKUP) {
      try {
        await this.env.BACKUP.put(`${this.env.EVENT_ID}/state-${new Date().toISOString().replace(/[:.]/g, '-')}.json`, snapshot);
        await this.env.BACKUP.put(`${this.env.EVENT_ID}/state-latest.json`, snapshot);
      } catch (e) {
        console.log('backup R2 nieudany', String(e));
      }
    }
  }

  // ---------- widoki zależne od roli ----------
  private publicView(): PublicView {
    const s = this.s;
    return {
      role: 'public', version: s.version, phoneMode: s.phoneMode, pollStatus: s.pollStatus, pollEpoch: s.pollEpoch,
      polls: s.polls.map((p) => ({ id: p.id, text: p.text, options: p.options })),
      experts: s.experts,
    };
  }

  private screenQuestion(q: Question): ScreenQuestion {
    return { id: q.id, text: q.text, name: q.name, expertId: q.expertId };
  }

  private screenView(): ScreenView {
    const s = this.s;
    const p = s.polls[s.activePoll] ?? s.polls[0];
    const frozen = s.pollStatus === 'closed';
    const tally = effectiveTally(p, frozen);
    // Na ekran idą wyłącznie pytania zatwierdzone. Reszta nie opuszcza serwera w tym widoku.
    const approved = s.questions
      .filter((q) => q.status === 'approved' || q.status === 'on_screen')
      .sort((a, b) => (a.approvedAt ?? a.createdAt).localeCompare(b.approvedAt ?? b.createdAt))
      .slice(-12)
      .map((q) => this.screenQuestion(q));
    const f = s.questions.find((q) => q.id === s.sceneParams.questionId && q.status === 'on_screen');
    return {
      role: 'screen', version: s.version, scene: s.scene, sceneParams: s.sceneParams, phoneMode: s.phoneMode,
      pollStatus: s.pollStatus,
      poll: { id: p.id, text: p.text, options: p.options, tally, total: sum(tally), frozen },
      votes: sum(effectiveTally(s.polls[0], frozen)),
      questionsSubmitted: s.counters.questionsSubmitted,
      approved, focus: f ? this.screenQuestion(f) : null,
      experts: s.experts,
      recommendations: s.recommendations.map((r) => ({ title: r.title, text: r.text })),
      slides: s.slides, slidesPaused: s.slidesPaused, fallbackStatic: s.fallbackStatic,
      publicUrl: this.env.PUBLIC_URL,
    };
  }

  private staffView(role: 'mod' | 'ops'): StaffView {
    const count = (r: Role) => this.ctx.getWebSockets(r).filter((w) => {
      const a = w.deserializeAttachment() as Attachment | null;
      return a?.authed && !a.preview;
    }).length;
    return {
      ...this.s, role,
      presence: {
        phones: count('public'), screens: count('screen'), mods: count('mod'), ops: count('ops'),
        screenBeatAt: this.screenBeatAt, screenSlide: this.screenSlide,
      },
      publicUrl: this.env.PUBLIC_URL, buildVersion: pkg.version,
    };
  }

  private viewFor(role: Role) {
    return role === 'public' ? this.publicView() : role === 'screen' ? this.screenView() : this.staffView(role);
  }

  // ---------- rozgłaszanie (batchowane) ----------
  private scheduleBroadcast(): void {
    if (this.timer) return;
    const wait = Math.max(0, BROADCAST_MS - (Date.now() - this.lastFlush));
    this.timer = setTimeout(() => { this.timer = null; this.flush(); }, wait);
  }

  private flush(): void {
    this.lastFlush = Date.now();
    for (const role of ['public', 'screen', 'mod', 'ops'] as Role[]) {
      const sockets = this.ctx.getWebSockets(role);
      if (!sockets.length) { this.lastSent.delete(role); continue; }
      const view = this.viewFor(role);
      // Dla telefonów i ekranu porównujemy bez numeru wersji: głos nie budzi 150 telefonów.
      const sig = JSON.stringify({ ...view, version: 0 });
      if (this.lastSent.get(role) === sig) continue;
      this.lastSent.set(role, sig);
      const msg = JSON.stringify({ t: 'state', version: this.s.version, view } satisfies ServerMsg);
      for (const ws of sockets) {
        const a = ws.deserializeAttachment() as Attachment | null;
        if (!a?.authed) continue;
        try { ws.send(msg); } catch { /* gniazdo zamknięte */ }
      }
    }
  }

  // ---------- HTTP ----------
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    try {
      if (path === '/ws') return this.acceptSocket(request, url);
      if (path === '/health') {
        const v = this.staffView('ops');
        return json({ ok: true, version: pkg.version, stateVersion: this.s.version, clients: v.presence, scene: this.s.scene, phoneMode: this.s.phoneMode, time: new Date().toISOString() });
      }
      if (path === '/api/state' && request.method === 'GET') return json({ ok: true, view: this.publicView() });
      if (path === '/api/vote' && request.method === 'POST') return json(await this.vote(await this.body(request)));
      if (path === '/api/question' && request.method === 'POST') return json(await this.submitQuestion(await this.body(request)));
      if (path === '/api/export' && request.method === 'GET') {
        this.requireOps(request);
        return json({ ok: true, exportedAt: new Date().toISOString(), event: config.event, state: this.s });
      }
      if (path === '/api/purge' && request.method === 'POST') {
        this.requireOps(request);
        const b = await this.body(request);
        if (b.confirm !== 'USUN-DANE') throw new CmdError('confirm_required', 'Wymagane potwierdzenie: USUN-DANE.');
        return json(await this.purge());
      }
      return json({ ok: false, code: 'not_found', message: 'Nie ma takiego adresu.' }, 404);
    } catch (e) {
      if (e instanceof CmdError) {
        const status = e.code === 'unauthorized' ? 401 : e.code === 'rate_limited' ? 429 : e.code === 'already_voted' ? 409 : 400;
        return json({ ok: false, code: e.code, message: e.message, data: e.data }, status);
      }
      console.log('błąd', String(e));
      return json({ ok: false, code: 'server_error', message: 'Błąd serwera.' }, 500);
    }
  }

  private async body(request: Request): Promise<Record<string, any>> {
    const text = await request.text();
    if (text.length > 20_000) throw new CmdError('too_large', 'Za duże żądanie.');
    try { const b = JSON.parse(text); if (b && typeof b === 'object') return b; } catch { /* niżej */ }
    throw new CmdError('bad_request', 'Niepoprawne dane.');
  }

  private requireOps(request: Request): void {
    if (!safeEqual(bearer(request), this.env.OPS_TOKEN)) throw new CmdError('unauthorized', 'Brak dostępu.');
  }

  private deviceOk(id: unknown): id is string {
    return typeof id === 'string' && /^[A-Za-z0-9_-]{8,64}$/.test(id);
  }

  // ---------- ankieta ----------
  private async vote(b: Record<string, any>): Promise<unknown> {
    if (!this.deviceOk(b.deviceId)) throw new CmdError('bad_request', 'Brak identyfikatora urządzenia.');
    const pollId = String(b.pollId ?? '');
    // Hasz służy wyłącznie do blokady drugiego głosu. Nie zapisujemy przy nim wyboru, czasu ani IP.
    const key = `v:${this.s.pollEpoch}:${await sha256Hex(`${b.deviceId}|${this.env.SALT}|${pollId}|${this.s.pollEpoch}`)}`;
    // Od tego miejsca bez await: sprawdzenie i zapis są niepodzielne.
    if (this.s.pollStatus !== 'open') throw new CmdError('poll_closed', 'Ankieta nie jest teraz otwarta.');
    const poll = this.s.polls.find((p) => p.id === pollId);
    const opt = poll?.options.find((o) => o.id === b.optionId);
    if (!poll || !opt) throw new CmdError('bad_request', 'Nie ma takiej odpowiedzi.');
    if (this.voters.has(key)) throw new CmdError('already_voted', 'Twój głos został już zapisany.');
    this.voters.add(key);
    poll.tally[opt.id] = (poll.tally[opt.id] ?? 0) + 1;
    this.s.counters.votes = sum(this.s.polls[0].tally);
    this.commit({ [key]: 1 });
    return { ok: true };
  }

  // ---------- pytania ----------
  private async submitQuestion(b: Record<string, any>): Promise<unknown> {
    if (!this.deviceOk(b.deviceId)) throw new CmdError('bad_request', 'Brak identyfikatora urządzenia.');
    if (b.website) return { ok: true }; // honeypot: bot dostaje "ok", nic nie zapisujemy
    const devHash = await sha256Hex(`${b.deviceId}|${this.env.SALT}|q`);
    const id = 'q' + (await sha256Hex(`${devHash}|${String(b.clientId ?? '')}`)).slice(0, 16);
    if (this.s.phoneMode === 'closed') throw new CmdError('closed', 'Zbieranie pytań jest zamknięte.');
    if (this.s.questions.some((q) => q.id === id)) return { ok: true, duplicate: true }; // podwójne kliknięcie
    const text = cleanText(b.text, L.questionMax + 50);
    if (text.length < L.questionMin || text.length > L.questionMax) {
      throw new CmdError('validation', `Pytanie powinno mieć od ${L.questionMin} do ${L.questionMax} znaków.`);
    }
    const now = Date.now();
    const windowMs = L.questionsWindowMinutes * 60_000;
    const times = (this.questionTimes.get(devHash) ?? []).filter((t) => now - t < windowMs);
    if (times.length >= L.questionsPerDevice) {
      const waitMin = Math.max(1, Math.ceil((windowMs - (now - times[0])) / 60_000));
      throw new CmdError('rate_limited', `Limit ${L.questionsPerDevice} pytań na ${L.questionsWindowMinutes} minut. Spróbuj za ${waitMin} min.`);
    }
    times.push(now);
    this.questionTimes.set(devHash, times);
    const q = this.makeQuestion(id, text, b.name, b.expertId, 'phone');
    this.commit(this.qKey(q));
    return { ok: true };
  }

  private makeQuestion(id: string, text: string, name: unknown, expertId: unknown, source: 'phone' | 'manual'): Question {
    const nm = cleanText(name, L.nameMax);
    const flagged = blocklistHit(`${text} ${nm}`, BLOCKLIST);
    const q: Question = {
      id, text, status: flagged ? 'hidden' : 'new', createdAt: new Date().toISOString(), source,
      ...(nm ? { name: nm } : {}),
      ...(this.s.experts.some((e) => e.id === expertId) ? { expertId: String(expertId) } : {}),
      ...(flagged ? { flagged: true } : {}),
    };
    this.s.questions.push(q);
    this.s.counters.questionsSubmitted++;
    return q;
  }

  private async purge(): Promise<unknown> {
    const counts = { questions: this.s.questions.length, voterHashes: this.voters.size };
    await this.ctx.storage.deleteAlarm();
    await this.ctx.storage.deleteAll();
    this.s = freshState();
    this.voters.clear();
    this.questionTimes.clear();
    const at = new Date().toISOString();
    console.log(`PURGE: dane wydarzenia ${this.env.EVENT_ID} trwale usunięte ${at}`, JSON.stringify(counts));
    this.scheduleBroadcast();
    return { ok: true, purgedAt: at, removed: counts };
  }

  // ---------- WebSocket ----------
  private acceptSocket(request: Request, url: URL): Response {
    if (request.headers.get('Upgrade') !== 'websocket') return json({ ok: false, code: 'bad_request', message: 'Oczekiwano WebSocket.' }, 426);
    const role = (['public', 'screen', 'mod', 'ops'] as Role[]).find((r) => r === url.searchParams.get('role')) ?? 'public';
    const pair = new WebSocketPair();
    this.ctx.acceptWebSocket(pair[1], [role]);
    pair[1].serializeAttachment({ role, authed: false } satisfies Attachment);
    return new Response(null, { status: 101, webSocket: pair[0] });
  }

  private send(ws: WebSocket, msg: ServerMsg): void {
    try { ws.send(JSON.stringify(msg)); } catch { /* zamknięte */ }
  }

  async webSocketMessage(ws: WebSocket, raw: string | ArrayBuffer): Promise<void> {
    if (typeof raw !== 'string' || raw.length > 400_000) return;
    let m: ClientMsg;
    try { m = JSON.parse(raw); } catch { return; }
    const a = (ws.deserializeAttachment() as Attachment | null) ?? { role: 'public' as Role, authed: false };

    if (m.t === 'hello') {
      const tok = m.token ?? '';
      const e = this.env;
      const ok =
        a.role === 'public' ||
        (a.role === 'ops' && safeEqual(tok, e.OPS_TOKEN)) ||
        (a.role === 'mod' && (safeEqual(tok, e.MOD_TOKEN) || safeEqual(tok, e.OPS_TOKEN))) ||
        (a.role === 'screen' && (safeEqual(tok, e.SCREEN_KEY) || safeEqual(tok, e.OPS_TOKEN)));
      if (!ok) {
        this.send(ws, { t: 'error', code: 'unauthorized', message: 'Niepoprawny token dostępu.' });
        ws.close(4401, 'unauthorized');
        return;
      }
      ws.serializeAttachment({ role: a.role, authed: true, preview: !!m.preview } satisfies Attachment);
      this.send(ws, { t: 'state', version: this.s.version, view: this.viewFor(a.role) });
      this.scheduleBroadcast(); // licznik podłączonych w panelu operatora
      return;
    }
    if (!a.authed) return;

    if (m.t === 'ping') {
      if (a.role === 'screen' && !a.preview) {
        const wasDead = Date.now() - this.screenBeatAt > 12_000;
        this.screenBeatAt = Date.now();
        const slideChanged = typeof m.slide === 'number' && m.slide !== this.screenSlide;
        if (typeof m.slide === 'number') this.screenSlide = m.slide;
        this.lastBeatBroadcast ??= 0;
        // Heartbeat odświeża panel operatora, ale nie częściej niż co 5 s.
        if (wasDead || slideChanged || Date.now() - this.lastBeatBroadcast > 4500) { this.lastBeatBroadcast = Date.now(); this.scheduleBroadcast(); }
      }
      this.send(ws, { t: 'pong' });
      return;
    }

    if (m.t === 'cmd') {
      if (a.role !== 'ops' && a.role !== 'mod') return;
      const id = String(m.id ?? '');
      if (this.seenCmd.has(id)) { this.send(ws, { t: 'ack', id }); return; } // powtórka po reconnect
      try {
        const data = this.exec(String(m.type), (m.payload ?? {}) as Record<string, any>, a.role);
        this.seenCmd.set(id, Date.now());
        if (this.seenCmd.size > 2000) { const cut = Date.now() - 600_000; for (const [k, t] of this.seenCmd) if (t < cut) this.seenCmd.delete(k); }
        this.send(ws, { t: 'ack', id, data });
      } catch (e) {
        if (e instanceof CmdError) this.send(ws, { t: 'error', id, code: e.code, message: e.message });
        else { console.log('cmd błąd', String(e)); this.send(ws, { t: 'error', id, code: 'server_error', message: 'Błąd serwera.' }); }
      }
    }
  }

  webSocketClose(ws: WebSocket, code: number): void {
    try { ws.close(code === 1005 || code === 1006 ? 1000 : code); } catch { /* już zamknięte */ }
    this.scheduleBroadcast();
  }
  webSocketError(): void { this.scheduleBroadcast(); }

  // ---------- komendy operatora i moderatora ----------
  private q(id: unknown): Question {
    const q = this.s.questions.find((x) => x.id === id);
    if (!q) throw new CmdError('not_found', 'Nie ma takiego pytania.');
    return q;
  }

  private unfocus(except?: string): Record<string, unknown> {
    const out: Record<string, unknown> = {};
    for (const q of this.s.questions) if (q.status === 'on_screen' && q.id !== except) { q.status = 'approved'; Object.assign(out, this.qKey(q)); }
    return out;
  }

  private exec(type: string, p: Record<string, any>, role: 'ops' | 'mod'): unknown {
    const s = this.s;
    const modAllowed = type.startsWith('q.') || type.startsWith('queue.') || type.startsWith('rec.');
    if (role === 'mod' && !modAllowed) throw new CmdError('forbidden', 'Ta akcja jest dostępna tylko dla operatora.');

    switch (type) {
      case 'scene.set': {
        if (!SCENES.includes(p.scene)) throw new CmdError('bad_request', 'Nieznana scena.');
        s.scene = p.scene as SceneId;
        return this.commit();
      }
      case 'phone.set': {
        if (!PHONE_MODES.includes(p.mode)) throw new CmdError('bad_request', 'Nieznany tryb telefonu.');
        s.phoneMode = p.mode;
        return this.commit();
      }
      case 'agenda.go': {
        const step = config.agenda[Number(p.step)];
        if (!step) throw new CmdError('bad_request', 'Nie ma takiego kroku agendy.');
        s.agendaStep = Number(p.step);
        s.scene = step.scene as SceneId;
        s.phoneMode = step.phoneMode as State['phoneMode'];
        if ((step as { pollOpen?: boolean }).pollOpen && s.pollStatus === 'draft') s.pollStatus = 'open';
        if (step.scene === 'recommendations') s.sceneParams.revealCount = 0;
        return this.commit();
      }
      case 'fallback.set': { s.fallbackStatic = !!p.on; return this.commit(); }

      // --- ankieta ---
      case 'poll.open': {
        s.pollStatus = 'open';
        for (const poll of s.polls) delete poll.frozenResult;
        return this.commit();
      }
      case 'poll.close': {
        s.pollStatus = 'closed';
        const at = new Date().toISOString();
        for (const poll of s.polls) { const t = effectiveTally(poll); poll.frozenResult = { tally: t, total: sum(t), at }; }
        return this.commit();
      }
      case 'poll.reset': {
        if (p.confirm !== 'RESET') throw new CmdError('confirm_required', 'Wpisz słowo RESET, aby wyzerować ankietę.');
        const old = [...this.voters];
        s.pollEpoch++;
        s.pollStatus = 'draft';
        for (const poll of s.polls) { poll.tally = Object.fromEntries(poll.options.map((o) => [o.id, 0])); delete poll.frozenResult; delete poll.manualOverride; }
        s.counters.votes = 0;
        this.voters.clear();
        for (let i = 0; i < old.length; i += 100) void this.ctx.storage.delete(old.slice(i, i + 100));
        return this.commit();
      }
      case 'poll.manual': {
        const poll = s.polls.find((x) => x.id === p.pollId);
        if (!poll) throw new CmdError('not_found', 'Nie ma takiej ankiety.');
        if (p.values === null) delete poll.manualOverride;
        else {
          const v: Record<string, number> = {};
          for (const o of poll.options) {
            const n = Number(p.values?.[o.id]);
            if (!Number.isInteger(n) || n < 0 || n > 100_000) throw new CmdError('validation', 'Podaj liczby całkowite od zera.');
            v[o.id] = n;
          }
          poll.manualOverride = v;
        }
        if (s.pollStatus === 'closed') { const t = effectiveTally(poll); poll.frozenResult = { tally: t, total: sum(t), at: new Date().toISOString() }; }
        return this.commit();
      }
      case 'poll.active': {
        const i = Number(p.index);
        if (!s.polls[i]) throw new CmdError('bad_request', 'Nie ma takiego pytania ankiety.');
        s.activePoll = i;
        return this.commit();
      }
      case 'poll.edit': {
        const poll = s.polls.find((x) => x.id === p.pollId);
        if (!poll) throw new CmdError('not_found', 'Nie ma takiej ankiety.');
        if (s.pollStatus !== 'draft' || sum(poll.tally) > 0) throw new CmdError('locked', 'Treść można zmieniać tylko przed otwarciem ankiety (lub po wyzerowaniu).');
        const text = cleanText(p.text, 300);
        if (text.length < 5) throw new CmdError('validation', 'Za krótkie pytanie.');
        poll.text = text;
        poll.options.forEach((o, i) => { const l = cleanText(p.labels?.[i], 60); if (l) o.label = l; });
        return this.commit();
      }
      case 'experts.set': {
        if (!Array.isArray(p.experts) || p.experts.length > 12) throw new CmdError('validation', 'Lista ekspertów: maksymalnie 12 pozycji.');
        s.experts = p.experts
          .map((e: any, i: number) => ({ id: `e${i + 1}`, name: cleanText(e?.name, 80), role: cleanText(e?.role, 120) || undefined }))
          .filter((e: Expert) => e.name);
        return this.commit();
      }

      // --- pytania ---
      case 'q.approve': {
        const q = this.q(p.id);
        q.status = 'approved'; q.approvedAt = new Date().toISOString(); delete q.duplicateOf;
        return this.commit(this.qKey(q));
      }
      case 'q.hide': {
        const q = this.q(p.id);
        q.status = 'hidden';
        s.queue = s.queue.filter((x) => x !== q.id);
        return this.commit(this.qKey(q));
      }
      case 'q.restore': {
        const q = this.q(p.id);
        q.status = 'new'; delete q.duplicateOf;
        return this.commit(this.qKey(q));
      }
      case 'q.duplicate': {
        const q = this.q(p.id);
        const parent = this.q(p.of);
        if (parent.id === q.id) throw new CmdError('validation', 'Pytanie nie może być duplikatem samego siebie.');
        q.status = 'duplicate'; q.duplicateOf = parent.id;
        s.queue = s.queue.filter((x) => x !== q.id);
        return this.commit(this.qKey(q));
      }
      case 'q.answered': {
        const q = this.q(p.id);
        q.status = 'answered';
        s.queue = s.queue.filter((x) => x !== q.id);
        return this.commit(this.qKey(q));
      }
      case 'q.edit': {
        const q = this.q(p.id);
        const text = cleanText(p.text, L.questionMax + 50);
        if (text.length < 3 || text.length > L.questionMax) throw new CmdError('validation', `Treść: do ${L.questionMax} znaków.`);
        if (text !== q.text) { q.originalText ??= q.text; q.text = text; }
        return this.commit(this.qKey(q));
      }
      case 'q.add': {
        const text = cleanText(p.text, L.questionMax + 50);
        if (text.length < 3 || text.length > L.questionMax) throw new CmdError('validation', `Treść: od 3 do ${L.questionMax} znaków.`);
        const q = this.makeQuestion('m' + crypto.randomUUID().replace(/-/g, '').slice(0, 16), text, p.name, p.expertId, 'manual');
        return this.commit(this.qKey(q));
      }
      case 'q.focus': {
        const q = this.q(p.id);
        if (!['approved', 'on_screen', 'answered'].includes(q.status)) throw new CmdError('not_approved', 'Najpierw zatwierdź pytanie.');
        const changed = this.unfocus(q.id);
        q.status = 'on_screen'; q.approvedAt ??= new Date().toISOString();
        s.sceneParams.questionId = q.id;
        if (p.switchScene !== false) s.scene = 'question_focus';
        return this.commit({ ...changed, ...this.qKey(q) });
      }
      case 'q.unfocus': {
        const changed = this.unfocus();
        delete s.sceneParams.questionId;
        return this.commit(changed);
      }
      case 'q.step': {
        // Poprzednie lub następne pytanie z kolejki "Na panel".
        const dir = p.dir === -1 ? -1 : 1;
        const list = s.queue.filter((id) => { const q = s.questions.find((x) => x.id === id); return q && (q.status === 'approved' || q.status === 'on_screen'); });
        if (!list.length) throw new CmdError('empty', 'Kolejka "Na panel" jest pusta.');
        const cur = list.indexOf(s.sceneParams.questionId ?? '');
        const next = cur < 0 ? (dir > 0 ? 0 : list.length - 1) : cur + dir;
        if (next < 0 || next >= list.length) throw new CmdError('end', dir > 0 ? 'To było ostatnie pytanie w kolejce.' : 'To jest pierwsze pytanie w kolejce.');
        return this.exec('q.focus', { id: list[next], switchScene: p.switchScene }, role);
      }
      case 'queue.set': {
        if (!Array.isArray(p.ids)) throw new CmdError('bad_request', 'Niepoprawna kolejka.');
        const known = new Set(s.questions.map((q) => q.id));
        s.queue = [...new Set(p.ids.map(String))].filter((id) => known.has(id)).slice(0, 100);
        return this.commit();
      }

      // --- rekomendacje ---
      case 'rec.set': {
        const i = Number(p.index);
        const r: Recommendation | undefined = s.recommendations[i];
        if (!r) throw new CmdError('bad_request', 'Nie ma takiego slotu.');
        if (Number(p.baseRev) !== r.rev) {
          throw new CmdError('conflict', 'Ktoś inny zmienił tę rekomendację przed chwilą. Wczytano aktualną wersję.');
        }
        const title = cleanText(p.title, REC_TITLE_MAX), text = cleanText(p.text, REC_TEXT_MAX);
        if (title === r.title && text === r.text) return { rev: r.rev };
        r.title = title; r.text = text; r.rev++;
        this.commit();
        return { rev: r.rev };
      }
      case 'rec.reveal': {
        const n = Number(p.count);
        if (!Number.isInteger(n) || n < 0 || n > 5) throw new CmdError('bad_request', 'Zakres 0 do 5.');
        s.sceneParams.revealCount = n;
        return this.commit();
      }

      // --- slajdy ---
      case 'slides.set': {
        const { slides, issues } = validateSlides(p.slides, true);
        if (issues.length) {
          throw new CmdError('validation', issues.map((i) => `${i.index >= 0 ? `Slajd ${i.index + 1} (${i.title || 'bez tytułu'}): ` : ''}${i.problems.join(', ')}`).join(' | '));
        }
        s.slides = slides; s.slidesCustom = true;
        s.sceneParams.slideIndex = 0; s.sceneParams.slideNonce = (s.sceneParams.slideNonce ?? 0) + 1;
        return this.commit({ slides });
      }
      case 'slides.reset': {
        s.slides = (seedSlides as { slides: Slide[] }).slides; s.slidesCustom = false;
        s.sceneParams.slideIndex = 0; s.sceneParams.slideNonce = (s.sceneParams.slideNonce ?? 0) + 1;
        void this.ctx.storage.delete('slides');
        return this.commit();
      }
      case 'slides.ctl': {
        const n = Math.max(1, s.slides.length);
        const cur = Date.now() - this.screenBeatAt < 15_000 ? this.screenSlide : (s.sceneParams.slideIndex ?? 0);
        if (p.action === 'pause') s.slidesPaused = true;
        else if (p.action === 'play') s.slidesPaused = false;
        else {
          const target = p.action === 'next' ? cur + 1 : p.action === 'prev' ? cur - 1 : Number(p.index);
          if (!Number.isFinite(target)) throw new CmdError('bad_request', 'Niepoprawny numer slajdu.');
          s.sceneParams.slideIndex = ((Math.trunc(target) % n) + n) % n;
          s.sceneParams.slideNonce = (s.sceneParams.slideNonce ?? 0) + 1;
          this.screenSlide = s.sceneParams.slideIndex;
        }
        return this.commit();
      }
      default:
        throw new CmdError('unknown_cmd', `Nieznana komenda: ${type}`);
    }
  }
}
