# BENCHMARK PODCASTU: rama nagrania i klipu

Ciemne studio, dwoje rozmówców przy okrągłym stole, **cztery kadry** w stałym rytmie cięć (średnio co 2,6 s) i **warstwa grafik na wierzchu**: napisy słowo po słowie
z akcentami w czerwonej kursywie, duże hasła, pasek z imieniem i pływająca karta w ujęciu totalnym. Ten plik to benchmark: liczby z pomiaru wzorca, wnioski o tym,
jak to nagrać i zmontować, przełożenie na kolory i kroje marki „Linia Kalewski” oraz lista kontrolna, którą porównasz każdy własny odcinek.

Wzorzec: jedna rolka (DezP_8mNORW), pion 9:16, 23,1 s, klip z dłuższej rozmowy. W repozytorium są tylko liczby, kolory i opis konstrukcji, bez obrazu, mowy i tekstów
z rolki. Wszystkie liczby leżą w [data/podcast_benchmark.json](src/reelcut/data/podcast_benchmark.json), a schemat kadrów jest na rysunku
[docs/podcast_rama.png](docs/podcast_rama.png) (narysowany z liczb, nie z klatek rolki).

To **jeszcze nie jest szablon montażu**: Rolka tnie jedno nagranie z B-rollem, a podcast to kilka kamer naraz. Ten plik jest specyfikacją do nagrywania i do oceny odcinka;
czy robić z niego szablon, opisuje ostatnia sekcja.

**Kto czyta co:** ekipa zdjęciowa: sekcje 1 i 2. Montażysta i grafik: sekcje 3, 4 i 5. Ty: „W skrócie”, sekcje 6 i 8 oraz lista kontrolna (7).

## Co jest pomiarem, co wnioskiem, czego nie wiemy

- **Pomiar:** rytm cięć, rozmiar i położenie twarzy, jasność, geometria i czasy grafik, głośność. Z klatek i z dźwięku, bez zgadywania.
- **Wniosek** (w tekście oznaczony): liczba kamer, ogniskowe, ustawienie świateł, kto mówi w którym fragmencie. Wynikają z obrazu, ale z jednego klipu ich nie potwierdzę.
- **Nieznane:** to jedna próbka 23 s, więc przeliczenia na minutę są ekstrapolacją. Całego odcinka (kilkadziesiąt minut, 16:9) nie widać. Poza mową i jednym
  uderzeniem basowym nie wykryłem podkładu muzycznego, ale cichego tła nie wykluczam.

## W skrócie

| Wymiar | Wzorzec |
|---|---|
| Klip | 23,1 s, pion 1080×1920, 23,976 kl./s |
| Ujęcia | 9 ujęć, 8 cięć (20,7 na minutę), średnio 2,57 s (mediana 2,96 s), od 0,96 do 3,96 s; wszystkie cięcia twarde |
| Kadry (udział czasu) | zbliżenie gościa 34,1%, totalny 30,4%, plan średni gościa 30,4%, reakcja prowadzącego 5,0% |
| Kolejność | zbliżenie gościa, totalny, reakcja, plan średni, zbliżenie, totalny, zbliżenie, plan średni, totalny: dwa takie same kadry nigdy obok siebie, koniec na totalnym |
| Wysokość twarzy | zbliżenie gościa 22%, reakcja prowadzącego 18%, plan średni 13%, głowa w totalnym 2,3% wysokości kadru |
| Światło | „low-key”: średnia jasność 25/255, 78% pikseli ciemniejszych niż 32/255, tło #16171A, twarz gościa 3,2× jaśniejsza od tła |
| Napisy | na ekranie 96% czasu; mowa białym pogrubionym bezszeryfem 40 px (2,1% wysokości) na 49% wysokości kadru, akcenty czerwoną kursywą szeryfową, hasło 110 px (5,7%) |
| Pasek z imieniem | czerwony słupek 204 px, imię i opis krojem mono (49 i 30 px); wchodzi 8 klatek po cięciu na plan średni i zostaje do końca ujęcia |
| Karta | ekran 2:3 o szerokości 39% kadru, tylko w totalnym; wyrasta ze stołu w 0,46 s, potem 4 szybkie zmiany slajdu |
| Otwarcie | 3 klatki (0,125 s) błysku: pomarańczowy, czerwony, żółty |
| Dźwięk | −14,9 LUFS, szczyt −0,9 dBTP, zakres 3,0 LU; sama mowa (3,7 słowa na sekundę) i jedno uderzenie basowe przy wejściu karty |
| Kolory | grafitowa czerń, **jedna czerwień** (#F00000, w słupku #FF0000) jako akcent, biel jako tekst; jedyny ciepły kolor to blat stołu #522E16 |

Tempo na tle naszych formatów (średnia długość ujęcia): podcast 2,57 s i 20,7 cięcia na minutę, Format 3 2,90 s i 19,6, Format 1 2,27 s i 24,7, Format 4 1,58 s i 37,2.
Podcast tnie w tempie Formatu 3, a głośność ma jak pozostałe (−14,9 LUFS wobec −14,4 do −14,7).

## 1. Plan zdjęciowy

### Kadry

| Kadr | Do czego służy | Twarz (wysokość kadru) | Środek twarzy | Linia oczu | Ujęcie |
|---|---|---|---|---|---|
| Zbliżenie gościa | gość mówi, tu lądują hasła | 22% (22–23%) | 46% × 28% | 25% | średnio 2,63 s, 3 ujęcia |
| Plan średni gościa | kontekst, zawsze z paskiem | 13% | 53% × 29% | 26% | średnio 3,52 s, 2 ujęcia |
| Reakcja prowadzącego | krótka reakcja w trakcie zdania gościa | 18% | 38% × 24% | 21% | 1,17 s, 1 ujęcie |
| Totalny | pytanie prowadzącego, liczba z kartą, zakończenie | głowa 2,3% (ok. 44 px) | prowadzący 26% × 48%, gość 77% × 48% | 48% | średnio 2,35 s, 3 ujęcia |

Wysokość twarzy to ramka detektora twarzy Rolki (mniej więcej od czoła do brody, bez czapki i włosów), mierzona tak samo jak w pozostałych formatach. Środek twarzy to współrzędne w kadrze (x od lewej, y od góry). Twarz gościa stoi blisko środka (46% w zbliżeniu, 53% w planie średnim), a w pionie w górnej trzeciej
części kadru, więc pod nią zostaje miejsce na napisy.

### Totalny: geometria

- Głowy na 48,4% wysokości, prowadzący na 25,8% szerokości, gość na 77,1% (środek między nimi 51%).
- Pas światła na podłodze na 64,5% wysokości, szeroki na 5% wysokości, przez całą szerokość kadru; to najjaśniejszy element kadru (na brzegach #858D94).
- Stół: blat ok. 45% szerokości, czarna podstawa ok. 28% szerokości, na środku.
- **Pusto nad i pod ludźmi:** ściana od 0 do 40% wysokości i podłoga od 67% do 100%. To miejsce na kartę, duże słowa i napisy, więc ma zostać puste.
- Tło rozjaśnia się w ujęciu powoli (o 12% w 1,8 s i o 18% w 2,8 s: powolny dojazd albo narastanie światła), więc kadr „oddycha”.

### Zasady zdjęć (wnioski z kadrów)

1. **Co najmniej trzy kamery, cztery kadry.** Totalny, gość ciasno i prowadzący ciasno to osobne kamery; plan średni gościa to czwarta kamera albo wycinek z szerszej.
   Nagrywaj wszystkie naraz, z jednym klapsem albo timecodem i jednym śladem głosu, żeby montaż mógł skakać między kadrami bez cięcia dźwięku.
2. **Oś 180°.** Prowadzący siedzi po lewej i patrzy w prawo, gość po prawej i patrzy w lewo, w totalnym tak samo jak w zbliżeniach. Wszystkie kamery stoją po jednej stronie
   osi rozmowy, więc cięcie nie odwraca kierunku spojrzeń.
3. **Kamery stoją.** Nie ma panoramy ani ruchu kamery, najwyżej kilkuprocentowy dojazd w ujęciu (na granicy błędu pomiaru). Ruch daje cięcie i grafika.
4. **Pion z poziomego 4K.** Puste pasy nad i pod ludźmi w totalnym pasują do wycinka 9:16 na pełną wysokość szerokiego kadru 16:9: ludzie zajmują wtedy środkowe ok. 1/6
   szerokości. Nagrywaj w 4K i kadruj z zapasem: wycinek 9:16 z 4K ma 1215 px szerokości, a wyjście 1080×1920 potrzebuje co najmniej 1080 px.
5. **Miejsce pod grafikę jest częścią kadru.** W zbliżeniach pas od 47% do 51% wysokości (pod brodą, nad blatem, na wysokości mikrofonu) ma być spokojny i ciemny:
   leży tam napis mowy. Zbliżenie gościa ma brodę na ok. 39% wysokości, więc napis wypada ok. 10% wysokości pod nią.
6. **Plan średni ma być luźny.** Twarz 13% wysokości, a pod klatką piersiową dużo ciemnej pustki: tam siada pasek z imieniem (środek paska na 67% albo 74% wysokości).

## 2. Scena i światło

| Element | Co widać |
|---|---|
| Tło | grafitowa czerń #16171A w zbliżeniach, u góry totalnego prawie czerń (#060402), przy głowach rozjaśniona; bez żadnych przedmiotów |
| Podłoga | błyszcząca, z pasem światła i odbiciem (pod pasem szary #282B2E–#3D4145, ciemnieje do dołu); wniosek: listwa albo światło u podstawy cyklorama |
| Stół | okrągły albo owalny, czarna podstawa, blat z ciepłego drewna #522E16 (jedyny ciepły kolor w kadrze poza skórą) |
| Krzesła | dwa krzesła reżyserskie, osoby w profilu, po przeciwnych stronach stołu |
| Mikrofony | dwa studyjne na wysięgnikach, **w kadrze**, po jednym na osobę; w zbliżeniach wchodzą z boku na wysokości klatki piersiowej |
| Rekwizyty | szklanka wody i notatnik po stronie prowadzącego, mały przedmiot (telefon albo rejestrator) na blacie po stronie gościa |
| Ubiór | wszystko czarne (bluza, czapka, sweter): w zbliżeniu skóra jest najjaśniejszą rzeczą w kadrze |

Jasność (skala 0–255): średnia całego klipu 25, mediana 18,9, 99. percentyl 153; 78% pikseli ciemniejszych niż 32, 44% ciemniejszych niż 16. Twarz gościa w zbliżeniu ma 72 przy tle 22
(3,2×), prowadzący 54 (2,4×), gość w planie średnim 43 (1,9×): plan średni jest najciemniejszy i najbardziej sylwetkowy. Twarz gościa jest oświetlona równo (połowy twarzy różnią się
o 5–16%), prowadzącego pada światło z boku (prawa połowa ok. 2× jaśniejsza od lewej). Wniosek: miękkie światło kluczowe z przodu, tło nieoświetlone, osobny pas światła
na podłodze i ewentualnie światło obrysowe.

## 3. Montaż: gramatyka cięć

Szkielet 23 s (czasy wzorca):

| Czas | Kadr | Funkcja | Grafika |
|---|---|---|---|
| 0,00–0,96 | zbliżenie gościa | hak | błysk 0,125 s, pierwsze słowa całe czerwoną kursywą |
| 0,96–3,21 | totalny | dowód liczbowy | karta wyrasta ze stołu, 4 zmiany slajdu w 0,7 s, duża liczba pod stołem z małym podpisem, uderzenie basowe |
| 3,21–4,38 | reakcja prowadzącego | reakcja w trakcie zdania gościa | napis mowy (białe słowa, jedno czerwone) |
| 4,38–7,76 | plan średni gościa | kontekst | pasek z imieniem po 0,33 s; napis: biała linia i czerwona linia pod nią |
| 7,76–11,72 | zbliżenie gościa | rozwinięcie | dwa hasła jedno po drugim (drugie zastępuje pierwsze z szarpnięciem), potem napis mowy |
| 11,72–13,51 | totalny | pytanie prowadzącego | dwie linie czerwonej kursywy (55 px), jedno słowo białe |
| 13,51–16,48 | zbliżenie gościa | odpowiedź | napis mowy z czerwonym słowem |
| 16,48–20,14 | plan średni gościa | wynik i wezwanie do pełnej rozmowy | hasło 110 px, pasek z nazwą serii i wezwaniem po 0,33 s |
| 20,14–23,15 | totalny | zamknięcie | dwie linie białym (50 px) z dwoma czerwonymi słowami, wchodzą 0,37 s po cięciu |

Podział na mówców (kto zadaje pytanie, czyja jest reakcja) to wniosek z pauz, z budowy zdań i z odmiennego kroju napisu, a nie rozpoznanie głosu.

Reguły, które z tego wynikają:

1. **Ciasno i luźno na przemian.** Ujęcia 1, 3, 5, 7 są ciasne (zbliżenie gościa, reakcja), ujęcia 2, 4, 6, 8, 9 luźne (totalny, plan średni). Żadne dwa sąsiednie ujęcia nie mają tego
   samego kadru.
2. **Prowadzący dostaje kadr raz:** 1,17 s reakcji w trakcie zdania gościa. Jego pytanie idzie na totalnym i ma osobny wygląd (czerwona kursywa, jedno słowo białe). Wniosek: to
   rozróżnienie głosów, nie przypadek.
3. **Totalny jest na grafikę.** Wszystko duże dzieje się na totalnym: karta, duża liczba, pytanie, zamknięcie. Mowa jest tam większa niż zwykle i leży w pustych strefach
   (nad głowami albo pod stołem), a paska nie ma nigdy.
4. **Plan średni jest na pasek.** Oba plany średnie mają pasek, który wchodzi 8 klatek (0,33 s) po cięciu i trwa do końca ujęcia (3,04 s i 3,34 s).
5. **Hasło ląduje na ujęciu gościa** (zbliżenie albo plan średni), nigdy na totalnym i nigdy na reakcji.
6. **Tylko twarde cięcia.** 8 z 8 cięć to jedna klatka, bez przejść, bez zanikania na końcu. Jedyny efekt otwarcia to błysk w 3 klatkach. Pierwsze cięcie pada po 0,96 s.
7. **Długie ujęcia niosą grafikę.** Najdłuższe ujęcia (3,4 do 4,0 s) mają pasek albo dwa hasła, najkrótsze (0,96 i 1,17 s) to hak i reakcja.
8. **Cięcie blisko zmiany mówcy.** Na totalny tnie się ok. 0,1 s po pierwszym słowie pytania, a z powrotem na gościa 0,13 s przed jego odpowiedzią (czasy słów z rozpoznawania
   mowy, błąd ok. 0,1 s). Dwie jedyne pauzy dłuższe niż 0,25 s (0,42 i 0,56 s) wypadają właśnie na zmianach mówcy.

## 4. Napisy i grafika

Wszystkie wymiary w pikselach kadru 1080×1920 i w ułamkach jego wysokości (y) albo szerokości (x). Napisy są na ekranie 96% czasu: bez napisu zostają tylko pierwsze 4 klatki (błysk),
3 klatki przy pierwszym cięciu i 8 klatek po cięciu na zamknięcie.

| Element | Gdzie | Wygląd | Wymiary i miejsce | Czas i ruch |
|---|---|---|---|---|
| Napis mowy | zbliżenia i plan średni | biały #FFFFFF, pogrubiony bezszeryf, miękka poświata | 40 px (2,1% wysokości), środek na 49% wysokości, do 2 wierszy co 40 px, do 50% szerokości | słowa dochodzą po jednym w chwili mowy (opóźnienie do 0,12 s), blok znika po frazie |
| Akcent | w napisie mowy | gruba kursywa szeryfowa, czerwień z poświatą, wyższa od białych słów (ok. 1,2–1,4× razem z poświatą) | w linii albo jako druga linia tuż pod białą | wchodzi razem z mową |
| Hasło | zbliżenie i plan średni | gruba kursywa szeryfowa, czerwień z poświatą | 110 px (5,7% wysokości), wyśrodkowane, środek na 47% wysokości (43–51%), 41–62% szerokości, 1–2 słowa | zastępuje napis mowy; wejście to 6 klatek (0,25 s) poziomego szarpnięcia z rozmyciem, potem stoi 0,8–1,6 s |
| Duża liczba | totalny, pod stołem | czerwona kursywa, pod nią mały biały podpis (28 px) | 90 px (4,7% wysokości), środek na 71,2% wysokości (pod pasem światła), podpis na 74,6%, szerokość 38% | słowa dochodzą jak w napisie mowy |
| Pytanie | totalny, nad głowami | czerwona kursywa, jedno słowo białe | 55 px (2,9%), 2 wiersze co 58 px, środek na 42,2% wysokości, szerokość 72% | wyśrodkowane |
| Zamknięcie | totalny, nad głowami | biały pogrubiony bezszeryf z poświatą neonu, dwa słowa czerwoną kursywą | 50 px (2,6%), 2 wiersze co 53 px, środek na 41,9% wysokości, szerokość 76% | wchodzi 0,37 s po cięciu |
| Pasek z imieniem | tylko plan średni gościa | słupek czerwony #FF0000 z poświatą, tekst biały krojem mono | słupek 10×204 px (10,6% wysokości) na 20,6% szerokości, tekst od 25,6%; imię wersalikami 49 px (wysokość wersalika 35 px), opis 30 px; środek na 67,4% albo 74,2% wysokości | pojawia się od razu 8 klatek (0,33 s) po cięciu, litery „dekodują się” 5 klatek (przesunięte o 1–3 miejsca w alfabecie układają się w tekst), zostaje do cięcia, bez wyjścia |
| Karta | tylko totalny | półprzezroczysty ekran 2:3 (zrzut posta), jasność wnętrza 87 wobec 40 tła obok | 39,3% szerokości (x od 30,4% do 69,6%), y od 15,6% do 48,9% (dolna krawędź na linii głów, tuż nad stołem) | wyrasta od 43,8% do 16,7% (górna krawędź) w 11 klatkach (0,46 s) z wyhamowaniem i rozmyciem ruchu, potem 4 zmiany slajdu co 0,21–0,25 s, ostatni stoi 1,13 s; wychodzi z cięciem |
| Błysk otwarcia | pierwsze klatki | #FB9C27, #FA3817, #FFEC3D (jasność 152, 82, 189 wobec 24 po błysku) | cały kadr | 3 klatki, 0,125 s |
| Uderzenie basowe | wejście karty | sinus ok. 50 Hz | ok. 25 dB nad medianą pasma poniżej 120 Hz, 0,35 s | zaczyna się przy cięciu na totalny z kartą |

Wszystkie grafiki mieszczą się między 15,4% a 79,5% wysokości kadru (najwyżej karta, najniżej słupek drugiego paska), czyli poza górnymi 15% i dolnymi 20%, w których platformy
kładają swój interfejs. To obserwacja, nie deklaracja autorów rolki.

Kolory napisów: biel i jedna czerwień (#F00000, rdzeń słupka #FF0000, poświata #600001). Nie ma drugiego koloru akcentu i nie ma kolorowego tła pod napisem: napis leży wprost na obrazie.
Czerwień jest obecna w ok. dwóch trzecich czasu z napisem (oszacowanie z klatek, ±10 punktów), więc to nie rzadki akcent, tylko drugi głos obok białego.

## 5. Dźwięk

- Głośność: −14,9 LUFS, szczyt −0,9 dBTP, zakres głośności 3,0 LU (od −16,4 do −13,4 LUFS). To poziom pozostałych formatów (−14,4 do −14,7 LUFS).
- Mowa: 85 słów w 23 s, 3,7 słowa na sekundę (wzorzec jest po angielsku), prawie bez przerw: dwie pauzy dłuższe niż 0,25 s (0,42 i 0,56 s), obie przy zmianie mówcy.
- Stereo (korelacja kanałów 0,84), nie podwójne mono; 44,1 kHz.
- Jeden efekt: uderzenie basowe (sinus ok. 50 Hz, 0,35 s) przy wejściu karty, najgłośniejszy fragment pasma niskiego w całym klipie. Podkładu muzycznego nie wykryłem;
  w przerwach między frazami poziom jest 12–16 dB poniżej mowy (szum pokoju albo pogłos).

## 6. Przełożenie na „Linię Kalewski” (propozycja do akceptacji)

Czerwień wzorca to marka tamtego konta, nie reguła formatu. Reguła brzmi: **biel na obrazie plus jeden kolor akcentu**, który jest jedynym jasnym kolorem naraz.

| Element | Wzorzec | Linia Kalewski (propozycja) |
|---|---|---|
| Akcent (słowa, słupek, błysk) | czerwień #F00000 | żółty #FFD346 (rola `highlight`: jedyny jasny element naraz) |
| Napis mowy | biel #FFFFFF, gruby bezszeryf | biel #FFFFFF, Bricolage Grotesque 700 |
| Kursywa szeryfowa | gruba, kontrastowa | Instrument Serif Italic (rola `serif_italic`) w wielkości ×1,15, jak w Formatach 2–4; brak grubości trzeba oddać poświatą |
| Pasek: tekst | mono wersaliki | **do decyzji**: Bricolage Grotesque 800 wersalikami z rozstrzeleniem albo dodać krój mono na licencji OFL (marka nie ma mono) |
| Pasek: słupek | czerwień #FF0000 | fiolet #795DFF (rola `line`) z fioletową poświatą, żeby żółty został jedynym jasnym akcentem; alternatywa: żółty |
| Błysk otwarcia | pomarańcz, czerwień, żółć | żółty #FFD346, fiolet #795DFF, biel |
| Poświata słów | czerwone halo | halo w kolorze słowa, ok. 35–40% krycia |
| Tło grafik i plansz | grafit #16171A | tusz #1B1440; scena zostaje czarna |
| Karta | zrzut posta na szkle | zrzut w ramce marki albo karta w kolorze papieru #F7F4EC |

Powód wyboru fioletu dla słupka: według tokenów marki (`brand_kalewski.json`) żółty `highlight` to jedyny jasny element naraz, a linie są fioletowe. We wzorcu hasło i słupek
paska bywają na ekranie razem (18,0–19,6 s) i oba są czerwone; w marce to dwa różne kolory.

## 7. Lista kontrolna odcinka

Pasma to wzorzec ±15 do 25%, nie pomiar rozrzutu (jedna próbka). Po trzech–pięciu własnych odcinkach zastąp je własnymi liczbami.

**Dzień zdjęciowy** (sprawdź na monitorze, zanim padnie pierwsze pytanie):

| # | Co | Wzorzec | Pasmo |
|---|---|---|---|
| 1 | Twarz gościa w zbliżeniu | 22% wysokości | 19–25% |
| 2 | Twarz w planie średnim | 13% | 11–15% |
| 3 | Twarz prowadzącego w reakcji | 18% | 16–21% |
| 4 | Głowa w totalnym | 2,3% | 1,8–2,8% |
| 5 | Jasność kadru | 25/255 | 20–35 |
| 6 | Twarz gościa względem tła | 3,2× | 2,5–4× |
| 7 | Oś 180°: wszystkie kamery po jednej stronie | zachowana | zachowana |
| 8 | Nagranie | 23,976 kl./s (4K to wniosek) | 4K, 24–25 kl./s, wspólny klaps |

**Po montażu klipu:**

| # | Co | Wzorzec | Pasmo |
|---|---|---|---|
| 9 | Cięcia na minutę | 20,7 | 15,5–26 |
| 10 | Długość ujęcia | 0,96–3,96 s, mediana 2,96 s | 0,9–4,5 s, mediana 2–3,5 s |
| 11 | Pierwsze cięcie | 0,96 s | do 1,2 s |
| 12 | Udział kadrów | zbliżenie 34%, totalny 30%, plan średni 30%, reakcja 5% | zbliżenie 25–45%, totalny 20–40%, plan średni 20–40%, reakcja do 10% |
| 13 | Dwa takie same kadry obok siebie | 0 | 0 |
| 14 | Napisy na ekranie | 96% czasu | co najmniej 90% |
| 15 | Linia napisu mowy | środek 49%, 40 px | 47–51%, 38–44 px |
| 16 | Pasek na każdym planie średnim | 0,33 s po cięciu, do końca ujęcia | 0,25–0,42 s po cięciu |
| 17 | Kolor akcentu słów (hasła, akcenty, liczba) | jeden (czerwień) | jeden (u nas żółty), plus biel |
| 18 | Głośność | −14,9 LUFS, −0,9 dBTP, 3,0 LU | −16 do −13,5 LUFS, szczyt do −1,0 dBTP, zakres do 4 LU |
| 19 | Wszystkie grafiki w strefie bezpiecznej | 15,4–79,5% wysokości | 15–80% wysokości |

## 8. Granice i decyzje

- **Jedna rolka, 23 s.** To pomiar jednego klipu, nie norma gatunku. Długiego odcinka 16:9 wzorzec nie pokazuje.
- **Nieznana ekipa i sprzęt.** Ile było kamer, jakie ogniskowe i jakie światła, to wnioski z obrazu. Najtaniej sprawdzić to u autorów albo na zdjęciach z planu.
- **Narzędzie nie mierzy tego jeszcze samo.** Polecenie `analyze` znalazło w tej rolce 6 z 9 ujęć (ciemny obraz słabo wychodzi na detektorze scen z progiem 0,18) i pomija twarze
  mniejsze niż 4% wysokości, czyli totalny. Liczby tej specyfikacji pochodzą z osobnego pomiaru różnicy klatek; do automatycznej oceny odcinka trzeba by dodać taki detektor.
- **Do podjęcia:**
  1. Kolory: akcent słów żółty (propozycja) czy fiolet; słupek paska fioletowy (propozycja) czy żółty.
  2. Krój paska: marka nie ma kroju mono; wersaliki Bricolage Grotesque czy nowy krój OFL.
  3. Czy narzędzie ma montować takie klipy. Wymaga trybu wielokamerowego: kilka zsynchronizowanych plików, wybór kadru według tego, kto mówi, napisy i pasek jak w tabeli
     powyżej, karta w totalnym. Szablon dostałby kolejny numer formatu (proponuję Format 5, jako założenie do potwierdzenia).
  4. Nazwa serii i wezwanie w pasku (w kadrze to nazwa serii i zaproszenie do pełnej rozmowy na YouTube): do ustalenia z Twoją serią.
