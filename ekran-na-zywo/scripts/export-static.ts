// Renderuje plansze awaryjne PNG 1920x1080 (sceny i slajdy) oraz PDF do apps/web/public/static/.
// Wymaga działającego serwera (npm run dev albo adres produkcyjny w BASE) i klucza ekranu.
// Uwaga: kod QR na planszach bierze adres z PUBLIC_URL serwera. Eksportuj po ustawieniu docelowego adresu.
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { BASE, OPS_TOKEN, SCREEN_KEY, client, playwright, root } from './lib.ts';

const out = resolve(root, 'apps/web/public/static');
rmSync(out, { recursive: true, force: true });
mkdirSync(resolve(out, 'slides'), { recursive: true });

const ops = await client('ops', OPS_TOKEN);
const slides = ops.view.slides as { title: string }[];
ops.close();

const { chromium } = playwright();
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
const shot = async (query: string, file: string) => {
  await page.goto(`${BASE}/screen?preview=1&noanim=1&${query}#k=${encodeURIComponent(SCREEN_KEY)}`);
  await page.waitForSelector('.stage .scene, .stage[data-scene="blackout"]', { timeout: 15000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: resolve(out, file) });
  console.log('zapisano', file);
};

const files: string[] = [];
for (const scene of ['idle', 'qr', 'questions_collect', 'poll_result', 'summary']) { await shot(`scene=${scene}`, `${scene}.png`); files.push(`${scene}.png`); }
for (let i = 0; i < slides.length; i++) { await shot(`scene=infographics&slide=${i}`, `slides/${i}.png`); files.push(`slides/${i}.png`); }

// Jeden PDF ze wszystkimi planszami: kopia na pendrive na wypadek całkowitej awarii.
writeFileSync(resolve(out, 'index.json'), JSON.stringify({ generatedAt: new Date().toISOString(), base: BASE, files }, null, 2));
const htmlFile = resolve(out, 'plansze.html');
writeFileSync(htmlFile, '<!doctype html><meta charset="utf-8"><style>@page{size:1920px 1080px;margin:0}body{margin:0;background:#000}img{display:block;width:1920px;height:1080px;page-break-after:always}</style>' +
  files.map((f) => `<img src="${f}">`).join(''));
const pdfPage = await browser.newPage();
await pdfPage.goto(`file://${htmlFile}`);
await pdfPage.waitForLoadState('networkidle');
await pdfPage.pdf({ path: resolve(out, 'plansze.pdf'), width: '1920px', height: '1080px', printBackground: true });
await browser.close();
console.log(`Gotowe: ${files.length} plansz PNG i plansze.pdf w apps/web/public/static/. Teraz zbuduj i wdróż ponownie (npm run deploy).`);
console.log('Plansze poll_result i summary pokazują stan z chwili eksportu. Przed wydarzeniem to puste szablony, po wydarzeniu gotowe wyniki.');
