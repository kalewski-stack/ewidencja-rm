# Ewidencja pojazdów RM — wdrożenie krok po kroku

Aplikacja działa tak samo jak ewidencja czasu: PWA na GitHub Pages, dane w prywatnym arkuszu Google, backend w Apps Script.
Koszt: 0 zł. Czas wdrożenia: ok. 30 minut.

## Co jest w paczce

| Plik | Po co |
|---|---|
| `pojazdy/index.html` | cała aplikacja (jeden plik) |
| `pojazdy/manifest.webmanifest`, `pojazdy/sw.js`, `pojazdy/ikony/` | ikona i praca jako aplikacja na ekranie głównym |
| `pojazdy/apps-script/Code.gs` | backend: wklejasz do Apps Script w arkuszu |
| `logo-ciemne-tlo.png`, `logo-jasne-tlo.png` | logotyp (te same pliki co w ewidencji czasu, aplikacja bierze je z głównego folderu) |

Folder `pojazdy/` ma trafić do tego samego repozytorium co ewidencja czasu (`ewidencja-rm`), obok jej plików.
Ewidencja czasu działa dalej bez zmian.

## Krok 1. Arkusz Google i backend (Apps Script)

1. Utwórz **nowy arkusz Google**, np. „Ewidencja pojazdów RM” (osobny od ewidencji czasu). Arkusz ma być prywatny.
2. **Rozszerzenia → Apps Script**. Usuń domyślny kod, wklej całą zawartość pliku `Code.gs`, zapisz (ikona dyskietki).
3. Wróć do arkusza i odśwież stronę (F5). Pojawi się menu **Pojazdy**.
4. **Pojazdy → Przygotuj arkusze (pierwsze uruchomienie)**. Google poprosi o uprawnienia:
   „Przejrzyj uprawnienia” → wybierz konto → „Zaawansowane” → „Przejdź do … (niebezpieczne)” → „Zezwól”.
   To normalne dla własnego skryptu. Po zatwierdzeniu uruchom polecenie jeszcze raz.
5. Uzupełnij zakładki:
   - **Kierowcy**: imię i nazwisko (dokładnie tak, jak ma się wyświetlać), rola (`admin` albo `kierowca`), aktywny (`tak`).
     Opcjonalnie: lista pojazdów po przecinku (puste = wszystkie) i data ważności prawa jazdy (`RRRR-MM-DD`).
     Co najmniej jedna osoba musi mieć rolę `admin`.
   - **Pojazdy**: możesz je dodać teraz w arkuszu albo później w aplikacji (zakładka **Pojazdy**, przycisk „Dodaj pojazd”).
     Kolumny: nr rejestracyjny, nazwa, rodzaj, paliwo, licznik początkowy, numer polisy, polisa od, polisa do, zakres, przegląd do (daty `RRRR-MM-DD`), aktywny, uwagi.
   - **Ustawienia**: w wierszu `APP_URL` wpisz adres aplikacji (krok 3). Poniżej są stawki za kilometr dla kilometrówki
     (maksymalne z przepisów: 0,89 / 1,15 / 0,69 / 0,42 zł/km). Zarząd może ustalić niższe. Stawkę dla aut elektrycznych zostaw pustą,
     ustala ją administrator przy zatwierdzaniu.
6. **Wdróż → Nowe wdrożenie → ikona koła zębatego → Aplikacja internetowa**. Ustawienia:
   *Wykonaj jako: Ja*, *Kto ma dostęp: Każdy*. Kliknij „Wdróż” i **skopiuj adres kończący się na `/exec`**.
   Dostęp „Każdy” jest potrzebny, bo telefony kierowców nie są zalogowane na Twoje konto. Zabezpieczeniem jest indywidualny klucz w linku.

## Krok 2. Wpisanie adresu backendu do aplikacji

W pliku `pojazdy/index.html` znajdź linię:

```
var API_URL = window.POJAZDY_API || '';
```

i wklej adres `/exec` między apostrofy:

```
var API_URL = window.POJAZDY_API || 'https://script.google.com/macros/s/AKfy.../exec';
```

## Krok 3. Publikacja na GitHub Pages

Repozytorium `ewidencja-rm` ma już workflow publikujący całość na GitHub Pages po każdej zmianie na gałęzi `main`.

1. Dodaj folder `pojazdy/` oraz pliki logo (jeśli ich jeszcze nie ma) do repozytorium na gałęzi `main`.
   Najprościej: na GitHubie **Add file → Upload files**, przeciągnij folder `pojazdy` (z podfolderem `ikony` i `apps-script`), **Commit changes**.
   Jeśli pracujesz z gałęzią `pojazdy-odswiezona-wersja`, zrób z niej Pull Request i go zatwierdź.
2. Po 1–2 minutach (zakładka **Actions** pokaże zielony znaczek) aplikacja działa pod adresem:
   `https://TWOJ-LOGIN.github.io/ewidencja-rm/pojazdy/`
3. Ten adres wpisz w arkuszu, w zakładce **Ustawienia**, w wierszu `APP_URL` (z końcowym ukośnikiem).

## Krok 4. Klucze i linki dla kierowców

1. W arkuszu: **Pojazdy → Wygeneruj klucze brakującym osobom**.
2. W zakładce **Linki** znajdziesz dla każdej osoby link i kod QR. Wyślij osobie jej link albo pokaż QR na ekranie.
   Po pierwszym otwarciu aplikacja zapamiętuje klucz na telefonie i adres nie zawiera już klucza.
3. Instalacja na telefonie:
   - **iPhone:** link w Safari → Udostępnij (kwadrat ze strzałką) → „Do ekranu początkowego”.
   - **Android:** link w Chrome → menu ⋮ → „Dodaj do ekranu głównego” / „Zainstaluj aplikację”.

## Krok 5. Test przed uruchomieniem (10 minut)

1. Wejdź jako administrator, w zakładce **Pojazdy** dodaj jeden pojazd z datami polisy i przeglądu.
2. Wejdź jako kierowca: wybierz pojazd → OK → wpisz cel → **Zdaj pojazd** → podaj stan licznika.
3. Dodaj tankowanie i zgłoszenie usterki.
4. Jako administrator sprawdź zakładki **Podsumowanie**, **Auta**, **Ludzie**.
5. Usuń testowe wpisy w arkuszu (zakładki Przejazdy, Koszty, Zdarzenia, Dziennik) albo wyczyść je przed startem produkcyjnym.

## Codzienna obsługa i aktualizacje

- **Nowa osoba:** dopisz w zakładce Kierowcy, uruchom „Wygeneruj klucze”, wyślij link.
- **Zgubiony telefon:** **Pojazdy → Unieważnij link osoby…**, potem wyślij nowy link z zakładki Linki.
- **Nowy pojazd, zmiana polisy lub przeglądu:** w aplikacji, zakładka **Pojazdy → Edytuj dane**.
- **Zatwierdzanie miesiąca i kilometrówek:** zakładka **Podsumowanie**.
- **Raport do księgowości i art. 86a VAT:** **Pojazdy → Raport miesiąca: ewidencja przebiegu i kilometrówki…**
- **Zmiana logiki** (stawki, listy miejsc, progi): zmień `Code.gs`, potem **Wdróż → Zarządzaj wdrożeniami → ołówek → Nowa wersja → Wdróż**.
  Adres `/exec` się nie zmienia.
- **Zmiana wyglądu:** podmień `index.html` w repozytorium i podbij `WERSJA` w `pojazdy/sw.js` (np. `pojazdy-rm-v2`), żeby telefony pobrały nową wersję.

## Co robi aplikacja (wg regulaminu pojazdów)

| Zakładka | Funkcja | Paragraf |
|---|---|---|
| Jazda | 1) wybór pojazdu, 2) potwierdzenie stanu licznika po poprzedniej jeździe („OK” albo „Dopisz ręcznie”), 3) cel przejazdu i **Zdaj pojazd** z oknem na aktualny stan licznika i miejsce zostawienia. Przyciski **Tankowanie** (paliwo, ładowanie, parking, opłaty, mycie i serwis) i **Usterka** (usterka, kolizja, wypadek, awaria, mandat). Na dole: dopisanie zapomnianego przejazdu i poprawa błędnego (do następnego dnia roboczego, z powodem, zapis w dzienniku) | §5, §7, §8, §13, §14 |
| Miesiąc | km, przejazdy, koszty, kilometrówka, zgłoszenia, status zatwierdzenia | §8 |
| Prywatny | kilometrówka: stawka z rodzaju pojazdu, zgoda przed wyjazdem, oświadczenie o pojeździe | §9, §10 |
| Podsumowanie (admin) | wszystkie pojazdy razem (km, przejazdy, koszty), kierowcy, terminy, km i zużycie l/100 per pojazd, kontrola ciągłości licznika, zatwierdzanie miesiąca, decyzje o kilometrówkach, zgłoszenia, wpis ręczny. Miesiąc lub rok | §3, §8.6, §10 |
| Auta (admin) | wybrany pojazd: kto jechał, kiedy, ile km, stany liczników; km per kierowca. Miesiąc lub rok | §8, §14 |
| Ludzie (admin) | wybrany pracownik: którymi autami jechał, kiedy, ile km; km per pojazd. Miesiąc lub rok | §8, §14 |
| Pojazdy (admin) | karta każdego auta: polisa, przegląd, licznik, przebieg i koszty w roku, ostatni przejazd, zgłoszenia; lista od najpilniejszych terminów; dodawanie i edycja | §3 |

Zabezpieczenia: licznik nie może się cofnąć, zakresy liczników nie mogą się nakładać, pojazd nie może być w dwóch trasach naraz,
luka licznika jest oznaczana, zatwierdzony miesiąc blokuje edycję, każda korekta trafia do zakładki **Dziennik** (kto, kiedy, co, powód),
administrator nie zatwierdza własnej kilometrówki.

## Rozwiązywanie problemów

| Objaw | Przyczyna i rozwiązanie |
|---|---|
| „Aplikacja nie ma jeszcze adresu arkusza” | nie wpisano `API_URL` w `index.html` (krok 2) |
| „Ten klucz nie jest już ważny” | klucz został unieważniony albo osoby nie ma w zakładce Kierowcy; wyślij świeży link |
| Aplikacja pokazuje starą wersję | podbij `WERSJA` w `sw.js`; na telefonie zamknij aplikację i otwórz ponownie |
| „Serwer odpowiedział błędem” albo brak danych | w Apps Script wdróż **Nową wersję** po każdej zmianie `Code.gs`; sprawdź, czy dostęp to „Każdy” |
| Pusta lista pojazdów u kierowcy | pojazd ma `nie` w kolumnie aktywny albo kierowca ma ograniczoną listę pojazdów |
| Daty w arkuszu zamieniają się w inny format | wpisuj daty w formacie `RRRR-MM-DD`; zakładki są sformatowane jako tekst |

## Bezpieczeństwo

- Klucz w linku to jedyna przepustka. Linki wysyłaj każdemu osobno.
- Arkusz pozostaje prywatny (udostępnij go tylko administratorom). Pliki aplikacji na GitHubie są publiczne, ale nie zawierają danych ani kluczy.
- Pamiętaj o RODO: ewidencja zawiera dane osobowe kierowców i trasy. Dostęp do arkusza ogranicz do osób upoważnionych.
