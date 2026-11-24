// Plansze PNG rysowane na canvasie w przeglądarce operatora (wynik ankiety, rekomendacje).
// Kolory i fonty z content/theme.json, więc plansza zmienia się razem z motywem.
import theme from '@content/theme.json';
import config from '@content/config.json';
import { percents, winners, sum } from '@shared/util.ts';
import { t } from './i18n.ts';

const C = (theme as any).colors;
const F = (theme as any).fonts;

function wrap(ctx: CanvasRenderingContext2D, text: string, maxW: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let cur = '';
  for (const w of words) {
    const test = cur ? `${cur} ${w}` : w;
    if (ctx.measureText(test).width <= maxW || !cur) cur = test;
    else { lines.push(cur); cur = w; }
  }
  if (cur) lines.push(cur);
  return lines;
}

function drawLines(ctx: CanvasRenderingContext2D, lines: string[], x: number, y: number, lh: number): number {
  lines.forEach((l, i) => ctx.fillText(l, x, y + i * lh));
  return y + lines.length * lh;
}

function rr(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  ctx.beginPath();
  ctx.roundRect(x, y, Math.max(0, w), h, r);
  ctx.fill();
}

function loadImg(src: string): Promise<HTMLImageElement | null> {
  return new Promise((ok) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => ok(null); i.src = src; });
}

async function base(w: number, h: number): Promise<{ cv: HTMLCanvasElement; ctx: CanvasRenderingContext2D; mx: number; my: number; footY: number }> {
  try { await document.fonts.ready; } catch { /* fonty systemowe */ }
  const cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  const ctx = cv.getContext('2d')!;
  ctx.fillStyle = C.bg; ctx.fillRect(0, 0, w, h);
  ctx.textBaseline = 'top';
  const mx = Math.round(w * 0.05), my = Math.round(h * 0.05);
  // Stopka: logotypy (jeśli są w motywie) i oznaczenie finansowania.
  const logoH = Math.round(w * 0.033);
  let footY = h - my;
  const logos = (theme as any).logos as Record<string, string | null>;
  const imgs = (await Promise.all(['wup', 'eures', 'ue'].map((k) => (logos[k] ? loadImg(`/theme/${logos[k]}`) : null)))).filter(Boolean) as HTMLImageElement[];
  const funding = (theme as any).fundingText as string;
  if (funding) {
    ctx.fillStyle = C.muted; ctx.font = `${Math.round(w * 0.0125)}px ${F.body}`;
    const lines = wrap(ctx, funding, w - 2 * mx);
    footY -= lines.length * Math.round(w * 0.016);
    drawLines(ctx, lines, mx, footY, Math.round(w * 0.016));
    footY -= 12;
  }
  if (imgs.length) {
    footY -= logoH;
    let x = mx;
    for (const im of imgs) { const iw = (im.width / im.height) * logoH; ctx.drawImage(im, x, footY, iw, logoH); x += iw + logoH * 0.75; }
    footY -= 16;
  }
  return { cv, ctx, mx, my, footY };
}

const toBlob = (cv: HTMLCanvasElement) => new Promise<Blob>((ok, fail) => cv.toBlob((b) => (b ? ok(b) : fail(new Error('png'))), 'image/png'));

export async function pollBoard(poll: { text: string; options: { id: string; label: string }[] }, tally: Record<string, number>): Promise<Blob> {
  const w = 1920, h = 1080;
  const { cv, ctx, mx, my, footY } = await base(w, h);
  const pct = percents(tally), win = winners(tally), total = sum(tally);
  ctx.fillStyle = C.text; ctx.font = `700 64px ${F.heading}`;
  let y = drawLines(ctx, wrap(ctx, poll.text, w - 2 * mx), mx, my, 74) + 40;
  const footer = 110;
  const rowH = Math.min(240, (footY - footer - y) / poll.options.length);
  const trackH = Math.min(112, rowH - 100);
  poll.options.forEach((o, i) => {
    const lose = win.length > 0 && !win.includes(o.id);
    ctx.globalAlpha = lose ? 0.5 : 1;
    ctx.fillStyle = C.text; ctx.font = `700 52px ${F.heading}`; ctx.textAlign = 'left';
    ctx.fillText(o.label, mx, y);
    ctx.fillStyle = C.muted; ctx.font = `36px ${F.body}`; ctx.textAlign = 'right';
    ctx.fillText(t('screen.poll.count', { n: tally[o.id] }), w - mx, y + 12);
    const ty = y + 76, tw = w - 2 * mx - 290;
    ctx.fillStyle = C.surface; rr(ctx, mx, ty, tw, trackH, 18);
    ctx.fillStyle = C.bars[i % C.bars.length]; rr(ctx, mx, ty, (tw * pct[o.id]) / 100, trackH, 18);
    ctx.fillStyle = C.text; ctx.font = `800 ${Math.min(120, trackH + 8)}px ${F.number}`;
    ctx.fillText(`${pct[o.id]}%`, w - mx, ty + (trackH - Math.min(120, trackH + 8)) / 2);
    ctx.globalAlpha = 1;
    y += rowH;
  });
  ctx.textAlign = 'left'; ctx.fillStyle = C.text; ctx.font = `48px ${F.body}`;
  ctx.fillText(`${t('screen.poll.final')}. ${t('screen.poll.total')} ${total}`, mx, footY - 76);
  ctx.fillStyle = C.muted; ctx.font = `28px ${F.body}`; ctx.textAlign = 'right';
  ctx.fillText(`${config.event.title}, ${config.event.date}`, w - mx, footY - 56);
  return toBlob(cv);
}

export async function recsBoard(recs: { title: string; text: string }[], w: number, h: number): Promise<Blob> {
  const { cv, ctx, mx, my, footY } = await base(w, h);
  const portrait = h > w;
  const k = portrait ? w / 1080 : w / 1920;
  const titleFs = Math.round((portrait ? 58 : 64) * k), recT = Math.round((portrait ? 38 : 44) * k), recX = Math.round((portrait ? 30 : 36) * k);
  const circle = Math.round((portrait ? 80 : 104) * k);
  ctx.fillStyle = C.text; ctx.font = `700 ${titleFs}px ${F.heading}`;
  let y = drawLines(ctx, wrap(ctx, t('screen.recs.title'), w - 2 * mx), mx, my, Math.round(titleFs * 1.15)) + Math.round(18 * k);
  ctx.fillStyle = C.muted; ctx.font = `${Math.round(28 * k)}px ${F.body}`;
  const sub = wrap(ctx, `${config.event.title}, ${config.event.subtitle}. ${config.event.place}, ${config.event.date}`, w - 2 * mx);
  y = drawLines(ctx, sub, mx, y, Math.round(36 * k)) + Math.round(24 * k);
  const rowH = (footY - y) / 5;
  const tx = mx + circle + Math.round(32 * k), tw = w - mx - tx;
  recs.slice(0, 5).forEach((r, i) => {
    const cy = y + i * rowH;
    ctx.font = `700 ${recT}px ${F.heading}`;
    const tl = wrap(ctx, r.title, tw);
    ctx.font = `${recX}px ${F.body}`;
    const xl = wrap(ctx, r.text, tw);
    const blockH = tl.length * recT * 1.14 + xl.length * recX * 1.22;
    const top = cy + Math.max(0, (rowH - Math.max(blockH, circle)) / 2);
    ctx.fillStyle = r.title || r.text ? C.accent1 : C.surface2;
    ctx.beginPath(); ctx.arc(mx + circle / 2, top + Math.max(blockH, circle) / 2, circle / 2, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = C.onAccent; ctx.font = `800 ${Math.round(circle * 0.6)}px ${F.number}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(String(i + 1), mx + circle / 2, top + Math.max(blockH, circle) / 2 + 2);
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    let ty = top + Math.max(0, (circle - blockH) / 2);
    ctx.fillStyle = C.text; ctx.font = `700 ${recT}px ${F.heading}`;
    ty = drawLines(ctx, tl, tx, ty, recT * 1.14);
    ctx.fillStyle = C.muted; ctx.font = `${recX}px ${F.body}`;
    drawLines(ctx, xl, tx, ty + 2, recX * 1.22);
  });
  return toBlob(cv);
}
