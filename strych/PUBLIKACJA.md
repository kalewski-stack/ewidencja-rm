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
2. Po dodaniu worka zakładka **Kartki → Wydrukuj** (A4, skala 100%, bez marginesów, dwie kartki A5 na arkusz). Kartkę przyklej albo przypnij do worka lub kartonu.
3. Zeskanuj kod zwykłym aparatem telefonu: otworzy się karta worka. Pusty numer otwiera formularz nowego worka.

## Rodzina, rozmiary i sezony

- Arkusz startuje z listą: Jurek, Ania, Marysia, Piotr, Tosia, Julek, Misia, Gabi i pozycja **Dom (wspólne)** na firany, pościel i materiały. Imiona i **rok urodzenia** poprawisz w aplikacji (Ustawienia). Wiek liczy się sam co roku.
  Rozmiary startowe dzieci są wzięte z tabeli orientacyjnej (Tosia i Julek 158 / buty 38, Misia 146 / 36, Gabi 92 / 23): sprawdź je w zakładce **Rozmiary**.
- **Rozmiary**: raz w roku wpisujesz aktualny rozmiar ubrań i butów każdego dziecka. Aplikacja przypomina, gdy od 10 miesięcy nikt tego nie sprawdził, i sama oznacza worki jako „pasuje teraz”, „za małe” albo „pasuje od ok. 2028”.
  Worek z tagiem „czeka na” jest oceniany względem tej osoby, nie względem tej, dla której został kupiony.
- **Sezon**: zaznaczasz dowolne z Wiosna, Lato, Jesień, Zima albo „Cały rok” (np. jesień + zima, tylko lato). Przypomnienie podpowiada się na 2 tygodnie przed pierwszym sezonem, w którym worek będzie potrzebny. Filtr „Na ten sezon” pokazuje, co wyjąć teraz.
- **Pojemniki**: małe, średnie i duże. Ich opisy (np. „pudełko ok. 60 l”) edytujesz w Ustawieniach.
- **Rzut strychu**: w zakładce Strych → Edytuj plan → Wgraj rzut. Na nim rysujesz palcem strefy (regały, skosy, kąty), każdej nadajesz nazwę i liczbę półek. Przy worku wybierasz strefę i półkę (liczone od dołu), a w szczegółach pulsuje punkt w tym miejscu.

## Etykiety, wyszukiwanie i alerty

- **Kartka A5 z opisem**: po zapisaniu worka aplikacja proponuje „Wydrukuj kartkę A5”. Na kartce jest duży kod QR (ok. 70% wysokości), nad nim wielkim drukiem właściciel, sezon z rokiem (np. Lato 2026), rodzaj (ciuchy letnie) i data założenia lub edycji, a obok numer i rozmiar. Resztę widać po zeskanowaniu. Zmieniony worek dostaje znacznik „do wydruku”, żeby nowa kartka nie została zapomniana.
  Drukujesz na zwykłym papierze **A4**: na jednej kartce mieszczą się dwie kartki A5 (górna i dolna połowa), przecinasz wzdłuż linii. Aplikacja pamięta, którą połowę zacząć następnym razem (można dokończyć częściowo zużyty arkusz). Wydruk jest czarno-biały, z grubą ramką i dużym drukiem, żeby było czytelne w ciemnym strychu. Kartkę przyklej taśmą, przypnij albo włóż w folię na worku lub kartonie.
  Zakładka Kartki → „Puste (numer i linie)” drukuje kartki z samym numerem i miejscem na ręczny opis.
- **Szukanie**: pole wyszukiwania w Garderobie rozumie zwykłe zdania, np. „czarne kozaki Ani”. Rozpoznaje właściciela (Ani, Ania), rodzaj rzeczy (kozaki = obuwie na jesień i zimę) i słowa z listy pojedynczych rzeczy oraz opisu. Pokazuje do trzech najbardziej prawdopodobnych worków, powód podpowiedzi i zaznacza te miejsca na planie strychu (numery 1–3). Dalej są filtry po osobie, sezonie, rodzaju i rozmiarze.
- **Pojedyncze rzeczy**: w formularzu worka dodajesz „czarne kozaki”, „kurtka puchowa” itp. Jeśli rzecz jest zapisana, wyszukiwarka wskaże dokładny worek. Jeśli nie, podpowie najbardziej prawdopodobne.
- **Alerty**: oznaczenie „Minął sezon” pojawia się, gdy w całości minął sezon z tagów worka (np. lato), a worek nie był ruszany od wstawienia albo ostatniego przeglądu. Do tego „Do przeglądu” (termin), „Zalega” (rok bez ruchu) oraz zmiany rozmiaru. Wszystko trafia też do poniedziałkowego e-maila.

## Przypomnienia e-mail

W zakładce **Domownicy** (albo w aplikacji, Ustawienia) wpisz adresy e-mail, potem w arkuszu **Strych → Włącz przypomnienia e-mail**.
Co poniedziałek rano przyjdzie lista worków po terminie, z terminem w ciągu 14 dni i takich, w które nikt nie zaglądał od ponad 12 mies. (stałe w `CONFIG`).

## Uwagi

- Zdjęcia leżą w folderze na Twoim Dysku jako „każdy z linkiem może wyświetlić”. Adresy są nie do odgadnięcia, ale nie wrzucaj zdjęć z danymi wrażliwymi.
- Kod domu chroni dane w arkuszu. Jeśli wycieknie: **Strych → Wygeneruj nowy kod domu** i roześlij nowy link.
- Aplikacja działa bez zasięgu na strychu na ostatnio pobranych danych (zmiany wymagają internetu).
- Skaner w aplikacji (przycisk „Skanuj”) pojawia się tam, gdzie przeglądarka go wspiera (Android/Chrome). Na iPhonie skanuj aparatem telefonu.
- Nowa wersja plików: podbij `WERSJA` w `strych/sw.js`.
