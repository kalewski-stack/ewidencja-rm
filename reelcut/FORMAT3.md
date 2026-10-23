# FORMAT 3: gadająca głowa v3

Twarde cięcia co kilka sekund, wstawki z innego źródła, a nad tym **hasła z jednym dużym słowem**: wyróżnione słowo wchodzi
żółtą kursywą, nad nim i pod nim drobne słowa wyjustowane do jego szerokości, wszystko w chwili, gdy to mówisz. Przy wstawce
biały błysk. Narzędzie robi to w Twoich kolorach i kroju marki „Linia Kalewski”, a czasy ustawia na słowach, które mówisz.

Nazwa: użytkownik powiedział „gadająca głowa wersja 3”, w narzędziu to **Format 3** (szablon `format3`).

- **Format 1** to mówiąca głowa z cięciami i B-rollem (rolka DeuOaXKtPBb): szablon `format1`, opis w [STYL.md](STYL.md).
- **Format 2** to jeden take bez cięć z animowanymi grafikami: szablon `format2`, opis w [FORMAT2.md](FORMAT2.md).
- **Format 3** to ten plik: cięcia jak w Formacie 1, ale napisy, hasła i błysk rysuje warstwa grafik (kolory i krój marki),
  a składnia scenariusza jest ta z Formatu 2 ([GRAFIKI.md](GRAFIKI.md)).
- **Motion** to obraz bez mówiącej głowy: [MOTION.md](MOTION.md).

Wzorzec: jedna rolka (DcS25CKkmFM). W repozytorium są tylko liczby, kolory i opis konstrukcji, bez obrazu, mowy i tekstów z rolki.
Jedna rolka to nie statystyka: liczby poniżej to jej pomiar, a nie mediana kilku.

## W skrócie

Karta stylu z tabelą kadrów każdego ujęcia: `python rolka.py style format3` (jest też na końcu tego pliku).

| Wymiar | Wzorzec |
|---|---|
| Długość | 55,0 s, 19 ujęć, 18 cięć (19,6 na minutę), pion 9:16 |
| Ujęcia | średnio 2,9 s (mediana 3,3 s), od 0,9 do 5,7 s; wszystkie cięcia twarde |
| Mówiąca głowa i wstawki | 83% czasu to mówiąca głowa (A), 17% to wstawki (B): dwa bloki po dwa ujęcia, głos leci dalej |
| Twarz | wysokość od 18% (najszerszy kadr) do 28% (najbliższy), środek twarzy na 32–36% wysokości kadru, więc dół zostaje na napisy |
| Napisy | porcje do 4 słów wyskakują naraz, białe, pogrubione; wysokość wersalików 2,25% kadru (43 px z 1920), górna krawędź na 50,4% |
| Hasło | duże słowo ok. 10% wysokości kadru, małe wiersze 44% jego wielkości, blok od 48,6% wysokości, najwyżej 78% szerokości |
| Błysk | biała nakładka, 86% krycia w pierwszej klatce nowego ujęcia, znika w 7 klatkach (0,23 s); tylko przy drugiej wstawce |
| Mowa | 3,3 słowa na sekundę, 11 pauz od 0,15 s, najdłuższa 0,56 s |
| Dźwięk | −14,6 LUFS, szczyt −0,1 dBTP, zakres głośności 6,9 LU |
| Kolory | napisy białe, duże słowo żółte; w narzędziu zawsze kolory marki. Kolory nagrania zostają bez zmian |

## Jak zbudowany jest film

Zasady widoczne w rolce wzorcowej (rytm i geometria z pomiaru klatek, reszta z oglądania):

1. **Cięcie to zmiana kadru, nie efekt.** Sąsiednie ujęcia z tej samej kamery różnią się rozmiarem twarzy (18%, 21%, 28%...),
   więc każde cięcie widać. Nie ma przejść, rozmyć ani najazdów między ujęciami mówionymi.
2. **Wstawka przerywa głowę, ale głos leci dalej.** Dwa bloki po dwa ujęcia (pierwszy ok. 4 s, drugi ok. 5 s): materiał z innego
   źródła niż mówiąca głowa. W pierwszym bloku cięcia są twarde, w drugim wejście i wyjście przykrywa biały błysk.
3. **Hasło tylko przy tezie.** W 55 sekundach jest ich ok. pięciu: jedno–dwa słowa kluczowe wchodzą dużym krojem i znikają
   razem z końcem myśli. Między hasłami idą zwykłe napisy.
4. **Napisy pojawiają się porcjami.** Cała porcja (1–4 słowa) wyskakuje w jednej klatce i zostaje, aż zacznie się następna. Nic nie
   rośnie ani nie wjeżdża.
5. **Dodatkowe grafiki są małe i rzadkie.** W rolce są trzy: kapsułki z hasłami wokół ikony, grupki ikon ludzi i karta
   ze zrzutem ekranu. Odpowiedniki w narzędziu to `pigułki`, `profil` i `karty` z Formatu 2.

## Hasło (lockup)

Hasło powstaje samo ze słów, które w scenariuszu otoczysz gwiazdkami: `Co ma się *zmienić* po tym evencie?`

```
          Co  ma  się            ← do 3 małych słów przed (w obrębie zdania), wyjustowane do szerokości dużego słowa
          zmienić                ← duży wiersz: 1-2 słowa, szeryfowa kursywa, żółty
       po   tym   evencie?       ← do 3 małych słów za
```

- **Duże słowa.** Jedno albo dwa. Dłuższe wyróżnienie program tnie do dwóch pierwszych słów (reszta idzie do małego wiersza pod nimi)
  i mówi o tym w ostrzeżeniu.
- **Małe słowa** to słowa wypowiedziane tuż przed i tuż za wyróżnionymi, ale **nie dalej niż do końca zdania, przecinka albo pauzy
  dłuższej niż 0,45 s**. Słowa leżące między dwoma hasłami dzielą się po równo.
- **Układ jest policzony z góry**: każde słowo wskakuje od razu (jedna klatka, bez animacji) w chwili, gdy je wypowiadasz, i nic się
  potem nie przesuwa. Małe wiersze są wyjustowane do szerokości dużego słowa; jedno długie małe słowo rozstrzela litery.
  Jeśli małe słowa są szersze niż duże, blok się poszerza (do 78% szerokości kadru), a za długi wiersz program zgłasza w ostrzeżeniu.
- **Na czas hasła jego słowa znikają ze zwykłych napisów**, więc nic nie pojawia się dwa razy. Hasło schodzi, zanim wrócą napisy.
- **Krój.** Duże słowo to Instrument Serif Italic (krój szeryfowy marki), powiększony o 30%, bo jest węższy od grotesku. Małe słowa to
  Bricolage Grotesque. Gruby sans zamiast kursywy: `big_font: display` w planie JSON (patrz [GRAFIKI.md](GRAFIKI.md)).
- **Nie rób haseł częściej niż co ok. 10 sekund.** Wzorzec ma ich ok. pięciu w 55 s.

Hasło możesz też wpisać ręcznie w planie JSON (element `lockup`, wiersze i czasy słów): [GRAFIKI.md](GRAFIKI.md).

## Błysk

Biała nakładka na całym obrazie, także na nagraniu pod spodem: krycie rośnie do 86% w pierwszej klatce nowego ujęcia i schodzi do zera
w siedmiu klatkach. W szablonie jest przy **drugiej wstawce**: błysk na wejściu w nią i na wyjściu z niej. Pierwsza wstawka ma
twarde cięcia. Gdy film jest dłuższy niż wzorzec, środek się powtarza, ale wstawka nie wypada zaraz po wstawce, a błysk idzie
razem z wstawką, która go ma.

Własny błysk dołożysz znacznikiem `{przejście: błysk}` (w chwili, gdy zaczynasz mówić następne słowo). Przejście wpisane przez Ciebie
w odległości 0,1 s od cięcia zastępuje błysk z szablonu. Pozostałe rodzaje przejść (rozmycie, najazd, przesunięcie, kurtyna)
obrabiają same grafiki, nie nagranie: [PRZEJSCIA.md](PRZEJSCIA.md).

## Jak zrobić film w Formacie 3

1. **Napisz scenariusz**: tekst, który powiesz, z gwiazdkami przy słowach kluczowych (jedno–dwa słowa) i, jeśli chcesz, z grafikami
   w `{ }` (przykład niżej). Na 45–60 s to ok. 150–200 słów, 4–6 haseł.
2. **Nagraj** w pionie, na statywie, **szeroko**: twarz ok. 15% wysokości kadru (najszerszy kadr wzorca ma 18%, a montaż przybliża
   do 28%), najlepiej w 4K. Wstawki: nagraj osobne ujęcia albo przygotuj klipy; bez nich program zrobi detale z Twojego nagrania.
3. **Surowiec** (raz, to trwa najdłużej): `python rolka.py nagranie.mp4 --template format3 -o surowiec.mp4`. Powstaje też
   `surowiec.slowa.json` z czasami słów.
4. **Podgląd haseł** na jednej klatce (sekundy): zrób zrzut dowolnej klatki swojego nagrania (`klatka.jpg`) i uruchom
   `python rolka.py grafiki scenariusz.txt --template format3 --words surowiec.slowa.json --tlo klatka.jpg --klatka 12`.
   Tłem ma być **zdjęcie**, nie surowiec: surowiec ma już wypalone napisy, które podwoiłyby te z podglądu. Podgląd pokazuje napisy
   i hasła (bez cięć i błysku, bo te zależą od montażu); bez `--tlo` jest ciemne tło.
5. **Film**: `python rolka.py nagranie.mp4 --template format3 --graphics scenariusz.txt --broll wstawki/ --words surowiec.slowa.json`.
   W interfejsie (`python rolka.py serve`) wybierz „Format 3: gadająca głowa v3”, w kroku 3 przeciągnij scenariusz, a wstawki w kroku 2.
   Poprawka gwiazdek albo literówki w scenariuszu to ta sama komenda: z `--words` nie rozpoznaje mowy od nowa.

Napisy i hasła biorą słowa z Twojego scenariusza (poprawna pisownia, wielkość liter, interpunkcja), a czasy z mowy. Działa, gdy mowa zgadza się
ze scenariuszem w co najmniej 80%; przy improwizacji program zostaje przy rozpoznanej mowie i mówi o tym w ostrzeżeniu. Wyróżnienia
`*tak*` działają w obu przypadkach.

### Szkielet scenariusza (hipotetyczny, podmień na swój temat)

<!-- scenariusz-f3:start -->
```
# Film ok. 25 s: „Cel przed budżetem” (szkielet, tekst hipotetyczny; na 45-60 s dopisz kolejne punkty)
Zanim zapłacisz za scenę, odpowiedz na jedno pytanie. Co ma się *zmienić* po tym evencie?
Nie ile osób przyjdzie i nie jak będzie wyglądał catering. Tylko co *konkretnie* zmieni się w decyzjach ludzi, których zapraszasz.
{pigułki: Cel; Uczestnik; Ślad | strefa: dół | do: po kolacji} Po pierwsze cel, który da się policzyć. Po drugie uczestnik, który ma wyjść z innym zdaniem. Po trzecie ślad, który zostaje po tygodniu, a nie po kolacji.
Dopiero wtedy wybierasz dostawcę. Nie do ceny, tylko *do zadania*.
Pomiar nie jest dodatkiem na koniec. Pomiar jest *pierwszą rozmową*.
```
<!-- scenariusz-f3:end -->

Znaczniki w `{ }` działają jak w Formacie 2 (od następnego słowa, koniec: `do: fraza`, `{/typ}` albo `czas: sekundy`): pełna składnia
w [GRAFIKI.md](GRAFIKI.md). Gwiazdki same wystarczą: scenariusz bez żadnego znacznika `{ }`, ale z `*wyróżnieniami*`, jest poprawnym planem.

## Karta stylu

<!-- karta-f3:start -->
# Karta stylu: Format 3: gadająca głowa v3 (cięcia i wstawki z błyskiem, hasła z dużym słowem, napisy marki)

Źródło: https://www.instagram.com/reel/DcS25CKkmFM/. Format 1080x1920, 30 kl./s, 55,0 s.

## Cięcia i tempo

- 18 cięć w 55,0 s, czyli 19,6 cięć na minutę.
- Ujęcie trwa średnio 2,90 s (mediana 3,30, od 0,90 do 5,67 s).
- Hak 3,3 s, rozwinięcie 38,6 s, zakończenie 13,1 s.
- Mówiąca głowa (A) to 83% czasu, wstawki (B) 17%.
- Wzór ujęć: `ABBAAAAAAAAAAABBAAA`. Ujęcie elastyczne (przejmuje różnicę długości): nr 17, 5,67 s.
- Rytm (s): 3,30A, 2,00B, 2,10B, 4,03A, 3,40A, 2,97A, 1,60A, 4,63A, 0,90A, 2,13A, 4,30A, 3,33A, 0,90A, 1,30A, 1,33B, 3,67B, 5,67A, 3,40A, 4,07A.
- Pauzy w mowie: powyżej 0,50 s skracane do 0,35 s.
- Głośność rolki: -14,6 LUFS, szczyt -0,1 dBTP, zakres LRA 6,9 LU (cel w szablonie: -14,6 LUFS).
- Mowa: 3,3 słowa na sekundę, 181 słów w całości.
- Słów w kolejnych ujęciach: 8, 6, 4, 15, 11, 12, 2, 13, 2, 7, 17, 13, 1, 6, 4, 11, 21, 16, 12.
- Pauzy między słowami (od 0,15 s): 11, mediana 0,28 s, najdłuższa 0,56 s.

## Kadry

Rozmiar i położenie twarzy w ujęciach z mową, jako ułamki kadru (x: 0% = lewa krawędź, y: 0% = góra).

| Ujęcie | Czas (s) | Plan | Twarz: wysokość | Twarz: x | Twarz: y | Oczy: y |
|---|---|---|---|---|---|---|
| 1 | 0,0-3,3 | plan średni | 23% | 54% | 34% | 32% |
| 4 | 7,4-11,4 | plan ogólny | 22% | 52% | 32% | 30% |
| 5 | 11,4-14,8 | plan ogólny | 20% | 53% | 34% | 32% |
| 6 | 14,8-17,8 | plan ogólny | 18% | 53% | 34% | 32% |
| 7 | 17,8-19,4 | plan ogólny | 21% | 55% | 36% | 33% |
| 8 | 19,4-24,0 | plan ogólny | 19% | 51% | 35% | 32% |
| 9 | 24,0-24,9 | plan ogólny | 22% | 50% | 36% | 33% |
| 10 | 24,9-27,1 | plan ogólny | 20% | 52% | 35% | 32% |
| 11 | 27,1-31,4 | plan ogólny | 20% | 51% | 33% | 30% |
| 12 | 31,4-34,7 | plan ogólny | 20% | 52% | 33% | 30% |
| 13 | 34,7-35,6 | plan średni | 28% | 56% | 34% | 32% |
| 14 | 35,6-36,9 | plan ogólny | 19% | 54% | 34% | 32% |
| 17 | 41,9-47,6 | plan średni | 23% | 53% | 33% | 30% |
| 18 | 47,6-51,0 | plan ogólny | 19% | 50% | 33% | 31% |
| 19 | 51,0-55,0 | plan średni | 23% | 51% | 32% | 30% |

Drabinka: najszerszy kadr ma twarz 18% wysokości, zbliżenia do 28% (1,5 raza więcej). Środek twarzy leży między 32% a 36% wysokości kadru, więc dół kadru zostaje wolny na napisy.

Gdy nie ma osobnego materiału na wstawkę B, wycinamy ją z nagrania z mową:
- detal 1: detal: twarz i oczy (zbliżenie na twarz), zoom x1,60
- detal 2: detal: klatka piersiowa i dłonie (pod twarzą), zoom x1,45

## Kolory

Szablon nie zmienia kolorów nagrania. Kolory mają grafiki i napisy, z marki.

Marka: Linia Kalewski.

| Rola | Kolor | Do czego |
|---|---|---|
| text | `#FFFFFF` | napisy i tekst na grafikach |
| title | `#FFD346` | tytuły |
| accent | `#795DFF` | etykiety, linie, pierścienie |
| accent_strong | `#6343FF` | plakietki i tła kart |
| highlight | `#FFD346` | jedyny jasny element naraz: liczba, kursor, aktywna pozycja, słowo kluczowe |
| panel | `#1B1440` | tło paneli |

## Napisy, hasła i błyski

- Napisy rysuje warstwa grafik, w kroju marki: statyczne porcje do 4 słów (cała porcja pojawia się naraz, bez animacji), wysokość wersalików 2,2% wysokości kadru (ok. 43 px z 1920), górna krawędź na 50,4% wysokości, pod brodą. Kolor biały, z lekkim cieniem. Słowa biorą się z Twojego scenariusza (poprawna pisownia), a czasy z mowy; bez scenariusza z rozpoznanej mowy.
- Hasło: słowa wyróżnione w scenariuszu (`*tak*`) wchodzą jako blok. Duży wiersz (2 słowa najwyżej, szeryfowa kursywa, żółty, ok. 10,1% wysokości kadru), nad nim do 3 małych słów, pod nim do 3: małe wiersze są wyjustowane do szerokości dużego słowa, a blok ma najwyżej 78% szerokości kadru. Blok zaczyna się na 48,6% wysokości. Każde słowo wskakuje od razu w chwili, gdy pada (bez animacji), a na czas hasła jego słowa znikają ze zwykłych napisów. Hasło nie wychodzi poza zdanie ani poza pauzę dłuższą niż 0,45 s.
- Błysk: biała nakładka na całym obrazie, także na nagraniu: krycie rośnie do 86% w pierwszej klatce nowego ujęcia i schodzi do zera w 7 klatkach (0,23 s). We wzorcu jest tylko przy drugiej wstawce, na wejściu w nią i na wyjściu z niej; pozostałe cięcia, także wejście w pierwszą wstawkę, są twarde.
- Przejścia w planie grafik: `przejście` (rozmycie, najazd, przesunięcie, kurtyna, błysk). Przy nagraniu pod spodem działa pełnym obrazem tylko błysk, reszta obrabia same grafiki (opis w PRZEJSCIA.md).
- Plan grafik to scenariusz ze znacznikami `{...}` albo plik JSON (`--graphics`); wyróżnienia `*tak*` wystarczą, żeby powstały hasła.
- Elementy planu:
  - `title`: duży napis (żółty, szeryfowy kursywą albo krojem marki) z małym słowem-akcentem nad prawym końcem
  - `badge`: plakietka: numer w kole i tytuł obok, np. „1 Scenariusz”
  - `cards`: miniatury 9:16 z etykietą (pogrubioną, szeryfową kursywą albo żółtą), punktami i licznikiem wyświetleń pod spodem: w rzędzie, siatce albo w dowolnym miejscu i pod kątem, jedna może się powiększyć
  - `profile`: chip z awatarem (Twoja twarz z nagrania), licznikiem, paskiem postępu i kursorem jadącym po kadrze
  - `pills`: krótkie hasła z ikoną, wlatujące jedna po drugiej (biała, szklana, fioletowa, żółta)
  - `chips`: małe kafelki z etykietą i liczbą, np. wartości do porównania
  - `steps`: lista kroków w szklanym panelu, która przewija się do aktywnego kroku
  - `axis`: wykres schodkowy z podpisanymi punktami (rosnący trend)
  - `bars`: wiersze z etykietami (podwójne, pojedyncze, ze spinnerem)
  - `callout`: wyróżnienie: ikona, tytuł i tekst „pisany” na żywo, opcjonalnie karta po prawej
  - `stat`: duża liczba odliczana od zera z podpisem i paskiem
  - `illustration`: obraz z miękką poświatą, np. nad głową; może jechać po ścieżce, rosnąć, obracać się i wychodzić poza kadr
  - `arrow`: strzałka albo linia rysowana na żywo: łuk, linia ciągła, przerywana lub kropkowana, grot otwarty lub pełny
  - `labels`: opisy z cienką linią i kropką, które wskazują miejsca na obrazie albo karcie
  - `text`: tekst z wyróżnieniami (*żółte*, _szeryfowe_), odsłaniany albo pisany na żywo, z podkreśleniem, pędzlem lub nawiasem
  - `list`: wiersze pojawiające się po kolei z „pisaniem” treści, polami do odhaczenia albo w dwóch kolumnach (porównanie)
  - `ring`: pierścień z kropek wokół wskazanego miejsca: cały albo dwa łuki
  - `lockup`: hasło: blok z dużym słowem kluczowym (szeryfowa kursywa, żółty) i małymi słowami nad nim i pod nim, wyjustowanymi do jego szerokości; słowa wskakują w chwili, gdy padają; powstaje samo ze słów wyróżnionych w scenariuszu (`*tak*`)
- Efekt: `blur` rozmywa i przyciemnia obraz na czas pokazywania kart, żeby grafiki były czytelne.
- „Za postacią” (`za: tak`) działa tylko w Formacie 2, w jednym ujęciu; przy cięciach grafiki leżą przed postacią.
- Miejsce w kadrze wynika z położenia Twojej twarzy: grafiki trafiają nad głowę, na boki albo pod napisy, nigdy na twarz.

## Opis ujęć

1. (A) Hak: kadr średni, twarz nad środkiem kadru, napisy na klatce piersiowej.
2. (B) Wstawka (inne źródło niż mówiąca głowa): twarde cięcie, bez błysku.
3. (B) Druga część wstawki: kolejne twarde cięcie w tym samym materiale.
6. (A) Najszerszy kadr rolki.
9. (A) Krótkie ujęcie z większym kadrem.
13. (A) Najbliższy kadr rolki, krótki akcent.
15. (B) Wstawka z błyskiem na wejściu.
16. (B) Druga część wstawki, błysk na wyjściu.
17. (A) Powrót po błysku. Elastyczne ujęcie: przejmuje różnicę długości.
19. (A) Ostatnie ujęcie.
<!-- karta-f3:end -->

## Granice

- **Cyfrowych najazdów w trakcie ujęcia nie ma.** We wzorcu niektóre ujęcia powoli się przybliżają; tu każde ujęcie ma stały kadr,
  a zmianę dają cięcia. To jedyna rzecz z wzorca, której świadomie nie odtwarzam.
- **Krój haseł.** We wzorcu duże słowo to gruby szeryf, w marce jest Instrument Serif Italic (kursywa). Zamiast niego możesz dać
  Bricolage (`big_font: display`) albo wskazać inny plik w `fonts.serif_italic` pliku marki.
- **Kapsułki, ikony ludzi i karta ze zrzutem** z wzorca mają odpowiedniki w Formacie 2 (`pigułki`, `profil`, `karty`), ale ich wygląd
  nie jest dopasowany do tej rolki. Dopasowane są kadry, rytm, napisy, hasła i błysk.
- **Wstawki** dostarczasz Ty. Narzędzie niczego nie wymyśla ani nie wycina z cudzych filmów.
- **Rytm błysku** (tylko przy drugiej wstawce) to obserwacja z jednej rolki, nie reguła. Chcesz błysk przy pierwszej: `{przejście: błysk}`
  w scenariuszu.
- **Pomiar z jednej rolki.** Szablon nie jest uśredniony: powtarza jej rytm, a przy dłuższym materiale powtarza środek.
- **Kolory nagrania.** Szablon ich nie zmienia (nie dopasowuje do wzorca): kolory marki mają grafiki i napisy. Dopasowanie nagrania
  do looku wzorca można dodać, jeśli będzie potrzebne.
- **Grafiki „za postacią”** (`za: tak`) działają tylko w Formacie 2; przy cięciach grafiki leżą przed postacią.
