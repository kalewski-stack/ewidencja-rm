# FORMAT 4: kinetyczna typografia

Bardzo szybki montaż (cięcie średnio co 1,6 s), a **cała mowa pojawia się na ekranie jako napisy z jednym dużym słowem**: duże słowo
(rzeczownik, czasownik, liczba) i drobne słowa nad nim i pod nim, każde w chwili, gdy je mówisz. Co kilka ujęć **karta w jednolitym kolorze**
(biała albo żółta), na której czarny tekst dochodzi słowo po słowie, a wyróżnione słowo dostaje **odręczną elipsę**. Hak otwierają dwa ujęcia
czarno-białe z dużym napisem. Narzędzie robi to w Twoich kolorach i kroju marki „Linia Kalewski”, a czasy ustawia na słowach, które mówisz.
Film wychodzi **w pionie 9:16 albo w poziomie 16:9**: wzorzec jest poziomy, więc są dwa szablony z tym samym rytmem.

Nazwa: użytkownik wrzucił rolkę bez nazwy, w narzędziu to **Format 4** (szablony `format4` i `format4h`). Numer 4 to **przyjęte założenie**
(potwierdź przy okazji).

- **Format 1** to mówiąca głowa z cięciami i B-rollem (rolka DeuOaXKtPBb): szablon `format1`, opis w [STYL.md](STYL.md).
- **Format 2** to jeden take bez cięć z animowanymi grafikami: szablon `format2`, opis w [FORMAT2.md](FORMAT2.md).
- **Format 3** to cięcia z hasłami i błyskiem: szablon `format3`, opis w [FORMAT3.md](FORMAT3.md).
- **Format 4** to ten plik: cięcia jak w Formacie 1, ale **każde słowo ma swój napis**, są karty w kolorach marki i film może być poziomy.
  Napisy, karty i elipsę rysuje warstwa grafik, a składnia scenariusza jest ta z Formatu 2 ([GRAFIKI.md](GRAFIKI.md)).
- **Motion** to obraz bez mówiącej głowy: [MOTION.md](MOTION.md).

Wzorzec: jedna rolka (DdZBWMyq4Zx). W repozytorium są tylko liczby, kolory i opis konstrukcji, bez obrazu, mowy i tekstów z rolki.
Jedna rolka to nie statystyka: liczby poniżej to jej pomiar, a nie mediana kilku.

## W skrócie

Karta stylu z tabelą kadrów każdego ujęcia: `python rolka.py style format4h` (jest też na końcu tego pliku).

| Wymiar | Wzorzec |
|---|---|
| Długość | 66,2 s, 42 ujęcia, 41 cięć (37,2 na minutę), poziom 16:9 (1916×1078), 25 kl./s |
| Ujęcia | średnio 1,58 s (mediana 1,22 s), od 0,56 do 5,12 s; wszystkie cięcia twarde, żadnych przejść |
| Co jest na ekranie | 42% czasu mówiąca głowa (A, 12 ujęć), 34% wstawki (B, 18 ujęć), 24% karty w jednolitym kolorze (S, 12 ujęć) |
| Karty | 12: 6 białych (średnio 1,01 s) i 6 żółtych (średnio 1,61 s); we wzorcu biała i pomarańczowa, w narzędziu `#F7F4EC` i `#FFD346` |
| Hak | 6,6 s: dwa ujęcia czarno-białe z dużym napisem, wstawka w kolorze i trzy karty (biała, żółta, biała) |
| Twarz | wysokość od 23% (najszerszy kadr) do 37% (zbliżenie), środek na 49% × 28% kadru, więc dół zostaje na napisy |
| Napisy na ujęciu z twarzą | duże słowo 8,7% wysokości kadru (94 px z 1080), małe 50% jego wielkości, blok od 57% wysokości |
| Napisy na wstawce | duże słowo 17% wysokości (184 px z 1080), małe 27% jego wielkości, blok od 38% wysokości |
| Karta: wiersz | słowa dochodzą po jednym, wiersz się wyśrodkowuje, 8,7% wysokości kadru; nowy wiersz po zdaniu, przecinku, pauzie albo 6 słowach |
| Karta: duże słowo | 19% wysokości kadru (205 px z 1080), małe słowa wokół, blok na środku |
| Elipsa | kreska 0,38% wysokości kadru, rysowana 0,4 s zgodnie z ruchem wskazówek zegara od lewej górnej strony; obejmuje cały tekst |
| Mowa | 3,8 słowa na sekundę, 248 słów w 66 s (wzorzec jest po angielsku) |
| Dźwięk | −14,4 LUFS, szczyt +0,6 dBTP (narzędzie ustawia −1 dBTP), zakres głośności 4,2 LU |
| Kolory | tekst na nagraniu biały, na kartach tusz marki; w narzędziu zawsze kolory marki. Kolory nagrania zostają bez zmian |

## Jak zbudowany jest film

Zasady widoczne w rolce wzorcowej (rytm i geometria z pomiaru klatek, reszta z oglądania):

1. **Cięcie co ok. 1,6 s i każde widać.** Ujęcie z twarzą trwa średnio 2,3 s, wstawka 1,2 s, karta 1,3 s. Sąsiednie ujęcia z tej samej kamery różnią się
   rozmiarem twarzy (od 23% do 37% wysokości kadru), a po kadrze twarzy zawsze idzie wstawka albo karta. Głos leci bez przerwy.
2. **Hak to dwa czarno-białe ujęcia z dużym napisem** (łącznie 2 s), potem wstawka w kolorze i trzy karty. Dopiero po 6,6 s wraca mówiąca głowa.
3. **Karty idą parami: biała (krótka), potem żółta (dłuższa).** W 66 s jest ich dwanaście. Na białej tekst dochodzi słowo po słowie jako jeden
   wiersz („this” → „this is” → „this is how”), na żółtej to samo albo jedno duże słowo z małymi wokół. Po kartach wraca mówiąca głowa.
4. **Każde słowo dostaje napis.** Zdanie rozpada się na krótkie frazy; w każdej jedno duże słowo i małe słowa wokół niego, wszystkie wskakują w jednej
   klatce w chwili, gdy je słychać. Na ujęciu z twarzą napis jest skromny, na wstawce czterokrotnie większy jak plansza.
5. **Elipsa to jedyne wyróżnienie na karcie.** Rysuje się na żywo wokół tekstu i rośnie razem z kolejnymi słowami; w narzędziu zaczyna, gdy pada słowo
   wyróżnione gwiazdkami.
6. **Nic się nie rusza poza tekstem.** Kadr stoi, cięcia są twarde, litery nie wjeżdżają ani nie rosną: pojawiają się od razu.

Czego z rolki **nie ma** w szablonie, bo to ozdobniki konkretnej opowieści: karta z zrzutem profilu i dużą liczbą, licznik z siatką kropek, strzałka
z podmianą słowa, duża szara cyfra za napisami i ekran dzielony. Strzałkę, licznik i karty ze zrzutami dołożysz ręcznie znacznikami z Formatu 2
(`strzałka`, `licznik`, `karty`, `profil`): [GRAFIKI.md](GRAFIKI.md).

## Pion i poziom

Wzorzec jest poziomy (16:9), więc szablon `format4h` ma jego liczby wprost. Szablon `format4` (pion 9:16) ma **ten sam rytm, te same karty i ten sam
hak**, ale kadr i napisy dobrane do telefonu. To nie jest pomiar, tylko przeliczenie:

| | Poziom (`format4h`, zmierzone) | Pion (`format4`, dobrane) |
|---|---|---|
| Kanwa | 1920×1080 | 1080×1920 |
| Twarz | wysokość 23–37%, środek na 28% wysokości | wysokość 19–30% (ta sama drabinka), środek na 34% wysokości |
| Napisy na ujęciu z twarzą | 8,7% wysokości (94 px), blok od 57% | 4,0% wysokości (77 px), blok od 51% |
| Napisy na wstawce | 17% wysokości (184 px), blok od 38% | 7,5% wysokości (144 px), blok od 42% |
| Karta: wiersz | 8,7% wysokości (94 px) | 4,7% wysokości (90 px) |
| Karta: duże słowo | 19% wysokości (205 px) | 10% wysokości (192 px) |

Nagraj w orientacji szablonu: poziomy film do `format4h`, pionowy do `format4`. Gdy orientacja się nie zgadza, program wycina pas ze środka kadru
(traci się góra i dół albo boki) i **ostrzega**; ustaw wtedy `--focus`. Wstawki (B-roll) są przycinane do kadru szablonu tak samo.

## Frazy: jak program wybiera duże słowo

Zdanie rozpada się na fragmenty: koniec zdania, przecinek albo pauza dłuższa niż 0,4 s kończą frazę. W każdym fragmencie program wybiera
najtańszy zestaw dużych słów, tak żeby **każde słowo było w zasięgu jakiegoś dużego**: na ujęciu z twarzą do 2 małych słów przed dużym i 1 po nim,
na wstawce i na karcie do 3 przed i 2 po.

- **Duże są słowa treściwe**: długie, z cyfrą, nie-funkcyjne. Słowa łączące (spójniki, przyimki, zaimki, „który”, „się”, „jest”...; lista polska
  i angielska) są duże tylko wtedy, gdy zasięg nie pozostawia wyboru. W innym języku wybór idzie po długości słowa.
- **Skróty** (AI, PR, HR, B2B, UX...) mają pierwszeństwo przed zwykłymi krótkimi słowami.
- **Twoje wyróżnienia wygrywają.** Słowo w `*gwiazdkach*` jest duże zawsze (jedno albo dwa z rzędu), a na ujęciu z twarzą i na wstawce ma kolor
  wyróżnika (żółty). Pozostałe duże słowa dobiera program. Na karcie wyróżnione słowo dostaje elipsę zamiast koloru.
- **Frazy nie przechodzą przez cięcia.** Słowo, które zaczęło się tuż przed cięciem, ale większość mówisz już po nim, trafia na nowe ujęcie.
  Cięcia planista dosuwa do granic mowy, więc zwykle wypadają między frazami.
- Każde słowo wskakuje **od razu** (jedna klatka), a fraza schodzi 0,12 s po ostatnim słowie albo gdy zaczyna się następna.
- Zwykłe napisy (białe, małe, słowo po słowie) zostają tylko jako rezerwa: pokażą słowo, którego żadna fraza nie objęła.

## Karty

Ujęcia z szablonu oznaczone jako karty nie mają nagrania ani B-rolla: to jednolity kolor na całym kadrze i tekst z tego, co w tym czasie mówisz.

- **Biała karta** (papier marki, `#F7F4EC`) zwykle pisze **wiersz**: słowa dochodzą po jednym, wiersz za każdym razem się wyśrodkowuje. Za długi wiersz
  łamie się na kilka (najwyżej 80% szerokości kadru), a nowy wiersz zaczyna się po zdaniu, przecinku, pauzie albo po 6 słowach.
- **Żółta karta** (`#FFD346`) zwykle pisze **duże słowo** z małymi wokół (jak fraza, tylko większe). Dwie żółte karty wzorca (nr 5 i 18 na liście
  ujęć) piszą wiersz.
- Tekst jest zawsze **tuszem marki** (`#1B1440`), bez cienia.
- **Które ujęcie jest kartą i jaką**, wynika z szablonu. Zmiana to edycja pliku `.json` (pole `slide`: `white` albo `orange`, `slide_style`: `line`
  albo `title`); szablon własny zrobisz kopiując `format4.json` do `~/ReelCut/szablony`.
- Gdy w czasie karty nic nie mówisz, karta jest pustym kolorem. Gdy wyłączysz napisy (`--no-captions`), karty też są puste, bo nie ma słów do pokazania.

## Jak zrobić film w Formacie 4

1. **Napisz tekst**: wystarczy sam tekst, który powiesz, z gwiazdkami przy kilku słowach kluczowych (3–8 na film). Znaczniki `{ }` z Formatu 2
   są opcjonalne. Na 45–60 s to ok. 170–230 słów (wzorzec ma 3,8 słowa na sekundę).
2. **Nagraj** w orientacji szablonu, na statywie, **szeroko**: twarz ok. 15–20% wysokości kadru (montaż przybliża do 37%), najlepiej w 4K. Mów w jednym ciągu.
   Wstawki: osobne ujęcia (detale, rekwizyty, dłonie, ekran) albo nic, a program zrobi detale z Twojego nagrania. **Co najmniej 13 sekund** (hak i zakończenie
   są stałe); najlepiej 25–70 s.
3. **Surowiec** (raz, to trwa najdłużej): `python rolka.py nagranie.mp4 --template format4 -o surowiec.mp4`. Powstaje też `surowiec.slowa.json` z czasami słów.
4. **Podgląd na jednej klatce** (sekundy): zrób zrzut klatki swojego nagrania (`klatka.jpg`) i uruchom
   `python rolka.py grafiki scenariusz.txt --template format4 --words surowiec.slowa.json --tlo klatka.jpg --klatka 12`. Podgląd pokazuje frazy tak, jak wyglądają na
   ujęciu z twarzą (karty, wstawki i cięcia zależą od montażu); tłem ma być **zdjęcie**, nie surowiec, bo surowiec ma już wypalone napisy.
5. **Film**: `python rolka.py nagranie.mp4 --template format4 --graphics scenariusz.txt --broll wstawki/ --words surowiec.slowa.json`
   (w poziomie `--template format4h`). W interfejsie (`python rolka.py serve`) wybierz „Format 4” albo „Format 4 (poziom 16:9)”, w kroku 3 przeciągnij
   scenariusz, a wstawki w kroku 2. Poprawka gwiazdki albo literówki w scenariuszu to ta sama komenda: z `--words` nie rozpoznaje mowy od nowa.
6. **Sprawdź plan**: `--dry-run --words surowiec.slowa.json` wypisze ujęcia (z oznaczeniem kart i czarno-białego haku) i harmonogram fraz i kart.

Napisy, frazy i karty biorą słowa z Twojego scenariusza (poprawna pisownia, wielkość liter, interpunkcja), a czasy z mowy. Działa, gdy mowa zgadza się
ze scenariuszem w co najmniej 80%; przy improwizacji program zostaje przy rozpoznanej mowie i mówi o tym w ostrzeżeniu. Wyróżnienia `*tak*` działają w obu
przypadkach. Scenariusz może być sam tekst bez żadnego znacznika: w Formacie 4 to poprawny plan.

### Szkielet scenariusza (hipotetyczny, podmień na swój temat)

<!-- scenariusz-f4:start -->
```
# Film ok. 30 s: „Zanim napiszesz brief” (tekst hipotetyczny, podmień na swój temat)
Zanim napiszesz brief, odpowiedz na trzy pytania. Po pierwsze: co ma się *zmienić* po wydarzeniu? Po drugie: kto ma to zauważyć? Po trzecie: po czym poznasz, że się udało?
Większość firm zaczyna od miejsca i budżetu. To kolejność, która gwarantuje *przeciętny* wynik. Dobry event zaczyna się od miary, ustalonej przed pierwszą rozmową z agencją.
Zapisz te trzy odpowiedzi na jednej kartce i dopiero z nią idź do dostawcy. Pomiar nie jest dodatkiem na koniec. Pomiar jest *pierwszą rozmową*.
```
<!-- scenariusz-f4:end -->

## Granice

- **Jedna rolka to nie statystyka.** Rytm, rozmiary i proporcje to pomiar jednej rolki poziomej (po angielsku, 248 słów). Wersja pionowa to przeliczenie
  rozmiarów na telefon, nie pomiar.
- **Duże słowo dobiera heurystyka.** Zwykle trafia w rzeczownik albo czasownik, ale zdarza się słowo, którego byś nie wybrał: wyróżnij je gwiazdkami.
- **Biały tekst na jasnym B-rollu słabo się czyta** (jest tylko lekki cień). Wstawki wybieraj ciemniejsze albo zmień kolor w planie JSON (`color`).
- **Nagranie bez twarzy** dostaje stałe zoomy z szablonu, a nagranie w innej orientacji niż szablon jest przycinane do środka kadru (ostrzeżenie).
- **Rytm jest sztywny.** Hak i zakończenie są zawsze takie jak we wzorcu, środek się powtarza; mowa w ujęciu-karcie trafia na kartę, więc przy bardzo
  krótkiej karcie (poniżej pół sekundy) jest tam jedno słowo.
- **Nie ma przejść między ujęciami**, bo wzorzec ma same twarde cięcia. Przejścia z [PRZEJSCIA.md](PRZEJSCIA.md) działają, ale tylko na grafikach (poza błyskiem).
- **Sprawdzone na materiale syntetycznym i na klatkach wzorca**, nie na Twoich nagraniach. Pierwszy film obejrzyj uważnie (kadr twarzy, czytelność, dobór dużych słów).

## Karta stylu

<!-- karta-f4h:start -->
# Karta stylu: Format 4: kinetyczna typografia (poziom 16:9)

Źródło: https://www.instagram.com/reel/DdZBWMyq4Zx/. Format 1920x1080, 25 kl./s, 66,2 s.

## Cięcia i tempo

- 41 cięć w 66,2 s, czyli 37,2 cięć na minutę.
- Ujęcie trwa średnio 1,58 s (mediana 1,22, od 0,56 do 5,12 s).
- Hak 6,6 s, rozwinięcie 50,2 s, zakończenie 9,4 s.
- Mówiąca głowa (A) to 42% czasu, wstawki (B) 34%, karty w jednolitym kolorze (S) 24%.
- Wzór ujęć: `BBBSSSABBABBBBAASSABABSSBBBASBABASSABBASSA`. Ujęcie elastyczne (przejmuje różnicę długości): nr 42, 5,12 s.
- Rytm (s): 1,16B, 0,88B, 1,12B, 1,88S, 0,88S, 0,68S, 2,20A, 1,64B, 1,08B, 3,12A, 1,12B, 1,08B, 0,68B, 0,80B, 1,08A, 4,68A, 0,92S, 0,56S, 1,84A, 2,36B, 1,32A, 1,08B, 0,88S, 1,92S, 2,08B, 1,00B, 1,28B, 1,64A, 1,40S, 1,80B, 1,48A, 1,08B, 1,80A, 0,76S, 3,12S, 2,24A, 0,96B, 1,16B, 1,56A, 0,96S, 1,76S, 5,12A.
- Pauzy w mowie: powyżej 0,45 s skracane do 0,30 s.
- Głośność rolki: -14,4 LUFS, szczyt 0,6 dBTP, zakres LRA 4,2 LU (cel w szablonie: -14,4 LUFS).
- Mowa: 3,8 słowa na sekundę, 248 słów w całości.

## Kadry

Rozmiar i położenie twarzy w ujęciach z mową, jako ułamki kadru (x: 0% = lewa krawędź, y: 0% = góra).

| Ujęcie | Czas (s) | Plan | Twarz: wysokość | Twarz: x | Twarz: y | Oczy: y |
|---|---|---|---|---|---|---|
| 7 | 6,6-8,8 | plan ogólny | 27% | 50% | 29% | 27% |
| 10 | 11,5-14,6 | plan ogólny | 25% | 49% | 27% | 25% |
| 15 | 18,3-19,4 | plan średni | 37% | 55% | 29% | 27% |
| 16 | 19,4-24,1 | plan ogólny | 23% | 50% | 28% | 26% |
| 19 | 25,6-27,4 | plan ogólny | 24% | 49% | 28% | 26% |
| 21 | 29,8-31,1 | plan ogólny | 27% | 48% | 29% | 27% |
| 28 | 39,3-41,0 | plan ogólny | 26% | 48% | 27% | 25% |
| 31 | 44,2-45,6 | plan ogólny | 26% | 49% | 28% | 26% |
| 33 | 46,7-48,5 | plan ogólny | 27% | 49% | 28% | 26% |
| 36 | 52,4-54,6 | plan ogólny | 26% | 51% | 28% | 26% |
| 39 | 56,8-58,3 | plan ogólny | 26% | 51% | 28% | 26% |
| 42 | 61,0-66,2 | plan ogólny | 24% | 50% | 27% | 25% |

Drabinka: najszerszy kadr ma twarz 23% wysokości, zbliżenia do 37% (1,6 raza więcej). Środek twarzy leży między 27% a 29% wysokości kadru, więc dół kadru zostaje wolny na napisy.

Gdy nie ma osobnego materiału na wstawkę B, wycinamy ją z nagrania z mową:
- detal 1: detal: twarz i oczy (zbliżenie na twarz), zoom x1,70
- detal 2: detal: dłonie i klatka piersiowa (pod twarzą), zoom x1,45

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

## Napisy, karty i elipsa

- Napisy zwykłe (tylko tam, gdzie fraza nic nie obejmuje): do 3 słów naraz, wysokość wersalików 3,0% wysokości kadru (ok. 32 px z 1080), górna krawędź na 57,0% wysokości.
- Fraza: mowa rozpada się na krótkie frazy (zdanie, przecinek i pauza dłuższa niż 0,40 s kończą frazę), w każdej jedno duże słowo (rzeczownik, czasownik, liczba; słowa wyróżnione w scenariuszu `*tak*` są duże zawsze) i małe słowa wokół niego: te przed nim stoją nad nim przy lewej krawędzi bloku, te po nim pod nim przy prawej. Duże słowa mają krój display, odstęp liter -3% wielkości kroju. Każde słowo wskakuje od razu w chwili, gdy pada (jedna klatka, bez animacji), a fraza schodzi 0,12 s po ostatnim słowie albo gdy zaczyna się następna.
  - Na ujęciach z twarzą (A): duże słowo 8,7% wysokości kadru (ok. 94 px z 1080), małe słowa 50% jego wielkości, do 2 przed nim i 1 po nim, blok od 57% wysokości, najwyżej 50% szerokości kadru.
  - Na wstawkach (B): duże słowo 17,0% wysokości kadru (ok. 184 px z 1080), małe słowa 27% jego wielkości, do 3 przed nim i 2 po nim, blok od 38% wysokości, najwyżej 78% szerokości kadru.
- Słowa wyróżnione w scenariuszu (`*tak*`) mają na ujęciach A i B kolor `highlight` (jedyny jasny akcent naraz).
- Karty (ujęcia w jednolitym kolorze, bez nagrania): biała `#F7F4EC`, żółta `#FFD346`; tekst tuszem marki. Na karcie jest to, co w tym czasie słychać.
  - Wiersz (domyślnie karta biała): słowa dochodzą po jednym i za każdym razem wyśrodkowują wiersz, wysokość kroju 8,7% wysokości kadru (ok. 94 px z 1080), najwyżej 80% szerokości; nowy wiersz zaczyna się po zdaniu, przecinku, pauzie albo po 6 słowach.
  - Duże słowo (domyślnie karta żółta): jak fraza, ale większa, 19,0% wysokości kadru (ok. 205 px z 1080), blok wyśrodkowany w pionie.
  - Które karty są które: 4. biała (line), 5. żółta (line), 6. biała (line), 17. biała (line), 18. żółta (line), 23. biała (line), 24. żółta (title), 29. żółta (title), 34. biała (line), 35. żółta (title), 40. biała (line), 41. żółta (title).
- Elipsa: cienka kreska (0,38% wysokości kadru), rysowana na żywo zgodnie z ruchem wskazówek zegara od lewej górnej strony w ciągu 0,4 s, z końcem zachodzącym na początek; obejmuje cały tekst (szerokość 1,12 tekstu, wysokość 2,7 jego wysokości przy jednym wierszu). Na kartach dostaje ją wyróżnione słowo (`*tak*`) i zaczyna się rysować, gdy to słowo pada; w wierszu rośnie razem z kolejnymi słowami.
- Hak: ujęcia 1 i 2 są czarno-białe (reszta ma kolory nagrania).
- Plan grafik to scenariusz (`--graphics`): do Formatu 4 wystarczy sam tekst, wyróżnienia `*tak*` i znaczniki `{...}` jak w innych formatach.
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
  - `lockup`: fraza: jedno duże słowo (gruba groteska) z małymi słowami nad nim, przy lewej krawędzi bloku, i pod nim, przy prawej; słowa wskakują w chwili, gdy padają; powstaje z całej mowy, a słowa wyróżnione w scenariuszu (`*tak*`) są duże zawsze
  - `slide`: karta: jednolity kolor na całym kadrze (biały albo żółty), pod tekstem kart
  - `typeline`: wiersz pisany słowami: słowa dochodzą po jednym w chwili, gdy padają, a wiersz za każdym razem się wyśrodkowuje; wyróżnione słowo dostaje odręczną elipsę
- „Za postacią” (`za: tak`) działa tylko w Formacie 2, w jednym ujęciu.
- Miejsce w kadrze wynika z położenia Twojej twarzy: grafiki trafiają nad głowę, na boki albo pod napisy, nigdy na twarz.

## Opis ujęć

1. (B) Hak: dwa czarno-białe ujęcia z dużymi napisami (wstawki), potem wstawka w kolorze i trzy karty: biała, żółta, biała.
15. (A) Zbliżenie: najazd w obrębie tego samego ujęcia.
16. (A) Najszerszy kadr.
20. (B) Największe zbliżenie twarzy.
42. (A) Ostatnie ujęcie. Elastyczne: przejmuje różnicę długości.
<!-- karta-f4h:end -->
