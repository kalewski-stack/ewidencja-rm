// Edytor "5 rekomendacji": autozapis, wersjonowanie per slot (moderator i operator nie nadpiszą sobie pracy).
import { useEffect, useRef, useState } from 'preact/hooks';
import { REC_TEXT_MAX, REC_TITLE_MAX } from '@shared/types.ts';
import { t } from '../lib/i18n.ts';
import { download } from '../lib/zip.ts';
import { recsBoard } from '../lib/board.ts';
import { recsDocx, recsMarkdown, type Staff } from './core.tsx';

interface Draft { title: string; text: string; baseRev: number; dirty: boolean; saving: boolean }

export function Recs({ staff }: { staff: Staff }) {
  const v = staff.view!;
  const [drafts, setDrafts] = useState<Draft[]>(() => v.recommendations.map((r) => ({ title: r.title, text: r.text, baseRev: r.rev, dirty: false, saving: false })));
  const ref = useRef(drafts);
  ref.current = drafts;
  const timers = useRef<Record<number, number>>({});

  // Zmiana z serwera (np. od operatora): przyjmujemy ją w slotach, których sami właśnie nie edytujemy.
  useEffect(() => {
    setDrafts((ds) => ds.map((d, i) => {
      const r = v.recommendations[i];
      return !d.dirty && !d.saving && r.rev !== d.baseRev ? { ...d, title: r.title, text: r.text, baseRev: r.rev } : d;
    }));
  }, [v.recommendations.map((r) => r.rev).join(',')]);

  const save = async (i: number) => {
    const d = ref.current[i];
    if (!d.dirty) return;
    setDrafts((ds) => ds.map((x, j) => (j === i ? { ...x, saving: true } : x)));
    const sent = { title: d.title, text: d.text };
    const res = await staff.run('rec.set', { index: i, ...sent, baseRev: d.baseRev });
    setDrafts((ds) => ds.map((x, j) => {
      if (j !== i) return x;
      if (res?.rev !== undefined) {
        const changedSince = x.title !== sent.title || x.text !== sent.text;
        if (changedSince) timers.current[i] = window.setTimeout(() => save(i), 400);
        return { ...x, baseRev: res.rev, saving: false, dirty: changedSince };
      }
      // Konflikt lub brak sieci: przy konflikcie bierzemy wersję z serwera, przy braku sieci zostawiamy tekst do ponowienia.
      const srv = staff.view?.recommendations[i];
      if (srv && srv.rev !== x.baseRev) return { title: srv.title, text: srv.text, baseRev: srv.rev, dirty: false, saving: false };
      return { ...x, saving: false };
    }));
  };

  const edit = (i: number, patch: Partial<Draft>) => {
    setDrafts((ds) => ds.map((x, j) => (j === i ? { ...x, ...patch, dirty: true } : x)));
    clearTimeout(timers.current[i]);
    timers.current[i] = window.setTimeout(() => save(i), 500);
  };

  // Po powrocie połączenia dosyłamy to, co czekało.
  useEffect(() => { if (staff.online) ref.current.forEach((d, i) => { if (d.dirty && !d.saving) save(i); }); }, [staff.online]);

  const shown = v.sceneParams.revealCount ?? 0;
  const pending = drafts.some((d) => d.dirty || d.saving);
  const png = async (w: number, h: number) => download(await recsBoard(v.recommendations, w, h), `rekomendacje-${w}x${h}.png`);

  return (
    <div class="recs-ed">
      <div class="row wrap">
        <b>{t('recs.reveal', { n: shown })}</b>
        <button class="btn" disabled={!staff.online || shown <= 0} onClick={() => staff.run('rec.reveal', { count: 0 })}>{t('recs.hideAll')}</button>
        <button class="btn primary big" disabled={!staff.online || shown >= 5} onClick={() => staff.run('rec.reveal', { count: shown + 1 })}>{t('recs.next')}</button>
        <button class="btn" disabled={!staff.online || shown >= 5} onClick={() => staff.run('rec.reveal', { count: 5 })}>{t('recs.showAll')}</button>
        <span class={`save-state ${pending ? 'pending' : ''}`}>{pending ? t('recs.saving') : t('recs.saved')}</span>
      </div>
      {drafts.map((d, i) => (
        <div class={`rec-slot ${i < shown ? 'shown' : ''}`}>
          <div class="rec-num">{i + 1}{i < shown ? <small>{t('recs.onScreen')}</small> : null}</div>
          <div class="rec-fields">
            <label>
              <span>{t('recs.title')} <i class={d.title.length >= REC_TITLE_MAX ? 'bad' : ''}>{d.title.length}/{REC_TITLE_MAX}</i></span>
              <input type="text" maxLength={REC_TITLE_MAX} value={d.title} onInput={(e) => edit(i, { title: (e.target as HTMLInputElement).value })} onBlur={() => save(i)} />
            </label>
            <label>
              <span>{t('recs.text')} <i class={d.text.length >= REC_TEXT_MAX ? 'bad' : ''}>{d.text.length}/{REC_TEXT_MAX}</i></span>
              <textarea rows={2} maxLength={REC_TEXT_MAX} value={d.text} onInput={(e) => edit(i, { text: (e.target as HTMLTextAreaElement).value })} onBlur={() => save(i)} />
            </label>
          </div>
        </div>
      ))}
      <div class="row wrap">
        <b>{t('recs.export')}</b>
        <button class="btn" onClick={() => png(1920, 1080)}>PNG 1920×1080</button>
        <button class="btn" onClick={() => png(1080, 1350)}>PNG 1080×1350</button>
        <button class="btn" onClick={() => download(new Blob([recsMarkdown(v)], { type: 'text/markdown' }), 'recommendations.md')}>.md</button>
        <button class="btn" onClick={() => download(recsDocx(v), 'rekomendacje.docx')}>.docx</button>
      </div>
    </div>
  );
}
