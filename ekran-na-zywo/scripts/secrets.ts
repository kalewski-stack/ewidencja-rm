// Generuje długie losowe sekrety, wgrywa je do Workera (wrangler secret bulk) i wypisuje gotowe linki dla zespołu.
// Użycie: npm run secrets -- https://twoj-krotki-adres
// Sekrety lądują też w .secrets.local.json (plik poza repozytorium). Nie wysyłaj ich mailem ani na czacie grupowym.
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const file = resolve(root, '.secrets.local.json');
const base = (process.argv[2] ?? '').replace(/\/$/, '');
const gen = () => randomBytes(24).toString('base64url');
const secrets: Record<string, string> = existsSync(file)
  ? JSON.parse(readFileSync(file, 'utf8'))
  : { OPS_TOKEN: gen(), MOD_TOKEN: gen(), SCREEN_KEY: gen(), SALT: gen() };
writeFileSync(file, JSON.stringify(secrets, null, 2), { mode: 0o600 });
if (!process.argv.includes('--print-only')) {
  execFileSync('npx', ['wrangler', 'secret', 'bulk', file], { cwd: root, stdio: 'inherit' });
}
const b = base || 'https://ADRES';
console.log(`\nLinki dla zespołu (zachowaj w bezpiecznym miejscu):
  Operator:   ${b}/ops#t=${secrets.OPS_TOKEN}
  Moderator:  ${b}/mod#t=${secrets.MOD_TOKEN}
  Ekran:      ${b}/screen?k=${secrets.SCREEN_KEY}
  Druk QR:    ${b}/print/qr#t=${secrets.OPS_TOKEN}
  Telefon:    ${b}/
Do skryptów (testy, eksport plansz): BASE=${b} OPS_TOKEN=... MOD_TOKEN=... SCREEN_KEY=... (wartości w .secrets.local.json)`);
