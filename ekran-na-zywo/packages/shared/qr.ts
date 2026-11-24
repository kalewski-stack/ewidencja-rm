// Kod QR jako SVG. Korekcja M, quiet zone 4 moduły (rozdział 13 specyfikacji).
import qrcode from 'qrcode-generator';

export function qrMatrix(text: string): boolean[][] {
  const qr = qrcode(0, 'M');
  qr.addData(text);
  qr.make();
  const n = qr.getModuleCount();
  return Array.from({ length: n }, (_, r) => Array.from({ length: n }, (_, c) => qr.isDark(r, c)));
}

export function qrPath(text: string, quiet = 4): { d: string; size: number } {
  const m = qrMatrix(text);
  let d = '';
  m.forEach((row, r) => row.forEach((dark, c) => { if (dark) d += `M${c + quiet} ${r + quiet}h1v1h-1z`; }));
  return { d, size: m.length + quiet * 2 };
}

/** Samodzielny plik SVG: zawsze czarne moduły na białym tle (najpewniejsze skanowanie). */
export function qrSvg(text: string, quiet = 4): string {
  const { d, size } = qrPath(text, quiet);
  return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="1000" height="1000" shape-rendering="crispEdges"><rect width="${size}" height="${size}" fill="#fff"/><path d="${d}" fill="#000"/></svg>\n`;
}
