// Sceny ekranu głównego. Każda rysuje się na płótnie 1920x1080.
import { useEffect, useRef, useState } from 'preact/hooks';
import type { ScreenQuestion, ScreenView } from '@shared/types.ts';
import { percents, slideHasData, winners } from '@shared/util.ts';
import { AnimNumber, Qr, shortUrl } from '../ui/common.tsx';
import { config, isDev } from '../lib/theme.ts';
import { t } from '../lib/i18n.ts';
import { SlideView } from './slides.tsx';

type P = { v: ScreenView };

export function Idle() {
  const e = config.event;
  return (
    <div class="scene idle">
      <p class="kicker">{e.organizer}</p>
      <h1 class="display">{e.title}</h1>
      <p class="subtitle">{e.subtitle}</p>
      <p class="meta">{e.place}, {e.date}</p>
    </div>
  );
}

export function QrScene({ v }: P) {
  return (
    <div class="scene qrscene">
      <div class="qr-big"><Qr url={v.publicUrl} size={620} /></div>
      <div class="qr-text">
        <h1>{t('screen.qr.title')}</h1>
        <p class="body">{v.phoneMode === 'questions' ? t('screen.qr.questions') : t('screen.qr.poll')}</p>
        <p class="url">{shortUrl(v.publicUrl)}</p>
        <p class="small">{t('screen.qr.noApp')}</p>
      </div>
    </div>
  );
}

export function PollScene({ v, result }: P & { result?: boolean }) {
  const { poll } = v;
  const pct = percents(poll.tally);
  const closed = v.pollStatus === 'closed';
  const final = closed || !!result;
  const win = final ? winners(poll.tally) : [];
  // Krótki puls licznika przy każdym nowym głosie.
  const [pulse, setPulse] = useState(0);
  const prev = useRef(poll.total);
  useEffect(() => { if (poll.total > prev.current) setPulse((x) => x + 1); prev.current = poll.total; }, [poll.total]);
  return (
    <div class={`scene poll ${final ? 'final' : 'live'} opts-${poll.options.length}`}>
      <h2 class="poll-q">{poll.text}</h2>
      <div class="poll-rows">
        {poll.options.map((o, i) => (
          <div class={`poll-row b${i + 1} ${win.includes(o.id) ? 'win' : ''} ${final && win.length && !win.includes(o.id) ? 'lose' : ''}`}>
            <div class="poll-head">
              <span class="poll-label">{o.label}</span>
              <span class="poll-count">{t('screen.poll.count', { n: poll.tally[o.id] })}</span>
            </div>
            <div class="poll-line">
              <div class="poll-track"><div class="poll-fill" style={{ transform: `scaleX(${Math.max(pct[o.id], poll.total ? 0.6 : 0) / 100})` }} /></div>
              <div class="poll-pct"><AnimNumber value={pct[o.id]} duration={500} /><span>%</span></div>
            </div>
          </div>
        ))}
      </div>
      <div class="poll-foot">
        <div class="poll-total">
          {final ? <span class="badge">{t('screen.poll.final')}</span> : null}
          <span>{t('screen.poll.total')} </span>
          <b key={pulse} class={pulse ? 'pulse' : ''}><AnimNumber value={poll.total} duration={450} /></b>
        </div>
        {!final && v.pollStatus === 'open' ? (
          <div class="poll-qr"><div><b>{t('screen.poll.scan')}</b><span>{shortUrl(v.publicUrl)}</span></div><Qr url={v.publicUrl} size={190} /></div>
        ) : null}
      </div>
    </div>
  );
}

function toLabel(v: ScreenView, id?: string): string {
  const e = v.experts.find((x) => x.id === id);
  return e ? t('q.to', { expert: e.name }) : t('q.toAll');
}

export function QuestionsCollect({ v }: P) {
  // Max 4 widoczne karty. Piąta (najstarsza) dostaje klasę "out" i wysuwa się.
  const list = v.approved.filter((q) => q.id !== undefined).slice(-5);
  const overflow = list.length > 4;
  return (
    <div class="scene collect">
      <div class="collect-left">
        <Qr url={v.publicUrl} size={420} />
        <h2>{t('screen.collect.title')}</h2>
        <p class="small">{t('screen.collect.how')}</p>
        <p class="url">{shortUrl(v.publicUrl)}</p>
        <p class="collect-count">{t('screen.collect.count')} <b><AnimNumber value={v.questionsSubmitted} duration={450} /></b></p>
      </div>
      <div class="collect-right">
        {list.length === 0 ? <p class="collect-empty">{t('screen.collect.empty')}</p> : null}
        {list.map((q, i) => (
          <div key={q.id} class={`qcard-wrap ${overflow && i === 0 ? 'out' : ''}`}>
            <div class="qcard-clip"><QCard v={v} q={q} /></div>
          </div>
        ))}
      </div>
    </div>
  );
}

function QCard({ v, q }: P & { q: ScreenQuestion }) {
  return (
    <div class="qcard">
      <p class="qcard-text">{q.text}</p>
      <p class="qcard-meta">{toLabel(v, q.expertId)}{q.name ? ` · ${q.name}` : ''}</p>
    </div>
  );
}

export function QuestionFocus({ v }: P) {
  const q = v.focus;
  if (!q) return <div class="scene focus"><p class="kicker">{t('screen.focus.kicker')}</p><h1 class="focus-empty">{t('screen.focus.empty')}</h1></div>;
  const size = q.text.length <= 90 ? 'xl' : q.text.length <= 170 ? 'l' : 'm';
  return (
    <div class="scene focus" key={q.id}>
      <p class="kicker">{t('screen.focus.kicker')}</p>
      <h1 class={`focus-text ${size}`}>{q.text}</h1>
      <p class="focus-meta"><b>{toLabel(v, q.expertId)}</b>{q.name ? <span> · {q.name}</span> : null}</p>
    </div>
  );
}

export function Recommendations({ v, summary }: P & { summary?: boolean }) {
  const shown = summary ? 5 : Math.min(5, v.sceneParams.revealCount ?? 0);
  return (
    <div class={`scene recs ${summary ? 'summary' : ''}`}>
      <h2 class="recs-title">{t('screen.recs.title')}</h2>
      <ol class="recs-list">
        {v.recommendations.map((r, i) => (
          <li class={`rec ${i < shown ? 'on' : ''} ${!r.title && !r.text ? 'blank' : ''}`}>
            <span class="rec-n">{i + 1}</span>
            <div class="rec-body">
              <p class="rec-title">{r.title}</p>
              <p class="rec-text">{r.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Pętla slajdów. Ekran sam odlicza czas, operator może zatrzymać, cofnąć i przeskoczyć. */
export function Infographics({ v, onIndex, fixed }: P & { onIndex: (i: number) => void; fixed?: number }) {
  const slides = v.slides.filter((s) => isDev || slideHasData(s));
  const [idx, setIdx] = useState(fixed ?? v.sceneParams.slideIndex ?? 0);
  const nonce = v.sceneParams.slideNonce ?? 0;
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (fixed === undefined) setIdx(v.sceneParams.slideIndex ?? 0);
  }, [nonce]);
  const n = slides.length;
  const cur = n ? ((idx % n) + n) % n : 0;
  useEffect(() => { onIndex(cur); }, [cur]);
  useEffect(() => {
    if (!n || v.slidesPaused || fixed !== undefined || n < 2) return;
    const secs = slides[cur].seconds ?? config.slides.defaultSeconds;
    const id = setTimeout(() => setIdx(cur + 1), secs * 1000);
    return () => clearTimeout(id);
  }, [cur, n, v.slidesPaused, fixed]);
  if (!n) return <Idle />;
  return <div class="scene info" key={`${cur}-${nonce}`}><SlideView slide={slides[cur]} showPlaceholder={isDev} /></div>;
}

/** Stały pasek w rogu: mały QR i licznik głosów, gdy ankieta jest otwarta. */
export function CornerBar({ v }: P) {
  if (!config.flags.cornerBar || v.pollStatus !== 'open') return null;
  return (
    <div class="corner">
      <div class="corner-text"><b>{t('screen.corner.cta')}</b><span>{t('screen.corner.voted')} <b><AnimNumber value={v.votes} duration={450} /></b></span></div>
      <Qr url={v.publicUrl} size={132} />
    </div>
  );
}
