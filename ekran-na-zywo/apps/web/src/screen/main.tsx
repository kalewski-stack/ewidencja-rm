// Ekran główny: płótno 1920x1080 skalowane do okna, tylko odczyt. Utrata połączenia nie zmienia sceny.
import { render } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import type { SceneId, ScreenView } from '@shared/types.ts';
import { SCENES } from '@shared/types.ts';
import { applyTheme, config, isDev, theme } from '../lib/theme.ts';
import { connect, takeToken } from '../lib/conn.ts';
import { t } from '../lib/i18n.ts';
import { Logos } from '../ui/common.tsx';
import { CornerBar, Idle, Infographics, PollScene, QrScene, QuestionFocus, QuestionsCollect, Recommendations } from './scenes.tsx';
import '../themes/base.css';
import '../themes/screen.css';

applyTheme();

const params = new URLSearchParams(location.search);
const preview = params.has('preview');
const forcedScene = SCENES.find((s) => s === params.get('scene')) ?? null;
const forcedSlide = params.has('slide') ? Number(params.get('slide')) : undefined;
if (params.has('noanim')) document.body.classList.add('noanim');
const key = takeToken('k', preview ? 'screenKeyPreview' : 'screenKey', !preview);

const CACHE_KEY = 'screen:lastView';
function cached(): ScreenView | null {
  try { return JSON.parse(localStorage.getItem(CACHE_KEY) ?? 'null'); } catch { return null; }
}

// Sceny, które mają gotowy obraz PNG w /static/ (generuje scripts/export-static.ts).
const STATIC_IMG: Partial<Record<SceneId, string>> = { idle: 'idle', qr: 'qr', questions_collect: 'questions_collect' };

function useScale() {
  const [s, setS] = useState(1);
  useEffect(() => {
    const fit = () => setS(Math.min(window.innerWidth / 1920, window.innerHeight / 1080));
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  return s;
}

function App() {
  const [view, setView] = useState<ScreenView | null>(cached);
  const [auth, setAuth] = useState(true);
  const [localScene, setLocalScene] = useState<SceneId | null>(null);
  const [localStatic, setLocalStatic] = useState(false);
  const slideRef = useRef(0);
  const sceneRef = useRef<SceneId | null>(null);
  const scale = useScale();

  useEffect(() => {
    const conn = connect({
      role: 'screen', token: key, preview, pingMs: 5000,
      onView: (v) => {
        const sv = v as ScreenView;
        // Operator zmienił scenę: lokalne, awaryjne nadpisanie przestaje obowiązywać.
        if (sceneRef.current && sceneRef.current !== sv.scene) setLocalScene(null);
        sceneRef.current = sv.scene;
        setView(sv);
        if (!preview) try { localStorage.setItem(CACHE_KEY, JSON.stringify(sv)); } catch { /* pełna pamięć */ }
      },
      onStatus: (s) => { if (s === 'unauthorized') setAuth(false); },
    });
    conn.setPingData(() => ({ slide: slideRef.current }));
    return () => conn.close();
  }, []);

  // Sterowanie awaryjne z klawiatury komputera przy ekranie (działa bez sieci):
  // Shift + strzałki zmieniają scenę lokalnie, Shift + S przełącza obrazy statyczne, Shift + B wygasza.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.shiftKey || preview) return;
      const cur = localScene ?? view?.scene ?? 'idle';
      const i = SCENES.indexOf(cur);
      if (e.key === 'ArrowRight') setLocalScene(SCENES[(i + 1) % SCENES.length]);
      else if (e.key === 'ArrowLeft') setLocalScene(SCENES[(i - 1 + SCENES.length) % SCENES.length]);
      else if (e.key.toLowerCase() === 's') setLocalStatic((x) => !x);
      else if (e.key.toLowerCase() === 'b') setLocalScene(cur === 'blackout' ? 'idle' : 'blackout');
      else if (e.key === 'Escape') { setLocalScene(null); setLocalStatic(false); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [localScene, view?.scene]);

  useEffect(() => {
    if (preview || !('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js', { scope: '/screen' }).catch(() => { /* bez SW też działa */ });
  }, []);

  const isStatic = !!view && (view.fallbackStatic || localStatic);
  useEffect(() => { document.body.classList.toggle('noanim', isStatic || params.has('noanim')); }, [isStatic]);

  if (!auth) return <div class="gate">{t('screen.unauthorized')}</div>;
  if (!view) return <div class="gate">{key ? t('screen.connecting') : t('screen.unauthorized')}</div>;

  const scene = forcedScene ?? localScene ?? view.scene;
  const bare = scene === 'blackout';
  return (
    <div class="viewport">
      <div class="stage" style={{ transform: `translate(-50%, -50%) scale(${scale})` }} data-scene={scene}>
        {bare ? null : (
          <>
            {config.flags.backgroundLayer ? <div class="bg-layer" /> : null}
            <div class="safe">
              <div class="scene-slot" key={scene}>
                <SceneBody scene={scene} v={view} isStatic={isStatic} onIndex={(i) => { slideRef.current = i; }} />
              </div>
              <footer class={`bar ${scene === 'recommendations' || scene === 'summary' ? 'compact' : ''}`}>
                <Logos />
                {scene === 'infographics' || scene === 'idle' ? <CornerBar v={view} /> : null}
              </footer>
            </div>
            {(theme as any).placeholder && isDev ? <div class="placeholder-tag">PLACEHOLDER</div> : null}
          </>
        )}
      </div>
    </div>
  );
}

function SceneBody({ scene, v, isStatic, onIndex }: { scene: SceneId; v: ScreenView; isStatic: boolean; onIndex: (i: number) => void }) {
  const [imgFailed, setImgFailed] = useState(false);
  if (isStatic && !imgFailed && STATIC_IMG[scene]) {
    // Tryb statyczny: gotowy obraz zamiast żywej sceny. Brak pliku = wracamy do sceny bez animacji.
    return <img class="static-img" src={`/static/${STATIC_IMG[scene]}.png`} alt="" onError={() => setImgFailed(true)} />;
  }
  switch (scene) {
    case 'idle': return <Idle />;
    case 'infographics': return <Infographics v={v} onIndex={onIndex} fixed={forcedSlide} />;
    case 'qr': return <QrScene v={v} />;
    case 'poll_live': return <PollScene v={v} />;
    case 'poll_result': return <PollScene v={v} result />;
    case 'questions_collect': return <QuestionsCollect v={v} />;
    case 'question_focus': return <QuestionFocus v={v} />;
    case 'recommendations': return <Recommendations v={v} />;
    case 'summary': return <Recommendations v={v} summary />;
    default: return null;
  }
}

render(<App />, document.getElementById('app')!);
