# MOTION: schemat z lektorem

Film bez mówiącej głowy. Wrzucasz **samo nagranie głosu** (lektora), a narzędzie rysuje cały obraz: animowany schemat
z tarczą, kamerą, która najeżdża i się cofa, czarne plansze z napisami i napisy słowo po słowie. Wszystko w Twoich
kolorach i kroju marki „Linia Kalewski”, a każdy ruch jest ustawiony na słowie, które właśnie pada.

- **Format 1**: mówiąca głowa z cięciami i B-rollem (rolka DeuOaXKtPBb). Szablon `format1`, opis w [STYL.md](STYL.md).
- **Format 2**: gadająca głowa, jedno ujęcie z grafikami (cztery rolki jednego konta). Szablon `format2`, opis w [FORMAT2.md](FORMAT2.md).
- **Format 3**: gadająca głowa v3, cięcia z hasłami i błyskiem przy wstawce (jedna rolka). Szablon `format3`, opis w [FORMAT3.md](FORMAT3.md).
- **Motion** to ten plik: schemat z lektorem. Szablon `motion`, składnia znaczników
  w [GRAFIKI.md](GRAFIKI.md).

Wzorzec: **jedna** rolka (DdttI7oyswS), zmierzona klatka po klatce. Nazwa „motion” to Twoje słowo, numeru
formatu nie nadawałem: jeśli chcesz inną nazwę albo numer, zmienię je w szablonie, interfejsie i dokumentach. W repozytorium są tylko liczby, kolory
i opis konstrukcji, bez obrazu, mowy i tekstów z rolki.

## W skrócie

Liczby ze wzorca (jedna rolka, więc to nie mediany). Pełna karta jest na dole: `python rolka.py style motion`.

| Wymiar | Wzorzec |
|---|---|
| Długość | 23,5 s, pion 9:16, 30 kl./s, bez mówiącej głowy |
| Obraz | tylko grafika: papier z siatką kropek, schemat z tarczą, dwie czarne plansze |
| Tarcza | 8 szprych (co 45°), 7 obrotów w czasie mowy i ósmy w finale, który zamyka okrąg |
| Obrót | o jedną szprychę przeciwnie do ruchu wskazówek; łagodzenie wejściowe i wyjściowe o potędze 5, nominalnie 1,2 s, widoczny ruch ok. 0,67 s, 10-90% w 0,36 s |
| Kamera | rozbudowa na szerokim ujęciu ok. 2 s (promień piasty 15,6% szerokości kadru), potem **twarde cięcie** na zbliżenie (promień piasty 34,5%, czyli ×2,35 względem widoku po finale, gdzie wynosi 14,7%), osiadanie 0,22 s od skali 90,7%, wolny najazd 0,78% na sekundę; w finale twarde cofnięcie do widoku całości z rozmyciem znikającym w 0,8 s |
| Etykiety | wpisywane 18 znaków na sekundę, blok-kursor, po dopisaniu cienki kursor jeszcze 0,25 s |
| Plansze | 2 w rolce (2,0 i 1,7 s), twarde cięcie na ciemną kartę i z powrotem; słowa wchodzą po kolei, wyróżnione frazy dużym krojem |
| Napisy | 1-2 słowa nad schematem na 25,5% wysokości, wyróżnione frazy dużym krojem pod nimi; po finale schodzą pod schemat |
| Mowa | ok. 4,3 słowa na sekundę (policzone z liczby zmian napisów, rozpoznawanie mowy dla wzorca nie było dostępne) |

## Jak zbudowany jest film

Pięć zasad: 1-3 i 5 widać we wzorcu, 4 wynika z systemu marki.

1. **Jedna tarcza, jedna lista kroków.** W piaście stoi temat, na szprychach kolejne hasła. Jedno hasło to jeden obrót
   i jedna etykieta, która wpisuje się w chwili, gdy je wymawiasz.
2. **Kamera pracuje zamiast montażu.** Najpierw szeroko (tarcza rośnie przez 2 s), potem jedno twarde cięcie na zbliżenie
   i kamera zostaje przy aktywnej szprysze aż do finału (przerywają ją tylko plansze).
3. **Czarne plansze są rzadkie i krótkie.** We wzorcu dwie w 23,5 s, każda ok. 2 s, wcięte w środek schematu; tarcza
   dalej pracuje pod nimi (najazd kamery trwa). Dobra praktyka: nie dwie pod rząd i najwyżej jedna na 10-12 s filmu.
4. **Żółty to jedyny jasny akcent.** Aktywna kropka na szprysze i wyróżnione słowa na planszy. Reszta to tusz, papier
   i fiolet.
5. **Finał na pełnym obrazie.** Kamera się cofa, widać wszystkie hasła naraz i tytuł z poleceniem dla widza.

## Elementy: co widać i jak to zrobić tutaj

| Co widać | Element | Znacznik w scenariuszu | Najważniejsze pola |
|---|---|---|---|
| Papier z siatką kropek | `backdrop` | dokładany sam przez szablon | `dark` (ciemna wersja), `grid`, `pitch` |
| Tarcza z piastą, szprychami, etykietami; kamera; obroty | `dial` | `tarcza`, potem `krok` i `finał` | `hub` (tekst piasty), `steps`, `finale`, `closeup_at`, `cps`, `drift`, `label_k` |
| Czarna plansza z napisami w trzech rozmiarach | `cutaway` | `plansza` … `{/plansza}` | `emphasis` (z gwiazdek), `text`, `align`, `x`, `y` |
| Krótki jasny błysk na piaście | `glint` | `błysk` | `x`, `y` (w planie JSON też `w`, `strength`, `dur`) |
| Napisy słowo po słowie nad schematem | `captions` (`style: kinetic`) | dokładane przez szablon, wyróżnienia z `*gwiazdek*` | `max_words`, `y`, `shift`, `emphasis` |

Znaczniki scenariusza (tarcza, krok, finał, plansza, błysk, `*wyróżnienie*`) opisuje tabela w [GRAFIKI.md](GRAFIKI.md).
Plan JSON (`--graphics plan.json`) działa tak samo i przyjmuje wszystkie pola z tabeli wyżej.

## Jak zrobić film w trybie motion

1. **Wybierz temat i hasła.** 4-8 haseł (tarcza ma od 2 do 12 szprych, najlepiej wygląda przy 6-8). Hasło to 1-2 słowa, do
   ok. 12 znaków: etykiety z boku po cofnięciu kamery muszą się zmieścić w kadrze. Tekst w piaście (temat filmu) do ok. 18 znaków.
   Program ostrzega, gdy któryś tekst jest za długi, i podaje, ile znaków się mieści.
2. **Napisz scenariusz ze znacznikami** (przykład niżej). Tekst, który czyta lektor, plus `{tarcza}`, `{krok}`, `{plansza}`
   i `{finał}` w klamrach. `*gwiazdki*` oznaczają frazy, które mają wyskoczyć dużym krojem. Zanim padnie pierwsze hasło, daj
   zdanie wstępne (ok. 2,3 s mowy): tarcza rośnie wtedy na szerokim ujęciu, jak we wzorcu, a kamera tnie na zbliżenie tuż przed hasłem.
3. **Nagraj lektora.** Sam głos, cicho w pomieszczeniu, telefon 15-20 cm od ust, czytasz **dokładnie** to, co poza klamrami
   i bez gwiazdek. Tempo 3,5-4,3 słowa na sekundę. Między hasłami zostaw co najmniej 1,5 s mowy: obrót trwa ok. 0,7 s,
   a etykieta wpisuje się 0,2-0,7 s (kroki bliżej niż 1 s od poprzedniego dostają ostrzeżenie). Pauzy dłuższe niż 0,5 s
   narzędzie skróci do 0,35 s.
4. **Plik.** Nagranie głosu (`.m4a`, `.wav`, `.mp3`, `.aac`, `.ogg`, `.opus`, `.flac`) albo wideo z dźwiękiem: obraz z wideo zostanie
   zignorowany (program to zgłosi).
5. **Film**: `python rolka.py glos.m4a --template motion --graphics scenariusz.txt -o film.mp4`. W interfejsie
   (`python rolka.py serve`) wybierz „Motion”, w kroku 1 wrzuć nagranie głosu, w kroku 3 scenariusz.
6. **Poprawki bez ponownego rozpoznawania mowy**: obok filmu leży `film.slowa.json`. Podgląd jednej klatki w sekundę:
   `python rolka.py grafiki scenariusz.txt --template motion --words film.slowa.json --klatka 14`, potem film jeszcze raz
   z `--words film.slowa.json`.

Napisy rysowane są ze **słów Twojego scenariusza** (poprawna pisownia i wielkie litery), a czasy biorą z mowy. Dzieje się to,
gdy mowa zgadza się ze scenariuszem w co najmniej 80%; inaczej napisy zostają z rozpoznanej mowy i program ostrzega, że lektor
chyba czyta inny tekst.

### Przykład scenariusza (hipotetyczny, podmień na swój temat)

<!-- scenariusz-motion:start -->
```
# Film ok. 35 s: „Formuła dobrego briefu” (tekst hipotetyczny; lektor czyta dokładnie to, co poza klamrami i gwiazdkami)
{tarcza: dobrego briefu | nad: Formuła} Skopiuj tę formułę, jeśli chcesz, żeby twój event miał wynik.
Pierwsza jest {krok: Cel} cel. Jeden cel, który da się zmierzyć.
Druga to {krok: Odbiorca} odbiorca: ktoś, kto ma wyjść z innym zdaniem, niż przyszedł.
Trzecia to {krok: Miara} miara, ustalona przed eventem, nie po nim.
{plansza} Ale jest *jeszcze jedna rzecz*. {/plansza}
Czwarta to {krok: Budżet} budżet, który wynika z celu, a nie z zeszłego roku.
Piąta to {krok: Termin} termin, bo dobry event zaczyna się dziewięć tygodni wcześniej.
Szósta to {krok: Ryzyko} ryzyko, czyli to, co zepsuje wynik, zanim go zobaczysz.
{plansza} Ale tu *większość ludzi* się myli. {/plansza}
Siódma to {krok: Dostawca} dostawca, wybrany do zadania, a nie do ceny.
Ósma to {krok: Decyzja} decyzja: kto powie "tak" i kiedy.
{finał: Zrób zrzut ekranu} To cała formuła. Zapisz ją, zanim zadzwonisz do pierwszej agencji.
```
<!-- scenariusz-motion:end -->

Znacznik działa od następnego słowa: `{krok: Cel}` przed słowem „cel” oznacza, że etykieta zaczyna się wpisywać, gdy to słowo
pada, a tarcza obraca się o jedną szprychę ok. 0,1 s wcześniej. `{tarcza}` stoi na początku, `{finał}` przed ostatnim zdaniem.
Przy tarczy z 8 hasłami pierwsze hasło stoi na górze bez obrotu, każde kolejne obraca tarczę, a finał robi ósmy obrót, który
zamyka okrąg (w tarczy o innej liczbie szprych obrotów jest tyle, ile szprych).

### Przejścia między scenami

Zmianę sceny (np. z tarczy na planszę i z powrotem) możesz zmiękczyć przejściem: `{przejście: rozmycie}` tuż przed `{plansza}` rozmywa
tarczę w papier i wyostrza planszę, `{przejście: przesunięcie | kierunek: lewo}` po `{/plansza}` wyrzuca planszę w bok. Rodzaje (rozmycie, najazd,
przesunięcie, kurtyna, błysk), zmierzone krzywe i składnia: [PRZEJSCIA.md](PRZEJSCIA.md). Bez znacznika cięcie zostaje twarde, jak we wzorcu motion.

## Granice

- **Jedna tarcza na film.** Kroki i finał należą do ostatniej `{tarcza}`; drugiej tarczy w tym samym filmie nie ma.
- **Szprych od 2 do 12**, etykiety krótkie. Przy bardzo długich etykietach program nie kurczy ich poniżej czytelnego rozmiaru
  (ok. 24 px przy szerokości 1080), tylko ostrzega i podaje, ile znaków się zmieści.
- **Lektora nagrywasz Ty.** Narzędzie nie generuje głosu. Bez `faster-whisper` nie ma jak ustawić grafik na słowach, więc
  trzeba podać gotową transkrypcję (`--words`).
- **Scenariusz musi pasować do nagrania**: w mowie znajdziemy co najmniej połowę jego słów (inaczej montaż się zatrzyma),
  a napisy ze scenariusza włączają się od 80%.
- **Render trwa**: w moim środowisku testowym (bez karty graficznej) ok. 3-4 s na sekundę filmu, więc film 30 s to 1,5-2 minuty.
  U Ciebie będzie inaczej. Podgląd jednej klatki liczy się w sekundach.
- **Wzorzec to jedna rolka**, więc liczby ruchu są pomiarem jednego filmu, nie średnią. Narzędzie nie dodaje muzyki ani
  efektów dźwiękowych: dźwięk to Twój głos, wyrównany do -14 LUFS.
- **Interpretacja marki jest moja**: aktywna kropka i wyróżnione słowa na planszach są żółte, obrys piasty fioletowy,
  tekst tuszem na papierze, a wyróżnione frazy w napisach różnią się wielkością, nie kolorem (żółty na papierze byłby
  nieczytelny). Krój to Bricolage Grotesque, nie krój wzorca.
- Sprawdzone na syntetycznym głosie (Piper) i rozpoznawaniu Whisper w środowisku testowym oraz na tonach w testach
  automatycznych, **nie na Twoim nagraniu**. Pierwszy film obejrzyj na telefonie przed publikacją.

## Dodatek: karta stylu szablonu (wygenerowana)

Odświeżysz ją poleceniem `python rolka.py style motion`.

<!-- karta-motion:start -->
# Karta stylu: Motion (schemat z kamerą, lektor, napisy kinetyczne)

Źródło: https://www.instagram.com/reel/DdttI7oyswS/. Format 1080x1920, 30 kl./s, 23,5 s.

## Montaż i kamera

- Obraz powstaje z grafik, z pliku liczy się tylko dźwięk (lektor). Wzorzec: 23,5 s, bez cięć montażowych; zmiany ujęć robi kamera w schemacie i dwie plansze.
- Pauzy w mowie: powyżej 0,50 s skracane do 0,35 s.
- Tempo napisów: ok. 4,3 słowa na sekundę (z liczby zmian napisów).
- Głośność rolki: -14,2 LUFS, zakres LRA 4,1 LU (cel w szablonie: -14,0 LUFS).

## Ruch (zmierzony)

- Rozbudowa na szerokim ujęciu: promień piasty 15,6% szerokości kadru, 8 szprych wyrasta po kolei zgodnie z ruchem wskazówek od góry co 0,055 s, całość trwa ok. 2,0 s.
- Cięcie na zbliżenie: jedna klatka, skala 0,91 → 1 w 0,22 s z doostrzeniem; zbliżenie ×2,35 (promień piasty 34,5%). W zbliżeniu piasta stoi przy dolnej krawędzi, widać szprychę na górze i jej etykietę.
- Wolny najazd w zbliżeniu: +0,78% na sekundę, także pod planszami.
- Obrót o jedną szprychę na krok (7 obrotów w rolce), przeciwnie do ruchu wskazówek, łagodzenie wejściowe i wyjściowe o potędze 5: ruch widać ok. 0,67 s, 10-90% w 0,36 s. Połowa obrotu wypada 0,1 s przed pierwszym znakiem etykiety.
- Pisanie etykiet: 18 znaków na sekundę, blok-kursor kurczy się do szerokości znaku, po dopisaniu cienki kursor jeszcze 0,25 s.
- Plansze (2 w rolce, 2,0 i 1,7 s): twarde cięcie na ciemną kartę i z powrotem; słowa wchodzą po kolei, małe i duże w dwóch wierszach, wyróżnione frazy dużym krojem.
- Finał: twarde cofnięcie kamery do widoku całości z rozmyciem, które znika w 0,8 s; tarcza obraca się jeszcze o jedną szprychę (0,9 s), wraca szprycha startowa, na górze pojawia się tytuł.
- Napisy: małe słowo po słowie nad schematem (1-2 słowa), wyróżnione frazy dużym krojem pod małymi; po finale schodzą pod schemat.

## Kolory

Nagrania nie ma, więc nie ma czego dopasowywać: cały obraz rysują grafiki w kolorach marki.

Marka: Linia Kalewski.

| Kolor | Wartość | Gdzie |
|---|---|---|
| papier | `#F7F4EC` | tło z siatką kropek (w eliptycznej winiecie), tekst w piaście tarczy i małe słowa na planszach |
| tusz | `#1B1440` | piasta, szprychy, kropki i etykiety tarczy, napisy, tło plansz |
| fiolet | `#795DFF` | obrys piasty i cienka linia wewnątrz niej |
| żółty | `#FFD346` | aktywna kropka na szprysze i wyróżnione słowa na planszach: jedyny jasny akcent naraz |

## Grafiki i napisy

- Napisy kinetyczne rysuje warstwa grafik w kroju marki: do 2 słów naraz, górna linia na 25,5% wysokości kadru; słowa wchodzą z rozmyciem i wjazdem od dołu. Napisy biorą słowa z Twojego scenariusza, a czasy z mowy.
- Plan grafik to scenariusz ze znacznikami `{...}` albo plik JSON (`--graphics`); kroki tarczy i plansze mają czasy z mowy.
- Elementy planu:
  - `backdrop`: tło całego filmu: papier z siatką kropek w eliptycznej winiecie (dark: true to ciemna plansza)
  - `dial`: tarcza schematu: piasta z tekstem, szprychy z kropkami i etykietami; rozbudowa na szerokim ujęciu, cięcie na zbliżenie, obrót o jedną szprychę na krok, pisanie etykiet z blokiem-kursorem, cofnięcie kamery z tytułem
  - `cutaway`: plansza na cały kadr z napisami w trzech rozmiarach (małe, duże, drobne), twarde cięcie wejścia i wyjścia
  - `glint`: krótki jasny błysk na piaście przy ważnym słowie
- Wyróżnienia w tekście scenariusza (`*fraza*`) dostają duży krój: na planszach w kolorze wyróżnika (żółtym), w napisach tuszem.

## Opis ujęć

1. (A) lektor i grafiki: obraz powstaje z elementów, nie z nagrania
<!-- karta-motion:end -->
