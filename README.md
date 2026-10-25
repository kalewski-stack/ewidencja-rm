# Ewidencja czasu pracy — Fundacja Redemptoris Missio

Aplikacja na telefon (PWA) do rejestrowania czasu pracy: Start / Przerwa / Zakończ, nieobecności, widok miesiąca.
Dane trafiają do arkusza Google przez Apps Script. Wygląd zgodny z kluczem komunikacji Fundacji (v1.0, 09.2026).

- `index.html` — aplikacja (adres API w linii `var API_URL`)
- `manifest.webmanifest`, `sw.js`, `ikony/` — ikona i praca jako aplikacja na ekranie głównym
- `PUBLIKACJA.md` — jak wdrożyć i aktualizować

Pliki nie zawierają danych pracowników ani kluczy dostępu. Klucze są wyłącznie w arkuszu.

## Ewidencja pojazdów

Folder `pojazdy/` to druga aplikacja (PWA + Apps Script) do ewidencji pojazdów służbowych, kosztów i kilometrówki, w tym samym layoucie. Wdrożenie: `pojazdy/PUBLIKACJA.md`.
