// Wspólne klocki: logotypy, kod QR, animowana liczba.
import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import { qrPath } from '@shared/qr.ts';
import { formatNumber } from '@shared/util.ts';
import { theme, reducedMotion } from '../lib/theme.ts';
import { t } from '../lib/i18n.ts';

const SLOTS = ['wup', 'eures', 'ue'] as const;

/** Pasek logotypów. Dopóki brak plików w content/assets, pokazujemy szare prostokąty z nazwą slotu. */
export function Logos({ withFunding = true }: { withFunding?: boolean }) {
  const logos = (theme as any).logos as Record<string, string | null>;
  return (
    <div class="logos">
      <div class="logos-row">
        {SLOTS.map((s) => logos[s]
          ? <img class="logo" src={`/theme/${logos[s]}`} alt={t(`logo.${s}`)} />
          : <div class="logo logo-empty" aria-label={t(`logo.${s}`)}>logo.{s}</div>)}
      </div>
      {withFunding && (theme as any).fundingText ? <div class="funding">{(theme as any).fundingText}</div> : null}
    </div>
  );
}

/** Kod QR: zawsze czarny na białym polu, z quiet zone 4 moduły. */
export function Qr({ url, size }: { url: string; size: number }) {
  const { d, size: n } = useMemo(() => qrPath(url, 4), [url]);
  return (
    <svg class="qr" width={size} height={size} viewBox={`0 0 ${n} ${n}`} shape-rendering="crispEdges" role="img" aria-label={t('qr.alt')}>
      <rect width={n} height={n} fill="#fff" />
      <path d={d} fill="#000" />
    </svg>
  );
}

export function shortUrl(url: string): string {
  return url.replace(/^https?:\/\//, '').replace(/\/$/, '');
}

/** Liczba, która "nabija się" do wartości (ease-out). */
export function AnimNumber({ value, decimals = 0, duration = 600, from }: { value: number; decimals?: number; duration?: number; from?: number }) {
  const [shown, setShown] = useState(from ?? value);
  const cur = useRef(from ?? value);
  useEffect(() => {
    if (reducedMotion() || duration <= 0) { cur.current = value; setShown(value); return; }
    const start = cur.current, t0 = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const p = Math.min(1, (now - t0) / duration);
      const v = start + (value - start) * (1 - Math.pow(1 - p, 3));
      cur.current = v;
      setShown(v);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  const pow = Math.pow(10, decimals);
  return <>{formatNumber(Math.round(shown * pow) / pow, decimals)}</>;
}
