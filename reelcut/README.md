# Rolka: tnie Twoje wideo jak rolka wzorcowa

**Pierwszy raz i nie jesteś informatykiem? Zacznij od [START.md](START.md)**: instalacja i pierwszy film krok po kroku, osobno dla Windows i Maca.

**Format 1** (domyślny, ten opis): wrzucasz swoje nagranie, dostajesz pionowy film (1080×1920) zmontowany według schematu rolki
<https://www.instagram.com/reel/DeuOaXKtPBb/>: ten sam rytm cięć, ten sam układ „mówiąca głowa + wstawki",
te same proporcje kadrów (rozmiar i miejsce twarzy), te same kolory (ciemny, stonowany look z winietą),
napisy słowo po słowie z wyróżnionymi frazami i dźwięk znormalizowany do −14 LUFS.

Wszystko liczy się na Twoim komputerze. Żaden plik nie jest nigdzie wysyłany.

- Szczegóły analizy rolki (czasy cięć, zasady, wymiary napisów): [ANALIZA.md](ANALIZA.md).
- **Nowy film krok po kroku** (co nagrać, co wrzucić, co sprawdzić): [WORKFLOW.md](WORKFLOW.md), jedna strona.
- **Format 2: gadająca głowa** (jeden take bez cięć, animowane grafiki w kolorach i kroju marki: tytuły, listy pisane
  na żywo, karty, strzałki, liczniki, także za postacią; czasy ustawiane na słowach ze scenariusza): zasady i słownik
  elementów w [FORMAT2.md](FORMAT2.md), składnia znaczników w [GRAFIKI.md](GRAFIKI.md). Szablon `format2`.
- **Format 3: gadająca głowa v3** (cięcia i wstawki jak w Formacie 1, ale napisy, hasła z dużym słowem kluczowym i biały błysk przy
  wstawce rysuje warstwa grafik w kolorach i kroju marki; hasła powstają ze słów w `*gwiazdkach*` w scenariuszu): zasady i liczby
  ze wzorca w [FORMAT3.md](FORMAT3.md), składnia znaczników w [GRAFIKI.md](GRAFIKI.md). Szablon `format3`.
- **Format 4: kinetyczna typografia** (pion 9:16 albo poziom 16:9; cięcie co ok. 1,6 s, cała mowa jako napisy z jednym dużym słowem i małymi wokół,
  białe i żółte karty z tekstem i odręczną elipsą, czarno-biały hak; wszystko rysuje warstwa grafik w kolorach i kroju marki): zasady i liczby
  ze wzorca w [FORMAT4.md](FORMAT4.md), składnia i elementy w [GRAFIKI.md](GRAFIKI.md). Szablony `format4` (pion) i `format4h` (poziom).
- **Motion** (bez mówiącej głowy: wrzucasz samo nagranie lektora, a narzędzie rysuje cały obraz, czyli schemat z tarczą
  i kamerą, czarne plansze i napisy kinetyczne, w kolorach i kroju marki; każdy ruch ma czas ze słowa, które pada): zasady
  i liczby ze wzorca w [MOTION.md](MOTION.md), składnia znaczników w [GRAFIKI.md](GRAFIKI.md). Szablon `motion`.
- **Benchmark podcastu** (ciemne studio, dwoje rozmówców przy stole, cztery kadry z kilku kamer, napisy z czerwonymi akcentami, pasek z imieniem,
  pływająca karta): zmierzona rama nagrania i klipu z jednej rolki, lista kontrolna odcinka i przełożenie na kolory marki w [PODCAST.md](PODCAST.md),
  liczby w `src/reelcut/data/podcast_benchmark.json`, schemat kadrów w `docs/podcast_rama.png`. To specyfikacja, jeszcze nie szablon montażu.
- **Przejścia między scenami** (rozmycie, najazd, przesunięcie, kurtyna, błysk; znacznik `{przejście: ...}`): zmierzone krzywe, składnia
  i granice w [PRZEJSCIA.md](PRZEJSCIA.md).
- **Styl do przeniesienia na inne tematy** (kolory, dynamika, kadry, cięcia, lista ujęć do nagrania, format
  scenariusza z budżetem słów): [STYL.md](STYL.md). Kartę stylu każdego szablonu wypisze `python rolka.py style`.

## Co robi dokładnie

1. **Skraca martwe powietrze.** Pauzy dłuższe niż 0,5 s ścina do 0,35 s (rolka wzorcowa ma sam ciągły głos).
2. **Tnie obraz w rytmie rolki.** 15 ujęć: 2,56 s, 2,68 s, 1,60 s, 1,16 s... (pełna lista w [ANALIZA.md](ANALIZA.md)).
   Początek (hak) i zakończenie są zawsze takie jak w rolce. Dla dłuższego materiału środek się powtarza,
   a jedno „elastyczne" ujęcie (monolog) przejmuje resztę czasu.
3. **Dosuwa cięcia do oddechu mowy.** W rolce 12 z 14 cięć wypada w pauzie lub na końcu frazy, więc narzędzie
   przesuwa każde cięcie (maks. o ok. 0,5 s) do najbliższej granicy zdania. Nie tnie Ci w pół słowa.
4. **Wstawki.** Ujęcia typu B to Twój B-roll (jeśli go podasz) albo zbliżenia z Twojego nagrania (twarz, dłonie),
   a głos leci bez przerwy, jak w wzorcu.
5. **Kadruje po Twojej twarzy.** Mierzy, jak duża i gdzie jest Twoja twarz, i w każdym ujęciu z mową dobiera
   zoom oraz położenie okna tak, by twarz miała rozmiar i miejsce z rolki (od 12% wysokości kadru w planie ogólnym
   do 36% w zbliżeniu). Sąsiednie ujęcia zawsze różnią się wyraźnie (jump cut). Opcje: `--framing`, `--max-zoom`.
6. **Kolory jak we wzorcu.** Dopasowuje jasność (krzywa tonalna), nasycenie, barwę szarych partii i winietę do
   rozkładu zmierzonego w rolce i nakłada to jedną tablicą LUT 3D (odcień skóry jest chroniony). Siła: `--look 0–1`.
7. **Napisy** w stylu rolki: 1–2 słowa naraz, krótkie słowa wiążą się z następnym, co kilka sekund wyróżniona fraza
   (stos z limonkowym akcentem, prawy górny/dolny róg, duży napis puenty). Czcionka Anton, rozmiar i pozycje
   zmierzone z rolki.
8. **Wejście z rozmycia** (focus-pull) w ujęciach, w których robi tak wzorzec, i **głośność −14 LUFS**.

## Wymagania

| Co | Po co | Jak zainstalować |
|---|---|---|
| **ffmpeg** (z ffprobe) | cały montaż | macOS: `brew install ffmpeg` · Windows: `winget install Gyan.FFmpeg` · Linux: `sudo apt install ffmpeg` |
| **Python 3.9+** | uruchamia narzędzie | <https://www.python.org/downloads/> |
| `faster-whisper` *(opcjonalnie)* | napisy (rozpoznawanie mowy) | `pip install faster-whisper` (przy pierwszym użyciu pobiera model, ok. 500 MB dla „small") |
| `pillow` *(opcjonalnie)* | grafiki na wideo i napisy w kroju marki (szablony `format2`, `format3`, `format4` i `motion`; w trybie motion cały obraz) | `pip install pillow` |
| `numpy` + `onnxruntime` *(opcjonalnie)* | kadrowanie po Twojej twarzy, dopasowanie kolorów, role ujęć w `analyze`, grafiki „za postacią” w Formacie 2 | `pip install numpy onnxruntime` (model twarzy YuNet, 230 KB, jest w paczce; model wycinania postaci, 26 MB, pobiera się raz przy pierwszym użyciu) |

Bez `faster-whisper` dostaniesz montaż bez napisów, bez `numpy`/`onnxruntime` kadry zostają stałymi zoomami
z szablonu, a kolory bez zmian. Narzędzie samo to zgłosi w ostrzeżeniach.

## Start

**Interfejs w przeglądarce (najprościej):**

```
python rolka.py serve
```

(Windows: dwuklik `start.bat`, macOS: dwuklik `start.command`; jeśli macOS go nie odpali, raz wpisz `chmod +x start.command`.) Pierwsze uruchomienie samo instaluje dodatki do folderu `.venv` obok programu (potrzebny internet, 5–15 minut); brakujący ffmpeg próbuje doinstalować przez `winget` (Windows) albo `brew` (macOS). Otworzy się strona: przeciągasz nagranie,
opcjonalnie B-roll, klikasz **Potnij**. Gotowe filmy lądują w `~/ReelCut/wyniki`.

**Terminal:**

```
python rolka.py moje_wideo.mp4
python rolka.py moje_wideo.mp4 --broll folder_z_ujeciami -o wynik.mp4
python rolka.py moje_wideo.mp4 --dry-run          # tylko plan cięć, bez renderu
python rolka.py nagranie.mp4 --template format3 --graphics scenariusz.txt --broll wstawki/   # Format 3: hasła ze słów w *gwiazdkach*, błysk przy wstawce
python rolka.py nagranie.mp4 --template format4 --graphics scenariusz.txt --broll wstawki/   # Format 4: każde słowo jako napis, karty, elipsa (pion)
python rolka.py nagranie_poziom.mp4 --template format4h --graphics scenariusz.txt          # Format 4 w poziomie 16:9
python rolka.py glos.m4a --template motion --graphics scenariusz.txt   # Motion: sam głos, obraz robią grafiki
```

Wynik: `moje_wideo_rolka.mp4` obok nagrania oraz `moje_wideo_rolka.slowa.json` (transkrypcja, patrz niżej).

## Jak nagrać, żeby wyszło jak we wzorcu

- **Pionowo (9:16)**, najlepiej 4K lub 1080p. Poziome nagranie zostanie przycięte do środka kadru. Wyjątek: szablon `format4h` (Format 4 w poziomie 16:9)
  chce nagrania poziomego, a pionowe przycina do pasa ze środka kadru; w obu przypadkach program ostrzega.
- **Mów w jednym ciągu** i patrz w obiektyw. Narzędzie samo zrobi zbliżenia i skróci pauzy.
- **Kamera nieruchoma, twarz w górnej połowie kadru, dół wolny** (tam lądują napisy). We wzorcu kadr zmienia
  się tylko cięciem; nie dodajemy ruchu kamery.
- **Ok. 34 sekundy po skróceniu pauz** daje montaż identyczny z rolką (`--no-snap`: co do klatki). Poniżej 16 s
  powstaje sam hak i zakończenie bez wstawek, a poniżej 11 s rytm jest ściskany. Dłuższe: środek rolki powtarza się,
  gęstość cięć rośnie od 24,7 do ok. 29 na minutę (tabela w [STYL.md](STYL.md)).
- **B-roll:** dodaj 6+ krótkich ujęć (detale, rekwizyty, dłonie, ekran). Bez nich wstawki to zbliżenia Twojego nagrania.
- **Światło i kolor** (wzorzec jest ciemny i stonowany) oraz **lista ujęć do nagrania**: [STYL.md](STYL.md).
- Bez rozpoznawania twarzy (brak `numpy`/`onnxruntime`) zbliżenia robimy wokół punktu `--focus 0.5,0.4`
  (X,Y od 0 do 1; domyślnie środek, trochę nad połową).

## Najważniejsze opcje

| Opcja | Znaczenie |
|---|---|
| `--broll FOLDER` | B-roll do wstawek (można podać kilka razy) |
| `--no-snap` | tnij **dokładnie** w sekundach szablonu, bez dosuwania do granic zdań |
| `--no-captions` | bez napisów |
| `--lang pl` | język mowy (`en`, `de`... albo `auto`) |
| `--model small` | dokładność rozpoznawania mowy: `base` (szybko), `small`, `medium`, `large-v3` (najdokładniej, wolno) |
| `--max-zoom 1.6` | największe przybliżenie kadru (`1.0` = bez zbliżeń; domyślnie automatycznie: ok. 1,6 dla 1080p, do 2,6 dla 4K) |
| `--framing auto` | kadrowanie po Twojej twarzy jak we wzorcu (`off` = stałe zoomy z szablonu, `on` = wymagaj) |
| `--look 1.0` | siła dopasowania kolorów do wzorca (0–1; `0` = obraz bez zmian; `0.6` łagodniej, gdy twarz wychodzi za ciemna) |
| `--no-tighten` | nie skracaj pauz |
| `--emphasis off` | bez wyróżnionych fraz w napisach |
| `--fps 30` | klatkaż wyniku (domyślnie 25 jak we wzorcu) |
| `--words plik.json` | użyj poprawionej transkrypcji zamiast rozpoznawania mowy |
| `--template ...` | inny szablon: `format2`, `format3`, `format4`, `format4h`, `motion`, `user/nazwa` albo plik `.json` (patrz niżej) |

Pełna lista: `python rolka.py cut --help`.

## Poprawianie napisów

Rozpoznawanie mowy czasem się myli (nazwy własne, żargon). Po każdym montażu obok wyniku leży
`*.slowa.json`: lista słów z czasami. Popraw literówki w polu `w` (czasów nie ruszaj), a potem:

```
python rolka.py moje_wideo.mp4 --words moje_wideo_rolka.slowa.json
```

Napisy zrobią się od nowa z Twojej wersji, bez ponownego rozpoznawania mowy.

## Własny szablon z innej rolki

```
python rolka.py analyze inna_rolka.mp4 -o moj_szablon
python rolka.py moje_wideo.mp4 --template user/moj_szablon
```

`analyze` wykrywa cięcia i ich długości, role ujęć (A = mówiąca głowa, B = wstawka) rozpoznaje po obecności twarzy
i mierzy w każdym ujęciu z mową rozmiar i położenie twarzy, rozkład kolorów (osobno A i B: jasność, nasycenie, barwa,
winieta, paleta, kolor skóry), tempo (cięcia na minutę, udział A/B, ruch w kadrze) i głośność. Wymaga to
`pip install numpy onnxruntime`; bez tego wszystkie ujęcia dostają rolę A i podajesz role sam: `--roles AABBABAB...`
(starsza metoda z `pip install "opencv-python-headless<5"` też działa, ale bez pomiaru kadrów i kolorów).
**Zawsze sprawdź wypisane role.** Dodatkowo `--speech` mierzy tempo mowy rolki (słowa na sekundę, pauzy, słowa
w każdym ujęciu; potrzebny `faster-whisper`). Szablon z nazwą (bez ścieżki) trafia do `~/ReelCut/szablony` i pojawia się
na liście w interfejsie. Szablon zawiera same liczby i kolory, bez obrazu i treści rolki. **Rolka pozioma daje szablon poziomy** (kanwa 1920×1080),
a napisy są wtedy przeliczane z kanwy 1080×1920 na tę kanwę, żeby nie wypadały poza kadr.

Kartę stylu (cięcia, tempo, kadry, kolory, napisy) każdego szablonu wypisze:

```
python rolka.py style                       # wbudowany szablon
python rolka.py style user/moj_szablon -o karta.md
```

## Ograniczenia (uczciwie)

- **Kopiowany jest montaż i wygląd, nie zawartość.** Rolka wzorcowa miała wiele lokacji i specjalnie nagranych ujęć
  (makro kawy, szyszka, dłoń z napisem). Z jednego nagrania takich ujęć się nie zrobi: dostaniesz ten sam rytm,
  te same proporcje kadrów i kolory, ale na Twoim materiale (lub B-rollu).
- **Dopasowanie kolorów jest statystyczne** (rozkład jasności i barwy wzorca, bez pary „przed/po"). Sprawdziłem je
  na zdjęciach, filmach syntetycznych i klatkach samej rolki sztucznie rozjaśnionych (błąd koloru względem oryginału
  spadł z ΔE 26 do 2), ale nie na Twoim nagraniu. Wzorzec ma skórę na ok. 30% waveformu, więc jasną twarz mocno
  przyciemni: zacznij od krótkiej próbki i ewentualnie `--look 0.6`. LUT i winieta działają na cały kadr, także na
  Twój B-roll.
- **Kadrowanie po twarzy** śledzi największą twarz w kadrze i jest niepewne przy szybkim ruchu i zasłoniętej twarzy
  (wtedy wracają stałe zoomy z szablonu).
- **Dobór wyróżnionych fraz jest heurystyczny** (liczby, końce zdań, krótka puenta po pauzie). Zwykle trafia,
  ale nie zastąpi oka montażysty. Wyłączysz to przez `--emphasis off`.
- **Nie ma muzyki ani efektów dźwiękowych**: we wzorcu też ich nie ma, to sam głos.
- **Nagrania HDR** (np. iPhone w Dolby Vision) mogą wyjść wyblakłe. Nagraj w SDR.
- **Pionowe zbliżenia z 1080p są miękkie** przy dużym zoomie. Zmniejsz `--max-zoom` albo nagraj w 4K.
- Przetestowane: Linux, ffmpeg 6.1, Python 3.13 (składnia sprawdzona dla 3.9+). Na Windows i macOS nie uruchamiałem.
- Szanuj prawa autorskie: używaj tylko własnych nagrań i B-rollu oraz muzyki, do których masz prawa.

## Testy

```
python -m unittest discover -s tests
```

ok. 600 testów (planista, pauzy, napisy łącznie z pomiarem pikseli, szablony, `analyze` z kadrami, kolorami i dynamiką,
moduł kolorów z LUT i winietą, wykrywanie twarzy i kadrowanie, karta stylu, silnik grafik Formatów 2, 3 i 4, scenariusz ze znacznikami,
serwer, end-to-end na syntetycznym wideo i samym głosie). Cały zestaw trwa ok. 10 minut.
Test end-to-end sprawdza, że cięcia w wyniku trafiają dokładnie w klatki szablonu, a test kadrowania, że twarz
w wyniku ma rozmiar i miejsce z planu. Część testów wymaga `numpy`/`onnxruntime`/Pillow (bez nich są pomijane).

## Pliki

```
rolka.py                      uruchamianie (python rolka.py ...)
start.bat / start.command     dwuklik: interfejs w przeglądarce
src/reelcut/                  kod (planner, framing, faces, look, render, captions, server, analyze, style...)
src/reelcut/data/             szablon rolki (JSON), czcionka Anton (SIL OFL, OFL-Anton.txt), model twarzy YuNet
                              (MIT, YuNet-LICENSE.txt), interfejs
tests/                        testy (tests/assets: zdjęcie NASA z domeny publicznej do testu twarzy)
ANALIZA.md                    wyniki analizy rolki wzorcowej (rytm, napisy)
START.md                      instrukcja od zera dla laika: instalacja, pierwszy film (intro „o mnie”), kolejne formaty, podcast, gdy coś nie działa
WORKFLOW.md                   ściąga: nowy film krok po kroku (Formaty 1, 2, 3, 4 i motion)
gotowe_teksty/                gotowy do wgrania tekst intro „o mnie” (z INTRO.md)
STYL.md                       styl do przeniesienia: kolory, kadry, dynamika, lista ujęć, format scenariusza
FORMAT2.md                    Format 2: gadająca głowa (zasady, słownik elementów, szkielet scenariusza)
FORMAT3.md                    Format 3: gadająca głowa v3 (cięcia, hasła, błysk: zasady, liczby ze wzorca, scenariusz, granice)
FORMAT4.md                    Format 4: kinetyczna typografia (pion i poziom: rytm, frazy, karty, elipsa: zasady, liczby ze wzorca, scenariusz, granice)
MOTION.md                     Motion (schemat z lektorem: zasady, liczby ze wzorca, scenariusz, granice)
PODCAST.md                    benchmark podcastu (rama nagrania i klipu: kadry, światło, cięcia, napisy, dźwięk, marka, lista kontrolna; docs/podcast_rama.png)
INTRO.md                      intro „o mnie”: scenariusz, rozpiska ujęć, co nagrać, decyzje (wersja w Formacie 4, pion i poziom, oraz szkic w Formacie 3)
PRZEJSCIA.md                  przejścia między scenami (rodzaje, zmierzone krzywe, składnia, granice)
GRAFIKI.md                    składnia znaczników scenariusza, plan JSON, elementy i pola (Formaty 2, 3, 4 i motion)
```
