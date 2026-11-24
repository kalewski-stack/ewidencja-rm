// Kompleksowy przegląd w prawdziwej przeglądarce: każdy przycisk panelu, teksty, układ na kilku rozmiarach ekranu.
// Użycie: BASE=... OPS_TOKEN=... MOD_TOKEN=... SCREEN_KEY=... node scripts/audit.ts [katalog-na-zrzuty]
// UWAGA: zostawia dane testowe. Po przeglądzie wyczyść stan (npm run purge -- --yes). Nie uruchamiać w trakcie wydarzenia.
import { mkdirSync, writeFileSync } from 'node:fs';
import { BASE, MOD_TOKEN, OPS_TOKEN, SCREEN_KEY, client, playwright, post, sleep } from './lib.ts';

const out = process.argv[2] ?? 'audit-out';
mkdirSync(out, { recursive: true });
const results: { ok: boolean; name: string; info?: string }[] = [];
const problems: string[] = [];
const note = (ok: boolean, name: string, info = '') => { results.push({ ok, name, info }); console.log(`${ok ? 'OK  ' : 'BŁĄD'} ${name}${info ? ` | ${info}` : ''}`); };
const step = async (name: string, fn: () => Promise<unknown>) => {
  try { const r = await fn(); note(true, name, typeof r === 'string' ? r : ''); } catch (e) { note(false, name, String((e as Error).message).split('\n')[0].slice(0, 220)); try { await (globalThis as any).__op?.screenshot({ path: `${out}/BLAD-${results.length}.png` }); } catch { /* brak strony */ } }
};

const ops = await client('ops', OPS_TOKEN);
const screen = await client('screen', SCREEN_KEY);
const V = () => ops.view;
const until = (fn: (v: any) => boolean, ms = 6000) => ops.waitFor(fn, ms);

const br = await playwright().chromium.launch();
const watch = (page: any, label: string) => {
  page.on('console', (m: any) => { if (m.type() === 'error') problems.push(`[konsola ${label}] ${m.text().slice(0, 200)}`); });
  page.on('pageerror', (e: any) => problems.push(`[wyjątek ${label}] ${e.message.slice(0, 200)}`));
  page.on('response', (r: any) => { if (r.status() >= 400 && !r.url().includes('/api/vote') && !r.url().includes('/api/question')) problems.push(`[HTTP ${r.status()} ${label}] ${r.url().replace(BASE, '')}`); });
  page.on('dialog', (d: any) => (d.type() === 'prompt' ? d.accept('RESET') : d.accept()));
};

/** Kontrola tekstów i układu jednej strony. */
const inspect = async (page: any, label: string, opts: { stage?: boolean } = {}) => {
  const r = await page.evaluate((stage: boolean) => {
    const text = document.body.innerText;
    const bad: string[] = [];
    if (/�/.test(text)) bad.push('znak zastępczy (krzak)');
    const moj = text.match(/Ã.|Å[^a-zA-Z ]|Ä[^a-zA-Z ]|â€|Â /g); if (moj) bad.push('podejrzenie złego kodowania: ' + [...new Set(moj)].slice(0, 5).join(' '));
    for (const w of ['undefined', 'NaN', '[object', 'null']) if (new RegExp(`(^|[^a-zA-Z])${w.replace('[', '\\[')}([^a-zA-Z]|$)`).test(text)) bad.push(`tekst "${w}" na stronie`);
    const keys = (text.match(/\b(common|logo|qr|q|phone|scene|screen|slide|staff|status|ops|poll|queue|recs|slides|mod|print)\.[a-zA-Z][a-zA-Z0-9_.-]*/g) ?? []).filter((k) => !/\.(csv|svg|json|md|docx|dev|pdf|png)$/.test(k));
    if (keys.length) bad.push('nieprzetłumaczone klucze: ' + [...new Set(keys)].slice(0, 6).join(', '));
    if (/—/.test(text)) bad.push('długi myślnik w tekście');
    if (!stage && document.documentElement.scrollWidth > window.innerWidth + 1) bad.push(`poziome przewijanie strony (${document.documentElement.scrollWidth} > ${window.innerWidth})`);
    const broken = [...document.images].filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.getAttribute('src'));
    if (broken.length) bad.push('niezaładowane obrazy: ' + broken.join(', '));
    const clipped = [...document.querySelectorAll('button, .btn, .tab, .chip, .pill')].filter((e) => (e as HTMLElement).offsetParent && e.scrollWidth > e.clientWidth + 3).map((e) => (e.textContent ?? '').trim().slice(0, 30));
    if (clipped.length) bad.push('ucięty tekst w przyciskach: ' + [...new Set(clipped)].slice(0, 5).join(' / '));
    const narrow = [...document.querySelectorAll('p, span, h1, h2, h3, li, label')].filter((e) => { const h = e as HTMLElement; const t = (h.innerText ?? '').trim(); return h.offsetParent && t.length > 12 && !h.children.length && h.clientWidth > 0 && h.clientWidth < 40; }).map((e) => (e.textContent ?? '').trim().slice(0, 30));
    if (narrow.length) bad.push('tekst ściśnięty w wąskiej kolumnie: ' + [...new Set(narrow)].slice(0, 4).join(' / '));
    if (stage) {
      const st = document.querySelector('.stage'), safe = document.querySelector('.safe');
      if (st && safe) {
        const s = safe.getBoundingClientRect();
        const over = [...safe.querySelectorAll('.scene-slot *')].filter((e) => { const b = e.getBoundingClientRect(); const cs = getComputedStyle(e as Element); let hid = false; for (let p: Element | null = e; p && p !== safe; p = p.parentElement) if (getComputedStyle(p).opacity === '0') hid = true; return b.width > 0 && !hid && !(e as any).ownerSVGElement && cs.position !== 'fixed' && (b.right > s.right + 2 || b.bottom > s.bottom + 2 || b.left < s.left - 2 || b.top < s.top - 2); }).map((e) => String(e.getAttribute('class') || e.tagName).slice(0, 40));
        if (over.length) bad.push('element poza marginesem bezpieczeństwa ekranu: ' + [...new Set(over)].slice(0, 5).join(', '));
        const slot = safe.querySelector('.scene-slot') as HTMLElement | null, bar = safe.querySelector('.bar') as HTMLElement | null;
        if (slot && bar) { const last = [...slot.querySelectorAll('.scene *')].filter((e) => !(e as any).ownerSVGElement).map((e) => e.getBoundingClientRect()).filter((b) => b.width > 0).reduce((m, b) => Math.max(m, b.bottom), 0); if (last > bar.getBoundingClientRect().top + 2) bad.push('treść sceny nachodzi na pasek logotypów'); }
      }
    }
    return bad;
  }, !!opts.stage);
  note(r.length === 0, `wygląd i teksty: ${label}`, r.join('; '));
};

// ================= PANEL OPERATORA =================
const opCtx = await br.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const op = await opCtx.newPage(); watch(op, 'ops'); (globalThis as any).__op = op;
if (process.env.DEBUG_WS) op.on('websocket', (w: any) => w.on('framesent', (f: any) => { const t = String(f.payload); if (t.includes('"cmd"')) console.log('   ws>', t.slice(0, 160)); }));
await op.goto(`${BASE}/ops#t=${OPS_TOKEN}`);
await op.getByText('Połączono').waitFor({ timeout: 20000 });
const b = (name: string | RegExp, scope: any = op) => scope.getByRole('button', { name }).first();
const panel = (i: number) => op.locator('.ops-grid > .panel').nth(i);
const tab = (name: RegExp) => op.locator('.main-tabs .tab', { hasText: name });
const dl = async (click: () => Promise<void>, expect: RegExp) => { const [d] = await Promise.all([op.waitForEvent('download', { timeout: 15000 }), click()]); const p = `${out}/${d.suggestedFilename()}`; await d.saveAs(p); if (!expect.test(d.suggestedFilename())) throw new Error('nieoczekiwana nazwa pliku ' + d.suggestedFilename()); return d.suggestedFilename(); };

const scenePg = await (await br.newContext({ viewport: { width: 1920, height: 1080 } })).newPage(); watch(scenePg, 'screen');
await scenePg.goto(`${BASE}/screen?k=${SCREEN_KEY}`);
await step('pasek stanu: „Ekran żyje" po otwarciu ekranu', async () => { await op.getByText('Ekran żyje').waitFor({ timeout: 20000 }); });
await inspect(op, 'panel operatora 1440×900, stan startowy');

const sceneNames = ['Plansza tytułowa', 'Infografiki', 'Duży kod QR', 'Ankieta na żywo', 'Wynik ankiety', 'Zbieranie pytań', 'Jedno pytanie', 'Rekomendacje (odsłanianie)', 'Podsumowanie (do zdjęć)', 'Blackout'];
const sceneIds = ['idle', 'infographics', 'qr', 'poll_live', 'poll_result', 'questions_collect', 'question_focus', 'recommendations', 'summary', 'blackout'];
for (const [i, n] of sceneNames.entries()) await step(`scena: przycisk „${n}"`, async () => { await op.locator('.scene-btn').nth(i).click(); await until((v) => v.scene === sceneIds[i]); await scenePg.locator(`.stage[data-scene="${sceneIds[i]}"]`).waitFor({ timeout: 6000 }); });
for (const [k, id] of [['2', 'infographics'], ['5', 'poll_result'], ['0', 'blackout'], ['1', 'idle']] as const) await step(`skrót klawiszowy ${k}`, async () => { await op.locator('h2').first().click(); await op.keyboard.press(k); await until((v) => v.scene === id); });
for (const [n, id] of [['Ankieta', 'poll'], ['Pytania', 'questions'], ['Podziękowanie', 'thanks'], ['Zamknięte', 'closed'], ['Poczekalnia', 'waiting']] as const) await step(`telefony: przycisk „${n}"`, async () => { await b(n, panel(1).locator('.seg')).click(); await until((v) => v.phoneMode === id); });
await step('tryb awaryjny: ekran statyczny włącz i wyłącz', async () => { await b('Włącz ekran statyczny').click(); await until((v) => v.fallbackStatic === true); await scenePg.locator('img.static-img').waitFor({ timeout: 6000 }); await b('Ekran statyczny WŁĄCZONY').click(); await until((v) => v.fallbackStatic === false); });
await step('tryb awaryjny: Blackout włącz i wyłącz', async () => { await b('Blackout', panel(1)).click(); await until((v) => v.scene === 'blackout'); await b('Wyłącz blackout').click(); await until((v) => v.scene === 'idle'); });

const agendaLen = await op.locator('.agenda li').count();
for (let i = 0; i < agendaLen; i++) await step(`agenda: „Dalej" do kroku ${i + 1}/${agendaLen}`, async () => { if (i % 2) { await op.locator('h2').first().click(); await op.keyboard.press(' '); } else await b(/^Dalej/).click(); await until((v) => v.agendaStep === i); return `${V().scene} / ${V().phoneMode}`; });
await step('agenda: „Dalej" zablokowane po ostatnim kroku', async () => { if (!(await b(/^Dalej/).isDisabled())) throw new Error('przycisk aktywny'); });
await step('agenda: kliknięcie w krok 9:30 z potwierdzeniem', async () => { await op.locator('.agenda-step').nth(1).click(); await until((v) => v.agendaStep === 1 && v.scene === 'poll_live' && v.pollStatus === 'open'); });

// ---- ankieta ----
const phCtx = await br.newContext({ viewport: { width: 360, height: 740 }, deviceScaleFactor: 2 });
const ph = await phCtx.newPage(); watch(ph, 'telefon');
await ph.goto(`${BASE}/`);
await step('telefon: głos jednym kliknięciem', async () => { await ph.getByRole('button', { name: 'Większe zagrożenie' }).click(); await ph.getByText('Twój głos został zapisany').waitFor(); await until((v) => v.counters.votes === 1); });
await inspect(ph, 'telefon 360 px: po głosowaniu');
for (let i = 0; i < 12; i++) await post('/api/vote', { pollId: 'p1', optionId: i % 3 ? 'szansa' : 'zagrozenie', deviceId: `audit-dev-${i}` });
await step('ekran: licznik głosów zgodny z panelem', async () => { await until((v) => v.counters.votes === 13); await scenePg.waitForTimeout(1200); const t = await scenePg.locator('.poll-total b').innerText(); if (!t.includes('13')) throw new Error('na ekranie: ' + t); });
await inspect(scenePg, 'ekran: ankieta na żywo', { stage: true });
if (process.env.DEBUG_WS) { op.on('console', (m: any) => { if (m.text().startsWith('EVT')) console.log('   ' + m.text()); }); await op.evaluate(() => { for (const t of ['click', 'keydown', 'keyup', 'pointerdown']) window.addEventListener(t, (e: any) => console.log('EVT', t, e.isTrusted, e.key ?? '', (e.target as HTMLElement).tagName, ((e.target as HTMLElement).innerText ?? '').slice(0, 30), Math.round(performance.now())), true); }); }
await step('ankieta: „Zamknij ankietę (finał)"', async () => { await b('Zamknij ankietę (finał)').click(); await until((v) => v.pollStatus === 'closed'); await scenePg.getByText('Wynik końcowy').waitFor(); });
await step('ankieta: „Pobierz planszę PNG"', () => dl(() => b('Pobierz planszę PNG 1920×1080').click(), /ankieta-wynik.*\.png$/));
await step('ankieta: wpis ręczny (otwórz, zapisz 70/30)', async () => { await b(/Wpis ręczny wyników/).click(); const inputs = panel(2).locator('.manual input'); await inputs.nth(0).fill('70'); await inputs.nth(1).fill('30'); await b('Pokaż te liczby na ekranie').click(); await until((v) => v.polls[0].manualOverride?.szansa === 70); await scenePg.waitForTimeout(900); const t = await scenePg.locator('.poll-total b').innerText(); if (!t.includes('100')) throw new Error('ekran pokazuje ' + t); });
await step('ankieta: „Wróć do głosów z telefonów"', async () => { await b('Wróć do głosów z telefonów').click(); await until((v) => !v.polls[0].manualOverride); await b(/Wpis ręczny wyników/).click(); });
await step('ankieta: „Otwórz ponownie"', async () => { await b('Otwórz ponownie').click(); await until((v) => v.pollStatus === 'open'); });
await step('ankieta: „Wyzeruj ankietę" (podwójne potwierdzenie, RESET)', async () => { await b('Wyzeruj ankietę').click(); await until((v) => v.pollStatus === 'draft' && v.counters.votes === 0); });
await step('telefon: po wyzerowaniu można głosować ponownie', async () => { await ops.cmd('poll.open'); await ph.getByRole('button', { name: 'Większa szansa' }).waitFor({ timeout: 8000 }); });

// ---- pytania ----
await step('agenda: krok 12:30 (zbieranie pytań)', async () => { await op.locator('.agenda-step').nth(3).click(); await until((v) => v.scene === 'questions_collect' && v.phoneMode === 'questions'); });
const long280 = 'Czy w perspektywie najbliższych dziesięciu lat polskie i europejskie instytucje rynku pracy będą w stanie jednocześnie odpowiadać na niedobory kadrowe w kluczowych sektorach gospodarki, chronić prawa pracowników migrujących oraz skutecznie przeciwdziałać nieuczciwym pośrednikom pracy?';
await step('telefon: formularz pytań, walidacja i wysyłka (280 znaków)', async () => {
  await ph.getByRole('button', { name: 'Wyślij pytanie' }).click(); await ph.getByText('od 10 do 280 znaków').waitFor();
  await ph.getByLabel('Twoje pytanie').fill(long280.slice(0, 280)); await ph.getByLabel('Do kogo').selectOption({ index: 1 }); await ph.getByLabel('Imię (opcjonalnie)').fill('Aleksandra-Magdalena Wiśniewska-Kowalczyk');
  await ph.screenshot({ path: `${out}/telefon-formularz.png`, fullPage: true });
  await ph.getByRole('button', { name: 'Wyślij pytanie' }).click(); await ph.getByText('pytanie wysłane').waitFor(); await until((v) => v.questions.length === 1);
  if (V().questions[0].name.length > 40) throw new Error('imię dłuższe niż 40 znaków');
  await ph.getByRole('button', { name: 'Zadaj kolejne pytanie' }).click(); await ph.getByLabel('Twoje pytanie').waitFor();
});
const qTexts = ['Jakie zawody będą najbardziej deficytowe w Polsce za dziesięć lat?', 'Jakie zawody beda najbardziej deficytowe w Polsce za dziesiec lat', 'Co EURES oferuje osobom, które chcą wrócić z emigracji do Polski?', 'Czy praca zdalna dla zagranicznego pracodawcy wymaga zmiany rezydencji podatkowej?', 'Żółć gęślą jaźń: czy polskie znaki ąćęłńóśźż wyświetlają się poprawnie?'];
for (const [i, t] of qTexts.entries()) await post('/api/question', { text: t, name: i === 3 ? 'Łucja' : '', deviceId: `audit-q-${i}`, clientId: `a${i}` });
await until((v) => v.questions.length === 6);
await tab(/^Pytania/).click(); await op.waitForTimeout(500);
const card = (text: string) => op.locator('.q-card', { hasText: text }).first();
const filt = (name: string) => op.locator('.q-toolbar .tab', { hasText: name }).click();
await step('pytania: podpowiedź duplikatu i „Oznacz jako duplikat"', async () => { const c = card('beda najbardziej'); await c.getByText('Podobne do:').waitFor(); await b('Oznacz jako duplikat', c).click(); await until((v) => v.questions.some((q: any) => q.status === 'duplicate')); });
await step('pytania: „Edytuj" i „Zapisz"', async () => { await b('Edytuj', card('Co EURES oferuje')).click(); await op.locator('.q-edit textarea').fill('Co EURES oferuje osobom, które wracają z emigracji do Polski?'); await b('Zapisz', op.locator('.q-edit')).click(); await until((v) => v.questions.some((q: any) => q.originalText)); });
await step('pytania: „Zatwierdź na ekran" (4 pytania)', async () => { for (const t of ['Czy w perspektywie', 'Jakie zawody będą', 'wracają z emigracji', 'Czy praca zdalna']) await b('Zatwierdź na ekran', card(t)).click(); await until((v) => v.questions.filter((q: any) => q.status === 'approved').length === 4); });
await step('pytania: „Ukryj" i „Przywróć do nowych"', async () => { await b('Ukryj', card('Żółć gęślą')).click(); await until((v) => v.questions.some((q: any) => q.status === 'hidden')); await filt('Ukryte'); await b('Przywróć do nowych', card('Żółć gęślą')).click(); await until((v) => !v.questions.some((q: any) => q.status === 'hidden')); });
await step('pytania: „Duplikat..." z wyborem pytania nadrzędnego i „Anuluj"', async () => { await filt('Nowe'); const c = card('Żółć gęślą'); await b('Duplikat...', c).click(); await c.locator('select').waitFor(); await b('Anuluj', c).click(); await b('Zatwierdź na ekran', c).click(); await until((v) => v.questions.filter((q: any) => q.status === 'approved').length === 5); });
await step('ekran: zbieranie pytań, max 4 karty, polskie znaki', async () => { await scenePg.waitForTimeout(1800); const n = await scenePg.locator('.qcard-wrap:not(.out)').count(); if (n !== 4) throw new Error(`widocznych kart: ${n}`); await scenePg.getByText('Żółć gęślą jaźń').waitFor(); await scenePg.screenshot({ path: `${out}/ekran-pytania.png` }); });
await inspect(scenePg, 'ekran: zbieranie pytań z długimi treściami', { stage: true });
await step('pytania: filtry, sortowanie, grupowanie, filtr eksperta', async () => { await filt('Wszystkie'); await b(/^Sortowanie/).click(); await b(/^Sortowanie/).click(); await op.getByLabel('Grupuj według eksperta').check(); await op.locator('.q-group').first().waitFor(); await op.getByLabel('Grupuj według eksperta').uncheck(); await op.locator('.q-toolbar select').selectOption({ index: 2 }); await op.locator('.q-toolbar select').selectOption({ index: 0 }); });
await step('pytania: „Dodaj pytanie ręcznie"', async () => { await b('Dodaj pytanie ręcznie').click(); await op.locator('.q-add textarea').fill('Pytanie przyjęte ustnie od osoby bez zasięgu w telefonie?'); await op.locator('.q-add input').fill('Jan'); await b('Dodaj', op.locator('.q-add')).click(); await until((v) => v.questions.some((q: any) => q.source === 'manual')); });
await step('kolejka: „Do kolejki Na panel" (3 pytania)', async () => { await filt('Zatwierdzone'); for (const t of ['Czy w perspektywie', 'Jakie zawody będą', 'Czy praca zdalna']) await b('Do kolejki Na panel', card(t)).click(); await until((v) => v.queue.length === 3); });
await step('kolejka: strzałki zmiany kolejności', async () => { const first = V().queue[0]; await op.locator('.queue li').nth(0).locator('.queue-btns button').nth(1).click(); await until((v) => v.queue[1] === first); await op.locator('.queue li').nth(1).locator('.queue-btns button').nth(0).click(); await until((v) => v.queue[0] === first); });
await step('kolejka: „Następne na ekran" (długie pytanie 280 znaków)', async () => { await b('Następne na ekran').click(); await until((v) => v.scene === 'question_focus' && v.sceneParams.questionId === v.queue[0]); await scenePg.locator('.focus-text').waitFor(); await scenePg.waitForTimeout(900); await scenePg.screenshot({ path: `${out}/ekran-pytanie-dlugie.png` }); });
await inspect(scenePg, 'ekran: jedno pytanie, 280 znaków i długie imię', { stage: true });
await step('kolejka: „Następne" i „Poprzednie"', async () => { await b('Następne na ekran').click(); await until((v) => v.sceneParams.questionId === v.queue[1]); await b('Poprzednie').click(); await until((v) => v.sceneParams.questionId === v.queue[0]); });
await step('kolejka: „Oznacz aktualne jako zadane"', async () => { await b('Oznacz aktualne jako zadane').click(); await until((v) => v.queue.length === 2 && v.questions.some((q: any) => q.status === 'answered')); });
await step('kolejka: usunięcie pytania krzyżykiem', async () => { await op.locator('.queue li').first().locator('.queue-btns button').last().click(); await until((v) => v.queue.length === 1); });
await step('pytania: „Pokaż na ekranie" i „Zdejmij z ekranu"', async () => { await filt('Zatwierdzone'); await b('Pokaż na ekranie', card('wracają z emigracji')).click(); await until((v) => v.questions.some((q: any) => q.status === 'on_screen')); await filt('Na ekranie'); await b('Zdejmij z ekranu').click(); await until((v) => !v.questions.some((q: any) => q.status === 'on_screen')); });
await step('pytania: „Zadane" przy pytaniu', async () => { await filt('Zatwierdzone'); const n = V().questions.filter((q: any) => q.status === 'answered').length; await b('Zadane', op.locator('.q-card').first()).click(); await until((v) => v.questions.filter((q: any) => q.status === 'answered').length === n + 1); });
await inspect(op, 'panel operatora: zakładka Pytania z danymi');
await op.screenshot({ path: `${out}/panel-pytania.png`, fullPage: true });

// ---- rekomendacje ----
await tab(/^Rekomendacje/).click(); await op.waitForTimeout(400);
const T60 = 'Legalna mobilność zaczyna się od rzetelnej informacji: żółć', X140 = 'Każdy pracownik i pracodawca powinien wiedzieć, gdzie sprawdzić ofertę oraz pośrednika, zanim podpisze umowę o pracę za granicą, bez wyjątku.';
await step('rekomendacje: wpisanie 5 pozycji z autozapisem (60 i 140 znaków)', async () => { for (let i = 0; i < 5; i++) { await op.locator('.rec-slot').nth(i).locator('input').fill(T60.slice(0, 60)); await op.locator('.rec-slot').nth(i).locator('textarea').fill(X140.slice(0, 140)); } await until((v) => v.recommendations.every((r: any) => r.title.length >= 55 && r.text.length >= 130), 10000); await op.getByText('Wszystko zapisane').waitFor(); });
await step('agenda: krok „5 rekomendacji"', async () => { await op.locator('.agenda-step').nth(7).click(); await until((v) => v.scene === 'recommendations' && v.sceneParams.revealCount === 0); });
for (let n = 1; n <= 5; n++) await step(`rekomendacje: „Następna" ${n}/5`, async () => { await b('Następna').click(); await until((v) => v.sceneParams.revealCount === n); });
await step('rekomendacje: „Następna" zablokowana po piątej', async () => { if (!(await b('Następna').isDisabled())) throw new Error('aktywna'); });
await scenePg.waitForTimeout(1200); await scenePg.screenshot({ path: `${out}/ekran-rekomendacje-max.png` });
await inspect(scenePg, 'ekran: 5 rekomendacji o maksymalnej długości', { stage: true });
await step('rekomendacje: „Ukryj wszystkie" i „Pokaż wszystkie"', async () => { await b('Ukryj wszystkie').click(); await until((v) => v.sceneParams.revealCount === 0); await b('Pokaż wszystkie').click(); await until((v) => v.sceneParams.revealCount === 5); });
await step('rekomendacje: eksport PNG 1920×1080', () => dl(() => b('PNG 1920×1080').click(), /1920x1080\.png$/));
await step('rekomendacje: eksport PNG 1080×1350', () => dl(() => b('PNG 1080×1350').click(), /1080x1350\.png$/));
await step('rekomendacje: eksport .md', () => dl(() => b('.md').click(), /\.md$/));
await step('rekomendacje: eksport .docx', () => dl(() => b('.docx').click(), /\.docx$/));
await inspect(op, 'panel operatora: zakładka Rekomendacje');
await step('agenda: krok „Podsumowanie"', async () => { await op.locator('.agenda-step').nth(8).click(); await until((v) => v.scene === 'summary'); await scenePg.waitForTimeout(900); });
await inspect(scenePg, 'ekran: podsumowanie (plansza do zdjęć)', { stage: true });

// ---- slajdy ----
await tab(/^Slajdy/).click(); await op.waitForTimeout(400);
await step('slajdy: Pauza, Wznów, Następny, Poprzedni', async () => { await b('Pauza').click(); await until((v) => v.slidesPaused === true); await b('Wznów pętlę').click(); await until((v) => v.slidesPaused === false); await b('Następny').click(); await b('Poprzedni').click(); });
const meta = { source: 'DANE TESTOWE przeglądu (nie do emisji)', year: 2026, verified: true, notes: 'test' };
const testSlides = { slides: [{ type: 'bigNumber', title: 'TEST: duża liczba', value: 1234567, unit: 'osób', caption: 'Podpis testowy.', ...meta }, { type: 'bar', title: 'TEST: słupki', unit: '%', categories: [{ label: 'Kategoria A', value: 42.5 }, { label: 'Kategoria B', value: 31 }, { label: 'Kategoria C', value: 9 }], ...meta }, { type: 'line', title: 'TEST: linia', x: [2020, 2022, 2024, 2026], series: [{ name: 'Seria 1', values: [1, 3, 2, 5] }], ...meta }, { type: 'compare', title: 'TEST: porównanie', left: { value: 38.2, unit: '%', label: 'Lewa' }, right: { value: 45.7, unit: '%', label: 'Prawa' }, ...meta }, { type: 'map', title: 'TEST: mapa', unit: '%', values: { PL: 5, DE: 12, FR: 9, ES: 7 }, ...meta }] };
writeFileSync(`${out}/slides-test.json`, JSON.stringify(testSlides));
writeFileSync(`${out}/slides-bad.json`, JSON.stringify({ slides: [{ ...testSlides.slides[0], verified: false }] }));
await step('slajdy: plik bez verified jest odrzucany z komunikatem', async () => { await op.locator('.btn.file input').setInputFiles(`${out}/slides-bad.json`); await op.locator('.issues li').first().waitFor(); });
await step('slajdy: wgranie poprawnego pliku, podgląd, „Zapisz slajdy"', async () => { await op.locator('.btn.file input').setInputFiles(`${out}/slides-test.json`); await op.getByText('Plik poprawny').waitFor(); await op.locator('.slide-item').nth(1).click(); await op.locator('.mini-stage .bars').waitFor(); await b(/^Zapisz slajdy/).click(); await until((v) => v.slides.length === 5 && v.slidesCustom); });
await step('slajdy: „Pokaż" konkretny slajd na ekranie (wszystkie 5 typów)', async () => { await ops.cmd('scene.set', { scene: 'infographics' }); for (let i = 0; i < 5; i++) { await op.locator('.slide-list li').nth(i).getByRole('button', { name: 'Pokaż' }).click(); await until((v) => v.sceneParams.slideIndex === i); await scenePg.locator(`.slide-${testSlides.slides[i].type}`).waitFor({ timeout: 8000 }); await scenePg.waitForTimeout(i === 4 ? 2500 : 1500); await inspect(scenePg, `ekran: slajd typu ${testSlides.slides[i].type}`, { stage: true }); } });
await step('slajdy: „Przywróć slajdy z wdrożenia"', async () => { await b('Przywróć slajdy z wdrożenia').click(); await until((v) => v.slidesCustom === false && v.slides.length === 0); });
await inspect(op, 'panel operatora: zakładka Slajdy');

// ---- eksport i ustawienia ----
await tab(/^Eksport/).click(); await op.waitForTimeout(400);
await step('eksport: „Pobierz wszystko (ZIP)"', () => dl(() => b('Pobierz wszystko (ZIP)').click(), /eksport.*\.zip$/));
await step('eksport: votes.csv', () => dl(() => b('votes.csv').click(), /votes\.csv$/));
await step('eksport: questions.csv', () => dl(() => b('questions.csv').click(), /questions\.csv$/));
await step('eksport: „Pobierz qr.svg"', () => dl(() => b('Pobierz qr.svg').click(), /qr\.svg$/));
await step('ustawienia: „Zapisz listę ekspertów" (bez zmiany treści)', async () => { const n = V().experts.length; await b('Zapisz listę ekspertów').click(); await op.getByText('Zapisano').first().waitFor(); await sleep(400); if (V().experts.length !== n) throw new Error(`ekspertów: ${V().experts.length}, było ${n}`); });
await step('ustawienia: „Zapisz treść ankiety" działa tylko przed otwarciem', async () => { if (!(await b('Zapisz treść ankiety').isDisabled())) throw new Error('aktywny przy otwartej ankiecie'); await ops.cmd('poll.reset', { confirm: 'RESET' }); await until((v) => v.pollStatus === 'draft'); await b('Zapisz treść ankiety').click(); await op.getByText('Zapisano').first().waitFor(); });
await step('plansza QR do druku: otwiera się, kod się ładuje, 4 formaty', async () => { const [pg] = await Promise.all([opCtx.waitForEvent('page'), op.getByRole('link', { name: 'Plansza do druku (A4, A5)' }).click()]); watch(pg, 'druk'); await pg.locator('.sheet-qr img').waitFor({ timeout: 10000 }); for (const f of ['A4 poziom', 'A5 pion', 'A5 poziom', 'A4 pion']) await pg.getByRole('button', { name: f }).click(); const ok = await pg.locator('.sheet-qr img').evaluate((i: HTMLImageElement) => i.naturalWidth > 0); if (!ok) throw new Error('kod QR się nie załadował'); const u = await pg.locator('.sheet-url').innerText(); if (!BASE.includes(u)) throw new Error('adres pod kodem: ' + u); await inspect(pg, 'plansza QR do druku'); await pg.close(); });
await inspect(op, 'panel operatora: zakładka Eksport i ustawienia');

// ================= WIDOK MODERATORA =================
for (const [w, h, lab] of [[1180, 820, 'tablet poziomo'], [820, 1180, 'tablet pionowo'], [390, 844, 'telefon']] as const) {
  const m = await (await br.newContext({ viewport: { width: w, height: h } })).newPage(); watch(m, `mod ${lab}`);
  await m.goto(`${BASE}/mod#t=${MOD_TOKEN}`); await m.getByText('Połączono').waitFor({ timeout: 15000 });
  await m.locator('.q-toolbar .tab', { hasText: 'Wszystkie' }).click(); await m.waitForTimeout(400);
  await inspect(m, `widok moderatora, ${lab} ${w}×${h}: Pytania`);
  await m.locator('.main-tabs .tab', { hasText: 'Rekomendacje' }).click(); await m.waitForTimeout(400);
  await inspect(m, `widok moderatora, ${lab} ${w}×${h}: Rekomendacje`);
  if (w === 1180) {
    await step('moderator: edycja rekomendacji widoczna u operatora', async () => { await m.locator('.rec-slot').nth(4).locator('input').fill('Zmiana od moderatora'); await until((v) => v.recommendations[4].title === 'Zmiana od moderatora', 8000); });
    await step('moderator: „Następne na ekran" z kolejki', async () => { await m.locator('.main-tabs .tab', { hasText: 'Pytania' }).click(); await m.getByRole('button', { name: 'Następne na ekran' }).click(); await until((v) => v.scene === 'question_focus'); });
  }
  await m.screenshot({ path: `${out}/moderator-${w}.png` }); await m.close();
}

// ================= PANEL NA INNYCH ROZMIARACH =================
for (const [w, h] of [[1366, 768], [1280, 720], [390, 844]] as const) {
  const p = await (await br.newContext({ viewport: { width: w, height: h } })).newPage(); watch(p, `ops ${w}`);
  await p.goto(`${BASE}/ops#t=${OPS_TOKEN}`); await p.getByText('Połączono').waitFor({ timeout: 15000 }); await p.waitForTimeout(1200);
  for (const t of ['Pytania', 'Rekomendacje', 'Slajdy', 'Eksport']) { await p.locator('.main-tabs .tab', { hasText: t }).click(); await p.waitForTimeout(300); await inspect(p, `panel operatora ${w}×${h}: ${t}`); }
  await p.screenshot({ path: `${out}/panel-${w}.png`, fullPage: true }); await p.close();
}

// ================= TELEFON: WSZYSTKIE TRYBY, JASNY I CIEMNY =================
for (const scheme of ['dark', 'light'] as const) for (const w of [360, 430]) {
  const c = await br.newContext({ viewport: { width: w, height: 760 }, colorScheme: scheme }); const p = await c.newPage(); watch(p, `telefon ${scheme} ${w}`);
  await p.goto(`${BASE}/`);
  for (const mode of ['waiting', 'poll', 'questions', 'thanks', 'closed']) { await ops.cmd('phone.set', { mode }); await p.waitForTimeout(700); await inspect(p, `telefon ${w} px, ${scheme === 'dark' ? 'ciemny' : 'jasny'}, tryb ${mode}`); if (w === 360) await p.screenshot({ path: `${out}/telefon-${scheme}-${mode}.png` }); }
  await ops.cmd('poll.open'); await ops.cmd('phone.set', { mode: 'poll' }); await p.waitForTimeout(700); await inspect(p, `telefon ${w} px, ${scheme === 'dark' ? 'ciemny' : 'jasny'}, ankieta otwarta`);
  if (w === 360) await p.screenshot({ path: `${out}/telefon-${scheme}-ankieta.png` });
  await ops.cmd('poll.reset', { confirm: 'RESET' }); await c.close();
}
for (const path of ['/ankieta', '/pytania']) await step(`bezpośredni adres ${path}`, async () => { const p = await phCtx.newPage(); watch(p, path); await p.goto(BASE + path); await p.locator('h1').first().waitFor(); await inspect(p, `telefon: ${path}`); await p.close(); });

// ================= EKRAN: KAŻDA SCENA =================
for (const id of sceneIds) { await ops.cmd('scene.set', { scene: id }); await scenePg.locator(`.stage[data-scene="${id}"]`).waitFor(); await scenePg.waitForTimeout(1300); await inspect(scenePg, `ekran: scena ${id}`, { stage: true }); await scenePg.screenshot({ path: `${out}/ekran-${id}.png` }); }
await step('ekran: okno 1366×768 skaluje płótno bez ucięcia', async () => { const p = await (await br.newContext({ viewport: { width: 1366, height: 768 } })).newPage(); await p.goto(`${BASE}/screen?preview=1&scene=poll_result#k=${SCREEN_KEY}`); await p.locator('.stage').waitFor(); await p.waitForTimeout(800); const r = await p.locator('.stage').boundingBox(); if (!r || r.width > 1367 || r.height > 769 || r.x < -1 || r.y < -1) throw new Error(JSON.stringify(r)); await p.close(); });
await step('ekran bez klucza: komunikat zamiast treści', async () => { const p = await (await br.newContext()).newPage(); await p.goto(`${BASE}/screen`); await p.getByText('Brak klucza ekranu').waitFor({ timeout: 10000 }); await p.close(); });
await step('panel bez tokenu: formularz logowania, bez danych', async () => { const p = await (await br.newContext()).newPage(); await p.goto(`${BASE}/ops`); await p.getByPlaceholder('Token dostępu').waitFor(); if (await p.locator('.scene-btn').count()) throw new Error('widoczne sterowanie'); await p.close(); });

await br.close(); ops.close(); screen.close();
const uniq = [...new Set(problems)];
const failed = results.filter((r) => !r.ok);
console.log(`\nKROKI: ${results.length}, zaliczone: ${results.length - failed.length}, błędy: ${failed.length}`);
console.log(`Błędy konsoli, wyjątki i nieudane żądania: ${uniq.length}`);
for (const p of uniq) console.log('  ' + p);
writeFileSync(`${out}/raport.json`, JSON.stringify({ at: new Date().toISOString(), base: BASE, results, problems: uniq }, null, 2));
process.exit(failed.length || uniq.length ? 1 : 0);
