# Analiza rolki DeuOaXKtPBb

Źródło: <https://www.instagram.com/reel/DeuOaXKtPBb/> (autorka: jwnuk.creator). Poniżej wyłącznie parametry montażu
zmierzone z pliku: czasy, kadry, wymiary. Nie ma tu obrazu ani treści z rolki.

## Parametry techniczne

| | |
|---|---|
| Format | 1080×1920 (9:16), 25 kl./s, 34,00 s (850 klatek) |
| Dźwięk | tylko głos, bez muzyki i efektów; ciągły pod wszystkimi cięciami |
| Głośność | −14,7 LUFS, szczyt −0,7 dBTP, rozrzut LRA 2,9 LU (ffmpeg `loudnorm`; pomiar innej kopii pliku dał −14,5 / −0,6 / 2,7) |
| Cięcia | 14 twardych cięć (15 ujęć), zero przejść typu crossfade |

## Rytm cięć: 15 ujęć

A = mówiąca głowa, B = wstawka (głos leci dalej). Klatki przy 25 kl./s.

| # | od | do | dł. [s] | klatek | rola | kadr / uwagi |
|--:|--:|--:|--:|--:|:-:|---|
| 1 | 0,00 | 2,56 | 2,56 | 64 | A | szeroki, haczyk: duże liczby w napisach |
| 2 | 2,56 | 5,24 | 2,68 | 67 | A | średni, inne ustawienie kamery |
| 3 | 5,24 | 6,84 | 1,60 | 40 | B | makro, detal |
| 4 | 6,84 | 8,00 | 1,16 | 29 | B | ekran telefonu, przeostrzanie |
| 5 | 8,00 | 10,76 | 2,76 | 69 | A | średni |
| 6 | 10,76 | 12,56 | 1,80 | 45 | B | światło, klimat |
| 7 | 12,56 | 14,28 | 1,72 | 43 | A | szeroki, postać w całości |
| 8 | 14,28 | 17,36 | 3,08 | 77 | B | rekwizyt na jednolitym tle |
| 9 | 17,36 | 19,04 | 1,68 | 42 | B | rekwizyt, ruch ręki |
| 10 | 19,04 | 20,08 | 1,04 | 26 | A | akcja do kamery |
| 11 | 20,08 | 22,60 | 2,52 | 63 | B | dłonie na klawiaturze |
| 12 | 22,60 | 24,48 | 1,88 | 47 | A | bardzo bliski kadr |
| 13 | 24,48 | 25,36 | 0,88 | 22 | A | puenta: najbliższy kadr, **wejście z rozmycia**, duży napis |
| 14 | 25,36 | 31,00 | 5,64 | 141 | A | monolog (najdłuższe ujęcie) |
| 15 | 31,00 | 34,00 | 3,00 | 75 | A | zamknięcie, **wejście z rozmycia**, wezwanie do działania |

Statystyki: średnia 2,27 s, mediana 1,88 s, najkrótsze 0,88 s, najdłuższe 5,64 s.
Rola A to 22,2 s (65%), rola B to 11,8 s (35%).

## Zasady, które z tego wynikają

1. **Trzy części.** Hak (ujęcia 1–2, 5,24 s, 15%), środek (3–12, 19,24 s, 57%), zakończenie (13–15, 9,52 s, 28%).
2. **Wstawki B pojawiają się dopiero po haku** i potem przeplatają się z A w parach (BB, A, B, A, BB, A, B, A).
3. **Cięcia idą za mową, nie za metronomem.** 12 z 14 cięć wypada w pauzie lub na końcu frazy (±0,06 s),
   jedno na początku słowa, jedno w środku słowa. Dlatego narzędzie dosuwa cięcia do granic zdań.
4. **Tnie się obraz, dźwięk jest jednym torem.** Wstawki B zakrywają mówiącą osobę, ale głos się nie przerywa.
5. **Sąsiednie ujęcia A zawsze różnią się kadrem** (szeroki, średni, bliski), inaczej cięcie byłoby niewidoczne.
6. **Efekt wejścia z rozmycia** w 2 ujęciach (13 i 15): pierwsza klatka mocno rozmyta, ostrość wraca w ok. 0,3 s.

## Napisy

Wymiary w pikselach przy 1080×1920.

| Element | Zmierzone |
|---|---|
| Krój | ciężki, wąski groteskowy; w wolnej licencji najbliżej: **Anton** rozciągnięty do 113% (różnica szerokości słów ≤ 2,5%) |
| Napis bieżący | wersaliki 57 px (3% wysokości), górna krawędź 1211 px (63%), wyśrodkowany; 1–2 słowa naraz |
| Grupowanie | krótkie słowa (do 3 liter) wiążą się z następnym; interpunkcja zostaje |
| Czas | pojawia się na początku słowa (±0,05 s), zmienia się z następnym |
| Stos „środkowy z akcentem" | 3 wiersze: 68 / **105** / 68 px; środkowy w kolorze `#E2FB77` (limonka); górna krawędź 1123 px |
| Stos „prawy górny" | wersaliki 75 px, wyrównane do prawej (x = 1005), od y = 390, odstęp wierszy 95 px |
| Stos „prawy dolny" | wersaliki 100 px, do prawej (x = 1017), od y = 1204, odstęp 130 px |
| Stos „środkowy" | 4 wiersze po ok. 80 px, odstęp 124 px, od y = 668 |
| Duży napis (puenta) | wersaliki 205 px (11% wysokości), środek y = 1260, szerokość do 926 px |
| Wygaszanie stosów | 0,25–1,0 s po ostatnim słowie; pod stosem środkowym/dolnym zwykłe napisy są wstrzymane |
| Animacja | wskakuje w 1–2 klatki, wiersze stosu dochodzą po kolei, wraz ze słowami |

Wyróżnione frazy (5 w 34 s, czyli co ok. 6,8 s) układają się w kolejności: stos środkowy z akcentem,
prawy górny, prawy dolny, środkowy, na końcu duży napis puenty.

## Czego narzędzie nie odtwarza

- Samych ujęć: lokacji, makro, rekwizytów, dłoni z napisem na skórze (to treść, nie montaż).
- Wielu ustawień kamery: autorka nagrała tę samą wypowiedź w kilku miejscach. Z jednego nagrania powstają zbliżenia.
- Samego światła: kolory dopasowujemy statystycznie (`--look`), ale ciepłych lamp w kadrze i zielonkawych ścian nie da się
  dorobić w montażu. Opis i wartości: [STYL.md](STYL.md).
- Animacji wjazdu małych liter w drobnych dopowiedzeniach (tu zwykły napis).

## Jak to zmierzono

Wykrywanie cięć: wskaźnik zmiany sceny ffmpeg dla każdej klatki (piki 0,20–0,43 na tle 0,002) z ręczną weryfikacją
na klatkach. Twarze: model YuNet (ONNX) co 0,12 s, mediana wykryć w ujęciu; porównałem go z OpenCV `FaceDetectorYN`
(średnia różnica ramki ok. 0,3 px). Kolory: rozkład L* i barwa w CIE Lab (D65) na klatkach co 0,2 s, bez pikseli
napisów; paleta metodą k-średnich w Lab. Ruch kamery: śledzenie cech (przepływ optyczny) oraz kontrola tła na klatkach. Wymiary napisów: maski pikseli na klatkach pełnej rozdzielczości. Zgodność z mową: transkrypcja
Whisper (słowa ze znacznikami czasu) zestawiona z cięciami. Krój: porównanie szerokości słów i „gęstości tuszu"
dla 11 wolnych krojów. Polecenie `python rolka.py analyze` powtarza wykrywanie cięć, ról, kadrów twarzy, kolorów i tempa na dowolnej rolce
i na tej daje te same 15 ujęć i te same role co ręczna analiza (a kadry twarzy z dokładnością do 0,005 kadru
w 8 z 9 ujęć z mową; dziewiąte, ujęcie 10, ma 1 s i twarz porusza się w nim szybko).

## Kolory, kadry i dynamika

Zmierzone w drugim etapie analizy, opisane w [STYL.md](STYL.md) (z kartą stylu generowaną z szablonu):
rozkład jasności (mediana L* 21, cienie 8%, światła do 72–78% waveformu), stonowana barwa z ciepłymi półtonami
i zielonkawymi światłami, winieta, paleta, kolor skóry, rozmiar i położenie twarzy w każdym ujęciu (12% → 36% wysokości
kadru), statyczna kamera w ujęciach z mową, tempo (24,7 cięć na minutę) i budżet słów na ujęcie (123 słowa, 3,6 słowa/s).
