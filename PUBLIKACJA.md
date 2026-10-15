# Aplikacja na telefon (PWA) — publikacja krok po kroku

Folder `app/` to gotowa aplikacja w barwach Fundacji (klucz komunikacji v1.0: grafit #383838,
pomarańcz #FFA142 / #E87229, beż #F3F1EA, piasek #E3DDD1, Roboto, przyciski-pigułki, zaokrąglenia 20/40 px,
logotyp z pliku źródłowego). Działa na iPhonie i Androidzie, dodaje się do ekranu głównego, koszt: 0 zł.

Dane i logika zostają w Apps Script i arkuszu. Aplikacja tylko rozmawia z nimi przez API.

## Co jest w folderze

| Plik | Po co |
|---|---|
| `index.html` | cała aplikacja (jeden plik) |
| `manifest.webmanifest` | nazwa, ikona, kolory dla ekranu głównego |
| `sw.js` | pamięć podręczna, żeby ikona otwierała się od razu i działała bez sieci (odczyt) |
| `ikony/` | ikony aplikacji (Android, iPhone, maskable) |
| `logo-ciemne-tlo.png`, `logo-jasne-tlo.png` | logotyp w obu wersjach z klucza komunikacji |

## Krok 1. Apps Script (backend)

1. Podmień `Code.gs` i `index.html` w projekcie Apps Script (jak dotąd).
2. **Wdróż → Zarządzaj wdrożeniami → ołówek → Nowa wersja → Wdróż.** Ustawienia: *Wykonaj jako: Ja*,
   *Dostęp: Każdy*. Skopiuj adres kończący się na `/exec`.
3. W `app/index.html` znajdź linię zaczynającą się od `var API_URL =` i wklej tam ten adres.
   (Obecnie wpisany jest Twój dotychczasowy adres `/exec`. Jeśli nie tworzysz nowego wdrożenia, tylko nową
   wersję istniejącego, adres się nie zmienia i nic nie trzeba zmieniać.)

## Krok 2. Hosting na GitHub Pages (darmowy)

1. Załóż konto na github.com (jeśli nie masz) i kliknij **New repository**. Nazwa np. `ewidencja`,
   widoczność **Public** (pliki aplikacji nie zawierają danych pracowników ani kluczy; klucze są tylko w arkuszu).
2. W repozytorium: **Add file → Upload files**. Przeciągnij całą zawartość folderu `app/`
   (razem z podfolderem `ikony/`). Zatwierdź **Commit changes**.
3. **Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main / (root) → Save.**
4. Po 1–2 minutach aplikacja działa pod `https://TWOJ-LOGIN.github.io/ewidencja/`.

Własny adres (np. `ewidencja.redemptorismissio.org`): w Settings → Pages wpisz domenę, a u operatora domeny
dodaj rekord CNAME wskazujący na `TWOJ-LOGIN.github.io`. Opcjonalne.

Alternatywa bez GitHuba: Cloudflare Pages albo Netlify (też darmowe, też „przeciągnij folder”).

## Krok 3. Spięcie i linki

1. W `Code.gs` w CONFIG ustaw `APP_URL: 'https://TWOJ-LOGIN.github.io/ewidencja/'` i zrób nową wersję wdrożenia.
2. W arkuszu: **Ewidencja → Linki pracowników**. Zakładka „Linki” dostaje dla każdej osoby: link do aplikacji
   (już z adresem PWA), sam klucz (gdyby ktoś wolał wkleić ręcznie) i **kod QR**.
3. Każdej osobie wyślij jej link albo pokaż kod QR na ekranie. Po pierwszym otwarciu aplikacja zapamiętuje
   klucz na telefonie i adres nie zawiera już klucza.

## Krok 4. Instrukcja dla pracownika (do przekazania)

**iPhone:** otwórz link w Safari → ikona Udostępnij (kwadrat ze strzałką) → „Do ekranu początkowego” → Dodaj.
**Android:** otwórz link w Chrome → menu ⋮ → „Dodaj do ekranu głównego” / „Zainstaluj aplikację”.

Od tej pory: ikona „Ewidencja RM” → Start pracy → Przerwa / Wznów → Zakończ pracę. Aplikacja sama pokazuje
tę podpowiedź przy pierwszym wejściu z przeglądarki.

## Aktualizacje

- Zmiana w logice (osoby, miejsca, etaty, reguły): tylko `Code.gs` + nowa wersja wdrożenia. Aplikacji nie ruszasz.
- Zmiana w wyglądzie: podmień `index.html` w repozytorium (Upload files, nadpisz) i w `sw.js` podbij `WERSJA`
  (np. `v2`), żeby telefony pobrały nową wersję.

## Bezpieczeństwo

- Klucz w linku to jedyna przepustka. Zgubiony telefon: **Ewidencja → Unieważnij link osoby…** i nowy link.
- Pracownik może sam kliknąć „Wyloguj z tego telefonu” na dole aplikacji.
- Arkusz pozostaje prywatny. Pliki aplikacji na GitHubie są publiczne, ale nie zawierają danych.
