# START: jak uruchomić Rolkę od zera (instrukcja dla osoby bez doświadczenia technicznego)

Ta instrukcja prowadzi Cię od pobrania paczki do pierwszego gotowego filmu. Robisz kroki po kolei i nic nie musisz rozumieć: wystarczy kliknąć i wkleić.
**Kroki 1–4 robisz tylko raz.** Potem każdy film to jeden dwuklik i przeciąganie plików.

**Czego potrzebujesz:** komputer z Windows 10/11 albo Mac, ok. 5 GB wolnego miejsca, internet (przy instalacji i przy pierwszym montażu z napisami), godzinę czasu na początek
i telefon, którym nagrasz siebie.

**Jeśli utkniesz:** zrób zdjęcie ekranu (albo skopiuj komunikat) i napisz w rozmowie z Claude, na którym jesteś kroku. Poprowadzi Cię dalej.

## Co dostajesz

| Element | Co to jest |
|---|---|
| **Rolka** | Program na Twoim komputerze. Wrzucasz nagranie, a on tnie je na krótki film w stylu wzorców: cięcia, kadry po Twojej twarzy, napisy słowo po słowie, grafiki w kolorach marki, dźwięk. Nic nie wysyła do internetu. |
| **Formaty 1–4 i Motion** | Pięć rodzajów filmów (tabela w części 4). Wybierasz je z listy na stronie programu. |
| **Intro „o mnie”** | Gotowy tekst do przeczytania (folder `gotowe_teksty`) i opis, co nagrać. To Twój pierwszy prawdziwy film (część 3). |
| **Benchmark podcastu** | Dokument i rysunek: jak ma wyglądać nagranie podcastu. To nie program, nic nie instalujesz (część 5). |

## Część 1. Instalacja (raz, 30–60 minut, głównie czekanie)

### Krok 1. Pobierz i rozpakuj paczkę

1. Plik `rolka-narzedzie.zip` wysłał Ci Claude w rozmowie (karta pliku pod wiadomością). Kliknij go i zapisz na komputerze.
2. **Windows:** otwórz folder „Pobrane”, kliknij plik prawym przyciskiem myszy, wybierz „Wyodrębnij wszystko...”, potem „Wyodrębnij”.
   **Mac:** kliknij plik dwa razy. Powstanie folder.
3. Folder o nazwie `reelcut` przenieś na Pulpit. Od teraz to jest „folder programu”.

Nie uruchamiaj niczego z podglądu zipa: folder musi być rozpakowany.

### Krok 2. Zainstaluj Pythona (programu, na którym działa Rolka)

Instaluj dokładnie wersję **3.12.10**. Nie klikaj dużego żółtego przycisku na stronie python.org: daje najnowszą wersję, która bywa niezgodna z dodatkami Rolki.

- **Windows:** pobierz <https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe> i uruchom plik. W pierwszym oknie **zaznacz pole „Add python.exe to PATH”**
  (na dole), potem kliknij „Install Now”. Poczekaj, na końcu kliknij „Close”.
- **Mac:** pobierz <https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg>, otwórz plik i klikaj „Continue” (Dalej), „Agree” (Zgadzam się), „Install” (Zainstaluj).
  Gdy poprosi, wpisz hasło do swojego Maca. Na końcu „Close”.

### Krok 3. Zainstaluj ffmpeg (program do obróbki wideo)

- **Windows:**
  1. Kliknij przycisk Start, wpisz `PowerShell` i naciśnij Enter. Otworzy się niebieskie okno.
  2. Wklej do niego `winget install Gyan.FFmpeg` (prawy przycisk myszy wkleja) i naciśnij Enter.
  3. Jeśli zapyta o zgodę na warunki (Y/N albo T/N), wpisz `Y` (albo `T`) i Enter.
  4. Poczekaj, aż pojawi się napis „Successfully installed” (Pomyślnie zainstalowano). Zamknij okno.
  5. Jeśli komputer napisze, że nie zna polecenia `winget`: zaktualizuj „Instalator aplikacji” w sklepie Microsoft Store albo napisz do Claude.
- **Mac:**
  1. Naciśnij Cmd + Spacja, wpisz `Terminal` i Enter. Otworzy się okno do wpisywania poleceń.
  2. Wklej to polecenie i naciśnij Enter (to instalator Homebrew, czyli „sklepu” z programami):
     `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
  3. Gdy poprosi o hasło, wpisz hasło do Maca (znaki się nie wyświetlają, to normalne) i Enter. Gdy napisze „Press RETURN”, naciśnij Enter.
     Może zaproponować instalację „narzędzi wiersza poleceń”: zgódź się, to kilka minut.
  4. Na końcu Homebrew wypisze „Next steps” i dwa wiersze poleceń. Skopiuj je, wklej do okna i naciśnij Enter.
  5. Wklej `brew install ffmpeg` i Enter. Poczekaj kilka minut. Zamknij okno.

### Krok 4. Pierwsze uruchomienie

1. Otwórz folder programu (`reelcut`).
2. **Windows:** kliknij dwa razy plik `start.bat`. **Mac:** kliknij dwa razy plik `start.command`.
3. Jeśli system się zawaha:
   - **Windows** pokazał niebieskie okno „System Windows ochronił ten komputer”: kliknij „Więcej informacji”, potem „Uruchom mimo to”.
   - **Mac** napisał, że nie może otworzyć pliku: kliknij plik prawym przyciskiem, wybierz „Otwórz” i jeszcze raz „Otwórz”. Jeśli nadal nie: Ustawienia systemowe,
     Prywatność i bezpieczeństwo, przewiń na dół i przy komunikacie o `start.command` kliknij „Otwórz mimo to”.
4. Otworzy się czarne okno. **Przy pierwszym razie instaluje dodatki: to trwa 5–15 minut.** Nie zamykaj go, nic nie klikaj, czekaj.
5. Gdy skończy, w przeglądarce otworzy się strona z nagłówkiem **„Rolka”** i trzema ramkami: „1 Twoje nagranie”, „2 B-roll”, „3 Grafiki”. To jest program.
   Czarne okno zostaw otwarte (możesz je zminimalizować). Gdy je zamkniesz, program przestaje działać.
6. Strona się nie otworzyła sama? W czarnym oknie szukaj wiersza z adresem (np. `http://127.0.0.1:8765/`) i wpisz go w pasku adresu przeglądarki.

**Każde kolejne uruchomienie:** ten sam dwuklik (`start.bat` albo `start.command`). Trwa kilka sekund.

## Część 2. Test na krótkim nagraniu

### Krok 5. Sprawdź, że wszystko działa (10–20 minut, głównie czekanie)

1. Nagraj telefonem **pionowo** 20 sekund, jak mówisz do kamery (o czymkolwiek). Przenieś plik na komputer (kablem, AirDropem albo przez dysk Google).
2. Na stronie Rolki przeciągnij ten plik na ramkę „1 Twoje nagranie” (albo kliknij ramkę i wybierz plik).
3. Kliknij duży przycisk **„Potnij”** (jest aktywny dopiero po wgraniu nagrania).
4. **Za pierwszym razem program pobiera model rozpoznawania mowy (ok. 500 MB).** To normalne, trwa kilka minut. Pasek postępu się rusza, czekaj.
5. Gdy pojawi się „Gotowe”, kliknij **„Pobierz MP4”** i obejrzyj film. Jeśli widzisz pocięty film z napisami, wszystko działa.

Gotowe filmy zapisują się też w folderze `ReelCut` w Twoim folderze użytkownika, w podfolderze `wyniki` (strona podaje dokładną ścieżkę na dole).

## Część 3. Pierwszy prawdziwy film: intro „o mnie”

Ten film to Twoja wizytówka (ok. 65 sekund). Tekst jest gotowy, a fakty w nim pochodzą z kanonu marki (Notion). Przed publikacją sprawdź je jeszcze raz: to szkic do Twojej akceptacji
(liczby: 12 lat, ponad 700 wydarzeń, ponad 400 wystąpień; wyjaśnienia i decyzje w pliku `INTRO.md`).

### Krok 6. Przygotuj tekst

1. W folderze programu otwórz folder `gotowe_teksty` i plik `intro_o_mnie_scenariusz.txt` (Notatnik albo TextEdit).
2. To tekst, który **czytasz do kamery**. Pomiń wiersze zaczynające się od znaku `#` (to uwagi). Gwiazdek `*takich*` nie wymawiasz: oznaczają słowa, które program pokaże dużym drukiem.
3. Wydrukuj tekst albo wczytaj go do aplikacji z teleprompterem w telefonie.

### Krok 7. Nagraj siebie i wstawki

1. **Nagranie z mową (jedno, ciągłe, 65–70 sekund):** telefon **pionowo**, na statywie albo oparty o coś stabilnego, najwyższa jakość (4K, jeśli telefon potrafi).
   Odsuń telefon tak, żeby Twoja głowa miała **ok. 1/6 wysokości ekranu**, w górnej połowie kadru, a pod brodą było dużo wolnego miejsca (tam pokażą się napisy).
   Dobre światło, patrz w obiektyw, mów spokojnie, po każdej tezie oddech. Nagraj cały tekst naraz, cięcia zrobi program.
2. **Wstawki:** 6–10 krótkich klipów po 4–6 sekund z Twojego archiwum: Ty na scenie, publiczność, sala przed wydarzeniem, stoły, backstage, okładka książki, sala wykładowa.
   Dźwięk nie jest potrzebny. Włóż wszystkie do jednego folderu.
   Bez wstawek program zrobi zbliżenia z Twojego nagrania, ale film będzie dużo słabszy.

### Krok 8. Zmontuj w Rolce

1. Uruchom Rolkę (dwuklik `start.bat` albo `start.command`).
2. Ramka **„1 Twoje nagranie”**: przeciągnij nagranie z mową.
3. Ramka **„2 B-roll”**: otwórz folder ze wstawkami, zaznacz wszystkie pliki (Ctrl + A, na Macu Cmd + A) i przeciągnij je naraz na ramkę.
4. Ramka **„3 Grafiki”**: przeciągnij plik `intro_o_mnie_scenariusz.txt`. Bez niego nie powstaną duże słowa i karty.
5. Kliknij **„Ustawienia”** (rozwinie się lista), w polu **„Szablon montażu”** wybierz **„Format 4: kinetyczna typografia (pion 9:16)”**. Resztę zostaw.
6. Kliknij **„Potnij”**. Montaż trwa kilka–kilkanaście minut. Gdy pojawi się „Gotowe”, kliknij **„Pobierz MP4”**.
7. Obejrzyj cały film z dźwiękiem. Zwróć uwagę na napisy: czy nie ma literówek i czy Twoje nazwisko oraz nazwy własne są napisane dobrze. Jeśli coś wymaga poprawki, napisz w rozmowie z Claude, co poprawić.

Wersja pozioma (16:9) wymaga osobnego nagrania poziomego i szablonu „Format 4: kinetyczna typografia (poziom 16:9)”. Resztę robisz tak samo.

## Część 4. Kolejne filmy

Za każdym razem: nagranie w ramce 1, wstawki w ramce 2 (jeśli format ich używa), tekst w ramce 3, szablon w „Ustawienia”, „Potnij”.

| Chcesz zrobić | Wybierz w „Szablon montażu” | Co wrzucasz | Tekst w ramce 3 |
|---|---|---|---|
| Szybki film z wstawkami, napisy słowo po słowie | „Format 1: mówiąca głowa + B-roll...” | nagranie, wstawki | niepotrzebny |
| Jedno ciągłe nagranie z animowanymi grafikami (tytuły, listy, liczniki) | „Format 2: gadająca głowa...” | nagranie | tak, ze znacznikami w klamrach |
| Cięcia, wstawki z błyskiem i hasła z dużym słowem | „Format 3: gadająca głowa v3...” | nagranie, wstawki | tak, z `*gwiazdkami*` |
| Każde słowo jako napis, kolorowe karty | „Format 4: kinetyczna typografia (pion 9:16)” albo „(poziom 16:9)” | nagranie, wstawki | tak, z `*gwiazdkami*` |
| Animowany schemat, tylko Twój głos | „Motion...” | samo nagranie głosu (.m4a, .mp3, .wav) | tak, ze znacznikami |

**Najprościej:** napisz w rozmowie z Claude, jaki ma być film (temat, długość, który format), a dostaniesz gotowy tekst do wrzucenia w ramkę 3. Znaczniki w klamrach to jego robota, nie Twoja.

Szczegóły każdego formatu są w plikach `FORMAT2.md`, `FORMAT3.md`, `FORMAT4.md`, `MOTION.md` i `WORKFLOW.md`. Nie musisz ich czytać, żeby zacząć.

## Część 5. Podcast: co zrobić z benchmarkiem

To jest dokument, nie program. Nic nie instalujesz i niczego nie uruchamiasz.

1. Otwórz `Benchmark_podcastu.pdf` (jest w folderze programu). Pierwsza strona to rysunek: pięć kadrów i oś czasu 23 sekund. Dalej jest opis (ten sam tekst leży w pliku `PODCAST.md`).
2. Przeczytaj tabelę „W skrócie” (druga strona). To wszystko, co trzeba wiedzieć o formacie w pół minuty.
3. **Podejmij trzy decyzje** i odpowiedz na nie w rozmowie z Claude (możesz jednym zdaniem):
   - Akcent słów: żółty (propozycja) czy fiolet. Słupek paska: fioletowy (propozycja) czy żółty.
   - Krój paska z imieniem: wersaliki kroju marki (propozycja) czy nowy krój.
   - Czy zbudować szablon, który montuje odcinek z kilku kamer automatycznie (propozycja: tak).
4. **Przekaż PDF ekipie.** Ekipie zdjęciowej wskaż rozdziały 1 i 2 („Plan zdjęciowy” oraz „Scena i światło”), montażyście i grafikowi rozdziały 3, 4 i 5.
5. **Przed nagraniem** ekipa przechodzi tabelę „Dzień zdjęciowy” (rozdział 7). **Po montażu** Ty albo montażysta sprawdzacie klip tabelą „Po montażu”.
6. Po trzech–pięciu własnych odcinkach daj Claude gotowe klipy: zmierzy je i zamieni liczby wzorca na Twoje własne.

## Gdy coś nie działa

| Co widzisz | Co zrobić |
|---|---|
| „Nie znalazłem Pythona” | Zrób krok 2 jeszcze raz (na Windows pamiętaj o polu „Add python.exe to PATH”). Uruchom ponownie komputer i kliknij `start.bat` albo `start.command`. |
| „Nie znalazłem programu ffmpeg” | Zrób krok 3 jeszcze raz, uruchom ponownie komputer i kliknij plik startowy. |
| „Instalacja dodatków się nie udała” | Sprawdź internet i kliknij plik startowy jeszcze raz. Nic nie psujesz: instalacja ruszy od miejsca, w którym stanęła. |
| Strona się nie otworzyła | W czarnym oknie znajdź adres (zaczyna się od `http://127.0.0.1`) i wpisz go w przeglądarce. |
| Napis o braku pakietu `faster-whisper` | Zamknij czarne okno. W folderze programu usuń folder `.venv` (na Macu pokaż ukryte foldery skrótem Cmd + Shift + kropka) i kliknij plik startowy: dodatki zainstalują się od nowa. |
| Film jest bez napisów | W „Ustawienia” przy „Napisy” wybierz „Zawsze”. Pierwszy montaż z napisami potrzebuje internetu (pobiera model mowy). |
| Skóra na filmie jest za ciemna | W „Ustawienia” przesuń suwak „Kolory jak we wzorcu” na 60% i kliknij „Potnij” jeszcze raz. |
| Napisy mają literówki | Napisz w rozmowie z Claude, co poprawić. |
| Mac: błąd „CERTIFICATE_VERIFY_FAILED” | W Finderze otwórz Programy, folder „Python 3.12” i kliknij dwa razy „Install Certificates.command”. |
| Czerwony komunikat „ffmpeg zakończył się błędem” z napisem „Cannot select channel layout” | To znany błąd starszych wersji ffmpeg (do 6.0), wychodzi przy nagraniach z wyraźnymi szczytami głośności. Zainstaluj aktualizację programu (sekcja niżej). Wersja ffmpeg jest w nawiasie na końcu komunikatu. |
| Cokolwiek innego | Zrób zdjęcie ekranu (albo skopiuj komunikat z czarnego okna) i wyślij w rozmowie z Claude, razem z informacją: Windows czy Mac. |

## Aktualizacja programu

Czasem dostaniesz ode mnie plik `rolka-aktualizacja.zip` z poprawkami programu. Instalujesz go w kilka minut, bez ponownego ściągania dodatków.

**Mac:**

1. Zamknij czarne okno z napisami (Terminal): kliknij czerwoną kropkę w lewym górnym rogu okna. Jeśli zapyta, czy zakończyć proces, kliknij „Zakończ”.
2. Kliknij dwa razy `rolka-aktualizacja.zip` w folderze „Pobrane”. Obok pojawi się folder `src`.
3. Przeciągnij folder `src` na folder `reelcut` na Pulpicie. Mac zapyta, czy zastąpić istniejący element: kliknij „Zastąp”.
4. Kliknij dwa razy `start.command`, jak zawsze. Tym razem nic się nie doinstaluje, a strona Rolki otworzy się po kilku sekundach.

**Windows:**

1. Zamknij czarne okno z napisami (kliknij X w rogu).
2. Kliknij `rolka-aktualizacja.zip` prawym przyciskiem, wybierz „Wyodrębnij wszystko”, potem „Wyodrębnij”. Obok pojawi się folder `src`.
3. Przeciągnij folder `src` na folder `reelcut` na Pulpicie. Windows zapyta, czy scalić foldery albo zastąpić pliki: potwierdź („Tak” albo „Zamień pliki w miejscu docelowym”).
4. Kliknij dwa razy `start.bat`, jak zawsze.

**Jak sprawdzić, że aktualizacja weszła:** na samym dole strony Rolki jest wiersz „Wersje: Rolka 1.1.1, ffmpeg …” (numer Rolki 1.1.1 albo wyższy). Poprzednia wersja programu nie miała tam informacji o ffmpeg, więc jeśli ją widzisz, aktualizacja weszła.

## Słowniczek

- **Czarne okno** (terminal): okno z napisami, w którym pracuje program. Ma zostać otwarte, dopóki montujesz.
- **Python**, **ffmpeg**: dwa programy, na których działa Rolka. Instalujesz je raz.
- **Szablon**: gotowy styl filmu (rytm cięć, kadry, napisy). Wybierasz go z listy.
- **B-roll** (wstawki): krótkie klipy „obrazkowe”, które program przeplata z Twoim nagraniem.
- **Scenariusz**: plik tekstowy (.txt) z tym, co mówisz. Słowa w `*gwiazdkach*` program pokazuje dużym drukiem.
- **Pion 9:16**: format telefonu (rolki, TikTok, Shorts). **Poziom 16:9**: format YouTube i telewizora.
