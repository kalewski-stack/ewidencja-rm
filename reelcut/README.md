# Rolka: tnie Twoje wideo jak rolka wzorcowa

Wrzucasz swoje nagranie, dostajesz pionowy film (1080×1920) zmontowany według schematu rolki
<https://www.instagram.com/reel/DeuOaXKtPBb/>: ten sam rytm cięć, ten sam układ „mówiąca głowa + wstawki",
napisy słowo po słowie z wyróżnionymi frazami i dźwięk znormalizowany do −14 LUFS.

Wszystko liczy się na Twoim komputerze. Żaden plik nie jest nigdzie wysyłany.
Szczegóły analizy rolki (czasy cięć, zasady, wymiary napisów): [ANALIZA.md](ANALIZA.md).

## Co robi dokładnie

1. **Skraca martwe powietrze.** Pauzy dłuższe niż 0,5 s ścina do 0,35 s (rolka wzorcowa ma sam ciągły głos).
2. **Tnie obraz w rytmie rolki.** 15 ujęć: 2,56 s, 2,68 s, 1,60 s, 1,16 s... (pełna lista w [ANALIZA.md](ANALIZA.md)).
   Początek (hak) i zakończenie są zawsze takie jak w rolce. Dla dłuższego materiału środek się powtarza,
   a jedno „elastyczne" ujęcie (monolog) przejmuje resztę czasu.
3. **Dosuwa cięcia do oddechu mowy.** W rolce 12 z 14 cięć wypada w pauzie lub na końcu frazy, więc narzędzie
   przesuwa każde cięcie (maks. o ok. 0,3 s) do najbliższej granicy zdania. Nie tnie Ci w pół słowa.
4. **Wstawki.** Ujęcia typu B to Twój B-roll (jeśli go podasz) albo zbliżenia z Twojego nagrania (twarz, dłonie),
   a głos leci bez przerwy, jak w wzorcu. Ujęcia z mową dostają różne zbliżenia (jump cut).
5. **Napisy** w stylu rolki: 1–2 słowa naraz, krótkie słowa wiążą się z następnym, co kilka sekund wyróżniona fraza
   (stos z limonkowym akcentem, prawy górny/dolny róg, duży napis puenty). Czcionka Anton, rozmiar i pozycje
   zmierzone z rolki.
6. **Wejście z rozmycia** (focus-pull) w ujęciach, w których robi tak wzorzec, i **głośność −14 LUFS**.

## Wymagania

| Co | Po co | Jak zainstalować |
|---|---|---|
| **ffmpeg** (z ffprobe) | cały montaż | macOS: `brew install ffmpeg` · Windows: `winget install Gyan.FFmpeg` · Linux: `sudo apt install ffmpeg` |
| **Python 3.9+** | uruchamia narzędzie | <https://www.python.org/downloads/> |
| `faster-whisper` *(opcjonalnie)* | napisy (rozpoznawanie mowy) | `pip install faster-whisper` (przy pierwszym użyciu pobiera model, ok. 500 MB dla „small") |

Bez `faster-whisper` dostaniesz sam montaż, bez napisów. Narzędzie samo to zgłosi.

## Start

**Interfejs w przeglądarce (najprościej):**

```
python rolka.py serve
```

(Windows: dwuklik `start.bat`, macOS: dwuklik `start.command`; jeśli macOS go nie odpali, raz wpisz `chmod +x start.command`.) Otworzy się strona: przeciągasz nagranie,
opcjonalnie B-roll, klikasz **Potnij**. Gotowe filmy lądują w `~/ReelCut/wyniki`.

**Terminal:**

```
python rolka.py moje_wideo.mp4
python rolka.py moje_wideo.mp4 --broll folder_z_ujeciami -o wynik.mp4
python rolka.py moje_wideo.mp4 --dry-run          # tylko plan cięć, bez renderu
```

Wynik: `moje_wideo_rolka.mp4` obok nagrania oraz `moje_wideo_rolka.slowa.json` (transkrypcja, patrz niżej).

## Jak nagrać, żeby wyszło jak we wzorcu

- **Pionowo (9:16)**, najlepiej 4K lub 1080p. Poziome nagranie zostanie przycięte do środka kadru.
- **Mów w jednym ciągu** i patrz w obiektyw. Narzędzie samo zrobi zbliżenia i skróci pauzy.
- **Ok. 35 sekund po skróceniu pauz** daje montaż identyczny z rolką. Krótsze niż 11 s zostanie ściśnięte,
  dłuższe: środek rolki powtarza się cyklicznie.
- **B-roll:** dodaj 6+ krótkich ujęć (detale, rekwizyty, dłonie, ekran). Bez nich wstawki to zbliżenia Twojego nagrania.
- Na zbliżeniach po pozycji twarzy: `--focus 0.5,0.4` (X,Y od 0 do 1; domyślnie środek, trochę nad połową).

## Najważniejsze opcje

| Opcja | Znaczenie |
|---|---|
| `--broll FOLDER` | B-roll do wstawek (można podać kilka razy) |
| `--no-snap` | tnij **dokładnie** w sekundach szablonu, bez dosuwania do granic zdań |
| `--no-captions` | bez napisów |
| `--lang pl` | język mowy (`en`, `de`... albo `auto`) |
| `--model small` | dokładność rozpoznawania mowy: `base` (szybko), `small`, `medium`, `large-v3` (najdokładniej, wolno) |
| `--max-zoom 1.6` | największe przybliżenie kadru (`1.0` = bez zbliżeń) |
| `--grade cinema` | delikatna kinowa korekta kolorów (domyślnie obraz bez zmian) |
| `--no-tighten` | nie skracaj pauz |
| `--emphasis off` | bez wyróżnionych fraz w napisach |
| `--fps 30` | klatkaż wyniku (domyślnie 25 jak we wzorcu) |
| `--words plik.json` | użyj poprawionej transkrypcji zamiast rozpoznawania mowy |
| `--template ...` | inny szablon (patrz niżej) |

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

`analyze` wykrywa cięcia i ich długości, a role ujęć (A = mówiąca głowa, B = wstawka) rozpoznaje po obecności
twarzy, jeśli masz `pip install "opencv-python-headless<5"`. Bez tego wszystkie ujęcia dostają rolę A i podajesz
role sam: `--roles AABBABAB...`. **Zawsze sprawdź wypisane role.** Szablon z nazwą (bez ścieżki) trafia do
`~/ReelCut/szablony` i pojawia się na liście w interfejsie. Szablon zawiera same liczby, bez obrazu i treści rolki.

## Ograniczenia (uczciwie)

- **Kopiowany jest montaż, nie zawartość.** Rolka wzorcowa miała wiele lokacji i specjalnie nagranych ujęć
  (makro kawy, szyszka, dłoń z napisem). Z jednego nagrania takich ujęć się nie zrobi: dostaniesz ten sam rytm
  i te same typy kadrów, ale na Twoim materiale (lub B-rollu).
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

70 testów (planista, pauzy, napisy łącznie z pomiarem pikseli, szablony, `analyze`, end-to-end na syntetycznym wideo).
Test end-to-end sprawdza, że cięcia w wyniku trafiają dokładnie w klatki szablonu.

## Pliki

```
rolka.py                      uruchamianie (python rolka.py ...)
start.bat / start.command     dwuklik: interfejs w przeglądarce
src/reelcut/                  kod (planner, render, captions, server, analyze...)
src/reelcut/data/             szablon rolki (JSON), czcionka Anton (licencja SIL OFL, OFL-Anton.txt), interfejs
tests/                        testy
ANALIZA.md                    wyniki analizy rolki wzorcowej
```
