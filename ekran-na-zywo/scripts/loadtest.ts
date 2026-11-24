// Test obciążeniowy: 150 klientów WebSocket, 150 głosów w 10 s, 60 pytań w 2 minuty.
// Użycie: npm run loadtest            (pełny, ok. 2,5 min)
//         npm run loadtest -- --fast  (pytania w 12 s zamiast 2 min)
// UWAGA: zeruje ankietę. Nie uruchamiać na produkcji w trakcie wydarzenia.
import { BASE, OPS_TOKEN, SCREEN_KEY, client, post, sleep } from './lib.ts';

const fast = process.argv.includes('--fast');
const N = 150, QN = 60;
const run = Date.now().toString(36);
let failed = false;
const check = (ok: boolean, msg: string) => { console.log(`${ok ? 'OK  ' : 'BŁĄD'} ${msg}`); if (!ok) failed = true; };

const ops = await client('ops', OPS_TOKEN);
const screen = await client('screen', SCREEN_KEY);
await ops.cmd('poll.reset', { confirm: 'RESET' });
await ops.cmd('poll.open');
await ops.cmd('phone.set', { mode: 'poll' });
const poll = ops.view.polls[0];

console.log(`Łączę ${N} telefonów (WebSocket) z ${BASE}...`);
const phones = await Promise.all(Array.from({ length: N }, () => client('public', '', false)));
await ops.waitFor((v) => v.presence.phones >= N, 8000).catch(() => null);
check(ops.view.presence.phones >= N, `podłączone telefony: ${ops.view.presence.phones}/${N}`);

// --- 150 głosów rozłożonych na 10 sekund ---
const sentAt: number[] = [];
const seenAt: number[] = [];
const watch = setInterval(() => { const total = screen.view?.poll?.total ?? 0; while (seenAt.length < total) seenAt.push(Date.now()); }, 5);
const t0 = Date.now();
const results = await Promise.all(Array.from({ length: N }, async (_, i) => {
  await sleep((i * 10_000) / N);
  const r = await post('/api/vote', { pollId: poll.id, optionId: poll.options[i % 3 === 0 ? 1 : 0].id, deviceId: `load-${run}-${i}` });
  sentAt.push(Date.now());
  return r.status;
}));
await screen.waitFor((v) => v.poll.total >= N, 5000).catch(() => null);
await sleep(100);
clearInterval(watch);
const okVotes = results.filter((s) => s === 200).length;
sentAt.sort((a, b) => a - b);
const lat = seenAt.map((t, i) => t - (sentAt[i] ?? t)).filter((x) => x >= 0);
const maxLat = Math.max(0, ...lat), avgLat = lat.reduce((a, b) => a + b, 0) / (lat.length || 1);
check(okVotes === N, `głosy przyjęte: ${okVotes}/${N} w ${((Date.now() - t0) / 1000).toFixed(1)} s`);
check(screen.view.poll.total === N, `licznik na ekranie: ${screen.view.poll.total} (zero utraconych głosów)`);
const tallySum = Object.values(screen.view.poll.tally as Record<string, number>).reduce((a, b) => a + b, 0);
check(tallySum === screen.view.poll.total, `suma słupków (${tallySum}) zgodna z licznikiem (${screen.view.poll.total})`);
check(maxLat < 1000, `opóźnienie głos -> ekran: średnio ${avgLat.toFixed(0)} ms, max ${maxLat} ms (wymagane < 1000 ms)`);
const dup = await post('/api/vote', { pollId: poll.id, optionId: poll.options[0].id, deviceId: `load-${run}-0` });
check(dup.status === 409, `drugi głos z tego samego urządzenia odrzucony (HTTP ${dup.status})`);

// --- 60 pytań ---
const before = ops.view.counters.questionsSubmitted;
const span = fast ? 12_000 : 120_000;
console.log(`Wysyłam ${QN} pytań w ${span / 1000} s...`);
const qres = await Promise.all(Array.from({ length: QN }, async (_, i) => {
  await sleep((i * span) / QN);
  return (await post('/api/question', { text: `Pytanie testowe numer ${i + 1} z testu obciążeniowego ${run}?`, deviceId: `loadq-${run}-${i}`, clientId: `c${i}` })).status;
}));
await ops.waitFor((v) => v.counters.questionsSubmitted >= before + QN, 5000).catch(() => null);
check(qres.every((s) => s === 200), `pytania przyjęte: ${qres.filter((s) => s === 200).length}/${QN}`);
check(ops.view.counters.questionsSubmitted === before + QN, `licznik pytań: +${ops.view.counters.questionsSubmitted - before}`);
check(screen.view.questionsSubmitted === ops.view.counters.questionsSubmitted, 'licznik pytań na ekranie zgodny z panelem');
check(!JSON.stringify(screen.view).includes(run), 'niezatwierdzone pytania nie trafiły do danych ekranu');
check(phones.every((p) => !p.closed), 'wszystkie połączenia telefonów utrzymane');

// Sprzątanie po teście: ukrywamy pytania testowe i zerujemy ankietę.
for (const q of ops.view.questions.filter((q: any) => q.text.includes(run))) await ops.cmd('q.hide', { id: q.id });
await ops.cmd('poll.reset', { confirm: 'RESET' });
for (const p of phones) p.close();
ops.close(); screen.close();
console.log(failed ? '\nTEST OBCIĄŻENIOWY: NIEZALICZONY' : '\nTEST OBCIĄŻENIOWY: ZALICZONY');
process.exit(failed ? 1 : 0);
