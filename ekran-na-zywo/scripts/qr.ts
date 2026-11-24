// Zapisuje kod QR do pliku SVG. Użycie: npm run qr -- https://krotki.adres [plik.svg]
import { writeFileSync } from 'node:fs';
import { qrSvg } from '../packages/shared/qr.ts';

const url = process.argv[2];
const out = process.argv[3] ?? 'qr.svg';
if (!url || !/^https?:\/\//.test(url)) { console.error('Podaj pełny adres, np.: npm run qr -- https://praca.example.pl'); process.exit(1); }
writeFileSync(out, qrSvg(url));
console.log(`Zapisano ${out} (korekcja M, quiet zone 4 moduły) dla adresu ${url}`);
