// Panel operatora: sceny, telefon, ankieta, pytania, rekomendacje, slajdy, tryb awaryjny, eksport.
import { render } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import type { PhoneMode, SceneId, Slide, StaffView } from '@shared/types.ts';
import { PHONE_MODES, SCENES } from '@shared/types.ts';
import { effectiveTally, percents, sum, validateSlides } from '@shared/util.ts';
import { applyTheme, config } from '../lib/theme.ts';
import { t } from '../lib/i18n.ts';
import { download } from '../lib/zip.ts';
import { Confirm, Gate, OfflineBanner, Toasts, exportAll, hhmm, pollPng, questionsCsv, useStaff, votesCsv, type Staff } from '../staff/core.tsx';
import { Questions } from '../staff/Questions.tsx';
import { Recs } from '../staff/Recs.tsx';
import { SlideView } from '../screen/slides.tsx';
import '../themes/base.css';
import '../themes/screen.css';
import '../themes/staff.css';

applyTheme();

type Tab = 'questions' | 'recs' | 'slides' | 'export';

function App() {
  const staff = useStaff('ops');
  const [tab, setTab] = useState<Tab>('questions');
  const v = staff.view;
  const vRef = useRef(v);
  vRef.current = v;

  const nextStep = () => {
    const cur = vRef.current;
    if (!cur) return;
    const i = cur.agendaStep + 1;
    if (i < config.agenda.length) staff.run('agenda.go', { step: i });
  };

  // Skróty: 1 do 9 i 0 przełączają sceny, spacja to "Dalej". Nie działają podczas pisania w polach.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.ctrlKey || e.metaKey || e.altKey || /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(el.tagName) || el.isContentEditable) return;
      if (e.key === ' ') { e.preventDefault(); nextStep(); return; }
      if (/^[0-9]$/.test(e.key)) {
        const scene = e.key === '0' ? SCENES[9] : SCENES[Number(e.key) - 1];
        if (scene) staff.run('scene.set', { scene });
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!staff.token || staff.status === 'unauthorized') return <Gate staff={staff} title={t('ops.title')} />;
  if (!v) return <div class="loading">{t('staff.connecting')}</div>;

  return (
    <div class="ops">
      <StatusBar staff={staff} />
      <OfflineBanner staff={staff} />
      <div class="ops-grid">
        <section class="panel">
          <h2>{t('ops.scenes')}</h2>
          <div class="scene-grid">
            {SCENES.map((s, i) => (
              <button class={`btn scene-btn ${v.scene === s ? 'on' : ''} ${s === 'blackout' ? 'danger' : ''}`} disabled={!staff.online}
                onClick={() => staff.run('scene.set', { scene: s })}>
                <kbd>{i === 9 ? 0 : i + 1}</kbd>{t(`scene.${s}`)}
              </button>
            ))}
          </div>
          <h2>{t('ops.agenda')}</h2>
          <ol class="agenda">
            {config.agenda.map((a, i) => (
              <li class={i === v.agendaStep ? 'cur' : i === v.agendaStep + 1 ? 'next' : ''}>
                <button class="agenda-step" disabled={!staff.online} onClick={() => { if (window.confirm(t('ops.agenda.jump', { label: a.label }))) staff.run('agenda.go', { step: i }); }}>
                  <b>{a.time}</b><span>{a.label}</span>
                </button>
              </li>
            ))}
          </ol>
          <button class="btn primary big wide" disabled={!staff.online || v.agendaStep + 1 >= config.agenda.length} onClick={nextStep}>
            {t('ops.next')} <kbd>{t('ops.space')}</kbd>
          </button>
          <p class="note">{t('ops.agenda.note')}</p>
        </section>

        <section class="panel">
          <h2>{t('ops.preview')} <small>{t(`scene.${v.scene}`)}</small></h2>
          <div class="preview"><iframe title={t('ops.preview')} src={`/screen?preview=1#k=${encodeURIComponent(staff.token)}`} /></div>
          <h2>{t('ops.phone')}</h2>
          <div class="seg">
            {PHONE_MODES.map((m: PhoneMode) => (
              <button class={`btn ${v.phoneMode === m ? 'on' : ''}`} disabled={!staff.online} onClick={() => staff.run('phone.set', { mode: m })}>{t(`phone.mode.${m}`)}</button>
            ))}
          </div>
          <h2>{t('ops.fallback')}</h2>
          <div class="row wrap">
            <button class={`btn ${v.fallbackStatic ? 'on warn' : ''}`} disabled={!staff.online} onClick={() => staff.run('fallback.set', { on: !v.fallbackStatic })}>
              {v.fallbackStatic ? t('ops.fallback.on') : t('ops.fallback.off')}
            </button>
            <button class={`btn danger ${v.scene === 'blackout' ? 'on' : ''}`} disabled={!staff.online} onClick={() => staff.run('scene.set', { scene: (v.scene === 'blackout' ? 'idle' : 'blackout') as SceneId })}>
              {v.scene === 'blackout' ? t('ops.blackout.off') : t('ops.blackout')}
            </button>
          </div>
          <p class="note">{t('ops.fallback.note')}</p>
        </section>

        <PollPanel staff={staff} />
      </div>

      <nav class="tabs main-tabs">
        {(['questions', 'recs', 'slides', 'export'] as Tab[]).map((x) => (
          <button class={`tab ${tab === x ? 'on' : ''}`} onClick={() => setTab(x)}>
            {t(`ops.tab.${x}`)}{x === 'questions' ? <b>{v.questions.filter((q) => q.status === 'new').length}</b> : null}
          </button>
        ))}
      </nav>
      <section class="panel tab-body">
        {tab === 'questions' ? <Questions staff={staff} compact />
          : tab === 'recs' ? <Recs staff={staff} />
          : tab === 'slides' ? <SlidesPanel staff={staff} />
          : <ExportPanel staff={staff} />}
      </section>
      <Toasts staff={staff} />
    </div>
  );
}

function StatusBar({ staff }: { staff: Staff }) {
  const v = staff.view!;
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id); }, []);
  const beatAge = v.presence.screenBeatAt ? Math.round((now - v.presence.screenBeatAt) / 1000) : null;
  // Heartbeat z /screen co 5 s. Powyżej 12 s bez sygnału uznajemy, że ekran nie żyje.
  const alive = staff.online && beatAge !== null && beatAge < 12;
  return (
    <header class="status">
      <span class={`dot ${staff.online ? 'ok' : 'err'}`} /> <b>{staff.online ? t('status.ws.ok') : t('status.ws.down')}</b>
      <span class={`chip ${alive ? 'ok' : 'err'}`}>{alive ? t('status.screen.alive') : t('status.screen.dead')}</span>
      <span>{t('status.screens')} <b>{v.presence.screens}</b></span>
      <span>{t('status.phones')} <b>{v.presence.phones}</b></span>
      <span>{t('status.mods')} <b>{v.presence.mods}</b></span>
      <span>{t('status.saved')} <b>{new Date(v.lastSavedAt).toLocaleTimeString('pl-PL')}</b></span>
      <span class="grow" />
      <span class="muted">{t('status.version')} {v.buildVersion} · #{v.version}</span>
    </header>
  );
}

function PollPanel({ staff }: { staff: Staff }) {
  const v = staff.view!;
  const p = v.polls[v.activePoll] ?? v.polls[0];
  const tally = effectiveTally(p, v.pollStatus === 'closed');
  const pct = percents(tally);
  const [manual, setManual] = useState<Record<string, string> | null>(null);
  const off = !staff.online;

  const reset = () => {
    if (!window.confirm(t('poll.reset.confirm1'))) return;
    const word = window.prompt(t('poll.reset.confirm2'));
    if (word === null) return;
    staff.run('poll.reset', { confirm: word.trim() }, t('poll.reset.done'));
  };

  return (
    <section class="panel">
      <h2>{t('ops.poll')} <span class={`chip st-${v.pollStatus}`}>{t(`poll.status.${v.pollStatus}`)}</span></h2>
      {v.polls.length > 1 ? (
        <div class="seg">
          {v.polls.map((x, i) => <button class={`btn sm ${v.activePoll === i ? 'on' : ''}`} disabled={off} onClick={() => staff.run('poll.active', { index: i })}>{t('poll.question', { n: i + 1 })}</button>)}
        </div>
      ) : null}
      <p class="poll-text">{p.text}</p>
      <table class="tally">
        {p.options.map((o) => <tr><td>{o.label}</td><td class="num">{tally[o.id]}</td><td class="num">{pct[o.id]}%</td></tr>)}
        <tr class="total"><td>{t('poll.total')}</td><td class="num">{sum(tally)}</td><td class="num">{p.manualOverride ? t('poll.manual.tag') : ''}</td></tr>
      </table>
      <div class="row wrap">
        {v.pollStatus !== 'open'
          ? <button class="btn primary big" disabled={off} onClick={() => staff.run('poll.open', {}, t('poll.opened'))}>{v.pollStatus === 'closed' ? t('poll.reopen') : t('poll.open')}</button>
          : <Confirm cls="warn big" disabled={off} text={t('poll.close.confirm')} onYes={() => staff.run('poll.close', {}, t('poll.closed'))}>{t('poll.close')}</Confirm>}
        <button class="btn" onClick={async () => download(await pollPng(v), 'ankieta-wynik-1920x1080.png')}>{t('poll.png')}</button>
      </div>
      <details open={!!manual} onToggle={(e) => { if (!(e.target as HTMLDetailsElement).open) setManual(null); }}>
        <summary onClick={() => setManual(manual ?? Object.fromEntries(p.options.map((o) => [o.id, String(tally[o.id])])))}>{t('poll.manual')}</summary>
        <p class="note">{t('poll.manual.note')}</p>
        {manual ? (
          <div class="manual">
            {p.options.map((o) => (
              <label><span>{o.label}</span>
                <input type="number" min={0} step={1} inputMode="numeric" value={manual[o.id]} onInput={(e) => setManual({ ...manual, [o.id]: (e.target as HTMLInputElement).value })} />
              </label>
            ))}
            <div class="row wrap">
              <Confirm cls="primary" disabled={off} text={t('poll.manual.confirm')}
                onYes={() => staff.run('poll.manual', { pollId: p.id, values: Object.fromEntries(p.options.map((o) => [o.id, Number(manual[o.id])])) }, t('poll.manual.saved'))}>
                {t('poll.manual.save')}
              </Confirm>
              {p.manualOverride ? <Confirm cls="" disabled={off} text={t('poll.manual.clear.confirm')} onYes={() => staff.run('poll.manual', { pollId: p.id, values: null })}>{t('poll.manual.clear')}</Confirm> : null}
            </div>
          </div>
        ) : null}
      </details>
      <button class="btn danger sm" disabled={off} onClick={reset}>{t('poll.reset')}</button>
    </section>
  );
}

function SlidesPanel({ staff }: { staff: Staff }) {
  const v = staff.view!;
  const [pending, setPending] = useState<Slide[] | null>(null);
  const [issues, setIssues] = useState<string[]>([]);
  const [sel, setSel] = useState(0);
  const off = !staff.online;
  const list = pending ?? v.slides;
  const cur = list[Math.min(sel, list.length - 1)];

  const onFile = async (e: Event) => {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    try {
      // Ta sama walidacja, co na serwerze: bez źródła, roku i verified: true plik nie przejdzie.
      const res = validateSlides(JSON.parse(await file.text()), true);
      if (res.issues.length) {
        setPending(null);
        setIssues(res.issues.map((i) => `${i.index >= 0 ? t('slides.issue', { n: i.index + 1, title: i.title || '?' }) : ''} ${i.problems.join(', ')}`));
      } else { setIssues([]); setPending(res.slides); setSel(0); }
    } catch { setPending(null); setIssues([t('slides.badJson')]); }
  };

  return (
    <div class="slides-panel">
      <div class="slides-left">
        <div class="row wrap">
          <button class="btn" disabled={off} onClick={() => staff.run('slides.ctl', { action: 'prev' })}>{t('slides.prev')}</button>
          <button class={`btn ${v.slidesPaused ? 'on warn' : ''}`} disabled={off} onClick={() => staff.run('slides.ctl', { action: v.slidesPaused ? 'play' : 'pause' })}>{v.slidesPaused ? t('slides.play') : t('slides.pause')}</button>
          <button class="btn" disabled={off} onClick={() => staff.run('slides.ctl', { action: 'next' })}>{t('slides.next')}</button>
          <span class="muted">{t('slides.onScreen', { n: v.presence.screenSlide + 1, of: v.slides.length })}</span>
        </div>
        <ol class="slide-list">
          {list.map((s, i) => (
            <li class={`${i === sel ? 'sel' : ''} ${!pending && v.scene === 'infographics' && i === v.presence.screenSlide ? 'live' : ''}`}>
              <button class="slide-item" onClick={() => setSel(i)}>
                <b>{i + 1}. {s.title}</b>
                <small>{s.type} · {s.source || t('slides.noSource')}{s.year ? `, ${s.year}` : ''} · {s.verified ? t('slides.verified') : t('slides.unverified')}</small>
              </button>
              {!pending ? <button class="btn sm" disabled={off} onClick={() => staff.run('slides.ctl', { action: 'goto', index: i })}>{t('slides.goto')}</button> : null}
            </li>
          ))}
        </ol>
        {list.length === 0 ? <p class="empty">{t('slides.empty')}</p> : null}
        <div class="row wrap">
          <label class="btn file">{t('slides.upload')}<input type="file" accept="application/json,.json" onChange={onFile} /></label>
          {pending ? (
            <>
              <Confirm cls="primary" disabled={off} text={t('slides.save.confirm', { n: pending.length })}
                onYes={async () => { if (await staff.run('slides.set', { slides: pending }, t('slides.saved'))) setPending(null); }}>{t('slides.save', { n: pending.length })}</Confirm>
              <button class="btn" onClick={() => setPending(null)}>{t('common.cancel')}</button>
            </>
          ) : v.slidesCustom ? <Confirm cls="" disabled={off} text={t('slides.reset.confirm')} onYes={() => staff.run('slides.reset')}>{t('slides.reset')}</Confirm> : null}
        </div>
        {pending ? <p class="note ok">{t('slides.pending', { n: pending.length })}</p> : null}
        {issues.length ? <ul class="issues">{issues.map((x) => <li>{x}</li>)}</ul> : null}
        <p class="note">{t('slides.note')}</p>
      </div>
      <div class="slides-right">
        <div class="mini-stage">
          {cur ? <div class="stage"><div class="safe"><div class="scene info" key={`${sel}-${pending ? 'p' : 'c'}`}><SlideView slide={cur} showPlaceholder /></div></div></div> : null}
        </div>
        {cur?.notes ? <p class="note">{t('slides.notes')} {cur.notes}</p> : null}
      </div>
    </div>
  );
}

function ExportPanel({ staff }: { staff: Staff }) {
  const v = staff.view!;
  const [experts, setExperts] = useState(() => v.experts.map((e) => `${e.name}${e.role ? ` | ${e.role}` : ''}`).join('\n'));
  const p = v.polls[v.activePoll] ?? v.polls[0];
  const [pollText, setPollText] = useState(p.text);
  const [labels, setLabels] = useState(p.options.map((o) => o.label));
  const off = !staff.online;
  const [busy, setBusy] = useState(false);

  const qr = async () => {
    const r = await fetch('/qr.svg', { headers: { Authorization: `Bearer ${staff.token}` } });
    if (r.ok) download(await r.blob(), 'qr.svg'); else staff.toast(t('ops.qr.fail'), 'err');
  };

  return (
    <div class="export-grid">
      <div>
        <h3>{t('ops.export')}</h3>
        <button class="btn primary big" disabled={busy} onClick={async () => { setBusy(true); try { await exportAll(staff); } catch { staff.toast(t('ops.export.fail'), 'err'); } setBusy(false); }}>{t('ops.export.all')}</button>
        <p class="note">{t('ops.export.note')}</p>
        <div class="row wrap">
          <button class="btn" onClick={() => download(new Blob([votesCsv(v)], { type: 'text/csv' }), 'votes.csv')}>votes.csv</button>
          <button class="btn" onClick={() => download(new Blob([questionsCsv(v)], { type: 'text/csv' }), 'questions.csv')}>questions.csv</button>
          <button class="btn" onClick={async () => download(await pollPng(v), 'ankieta-wynik-1920x1080.png')}>{t('poll.png')}</button>
        </div>
        <h3>{t('ops.qr')}</h3>
        <p class="note">{t('ops.qr.url')} <b>{v.publicUrl}</b></p>
        <div class="row wrap">
          <button class="btn" onClick={qr}>{t('ops.qr.svg')}</button>
          <a class="btn" href={`/print/qr#t=${encodeURIComponent(staff.token)}`} target="_blank" rel="noopener">{t('ops.qr.print')}</a>
        </div>
      </div>
      <div>
        <h3>{t('ops.experts')}</h3>
        <p class="note">{t('ops.experts.note')}</p>
        <textarea rows={5} value={experts} placeholder={t('ops.experts.placeholder')} onInput={(e) => setExperts((e.target as HTMLTextAreaElement).value)} />
        <Confirm cls="primary" disabled={off} text={t('ops.experts.confirm')}
          onYes={() => staff.run('experts.set', { experts: experts.split('\n').map((l) => { const [name, ...rest] = l.split('|'); return { name: name.trim(), role: rest.join('|').trim() }; }).filter((e) => e.name) }, t('common.saved'))}>
          {t('ops.experts.save')}
        </Confirm>
        <h3>{t('ops.pollEdit')}</h3>
        <p class="note">{t('ops.pollEdit.note')}</p>
        <textarea rows={3} value={pollText} onInput={(e) => setPollText((e.target as HTMLTextAreaElement).value)} />
        <div class="row wrap">
          {labels.map((l, i) => <input type="text" value={l} maxLength={60} onInput={(e) => setLabels(labels.map((x, j) => (j === i ? (e.target as HTMLInputElement).value : x)))} />)}
        </div>
        <button class="btn primary" disabled={off || v.pollStatus !== 'draft'} onClick={() => staff.run('poll.edit', { pollId: p.id, text: pollText, labels }, t('common.saved'))}>{t('ops.pollEdit.save')}</button>
        <p class="note">{t('ops.lastQuestion')} {v.questions.length ? hhmm(v.questions[v.questions.length - 1].createdAt) : t('common.none')}</p>
      </div>
    </div>
  );
}

render(<App />, document.getElementById('app')!);
