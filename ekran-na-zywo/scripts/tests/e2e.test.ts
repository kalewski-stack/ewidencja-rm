// Testy funkcjonalne i odpornościowe (rozdział 15 specyfikacji). Wymagają działającego serwera: npm run dev
// Uruchomienie: npm test   (albo BASE=https://adres OPS_TOKEN=... MOD_TOKEN=... SCREEN_KEY=... npm test)
// UWAGA: testy zerują ankietę i dopisują pytania testowe. Tylko na środowisku testowym lub przed wydarzeniem.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { BASE, MOD_TOKEN, OPS_TOKEN, SCREEN_KEY, client, playwright, post, sleep, type Client } from '../lib.ts';
import { percents } from '../../packages/shared/util.ts';

const run = Date.now().toString(36);
let ops: Client, mod: Client, screen: Client, browser: any;
const auth = { Authorization: `Bearer ${OPS_TOKEN}` };
const q = (text: string, extra: Record<string, unknown> = {}) => post('/api/question', { text, deviceId: `t-${run}-dev`, clientId: Math.random().toString(36), ...extra });
const find = (text: string) => ops.view.questions.find((x: any) => x.text === text);

before(async () => {
  ops = await client('ops', OPS_TOKEN);
  mod = await client('mod', MOD_TOKEN);
  screen = await client('screen', SCREEN_KEY);
  browser = await playwright().chromium.launch();
  await ops.cmd('poll.reset', { confirm: 'RESET' });
  await ops.cmd('scene.set', { scene: 'idle' });
  await ops.cmd('phone.set', { mode: 'waiting' });
  await ops.cmd('fallback.set', { on: false });
});
after(async () => { await browser?.close(); ops?.close(); mod?.close(); screen?.close(); });

test('health i zabezpieczenia dostępu', async () => {
  const h = await (await fetch(`${BASE}/health`)).json();
  assert.equal(h.ok, true);
  assert.ok(h.version);
  assert.equal((await fetch(`${BASE}/qr.svg`)).status, 401);
  assert.equal((await fetch(`${BASE}/api/export`)).status, 401);
  assert.equal((await post('/api/purge', { confirm: 'USUN-DANE' })).status, 401);
  const svg = await fetch(`${BASE}/qr.svg`, { headers: auth });
  assert.equal(svg.status, 200);
  assert.match(await svg.text(), /<svg/);
  await assert.rejects(client('ops', 'zly-token'), /odrzucił/);
  await assert.rejects(client('screen', 'zly-klucz'), /odrzucił/);
  const robots = await (await fetch(`${BASE}/robots.txt`)).text();
  assert.match(robots, /Disallow: \//);
  const page = await fetch(`${BASE}/ops`);
  assert.match(page.headers.get('x-robots-tag') ?? '', /noindex/);
  assert.match(page.headers.get('content-security-policy') ?? '', /default-src 'self'/);
});

test('moderator nie może sterować scenami', async () => {
  await assert.rejects(mod.cmd('scene.set', { scene: 'qr' }), /operatora/);
  await assert.rejects(mod.cmd('poll.reset', { confirm: 'RESET' }), /operatora/);
});

test('ankieta: pełny przepływ, 150 głosów, blokada drugiego głosu, zamrożony wynik', async () => {
  const poll = ops.view.polls[0];
  const closedTry = await post('/api/vote', { pollId: poll.id, optionId: poll.options[0].id, deviceId: `t-${run}-early` });
  assert.equal(closedTry.body.code, 'poll_closed');

  await ops.cmd('agenda.go', { step: 1 }); // 9:30: scena ankiety, telefony w trybie ankiety, ankieta otwarta
  await ops.waitFor((v) => v.pollStatus === 'open');
  await screen.waitFor((v) => v.scene === 'poll_live');

  // Telefon w przeglądarce: głos jednym kliknięciem, potem samo podziękowanie.
  const ctx = await browser.newContext({ viewport: { width: 360, height: 700 } });
  const phone = await ctx.newPage();
  await phone.goto(`${BASE}/`);
  await phone.getByRole('button', { name: poll.options[0].label }).click();
  await phone.getByText('Twój głos został zapisany').waitFor();
  await phone.reload();
  await phone.getByText('Twój głos został zapisany').waitFor();
  assert.equal(await phone.getByRole('button', { name: poll.options[0].label }).count(), 0, 'po powrocie nie ma przycisków głosowania');
  await ctx.close();

  const statuses = await Promise.all(Array.from({ length: 150 }, (_, i) =>
    post('/api/vote', { pollId: poll.id, optionId: poll.options[i % 5 < 3 ? 0 : 1].id, deviceId: `t-${run}-v${i}` }).then((r) => r.status)));
  assert.equal(statuses.filter((s) => s === 200).length, 150);
  const again = await post('/api/vote', { pollId: poll.id, optionId: poll.options[1].id, deviceId: `t-${run}-v7` });
  assert.equal(again.status, 409);
  assert.equal((await post('/api/vote', { pollId: poll.id, optionId: 'nie-ma', deviceId: `t-${run}-x1` })).status, 400);

  await screen.waitFor((v) => v.poll.total === 151);
  await ops.cmd('poll.close');
  await ops.waitFor((v) => v.pollStatus === 'closed');
  const frozen = ops.view.polls[0].frozenResult;
  assert.equal(frozen.total, 151);
  assert.equal(frozen.tally[poll.options[0].id], 91);
  assert.equal(frozen.tally[poll.options[1].id], 60);
  const pct = percents(frozen.tally);
  assert.equal(Object.values(pct).reduce((a, b) => a + b, 0), 100, 'procenty sumują się do 100');
  assert.equal((await post('/api/vote', { pollId: poll.id, optionId: poll.options[0].id, deviceId: `t-${run}-late` })).body.code, 'poll_closed');

  // W danych wydarzenia nie ma nic o pojedynczych głosach.
  const exp = await (await fetch(`${BASE}/api/export`, { headers: auth })).json();
  assert.ok(!JSON.stringify(exp).includes(`t-${run}-v7`), 'eksport nie zawiera identyfikatorów urządzeń');

  // Ekran: plansza końcowa.
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(`${BASE}/screen?preview=1&scene=poll_result#k=${SCREEN_KEY}`);
  await page.getByText('Wynik końcowy').waitFor();
  assert.match(await page.locator('.poll-total b').innerText(), /151/);
  await page.close();
});

test('ankieta: wpis ręczny i zerowanie z potwierdzeniem', async () => {
  const poll = ops.view.polls[0];
  await ops.cmd('poll.manual', { pollId: poll.id, values: { [poll.options[0].id]: 70, [poll.options[1].id]: 30 } });
  await screen.waitFor((v) => v.poll.total === 100 && v.poll.tally[poll.options[0].id] === 70);
  await assert.rejects(ops.cmd('poll.manual', { pollId: poll.id, values: { [poll.options[0].id]: -1, [poll.options[1].id]: 2 } }));
  await ops.cmd('poll.manual', { pollId: poll.id, values: null });
  await screen.waitFor((v) => v.poll.total === 151);
  await assert.rejects(ops.cmd('poll.reset', { confirm: 'tak' }), /RESET/);
  assert.equal(ops.view.polls[0].tally[poll.options[0].id], 91, 'bez słowa RESET głosy zostają');
});

test('pytania: walidacja, honeypot, filtr słów, limit, podwójne kliknięcie', async () => {
  await ops.cmd('phone.set', { mode: 'questions' });
  const base = ops.view.counters.questionsSubmitted;
  assert.equal((await q('Za krótko')).status, 400);
  assert.equal((await q('x'.repeat(281))).status, 400);

  const bot = await q(`Pytanie od automatu ${run}, które wypełniło ukryte pole?`, { website: 'http://spam.example', deviceId: `t-${run}-bot` });
  assert.equal(bot.status, 200);

  const dbl = { text: `Czy podwójne kliknięcie zapisze jedno pytanie ${run}?`, deviceId: `t-${run}-dbl`, clientId: 'ten-sam' };
  const [a, b] = await Promise.all([post('/api/question', dbl), post('/api/question', dbl)]);
  assert.equal(a.status, 200); assert.equal(b.status, 200);

  const bad = `Co za debilny pomysł z tymi migracjami ${run}?`;
  assert.equal((await q(bad, { deviceId: `t-${run}-bad` })).status, 200);

  const lim = [];
  for (let i = 0; i < 4; i++) lim.push((await post('/api/question', { text: `Pytanie numer ${i} do testu limitu ${run}?`, deviceId: `t-${run}-lim`, clientId: `l${i}` })).status);
  assert.deepEqual(lim, [200, 200, 200, 429], 'limit 3 pytań na urządzenie na 10 minut');

  await ops.waitFor((v) => v.counters.questionsSubmitted === base + 5);
  assert.equal(ops.view.questions.filter((x: any) => x.text === dbl.text).length, 1, 'podwójne kliknięcie = jedno pytanie');
  assert.ok(!ops.view.questions.some((x: any) => x.text.includes('automatu')), 'honeypot nic nie zapisał');
  const flagged = find(bad);
  assert.equal(flagged.status, 'hidden');
  assert.equal(flagged.flagged, true, 'trafienie w blocklist: ukryte z flagą, nie skasowane');

  // Formularz w przeglądarce telefonu.
  const ctx = await browser.newContext({ viewport: { width: 360, height: 700 } });
  const phone = await ctx.newPage();
  await phone.goto(`${BASE}/`);
  await phone.getByRole('button', { name: 'Wyślij pytanie' }).click();
  await phone.getByText('od 10 do 280 znaków').waitFor();
  const typed = `Jak EURES pomaga w legalnym wyjeździe do pracy ${run}?`;
  await phone.getByLabel('Twoje pytanie').fill(typed);
  await phone.getByLabel('Imię (opcjonalnie)').fill('Testerka');
  await phone.getByRole('button', { name: 'Wyślij pytanie' }).click();
  await phone.getByText('pytanie wysłane').waitFor();
  await ctx.close();
  await ops.waitFor(() => !!find(typed));
  assert.equal(find(typed).name, 'Testerka');
  assert.equal(find(typed).status, 'new');
});

test('moderacja: nic nie trafia na ekran bez zatwierdzenia', async () => {
  const texts = [`Pierwsze pytanie do moderacji ${run}, o zezwolenia na pracę?`, `Drugie pytanie do moderacji ${run}, o pracę zdalną?`, `Pierwsze pytanie do moderacji ${run}, o zezwolenia na prace?`];
  for (const [i, t] of texts.entries()) assert.equal((await q(t, { deviceId: `t-${run}-m${i}` })).status, 200);
  await ops.waitFor(() => texts.every((t) => !!find(t)));
  await sleep(400);
  assert.ok(!JSON.stringify(screen.view).includes(run), 'dane ekranu nie zawierają niezatwierdzonych pytań');
  const pub = await (await fetch(`${BASE}/api/state`)).json();
  assert.ok(!JSON.stringify(pub).includes(run), 'telefon nie dostaje treści pytań');

  const [q1, q2, q3] = texts.map((t) => find(t));
  await mod.cmd('q.approve', { id: q1.id });
  await screen.waitFor((v) => v.approved.some((x: any) => x.id === q1.id));
  assert.ok(!screen.view.approved.some((x: any) => x.id === q2.id));

  await mod.cmd('q.duplicate', { id: q3.id, of: q1.id });
  await mod.cmd('q.hide', { id: q2.id });
  await ops.waitFor(() => find(texts[2]).status === 'duplicate' && find(texts[1]).status === 'hidden');
  assert.equal(find(texts[2]).duplicateOf, q1.id);
  await assert.rejects(mod.cmd('q.focus', { id: q2.id }), /zatwierdź/i);

  await mod.cmd('q.edit', { id: q1.id, text: texts[0].replace('Pierwsze', 'Poprawione') });
  await ops.waitFor((v) => v.questions.find((x: any) => x.id === q1.id).originalText === texts[0]);

  await mod.cmd('q.approve', { id: q2.id });
  await mod.cmd('queue.set', { ids: [q2.id, q1.id] });
  await mod.cmd('q.step', { dir: 1 });
  await screen.waitFor((v) => v.scene === 'question_focus' && v.focus?.id === q2.id);
  await mod.cmd('q.step', { dir: 1 });
  await screen.waitFor((v) => v.focus?.id === q1.id);
  await mod.cmd('q.answered', { id: q1.id });
  await screen.waitFor((v) => v.focus === null);
  await ops.waitFor((v) => !v.queue.includes(q1.id));

  // Widok moderatora w przeglądarce: zatwierdzenie kliknięciem.
  const click = `Pytanie do zatwierdzenia kliknięciem ${run}, o rynek pracy?`;
  await q(click, { deviceId: `t-${run}-click` });
  const page = await browser.newPage({ viewport: { width: 820, height: 1180 } });
  await page.goto(`${BASE}/mod#t=${MOD_TOKEN}`);
  const card = page.locator('.q-card', { hasText: click });
  await card.waitFor();
  await card.getByRole('button', { name: 'Zatwierdź na ekran' }).click();
  await screen.waitFor((v) => v.approved.some((x: any) => x.text === click));
  assert.ok(!page.url().includes(MOD_TOKEN), 'token znika z paska adresu');
  await page.close();
});

test('rekomendacje: edycja, konflikt wersji, odsłanianie 1 do 5', async () => {
  const r0 = ops.view.recommendations[0];
  const res = await mod.cmd('rec.set', { index: 0, title: `Rekomendacja testowa ${run}`, text: 'Jedno zdanie rozwinięcia.', baseRev: r0.rev });
  assert.equal(res.rev, r0.rev + 1);
  await assert.rejects(ops.cmd('rec.set', { index: 0, title: 'Nadpisanie ze starej wersji', text: '', baseRev: r0.rev }), /zmienił/);
  await ops.waitFor((v) => v.recommendations[0].title === `Rekomendacja testowa ${run}`);
  const long = await ops.cmd('rec.set', { index: 1, title: 'x'.repeat(200), text: 'y'.repeat(400), baseRev: ops.view.recommendations[1].rev });
  assert.ok(long.rev);
  await ops.waitFor((v) => v.recommendations[1].title.length === 60 && v.recommendations[1].text.length === 140);
  await ops.cmd('scene.set', { scene: 'recommendations' });
  for (let n = 0; n <= 5; n++) {
    await ops.cmd('rec.reveal', { count: n });
    await screen.waitFor((v) => v.scene === 'recommendations' && v.sceneParams.revealCount === n);
  }
  await assert.rejects(ops.cmd('rec.reveal', { count: 6 }));
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(`${BASE}/screen?preview=1#k=${SCREEN_KEY}`);
  await page.locator('.rec.on').nth(4).waitFor();
  assert.equal(await page.locator('.rec.on').count(), 5);
  await page.close();
  await ops.cmd('rec.set', { index: 1, title: '', text: '', baseRev: ops.view.recommendations[1].rev });
});

test('slajdy: plik bez źródła, roku lub verified jest odrzucany', async () => {
  const ok = { type: 'bigNumber', title: 'Slajd testowy', value: 12.5, unit: '%', source: 'Instytucja testowa', year: 2026, verified: true, notes: 'dane testowe, nie do emisji' };
  await assert.rejects(ops.cmd('slides.set', { slides: [{ ...ok, verified: false }] }), /verified/);
  await assert.rejects(ops.cmd('slides.set', { slides: [{ ...ok, source: '' }] }), /źródła/);
  await assert.rejects(ops.cmd('slides.set', { slides: [{ ...ok, year: null }] }), /roku/);
  await assert.rejects(ops.cmd('slides.set', { slides: [{ ...ok, value: null }] }), /niekompletne/);
  await ops.cmd('slides.set', { slides: [ok, { ...ok, title: 'Drugi slajd testowy' }] });
  await screen.waitFor((v) => v.slides.length === 2 && v.slides[0].title === 'Slajd testowy');
  await ops.cmd('slides.ctl', { action: 'goto', index: 1 });
  await screen.waitFor((v) => v.sceneParams.slideIndex === 1);
  await ops.cmd('slides.ctl', { action: 'pause' });
  await screen.waitFor((v) => v.slidesPaused === true);
  await ops.cmd('slides.ctl', { action: 'play' });
  await ops.cmd('slides.reset');
  await ops.waitFor((v) => v.slidesCustom === false);
});

test('ekran: zerwane połączenie nie zmienia sceny, po powrocie ekran nadrabia', async () => {
  await ops.cmd('scene.set', { scene: 'qr' });
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/screen?preview=1#k=${SCREEN_KEY}`);
  await page.locator('.stage[data-scene="qr"]').waitFor();
  await ctx.setOffline(true);
  await page.evaluate(() => { for (const w of (window as any).__sockets ?? []) w.close(); });
  await ops.cmd('scene.set', { scene: 'idle' });
  await sleep(1500);
  assert.equal(await page.locator('.stage').getAttribute('data-scene'), 'qr', 'bez sieci scena zostaje');
  assert.equal(await page.getByText(/rozłącz|brak połączenia/i).count(), 0, 'publiczność nie widzi komunikatu o rozłączeniu');
  await ctx.setOffline(false);
  await page.locator('.stage[data-scene="idle"]').waitFor({ timeout: 15000 });
  await ctx.close();
});

test('operator: skróty klawiszowe i blokada akcji bez połączenia', async () => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/ops#t=${OPS_TOKEN}`);
  await page.getByText('Połączono').waitFor();
  await page.keyboard.press('3');
  await screen.waitFor((v) => v.scene === 'qr');
  await page.keyboard.press('1');
  await screen.waitFor((v) => v.scene === 'idle');
  await ctx.setOffline(true);
  await page.getByText('BRAK POŁĄCZENIA Z SERWEREM').waitFor({ timeout: 40000 });
  assert.ok(await page.locator('.scene-btn').first().isDisabled(), 'przyciski scen zablokowane offline');
  await ctx.setOffline(false);
  await page.getByText('Połączono').waitFor({ timeout: 15000 });
  await ctx.close();
});

test('sprzątanie po testach', async () => {
  for (const x of ops.view.questions.filter((x: any) => x.text.includes(run) && x.status !== 'hidden')) await ops.cmd('q.hide', { id: x.id });
  await ops.cmd('rec.set', { index: 0, title: '', text: '', baseRev: ops.view.recommendations[0].rev });
  await ops.cmd('rec.reveal', { count: 0 });
  await ops.cmd('poll.reset', { confirm: 'RESET' });
  await ops.cmd('scene.set', { scene: 'idle' });
  await ops.cmd('phone.set', { mode: 'waiting' });
  await ops.waitFor((v) => v.counters.votes === 0 && v.phoneMode === 'waiting');
});
