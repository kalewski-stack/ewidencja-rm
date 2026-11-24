// Trwałe usunięcie danych wydarzenia z Durable Object (retencja: 30 dni po konferencji).
// Użycie: BASE=https://adres OPS_TOKEN=... npm run purge -- --yes
import { BASE, OPS_TOKEN, post } from './lib.ts';

if (!process.argv.includes('--yes')) {
  console.error(`To usunie WSZYSTKIE dane (głosy, pytania, rekomendacje) z ${BASE}. Najpierw zrób eksport w /ops.\nAby potwierdzić, dodaj flagę: --yes`);
  process.exit(1);
}
const r = await post('/api/purge', { confirm: 'USUN-DANE' }, { Authorization: `Bearer ${OPS_TOKEN}` });
if (r.status !== 200) { console.error('Nie udało się:', r.status, r.body?.message ?? ''); process.exit(1); }
console.log(`POTWIERDZENIE: dane usunięte ${r.body.purgedAt} z ${BASE}.`, JSON.stringify(r.body.removed));
console.log('Zachowaj ten wpis w dokumentacji projektu. Ten sam wpis jest w logach Workera (wrangler tail).');
