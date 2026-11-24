# Ekran na żywo

System na konferencję „Praca ponad granicami – między szansą a zagrożeniem" (WUP w Warszawie, projekt EURES, Radom, 25.11.2026). Uczestnik skanuje jeden kod QR i trafia na stronę w przeglądarce. Bez aplikacji, bez kont, bez logowania.

## Narzędzia

Każdy element to osobne narzędzie pod własnym adresem. Wszystkie korzystają z jednego serwera stanu.

| Narzędzie | Adres | Dla kogo | Do czego |
|---|---|---|---|
| Telefon uczestnika | `/` | uczestnik | jedno wejście z QR: ankieta, formularz pytań, poczekalnia, podziękowanie |
| Ankieta (test) | `/ankieta` | zespół | bezpośrednie wejście do ankiety |
| Formularz pytań (test) | `/pytania` | zespół | bezpośrednie wejście do formularza |
| Ekran główny | `/screen?k=SCREEN_KEY` | komputer przy projektorze | 10 scen w 1920×1080, tylko odczyt |
| Panel operatora | `/ops#t=OPS_TOKEN` | operator | sceny, telefony, ankieta, pytania, rekomendacje, slajdy, tryb awaryjny, eksport |
| Widok moderatora | `/mod#t=MOD_TOKEN` | moderator (tablet) | pytania na żywo, kolejka „Na panel", edytor 5 rekomendacji |
| Kod QR | `/qr.svg` (nagłówek z tokenem) | zespół | plik SVG do materiałów |
| Plansza do druku | `/print/qr#t=OPS_TOKEN` | zespół | A4 i A5, pion i poziom |
| Plansze awaryjne | `/static/*` | awaryjnie | PNG 1920×1080 każdej sceny, PDF |
| Status | `/health` | monitoring | wersja, liczba klientów, aktualna scena |

Poza zakresem (nie budowane): elektroniczny informator, „Barometr Mobilności".

## Struktura

```
apps/web       frontend (Vite, TypeScript, Preact), osobny bundle na każde narzędzie
apps/worker    Cloudflare Worker + Durable Object (stan, WebSocket, API)
packages/shared  typy, protokół, walidacja slajdów, QR, procenty
content/       config.json, slides.json, theme.json, blocklist.txt, i18n/pl.json, assets/
scripts/       prepare, export-static, loadtest, purge, qr, secrets, tests/
```

## Uruchomienie lokalne

Wymagany Node 22.18 lub nowszy.

```bash
npm install
cp .dev.vars.example .dev.vars
npm run dev            # build roboczy + serwer na http://localhost:8787
```

Adresy lokalne: `/ops#t=dev-ops`, `/mod#t=dev-mod`, `/screen?k=dev-screen`, telefon `/`.
Tryb roboczy pokazuje szablony slajdów z napisem PLACEHOLDER. Na produkcji ich nie ma.

## Wdrożenie (Cloudflare)

1. Zaloguj się: `npx wrangler login`.
2. Ustaw adres z kodu QR w `wrangler.jsonc`, pole `PUBLIC_URL` (krótka subdomena). Podepnij domenę do Workera w panelu Cloudflare (Workers, Domains and Routes) albo użyj adresu `*.workers.dev`.
3. Slajdy: uzupełnij `content/slides.json` potwierdzonymi danymi. Build produkcyjny zatrzyma się, jeśli jakikolwiek slajd ma `verified: false` albo brak źródła lub roku. Jeśli danych jeszcze nie ma, zostaw `{ "slides": [] }` (scena Infografiki pokaże planszę tytułową), a slajdy wgrasz później z `/ops`.
4. Pierwsze wdrożenie: `npm run deploy`.
5. Sekrety i linki dla zespołu: `npm run secrets -- https://twoj-adres`. Skrypt generuje `OPS_TOKEN`, `MOD_TOKEN`, `SCREEN_KEY`, `SALT`, wgrywa je do Workera i wypisuje gotowe linki. Kopia trafia do `.secrets.local.json` (poza repozytorium).
6. Plansze awaryjne: `BASE=https://twoj-adres OPS_TOKEN=... SCREEN_KEY=... npm run export:static`, potem ponownie `npm run deploy`. Plansze i `plansze.pdf` skopiuj też na pendrive.
7. Sprawdź `https://twoj-adres/health` i przejdź `CHECKLIST-DZIEN-WYDARZENIA.md`.

Kopia zapasowa stanu: Durable Object zapisuje stan przy każdej komendzie i co 5 minut odkłada kopię (12 ostatnich). Kopia do R2 jest opcjonalna: utwórz bucket i odkomentuj `r2_buckets` w `wrangler.jsonc`.

### Zmienne

| Zmienna | Gdzie | Opis |
|---|---|---|
| `PUBLIC_URL` | `wrangler.jsonc` | adres zakodowany w QR |
| `EVENT_ID` | `wrangler.jsonc` | nazwa instancji wydarzenia (zmiana = czysty stan) |
| `OPS_TOKEN` | sekret | pełne sterowanie |
| `MOD_TOKEN` | sekret | pytania i rekomendacje |
| `SCREEN_KEY` | sekret | odczyt ekranu |
| `SALT` | sekret | sól do haszowania identyfikatorów urządzeń |

### Rollback

```bash
npx wrangler deployments list     # lista wersji
npx wrangler rollback             # powrót do poprzedniej wersji kodu
```

Rollback cofa kod, nie dane. Głosy i pytania zostają w Durable Object.

## Zmiana motywu

Cały wygląd steruje `content/theme.json` i katalog `content/assets/`.

- Kolory, fonty, skala typografii, promienie, cienie, czasy animacji: `theme.json`.
- Logotypy: wrzuć pliki do `content/assets/` i wpisz nazwy w `logos.wup`, `logos.eures`, `logos.ue`. Tekst finansowania: `fundingText`. Brak pliku = szary prostokąt z nazwą slotu.
- Fonty self-hosted: pliki do `content/assets/`, wpis w `fonts.files` (`{ "family": "Nazwa", "file": "plik.woff2", "weight": "700" }`) i nazwa rodziny w `fonts.heading`, `fonts.body`, `fonts.number`.
- Tło ekranu: `background: { "type": "image", "file": "tlo.svg" }`. Warstwę tła wyłącza flaga `flags.backgroundLayer` w `config.json`.
- Po podmianie ustaw `"placeholder": false`. Poprawki układu: `apps/web/src/themes/`.
- Po zmianie motywu wygeneruj plansze awaryjne od nowa (`npm run export:static`).

## Zmiana slajdów

- Przed wdrożeniem: edytuj `content/slides.json`. Typy: `bigNumber`, `bar` (do 8 kategorii), `line` (do 4 serii), `compare`, `map` (kody ISO alpha-2, akceptowane też `EL` i `UK`).
- W trakcie: `/ops`, zakładka Slajdy, „Wgraj slides.json". Plik przechodzi tę samą walidację, jest podgląd przed zapisem.
- Każdy slajd: `title`, `source`, `year`, `verified: true`, `notes`. Opcjonalnie `seconds` (czas na ekranie, domyślnie 10 s), `unit`, `caption`.
- W kodzie i w seedzie nie ma żadnych liczb statystycznych. Dane wpisuje człowiek, który je sprawdził u źródła.

## Teksty i konfiguracja

- Teksty interfejsu: `content/i18n/pl.json` (struktura gotowa pod kolejne języki).
- Pytanie ankiety, etykiety, trzecia opcja („Trudno powiedzieć", flaga `thirdOption.enabled`), agenda, limity: `content/config.json`. Kolejne pytania ankiety: dopisz następny obiekt w `polls`, telefon przejdzie przez nie po kolei.
- Treść ankiety i listę ekspertów da się też zmienić bez wdrożenia: `/ops`, zakładka „Eksport i ustawienia".
- Filtr słów: `content/blocklist.txt`. Trafienie nie kasuje pytania, tylko ukrywa je z flagą dla moderatora.

## Testy

Serwer musi działać (`npm run dev`). Testy zerują ankietę, więc nie uruchamiaj ich na produkcji w trakcie wydarzenia.

```bash
npm test                    # funkcjonalne i odpornościowe (Playwright)
npm run loadtest            # 150 klientów WS, 150 głosów w 10 s, 60 pytań w 2 min
npm run loadtest -- --fast  # to samo, pytania w 12 s
```

Playwright: `npm i -D playwright && npx playwright install chromium` (jeśli nie ma go w systemie).

## Dane i bezpieczeństwo

- Ankieta: przechowujemy wyłącznie sumy. Osobno, bez powiązania z wyborem, trzymamy zahaszowane identyfikatory urządzeń (SHA-256 z solą), tylko do blokady drugiego głosu. Bez IP, bez user-agentów, bez czasu pojedynczego głosu.
- Pytania: treść, opcjonalne imię, ekspert, znacznik czasu. Na ekran trafiają wyłącznie pytania zatwierdzone.
- Telefon: `localStorage` tylko na identyfikator urządzenia i flagę „zagłosowano". Bez ciasteczek, analityki, zewnętrznych fontów i skryptów.
- Limity: 1 głos i 3 pytania na 10 minut na urządzenie. Limit per IP ustawiony szeroko (6000 żądań na minutę), bo cała sala jest za jednym adresem hotelowego Wi-Fi.
- Tokeny idą we fragmencie adresu lub w nagłówku i od razu znikają z paska adresu. CSP, `noindex`, `robots.txt` blokujący wszystko.
- Retencja: po wydarzeniu eksport z `/ops`, po 30 dniach `BASE=... OPS_TOKEN=... npm run purge -- --yes`. Skrypt wypisuje potwierdzenie, ten sam wpis jest w logach Workera.

## Odstępstwa od specyfikacji (z uzasadnieniem)

- Animacje w CSS i `requestAnimationFrame` zamiast GSAP: te same efekty na transformacjach, o jedną zależność mniej.
- Serwer wysyła pełny widok roli zamiast przyrostów (`patch`): stan jest mały, aktualizacje są batchowane do 4 na sekundę, a telefony w ogóle nie dostają aktualizacji przy głosach.
- Telefon wysyła głos i pytanie przez HTTPS (potwierdzenie i jasny błąd), a WebSocket służy mu tylko do zmiany trybu. Fallback: odpytywanie co 2 s.
- Kopia co 5 minut domyślnie w Durable Object, R2 opcjonalnie (wymaga utworzenia bucketa).
