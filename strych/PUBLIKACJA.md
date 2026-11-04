# Strych — wdrożenie krok po kroku

Domowy bank garderoby: kod QR na każdym worku, zdjęcie zawartości, dla kogo, rozmiar, sezon, miejsce na planie strychu i przypomnienia o wymianie.
Ta sama technika co ewidencje: PWA na GitHub Pages, dane w prywatnym arkuszu Google, backend w Apps Script. Koszt: 0 zł. Czas: ok. 20 minut.

## Krok 1. Arkusz i backend

1. Nowy **prywatny arkusz Google**, np. „Strych”.
2. **Rozszerzenia → Apps Script**, wklej całość `strych/apps-script/Code.gs`, zapisz.
3. Odśwież arkusz (F5), pojawi się menu **Strych**. Uruchom **Strych → Przygotuj arkusze** (zatwierdź uprawnienia, w tym Dysk i Gmail, potem uruchom jeszcze raz).
   Powstają zakładki, **kod domu**, lista domowników (imiona zmienisz w aplikacji) i folder na zdjęcia na Dysku.
4. **Wdróż → Nowe wdrożenie → Aplikacja internetowa** (Wykonaj jako: Ja, Dostęp: Każdy). Skopiuj adres `/exec`.
   Po każdej zmianie `Code.gs` wdróż **nową wersję**.

## Krok 2. Adres backendu w aplikacji

W `strych/index.html` znajdź `var API_URL = window.STRYCH_API || '';` i wklej adres `/exec` między apostrofy.

## Krok 3. Publikacja

Po zmianie na `main` workflow publikuje wszystko na GitHub Pages. Aplikacja: `https://TWOJ-LOGIN.github.io/ewidencja-rm/strych/`.
Wpisz ten adres (z ukośnikiem na końcu) w arkuszu, zakładka **Ustawienia**, wiersz `APP_URL`.

## Krok 4. Telefony domowników

**Strych → Pokaż kod domu i link** w arkuszu albo aplikacja: **Ustawienia → Dodaj telefon domownika** (kod QR do zeskanowania).
Link zawiera kod domu, więc wystarczy go otworzyć raz, potem „Dodaj do ekranu głównego”. Przy pierwszym wejściu wybierasz, kim jesteś.

## Krok 5. Plan strychu i etykiety

1. Zakładka **Strych → Edytuj plan**: przeciągnij palcem po planie, żeby narysować regały i miejsca (albo „Wstaw przykładowy układ”). Wymiary strychu ustawisz w Ustawieniach (liczą się proporcje).
2. Zakładka **Etykiety → Drukuj arkusz** (A4, naklejki 70 × 37 mm, 3 × 8; skala 100%, bez marginesów). Naklejka na worek albo na plastikową zawieszkę przy worku.
3. Zeskanuj pustą etykietę zwykłym aparatem telefonu: otworzy się formularz nowego worka z tym numerem.

## Przypomnienia e-mail

W zakładce **Domownicy** (albo w aplikacji, Ustawienia) wpisz adresy e-mail, potem w arkuszu **Strych → Włącz przypomnienia e-mail**.
Co poniedziałek rano przyjdzie lista worków po terminie, z terminem w ciągu 14 dni i takich, w które nikt nie zaglądał od ponad 12 mies. (stałe w `CONFIG`).

## Uwagi

- Zdjęcia leżą w folderze na Twoim Dysku jako „każdy z linkiem może wyświetlić”. Adresy są nie do odgadnięcia, ale nie wrzucaj zdjęć z danymi wrażliwymi.
- Kod domu chroni dane w arkuszu. Jeśli wycieknie: **Strych → Wygeneruj nowy kod domu** i roześlij nowy link.
- Aplikacja działa bez zasięgu na strychu na ostatnio pobranych danych (zmiany wymagają internetu).
- Skaner w aplikacji (przycisk „Skanuj”) pojawia się tam, gdzie przeglądarka go wspiera (Android/Chrome). Na iPhonie skanuj aparatem telefonu.
- Nowa wersja plików: podbij `WERSJA` w `strych/sw.js`.
