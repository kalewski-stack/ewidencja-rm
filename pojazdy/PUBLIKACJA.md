# Ewidencja pojazdów RM — wdrożenie krok po kroku

Aplikacja działa jak ewidencja czasu: PWA na GitHub Pages, dane w prywatnym arkuszu Google, backend w Apps Script.
Adres po publikacji: `https://TWOJ-LOGIN.github.io/ewidencja-rm/pojazdy/`. Pliki idą razem z repozytorium (workflow `pages.yml`).

## 1. Arkusz i Apps Script (backend)

1. Utwórz **nowy arkusz Google** „Ewidencja pojazdów RM” (osobny od ewidencji czasu).
2. **Rozszerzenia → Apps Script**, wklej zawartość `pojazdy/apps-script/Code.gs`, zapisz.
3. Odśwież arkusz. W menu pojawi się **Pojazdy → Przygotuj arkusze**. Uruchom (zatwierdź uprawnienia).
4. Uzupełnij zakładki:
   - **Pojazdy**: najłatwiej uzupełnić w aplikacji (zakładka **Pojazdy**, przycisk „Dodaj pojazd”). W arkuszu kolumny to: nr rejestracyjny, nazwa, rodzaj, paliwo, licznik początkowy, numer polisy, polisa od, polisa do, zakres, przegląd do (daty `RRRR-MM-DD`), aktywny (`tak`/`nie`), uwagi.
   - **Kierowcy**: imię i nazwisko, rola (`admin` albo `kierowca`), aktywny, opcjonalnie: lista pojazdów po przecinku (puste = wszystkie), data ważności prawa jazdy.
   - **Ustawienia**: `APP_URL` (adres aplikacji z końcówką `/pojazdy/`) oraz stawki za km (Zarząd może ustalić niższe niż maksymalne).
5. **Pojazdy → Wygeneruj klucze brakującym osobom**. W zakładce **Linki** dostajesz link i kod QR dla każdej osoby.
6. **Wdróż → Nowe wdrożenie → Aplikacja internetowa** (Wykonaj jako: Ja, Dostęp: Każdy). Skopiuj adres `/exec`.

## 2. Połączenie aplikacji z arkuszem

W `pojazdy/index.html` znajdź linię `var API_URL =` i wpisz adres `/exec`:
`var API_URL = window.POJAZDY_API || 'https://script.google.com/macros/s/.../exec';`
Wypchnij zmianę na `main`, Pages opublikuje całość. Przy zmianach wyglądu podbij `WERSJA` w `pojazdy/sw.js`.

## 3. Co robi aplikacja (wg regulaminu pojazdów)

| Zakładka | Funkcja | Paragraf |
|---|---|---|
| Jazda | Start / Koniec jazdy, kontrola pojazdu przed jazdą, stan licznika, konkretny cel (ogólne opisy są odrzucane), dopisanie zapomnianego przejazdu do następnego dnia roboczego | §5, §8 |
| Miesiąc | km, przejazdy, koszty, kilometrówka, zgłoszenia, status zatwierdzenia | §8 |
| Prywatny | kilometrówka: stawka z rodzaju pojazdu, zgoda przed wyjazdem, oświadczenie o pojeździe | §9, §10 |
| Koszty | paliwo, ładowanie, parking, opłaty, mycie i serwis (wymagają zgody lub trybu awaryjnego) | §7 |
| Zgłoś | usterka, szkoda, wypadek, awaria, mandat; przy kolizji lista kroków | §12, §13 |
| Pojazdy (admin) | karta każdego auta: polisa (numer, okres, zakres), przegląd, licznik, przebieg i koszty w roku, ostatni przejazd, zgłoszenia; lista od najpilniejszych terminów; dodawanie i edycja pojazdów; ostrzeżenia 30 dni przed końcem | §3 |
| Flota (admin) | terminy (przegląd, OC, prawo jazdy), km i zużycie l/100, kontrola ciągłości licznika, zatwierdzanie miesiąca, decyzje o kilometrówkach, zgłoszenia, wpis ręczny | §3, §8.6, §10 |

Zabezpieczenia: licznik nie może się cofnąć, zakresy liczników nie mogą się nakładać, pojazd nie może być w dwóch trasach naraz,
luka licznika jest oznaczana, zatwierdzony miesiąc blokuje edycję, każda korekta trafia do zakładki **Dziennik** (kto, kiedy, co, powód),
administrator nie zatwierdza własnej kilometrówki. Raport do księgowości i art. 86a VAT: **Pojazdy → Raport miesiąca**.

## 4. Do ustalenia z Zarządem

- Stawki w zakładce Ustawienia (maksymalne: 0,89 / 1,15 / 0,69 / 0,42 zł/km) i stawka dla aut elektrycznych (potwierdza księgowość).
- Czy świąteczne dni ruchome i weekend mają blokować dopisywanie (obecnie: najpóźniej następny dzień roboczy, z uwzględnieniem polskich świąt).
- Lista miejsc startu (`MIEJSCA` w `Code.gs`).
