# Workflow: nowy film w stylu rolki (ściąga)

Wrzucasz dwie rzeczy: **jedno nagranie z mową** i **kilka klipów B-roll**. Reszta (cięcia, kadry po Twojej twarzy,
kolory, napisy, głośność) dzieje się sama. Szczegóły stylu: [STYL.md](STYL.md).

## Jednorazowo (ok. 10 minut)

1. Zainstaluj ffmpeg i Python 3.9+ (macOS: `brew install ffmpeg`, Windows: `winget install Gyan.FFmpeg`).
2. `pip install faster-whisper numpy onnxruntime` (napisy, kadrowanie po twarzy, kolory; bez tych pakietów dostaniesz
   sam montaż, a narzędzie zgłosi, czego brakuje).
3. Rozpakuj paczkę. Dwuklik `start.bat` (Windows) albo `start.command` (macOS) otwiera stronę narzędzia.
4. Zrób próbę na 20-sekundowym nagraniu: przy pierwszych napisach pobiera się model mowy (ok. 500 MB).

## Każdy nowy film

| Krok | Co robisz | Czas (szacunek) |
|---|---|---|
| 1. Scenariusz | Wg [STYL.md](STYL.md), rozdział „Format scenariusza": 8 beatów, ok. 123 słowa na 34 s (3,6 słowa/s), zdania po 2–13 słów, liczba w pierwszych 5 s, puenta z dwóch słów po krótkiej pauzie. | 15–20 min |
| 2. Nagranie z mową | Pion 9:16, najlepiej 4K, statyw, jedno ustawienie kamery, **jeden ciągły take** (30–40 s po skróceniu pauz). Twarz w górnej połowie kadru, dół wolny na napisy. Ciemne, ciepłe światło (STYL.md, rozdział „Kolory"). Pauza przed puentą najwyżej 0,5 s (dłuższe narzędzie skraca do 0,35 s). | 10–20 min |
| 3. B-roll | 6–8 klipów pionowych, po 4–6 s (minimum 3,2 s): makro detalu, ekran telefonu, światło i klimat, rekwizyt na jednolitym tle (2 klipy, najlepiej pomarańczowym), ruch ręki, dłonie na klawiaturze. Dźwięk niepotrzebny. | ok. 15 min |
| 4. Cięcie | Uruchom narzędzie, przeciągnij nagranie, **zaznacz wszystkie klipy B-roll i przeciągnij je naraz** (pliki, nie folder), kliknij „Potnij". Ustawienia zostaw domyślne. | 2–5 min pracy komputera |
| 5. Kontrola | Cztery rzeczy poniżej. | 5 min |
| 6. Publikacja | Gotowy plik leży w `~/ReelCut/wyniki`. | |

Terminal zamiast strony: `python rolka.py nagranie.mp4 --broll folder_z_b_rollem` (tu można podać folder).

## Kontrola po cięciu

1. **Ostrzeżenia** pod podglądem: brak pakietów, zbyt krótkie nagranie (poniżej 16 s nie ma wstawek B), pominięte klipy.
2. **Twarz**: w każdym ujęciu nad pasem napisów i nieucięta. Jeśli kadry są złe: odznacz „Kadruj według mojej twarzy"
   albo wpisz „Maksymalne zbliżenie" 1,3.
3. **Kolor**: skóra za ciemna albo płaska → suwak „Kolory jak we wzorcu" na 60% i potnij jeszcze raz (wzorzec jest
   bardzo ciemny: skóra na ok. 30% waveformu).
4. **Napisy**: przeczytaj całość. Literówki popraw w pobranym pliku `*.slowa.json` (pole `w`, czasów nie ruszaj) i uruchom
   w terminalu: `python rolka.py nagranie.mp4 --words plik.slowa.json` (bez ponownego rozpoznawania mowy).

## Szybciej

- Szkic bez napisów: `python rolka.py nagranie.mp4 --no-captions --preset veryfast`.
- Samo sprawdzenie planu (kilka sekund, bez renderu): `python rolka.py nagranie.mp4 --dry-run`.
- Ten sam wynik za każdym razem: B-roll jest przydzielany z ziarnem (`--seed 7`); inny układ wstawek: `--seed 8`.
- Inny styl: `python rolka.py analyze inna_rolka.mp4 -o moj_styl`, potem `--template user/moj_styl`.

## Zasada kciuka

Im bliżej 34 s i 123 słów, tym bliżej oryginału (przy `--no-snap` cięcia są co do klatki jak we wzorcu). Dłuższy materiał
działa, ale tempo rośnie z 24,7 do ok. 29 cięć na minutę (tabela w STYL.md).
