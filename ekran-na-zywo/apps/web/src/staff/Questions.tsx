// Moderacja pytań: lista na żywo, zatwierdzanie, duplikaty, kolejka "Na panel", wywołanie na ekran.
import { useMemo, useRef, useState } from 'preact/hooks';
import type { Question, QuestionStatus, StaffView } from '@shared/types.ts';
import { DUPLICATE_THRESHOLD, similarity } from '@shared/util.ts';
import { config } from '../lib/theme.ts';
import { t } from '../lib/i18n.ts';
import { hhmm, type Staff } from './core.tsx';

type Filter = QuestionStatus | 'all';
const FILTERS: Filter[] = ['new', 'approved', 'on_screen', 'answered', 'hidden', 'duplicate', 'all'];

function toLabel(v: StaffView, id?: string): string {
  const e = v.experts.find((x) => x.id === id);
  return e ? t('q.to', { expert: e.name }) : t('q.toAll');
}

/** Podpowiedź duplikatu: najbardziej podobne wcześniejsze pytanie (Jaccard na trigramach > 0.6). Decyduje człowiek. */
function useDupHints(questions: Question[]): Map<string, string> {
  return useMemo(() => {
    const out = new Map<string, string>();
    const pool = questions.filter((q) => q.status !== 'duplicate' && q.status !== 'hidden');
    for (const q of questions) {
      if (q.status !== 'new') continue;
      let best = DUPLICATE_THRESHOLD, bestId = '';
      for (const o of pool) {
        if (o.id === q.id || o.createdAt > q.createdAt) continue;
        const s = similarity(q.text, o.text);
        if (s > best) { best = s; bestId = o.id; }
      }
      if (bestId) out.set(q.id, bestId);
    }
    return out;
  }, [questions]);
}

export function Questions({ staff, compact }: { staff: Staff; compact?: boolean }) {
  const v = staff.view!;
  const [filter, setFilter] = useState<Filter>('new');
  const [expert, setExpert] = useState('*');
  const [newestFirst, setNewestFirst] = useState(true);
  const [group, setGroup] = useState(false);
  const [adding, setAdding] = useState(false);
  const hints = useDupHints(v.questions);
  const seen = useRef(new Set(v.questions.map((q) => q.id)));

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: v.questions.length };
    for (const q of v.questions) c[q.status] = (c[q.status] ?? 0) + 1;
    return c;
  }, [v.questions]);

  let list = v.questions.filter((q) => (filter === 'all' || q.status === filter) && (expert === '*' || (q.expertId ?? '') === expert));
  list = [...list].sort((a, b) => (newestFirst ? b.createdAt.localeCompare(a.createdAt) : a.createdAt.localeCompare(b.createdAt)));
  const groups: { key: string; items: Question[] }[] = group
    ? [...new Set(list.map((q) => q.expertId ?? ''))].map((k) => ({ key: k, items: list.filter((q) => (q.expertId ?? '') === k) }))
    : [{ key: '', items: list }];

  return (
    <div class={`questions ${compact ? 'compact' : ''}`}>
      <Queue staff={staff} />
      <div class="q-toolbar">
        <div class="tabs">
          {FILTERS.map((f) => (
            <button class={`tab ${filter === f ? 'on' : ''} ${f === 'new' && counts.new ? 'attn' : ''}`} onClick={() => setFilter(f)}>
              {t(`q.status.${f}`)} <b>{counts[f] ?? 0}</b>
            </button>
          ))}
        </div>
        <div class="row wrap">
          <select value={expert} onChange={(e) => setExpert((e.target as HTMLSelectElement).value)} aria-label={t('q.filter.expert')}>
            <option value="*">{t('q.filter.allExperts')}</option>
            <option value="">{t('q.toAll')}</option>
            {v.experts.map((e) => <option value={e.id}>{e.name}</option>)}
          </select>
          <button class="btn sm" onClick={() => setNewestFirst((x) => !x)}>{newestFirst ? t('q.sort.newest') : t('q.sort.oldest')}</button>
          <label class="check"><input type="checkbox" checked={group} onChange={(e) => setGroup((e.target as HTMLInputElement).checked)} /> {t('q.group')}</label>
          <button class="btn sm" onClick={() => setAdding((x) => !x)}>{t('q.add')}</button>
        </div>
      </div>
      {adding ? <AddForm staff={staff} onDone={() => setAdding(false)} /> : null}
      <div class="q-list">
        {list.length === 0 ? <p class="empty">{t('q.empty')}</p> : null}
        {groups.map((g) => (
          <>
            {group ? <h4 class="q-group">{toLabel(v, g.key || undefined)} <b>{g.items.length}</b></h4> : null}
            {g.items.map((q) => {
              const fresh = !seen.current.has(q.id);
              seen.current.add(q.id);
              return <Card key={q.id} staff={staff} q={q} hint={hints.get(q.id)} fresh={fresh} />;
            })}
          </>
        ))}
      </div>
    </div>
  );
}

function Card({ staff, q, hint, fresh }: { staff: Staff; q: Question; hint?: string; fresh: boolean }) {
  const v = staff.view!;
  const [mode, setMode] = useState<'view' | 'edit' | 'dup'>('view');
  const [text, setText] = useState(q.text);
  const [dupOf, setDupOf] = useState(hint ?? '');
  const off = !staff.online;
  const inQueue = v.queue.includes(q.id);
  const parent = hint ? v.questions.find((x) => x.id === hint) : undefined;
  const dupParent = q.duplicateOf ? v.questions.find((x) => x.id === q.duplicateOf) : undefined;
  const candidates = v.questions.filter((x) => x.id !== q.id && x.status !== 'duplicate' && x.status !== 'hidden');
  const canShow = q.status === 'approved' || q.status === 'on_screen' || q.status === 'answered';

  return (
    <article class={`q-card st-${q.status} ${fresh ? 'fresh' : ''}`}>
      {mode === 'edit' ? (
        <div class="q-edit">
          <textarea rows={3} maxLength={config.limits.questionMax} value={text} onInput={(e) => setText((e.target as HTMLTextAreaElement).value)} />
          <div class="row">
            <button class="btn primary" disabled={off} onClick={async () => { if (await staff.run('q.edit', { id: q.id, text })) setMode('view'); }}>{t('common.save')}</button>
            <button class="btn" onClick={() => { setText(q.text); setMode('view'); }}>{t('common.cancel')}</button>
          </div>
        </div>
      ) : <p class="q-text">{q.text}</p>}
      <p class="q-meta">
        <span class={`pill st-${q.status}`}>{t(`q.status.${q.status}`)}</span>
        <span>{toLabel(v, q.expertId)}</span>
        <span>{q.name ?? t('q.anon')}</span>
        <span>{hhmm(q.createdAt)}</span>
        {q.source === 'manual' ? <span class="pill">{t('q.manual')}</span> : null}
        {q.originalText ? <span class="pill" title={q.originalText}>{t('q.edited')}</span> : null}
        {q.flagged ? <span class="pill warn">{t('q.flagged')}</span> : null}
        {inQueue ? <span class="pill ok">{t('q.inQueue')}</span> : null}
      </p>
      {dupParent ? <p class="q-hint">{t('q.dupOf')} „{dupParent.text}”</p> : null}
      {parent && q.status === 'new' && mode === 'view' ? (
        <p class="q-hint">
          {t('q.similar')} „{parent.text}”
          <button class="btn sm" disabled={off} onClick={() => staff.run('q.duplicate', { id: q.id, of: parent.id })}>{t('q.markDup')}</button>
        </p>
      ) : null}
      {mode === 'dup' ? (
        <div class="row wrap q-dup">
          <select value={dupOf} onChange={(e) => setDupOf((e.target as HTMLSelectElement).value)}>
            <option value="">{t('q.dup.choose')}</option>
            {candidates.map((c) => <option value={c.id}>{c.text.slice(0, 90)}</option>)}
          </select>
          <button class="btn primary" disabled={off || !dupOf} onClick={async () => { if (await staff.run('q.duplicate', { id: q.id, of: dupOf })) setMode('view'); }}>{t('q.markDup')}</button>
          <button class="btn" onClick={() => setMode('view')}>{t('common.cancel')}</button>
        </div>
      ) : null}
      {mode === 'view' ? (
        <div class="q-actions">
          {q.status === 'new' || q.status === 'hidden' || q.status === 'duplicate'
            ? <button class="btn primary" disabled={off} onClick={() => staff.run('q.approve', { id: q.id })}>{t('q.approve')}</button> : null}
          {canShow && q.status !== 'on_screen'
            ? <button class="btn accent" disabled={off} onClick={() => staff.run('q.focus', { id: q.id })}>{t('q.show')}</button> : null}
          {q.status === 'on_screen'
            ? <button class="btn" disabled={off} onClick={() => staff.run('q.unfocus')}>{t('q.unshow')}</button> : null}
          {(q.status === 'approved' || q.status === 'on_screen') && !inQueue
            ? <button class="btn" disabled={off} onClick={() => staff.run('queue.set', { ids: [...v.queue, q.id] })}>{t('q.toQueue')}</button> : null}
          {q.status === 'approved' || q.status === 'on_screen'
            ? <button class="btn" disabled={off} onClick={() => staff.run('q.answered', { id: q.id })}>{t('q.answered')}</button> : null}
          {q.status !== 'hidden'
            ? <button class="btn" disabled={off} onClick={() => staff.run('q.hide', { id: q.id })}>{t('q.hide')}</button> : null}
          {q.status !== 'duplicate'
            ? <button class="btn" onClick={() => setMode('dup')}>{t('q.dup')}</button> : null}
          {q.status === 'answered' || q.status === 'hidden' || q.status === 'duplicate'
            ? <button class="btn" disabled={off} onClick={() => staff.run('q.restore', { id: q.id })}>{t('q.restore')}</button> : null}
          <button class="btn" onClick={() => { setText(q.text); setMode('edit'); }}>{t('q.edit')}</button>
        </div>
      ) : null}
    </article>
  );
}

function Queue({ staff }: { staff: Staff }) {
  const v = staff.view!;
  const [drag, setDrag] = useState<string | null>(null);
  const items = v.queue.map((id) => v.questions.find((q) => q.id === id)).filter(Boolean) as Question[];
  const off = !staff.online;
  const move = (id: string, to: number) => {
    const ids = v.queue.filter((x) => x !== id);
    ids.splice(Math.max(0, Math.min(ids.length, to)), 0, id);
    staff.run('queue.set', { ids });
  };
  return (
    <section class="queue">
      <div class="row wrap">
        <h3>{t('queue.title')} <b>{items.length}</b></h3>
        <button class="btn" disabled={off || !items.length} onClick={() => staff.run('q.step', { dir: -1 })}>{t('queue.prev')}</button>
        <button class="btn primary" disabled={off || !items.length} onClick={() => staff.run('q.step', { dir: 1 })}>{t('queue.next')}</button>
        <button class="btn" disabled={off || !v.sceneParams.questionId} onClick={() => staff.run('q.answered', { id: v.sceneParams.questionId })}>{t('queue.answered')}</button>
      </div>
      {items.length === 0 ? <p class="empty">{t('queue.empty')}</p> : null}
      <ol>
        {items.map((q, i) => (
          <li key={q.id} draggable class={`${q.status === 'on_screen' ? 'live' : ''} ${drag === q.id ? 'dragging' : ''}`}
            onDragStart={(e) => { setDrag(q.id); e.dataTransfer?.setData('text/plain', q.id); }}
            onDragEnd={() => setDrag(null)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); if (drag && drag !== q.id) move(drag, i); setDrag(null); }}>
            <span class="grip" aria-hidden="true">⋮⋮</span>
            <span class="queue-text">{q.text}<small>{toLabel(v, q.expertId)}{q.name ? ` · ${q.name}` : ''}</small></span>
            <span class="queue-btns">
              <button class="btn sm" disabled={off || i === 0} aria-label={t('queue.up')} onClick={() => move(q.id, i - 1)}>↑</button>
              <button class="btn sm" disabled={off || i === items.length - 1} aria-label={t('queue.down')} onClick={() => move(q.id, i + 1)}>↓</button>
              <button class="btn sm accent" disabled={off || q.status === 'on_screen'} onClick={() => staff.run('q.focus', { id: q.id })}>{q.status === 'on_screen' ? t('queue.live') : t('q.show')}</button>
              <button class="btn sm" disabled={off} aria-label={t('queue.remove')} onClick={() => staff.run('queue.set', { ids: v.queue.filter((x) => x !== q.id) })}>✕</button>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function AddForm({ staff, onDone }: { staff: Staff; onDone: () => void }) {
  const v = staff.view!;
  const [text, setText] = useState('');
  const [name, setName] = useState('');
  const [expert, setExpert] = useState('');
  return (
    <form class="q-add" onSubmit={async (e) => { e.preventDefault(); if (await staff.run('q.add', { text, name, expertId: expert || undefined }, t('q.added'))) onDone(); }}>
      <textarea rows={2} maxLength={config.limits.questionMax} value={text} placeholder={t('q.add.placeholder')} onInput={(e) => setText((e.target as HTMLTextAreaElement).value)} />
      <div class="row wrap">
        <input type="text" maxLength={config.limits.nameMax} value={name} placeholder={t('q.add.name')} onInput={(e) => setName((e.target as HTMLInputElement).value)} />
        <select value={expert} onChange={(e) => setExpert((e.target as HTMLSelectElement).value)}>
          <option value="">{t('q.toAll')}</option>
          {v.experts.map((x) => <option value={x.id}>{x.name}</option>)}
        </select>
        <button class="btn primary" type="submit" disabled={!staff.online || text.trim().length < 3}>{t('q.add.save')}</button>
        <button class="btn" type="button" onClick={onDone}>{t('common.cancel')}</button>
      </div>
    </form>
  );
}
