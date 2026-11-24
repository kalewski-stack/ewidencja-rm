// Infografiki: jedna liczba lub jeden wykres na planszę. Źródło i rok zawsze widoczne.
import { useEffect, useMemo, useState } from 'preact/hooks';
import { scaleLinear } from 'd3-scale';
import { line as d3line, curveMonotoneX } from 'd3-shape';
import { geoAzimuthalEqualArea, geoPath } from 'd3-geo';
import { feature } from 'topojson-client';
import type { Slide, SlideBar, SlideBigNumber, SlideCompare, SlideLine, SlideMap } from '@shared/types.ts';
import { decimalsOf, formatNumber, slideHasData } from '@shared/util.ts';
import { AnimNumber } from '../ui/common.tsx';
import { t } from '../lib/i18n.ts';
import { theme } from '../lib/theme.ts';

export function SlideView({ slide, showPlaceholder }: { slide: Slide; showPlaceholder: boolean }) {
  const ok = slideHasData(slide);
  return (
    <div class={`slide slide-${slide.type}`}>
      <h2 class="slide-title">{slide.title}</h2>
      <div class="slide-body">
        {!ok ? (showPlaceholder ? <div class="placeholder"><b>PLACEHOLDER</b><span>{slide.notes}</span></div> : null)
          : slide.type === 'bigNumber' ? <BigNumber s={slide} />
          : slide.type === 'bar' ? <Bar s={slide} />
          : slide.type === 'line' ? <Line s={slide} />
          : slide.type === 'compare' ? <Compare s={slide} />
          : <EuropeMap s={slide} />}
      </div>
      <div class="slide-source">
        {slide.source ? t('slide.source', { source: slide.source, year: String(slide.year ?? '') }) : (showPlaceholder ? t('slide.noSource') : '')}
      </div>
    </div>
  );
}

function BigNumber({ s }: { s: SlideBigNumber }) {
  const d = s.decimals ?? decimalsOf(s.value!);
  return (
    <div class="big">
      <div class="big-value"><AnimNumber value={s.value!} from={0} decimals={d} duration={1800} />{s.unit ? <span class="unit">{s.unit}</span> : null}</div>
      {s.caption ? <p class="big-caption">{s.caption}</p> : null}
    </div>
  );
}

function Compare({ s }: { s: SlideCompare }) {
  const side = (c: SlideCompare['left'], cls: string) => (
    <div class={`cmp ${cls}`}>
      <div class="cmp-value"><AnimNumber value={c.value!} from={0} decimals={decimalsOf(c.value!)} duration={1600} />{c.unit ?? s.unit ? <span class="unit">{c.unit ?? s.unit}</span> : null}</div>
      <div class="cmp-label">{c.label}</div>
    </div>
  );
  return <div class="compare">{side(s.left, 'a')}{side(s.right, 'b')}{s.caption ? <p class="big-caption">{s.caption}</p> : null}</div>;
}

function Bar({ s }: { s: SlideBar }) {
  const max = Math.max(...s.categories.map((c) => c.value), 0) || 1;
  const x = scaleLinear().domain([0, max]).range([0, 100]);
  const [go, setGo] = useState(false);
  useEffect(() => { const r = requestAnimationFrame(() => requestAnimationFrame(() => setGo(true))); return () => cancelAnimationFrame(r); }, []);
  const dense = s.categories.length > 6;
  return (
    <div class={`bars ${dense ? 'dense' : ''}`}>
      {s.categories.map((c, i) => (
        <div class="bar-row">
          <div class="bar-label">{c.label}</div>
          <div class="bar-track">
            <div class="bar-fill" style={{ width: `${x(c.value)}%`, transform: go ? 'scaleX(1)' : 'scaleX(0)', transitionDelay: `${i * 120}ms` }} />
          </div>
          <div class="bar-value"><AnimNumber value={c.value} from={0} decimals={decimalsOf(c.value)} duration={1200 + i * 120} />{s.unit ? <span class="unit-s">{s.unit}</span> : null}</div>
        </div>
      ))}
    </div>
  );
}

function Line({ s }: { s: SlideLine }) {
  const W = 1728, H = 620, m = { l: 130, r: 300, t: 64, b: 70 };
  const all = s.series.flatMap((r) => r.values);
  const lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo || 1) * 0.1;
  const y = scaleLinear().domain([Math.min(lo - pad, lo >= 0 ? Math.max(0, lo - pad) : lo - pad), hi + pad]).nice(4).range([H - m.b, m.t]);
  const x = scaleLinear().domain([0, s.x.length - 1]).range([m.l, W - m.r]);
  const path = d3line<number>().x((_, i) => x(i)).y((v) => y(v)).curve(curveMonotoneX);
  const every = Math.ceil(s.x.length / 8);
  const colors = (theme as any).colors.series as string[];
  return (
    <svg class="linechart" viewBox={`0 0 ${W} ${H}`} width={W} height={H}>
      {y.ticks(4).map((v) => (
        <g>
          <line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} class="grid" />
          <text x={m.l - 18} y={y(v)} class="tick" text-anchor="end" dominant-baseline="middle">{formatNumber(v, decimalsOf(v))}</text>
        </g>
      ))}
      {s.x.map((lab, i) => (i % every === 0 || i === s.x.length - 1)
        ? <text x={x(i)} y={H - m.b + 44} class="tick" text-anchor="middle">{String(lab)}</text> : null)}
      {s.series.map((r, i) => (
        <g>
          <path d={path(r.values) ?? ''} pathLength={1} class="series" style={{ stroke: colors[i % colors.length], animationDelay: `${i * 350}ms` }} />
          <text x={W - m.r + 20} y={y(r.values[r.values.length - 1])} class="series-label" dominant-baseline="middle"
            style={{ fill: colors[i % colors.length], animationDelay: `${1400 + i * 350}ms` }}>{r.name}</text>
        </g>
      ))}
      {s.unit ? <text x={m.l - 18} y={m.t - 34} class="tick" text-anchor="end">{s.unit}</text> : null}
    </svg>
  );
}

// Kody ISO numeryczne (Natural Earth, pakiet world-atlas) na alpha-2. Eurostat: EL = GR, UK = GB.
const NUM2A: Record<string, string> = {
  '008': 'AL', '020': 'AD', '040': 'AT', '112': 'BY', '056': 'BE', '070': 'BA', '100': 'BG', '191': 'HR', '196': 'CY', '203': 'CZ',
  '208': 'DK', '233': 'EE', '246': 'FI', '250': 'FR', '276': 'DE', '300': 'GR', '348': 'HU', '352': 'IS', '372': 'IE', '380': 'IT',
  '428': 'LV', '438': 'LI', '440': 'LT', '442': 'LU', '470': 'MT', '498': 'MD', '492': 'MC', '499': 'ME', '528': 'NL', '807': 'MK',
  '578': 'NO', '616': 'PL', '620': 'PT', '642': 'RO', '643': 'RU', '674': 'SM', '688': 'RS', '703': 'SK', '705': 'SI', '724': 'ES',
  '752': 'SE', '756': 'CH', '792': 'TR', '804': 'UA', '826': 'GB',
};
const ALIAS: Record<string, string> = { EL: 'GR', UK: 'GB' };

function EuropeMap({ s }: { s: SlideMap }) {
  const [geo, setGeo] = useState<any[] | null>(null);
  useEffect(() => {
    let alive = true;
    // Mapa Natural Earth jest w paczce aplikacji (bez zewnętrznych CDN), ładowana tylko gdy potrzebna.
    import('world-atlas/countries-50m.json').then((m) => {
      const topo: any = (m as any).default ?? m;
      const fc: any = feature(topo, topo.objects.countries);
      if (alive) setGeo(fc.features.map((f: any) => ({ ...f, a2: f.properties?.name === 'Kosovo' ? 'XK' : NUM2A[String(f.id).padStart(3, '0')] })).filter((f: any) => f.a2));
    });
    return () => { alive = false; };
  }, []);
  const W = 1180, H = 640;
  const values = useMemo(() => Object.fromEntries(Object.entries(s.values).map(([k, v]) => [ALIAS[k] ?? k, v])), [s.values]);
  const nums = Object.values(values);
  const lo = Math.min(...nums), hi = Math.max(...nums);
  const stops = (theme as any).colors.mapScale as string[];
  const color = scaleLinear<string>().domain(stops.map((_, i) => lo + ((hi - lo || 1) * i) / (stops.length - 1))).range(stops).clamp(true);
  const order = useMemo(() => Object.keys(values).sort((a, b) => values[a] - values[b]), [values]);
  const [go, setGo] = useState(false);
  useEffect(() => { if (!geo) return; const id = setTimeout(() => setGo(true), 80); return () => clearTimeout(id); }, [geo]);
  const proj = useMemo(() => geoAzimuthalEqualArea().rotate([-12, -53]).fitExtent([[0, 0], [W, H]], {
    type: 'MultiPoint', coordinates: [[-11, 35], [33, 35], [-22, 64], [38, 69], [10, 71], [30, 36]],
  } as any), []);
  const path = geoPath(proj);
  const d = decimalsOf(hi);
  return (
    <div class="map">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H}>
        {(geo ?? []).map((f) => {
          const v = values[f.a2];
          const rank = order.indexOf(f.a2);
          return <path d={path(f) ?? ''} class="country"
            style={{ fill: v !== undefined && go ? color(v) : undefined, transitionDelay: v !== undefined ? `${rank * 90}ms` : '0ms' }} />;
        })}
      </svg>
      <div class="legend">
        <div class="legend-bar" style={{ background: `linear-gradient(to top, ${stops.join(',')})` }} />
        <div class="legend-ticks"><span>{formatNumber(hi, d)}{s.unit ? ` ${s.unit}` : ''}</span><span>{formatNumber(lo, d)}{s.unit ? ` ${s.unit}` : ''}</span></div>
        {s.caption ? <p class="legend-caption">{s.caption}</p> : null}
      </div>
    </div>
  );
}
