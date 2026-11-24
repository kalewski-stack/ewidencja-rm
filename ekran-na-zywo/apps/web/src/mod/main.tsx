// Widok moderatora (tablet lub laptop): pytania na żywo, kolejka "Na panel", edytor rekomendacji.
import { render } from 'preact';
import { useState } from 'preact/hooks';
import { applyTheme } from '../lib/theme.ts';
import { t } from '../lib/i18n.ts';
import { Gate, OfflineBanner, Toasts, useStaff } from '../staff/core.tsx';
import { Questions } from '../staff/Questions.tsx';
import { Recs } from '../staff/Recs.tsx';
import '../themes/base.css';
import '../themes/staff.css';

applyTheme();

function App() {
  const staff = useStaff('mod');
  const [tab, setTab] = useState<'questions' | 'recs'>('questions');
  const v = staff.view;
  if (!staff.token || staff.status === 'unauthorized') return <Gate staff={staff} title={t('mod.title')} />;
  if (!v) return <div class="loading">{t('staff.connecting')}</div>;
  const fresh = v.questions.filter((q) => q.status === 'new').length;
  return (
    <div class="mod">
      <header class="status">
        <span class={`dot ${staff.online ? 'ok' : 'err'}`} /> <b>{staff.online ? t('status.ws.ok') : t('status.ws.down')}</b>
        <span>{t('mod.onScreen')} <b>{t(`scene.${v.scene}`)}</b></span>
        <span>{t('mod.submitted')} <b>{v.counters.questionsSubmitted}</b></span>
        <span class="grow" />
        <span class={`chip ${fresh ? 'attn' : ''}`}>{t('mod.new')} <b>{fresh}</b></span>
      </header>
      <OfflineBanner staff={staff} />
      <nav class="tabs main-tabs">
        <button class={`tab ${tab === 'questions' ? 'on' : ''}`} onClick={() => setTab('questions')}>{t('ops.tab.questions')}<b>{fresh}</b></button>
        <button class={`tab ${tab === 'recs' ? 'on' : ''}`} onClick={() => setTab('recs')}>{t('ops.tab.recs')}</button>
      </nav>
      <section class="panel tab-body">{tab === 'questions' ? <Questions staff={staff} /> : <Recs staff={staff} />}</section>
      <Toasts staff={staff} />
    </div>
  );
}

render(<App />, document.getElementById('app')!);
