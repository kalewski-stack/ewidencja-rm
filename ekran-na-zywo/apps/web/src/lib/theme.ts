// Motyw: cały wygląd steruje content/theme.json. Komponenty używają wyłącznie zmiennych CSS.
import theme from '@content/theme.json';
import config from '@content/config.json';

export { theme, config };

type Dict = Record<string, unknown>;
const kebab = (s: string) => s.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase());

function colorVars(c: Dict): string {
  let out = '';
  for (const [k, v] of Object.entries(c)) {
    if (Array.isArray(v)) v.forEach((x, i) => { out += `--${kebab(k)}-${i + 1}:${x};`; });
    else out += `--${kebab(k)}:${v};`;
  }
  return out;
}

export function applyTheme(): void {
  const t = theme as any;
  let css = '';
  for (const f of t.fonts.files as { family: string; file: string; weight?: string; style?: string }[]) {
    css += `@font-face{font-family:"${f.family}";src:url("/theme/${f.file}");font-weight:${f.weight ?? '400'};font-style:${f.style ?? 'normal'};font-display:swap;}`;
  }
  css += `:root{${colorVars(t.colors)}`;
  css += `--font-head:${t.fonts.heading};--font-body:${t.fonts.body};--font-num:${t.fonts.number};`;
  for (const [k, v] of Object.entries(t.type)) css += `--fs-${k}:${v}px;`;
  for (const [k, v] of Object.entries(t.radius)) css += `--r-${k}:${v}px;`;
  css += `--shadow:${t.shadow};--t-fast:${t.motion.fast}ms;--t-base:${t.motion.base}ms;--t-slow:${t.motion.slow}ms;--ease:${t.motion.ease};}`;
  // Telefon szanuje jasny tryb systemu. Ekran i panele są zawsze ciemne.
  css += `@media (prefers-color-scheme: light){body.phone{${colorVars(t.phoneLight)}}}`;
  if (t.background?.type === 'image' && t.background.file) css += `:root{--bg-image:url("/theme/${t.background.file}");}`;
  const el = document.createElement('style');
  el.textContent = css;
  document.head.appendChild(el);
}

export const isDev = import.meta.env.DEV || import.meta.env.MODE === 'development' || new URLSearchParams(location.search).has('dev');
export const reducedMotion = () => document.body.classList.contains('noanim') || new URLSearchParams(location.search).has('noanim');
