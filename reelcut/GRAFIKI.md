# GRAFIKI: Format 2 (gadająca głowa), Format 3 i motion z animowanymi elementami w Twoich kolorach

To opis techniczny **Formatu 2** (gadająca głowa), **Formatu 3** (gadająca głowa v3: cięcia, hasła, błysk) i **motion** (schemat
z lektorem): składnia scenariusza, plan JSON, elementy i ich pola. Zasady samych formatów (konstrukcja filmu, słownik elementów,
parametry z rolek wzorcowych): [FORMAT2.md](FORMAT2.md), [FORMAT3.md](FORMAT3.md), [MOTION.md](MOTION.md); przejścia między scenami:
[PRZEJSCIA.md](PRZEJSCIA.md). Opisy i przykłady dotyczą Formatu 2, o ile nie zaznaczono inaczej; znaczniki motion (`tarcza`, `krok`,
`finał`, `plansza`, `błysk`) są w tabeli znaczników i w rozdziale „Motion: znaczniki”, hasła Formatu 3 (`lockup`) w rozdziale
„Format 3: hasła”, a znacznik `przejście` w rozdziale „Przejścia”.

Wzorce: cztery rolki jednego konta (Dez4fPJCR74, DeGQ3NAC2f9, Dd2i55aj43S, DdxAwodlOGG): jeden ciągły take 42-72 s,
zero cięć, kamera nieruchoma. Cała dynamika tych rolek to **animowane grafiki nałożone na mówiącą głowę** i małe napisy
słowo po słowie. Narzędzie odtwarza ten **zestaw elementów i gramatykę animacji** (wejście ze skalą, wjazd i rozmyciem,
kolejne karty co ułamek sekundy, liczniki, tekst pisany na żywo, strzałki rysowane na żywo, kursor jadący po kadrze),
ale w kolorach i kroju marki **Linia Kalewski**. Nie ma tu obrazu ani treści rolek wzorcowych: elementy dostają Twoje
teksty i Twoje obrazy.

## W skrócie

1. **Scenariusz ze znacznikami**: piszesz tekst, który powiesz, i wpisujesz w `{ }` grafiki (rozdział niżej).
2. **Nagranie**: jeden ciągły take, pion, statyw (zasady kadru niżej).
3. **Montaż**: jedna komenda albo przeciągnięcie plików w interfejsie. Program rozpoznaje mowę, dopasowuje do niej Twój
   scenariusz i sam ustawia czasy grafik na słowach.
4. **Kontrola** jednej klatki albo fragmentu bez pełnego renderu.

```
python rolka.py nagranie.mp4 --template format2 --graphics scenariusz.txt
```

W interfejsie (`python rolka.py serve`): w ustawieniach wybierz szablon „Format 2: gadająca głowa”, w kroku 3 („Grafiki”)
przeciągnij `scenariusz.txt` razem z obrazami, których używa, i kliknij **Potnij**.

Szablon `format2` robi jedno ujęcie bez cięć (kadruje Twoją twarz jak we wzorcu, skraca pauzy powyżej 0,5 s do
0,35 s, ustawia głośność −14 LUFS), rysuje napisy słowo po słowie w kroju marki i nakłada grafiki ze scenariusza.
Kolorów nagrania nie zmienia: kolory marki mają grafiki i napisy.

## Rytm wzorców

Z przeglądu klatek co 2 s (oglądane, nie mierzone komputerowo). W rolce Dez4fPJCR74 grafika jest na ekranie w 28 z 30
próbek; w trzech pozostałych w każdej obejrzanej próbce (pierwsze 31-41 s) było widać jakąś grafikę. Dalej:

- pierwsza grafika wchodzi w 1.-2. sekundzie (wcześniej jest sama głowa i napisy);
- często jest kilka elementów naraz (np. chip profilu z licznikiem, karty z podpisami i tytuł), a nowy wchodzi mniej
  więcej co kilka sekund;
- cały obraz jest rozmyty i przyciemniony tylko przy kartach z długim tekstem (w próbkach raz, ok. 29–32 s); poza tym głowa
  jest ostra;
- napisy słowo po słowie idą przez cały film w jednym miejscu, na wysokości klatki piersiowej.

Pisząc scenariusz, celuj w podobną gęstość: pierwszy element w 1.–2. sekundzie, potem nowy co 2–4 s, rozmycie tylko tam,
gdzie karta ma dużo tekstu.

## Szybka pętla: najpierw surowiec, potem grafiki

Rozpoznawanie mowy trwa najdłużej, a grafiki liczą się w sekundach. Dlatego:

```
# 1. surowy montaż z napisami (raz): powstaje nagranie_rolka.mp4 i nagranie_rolka.slowa.json
python rolka.py nagranie.mp4 --template format2

# 2. ocena grafik na klatce albo fragmencie (kilka sekund), tłem jest ten surowy montaż
python rolka.py grafiki scenariusz.txt --words nagranie_rolka.slowa.json --tlo nagranie_rolka.mp4 --klatka 12 --twarz 0.17,0.55,0.45
python rolka.py grafiki scenariusz.txt --words nagranie_rolka.slowa.json --tlo nagranie_rolka.mp4 --od 8 --czas 10 -o podglad.mp4

# 3. film końcowy bez ponownego rozpoznawania mowy
python rolka.py nagranie.mp4 --template format2 --graphics scenariusz.txt --words nagranie_rolka.slowa.json -o final.mp4
```

`--twarz H,X,Y` w podglądzie to położenie Twojej twarzy w kadrze (wysokość, środek x, środek y, ułamki). Wartości, które
zmierzył montaż, program wypisuje w logu („Twarz widoczna… wysokość 17% kadru, środek (55%, 40%)”). Bez `--twarz` podgląd
przyjmuje kadr wzorca. Tło `--tlo` może też być zdjęciem (png, jpg).

## Jak nagrać

| Co | Wartość (z wzorca) | Dlaczego |
|---|---|---|
| Format | pion 9:16, najlepiej 4K lub 1080p | wynik 1080×1920 |
| Kamera | nieruchoma, jeden take | cięć nie ma, zmiany robią grafiki |
| Twarz | wysokość ok. 15% kadru (13–19%), środek ok. 48% szerokości i 46% wysokości | mediana czterech rolek; tak ustawia ją montaż |
| Nad głową | ok. jednej trzeciej wysokości wolnego miejsca | tam lądują tytuły, karty, listy, liczniki |
| Po bokach głowy | wolne pasy | tam lecą liczniki i profil |
| Poziom klatki piersiowej | napisy słowo po słowie (ok. 55% wysokości) | dół zostaje na listy i pigułki |
| Tempo | ok. 4 słowa na sekundę, pauzy do 0,5 s | tak mówi wzorzec; dłuższe pauzy program skraca |
| Tło | spokojne, raczej ciemne | grafiki mają miękki cień, ale jasne, ruchliwe tło zawsze obniża czytelność |

Strefy kadru wyznacza położenie Twojej twarzy i elementy trafiają obok niej, nie na nią. Gdy coś ma być **za postacią**
(poświata za głową, ilustracja wystająca zza ramienia), dopisz `za: tak` (rozdział „Grafiki za postacią”).
Gdy karty z punktami nie mieszczą się w górnej strefie, program ostrzega i zmniejsza tekst; wtedy użyj `strefa: całość`
razem z rozmyciem obrazu (niżej).

## Scenariusz ze znacznikami

To zwykły plik tekstowy (`.txt` albo `.md`) z tekstem, który powiesz, i znacznikami w nawiasach klamrowych.
**Znacznik działa od następnego słowa**, czyli od momentu, w którym je wypowiadasz.

```
{typ: główna treść | pole: wartość | pole: wartość}
{/typ}
```

- Koniec elementu wyznacza `{/typ}` (po poprzednim słowie), `do: fraza z tekstu` (po tej frazie element znika) albo
  `czas: sekundy`. Bez żadnego z nich działa czas domyślny elementu (tabela niżej).
- `przesuń: -0,3` przesuwa start o sekundy (ujemne = wcześniej).
- `strefa:` góra, lewo, prawo, dół, głowa, całość (albo `x: 0,5 | y: 0,3`, środek elementu w ułamkach kadru).
- Położenia i rozmiary podajesz jako ułamek kadru (`0,3`) albo w procentach (`30%`). Punkt to dwie liczby: `od: 20%; 30%`.
- `za: tak` rysuje element za Twoją sylwetką (rozdział „Grafiki za postacią”).
- `wejście:` i `wyjście:` zmieniają czas wejścia i wyjścia (sekundy), `rozmycie: tak` dokłada rozmycie obrazu na czas elementu.
- Linie zaczynające się od `#` lub `//` oraz tekst w `[nawiasach kwadratowych]` to uwagi: nie są mową i nie liczą się
  do dopasowania.
- Nazwy mogą mieć polskie znaki albo bez nich (`tytuł`/`tytul`, `oś`/`os`), wielkość liter nie ma znaczenia. Nazwy pól
  z planu JSON (`text`, `accent`, `zone`…) też działają.
- Listy rozdzielasz średnikiem. `Etykieta = opis` dzieli element na część główną i dodatkową. Wartości `tak`/`nie`
  to prawda/fałsz, liczby z przecinkiem dziesiętnym są liczbami.

### Przykład (hipotetyczny, do podmiany na Twój temat)

```
# Film 45 s: „Brief eventowy w trzech krokach” (tekst hipotetyczny, podmień na swój)
{plakietka: Brief eventowy | numer: 1 | strefa: góra}
Częsty błąd w briefie to {tytuł: Brak celu | akcent: błąd nr 1 | styl: serif} zaczynanie od budżetu, a nie od celu.
{licznik: 700+ | podpis: wydarzeń B2B | strefa: lewo} Zrobiłem ich ponad siedemset i zawsze sprawdzam trzy rzeczy:
{kroki: Cel = Co ma się zmienić; Odbiorca = Kto decyduje; Pomiar = Skąd wiem, że zadziałało | aktywne: po pierwsze cel; po drugie odbiorca; po trzecie pomiar | strefa: dół} po pierwsze cel, po drugie odbiorca, po trzecie pomiar. {/kroki}
{karty: Wigilia = Cel: *integracja* / Pomiar: ankieta; Konferencja = Cel: *sprzedaż* / Pomiar: leady; Targi | rozmycie: tak | strefa: całość | do: z moich realizacji} Zobacz trzy przykłady z moich realizacji, każdy zaczął się od celu.
{wyróżnienie: Wniosek: | tekst: cel najpierw, budżet potem | ikona: bulb} Cel najpierw, budżet potem.
```

### Znaczniki

| Znacznik | Główna treść | Najważniejsze pola | Co robi | Czas domyślny |
|---|---|---|---|---|
| `tytuł` | tekst tytułu | `akcent` (małe słowo obrócone nad prawym końcem), `styl` serif/bold, `rozmiar`, `strefa` | duży żółty napis, wejście ze skalą i rozmyciem | 3 s |
| `plakietka` | tekst | `numer` | numer w fioletowym kole i tytuł obok | 4 s |
| `licznik` | liczba z jednostką: `700+`, `15 834 zł`, `2,5 mln` | `podpis`, `od`, `pasek` tak/nie, `rozmiar` | duża liczba odliczana do wartości, pasek postępu | 4 s |
| `karty` | `Etykieta = punkt / punkt; Etykieta; …` (w punktach `*wyróżnienie*` świeci żółto) | `obrazy: a.jpg; ; c.png` (puste = miniatura-zaślepka), `etykiety: szeryf` (kursywa szeryfowa) albo `żółte`, `wyświetlenia: 153K; ; 12,4K` (oko z liczbą pod kartą), `fokus: 1`, `focus_at: 2,5`, `układ: grid`, `kolumny`, `strefa` | rząd miniatur 9:16 wjeżdżających kolejno, jedna może się powiększyć | 4 s |
| `profil` | podpis | `tryb` mini/full, `licznik: 25; 60`, `jednostka`, `pasek: 0,3; 1`, `znacznik`, `korona: tak`, `kursor: nie`, `badge: clock` | chip z Twoją twarzą (wycięta z nagrania), licznikiem, paskiem i kursorem | 6 s |
| `pigułki` | `Tekst = znacznik; …` | `rozmiar`; style i ikona przy każdej: w planie JSON | etykiety wlatujące na przemian z lewej i prawej | 4 s |
| `kafelki` | `Etykieta = wartość; …` | `chip_w` | małe kafelki z odliczaną wartością | 4 s |
| `kroki` | `Tytuł = opis; …` | `aktywne: fraza; fraza; …` (kiedy zmienia się aktywny krok; frazy muszą paść w mowie), `szerokość` | lista w szklanym panelu, aktywny krok pośrodku | 6 s |
| `oś` | podpisy od najniższego | `step` | wykres schodkowy w kształcie litery L, ostatni punkt żółty | 6 s |
| `paski` | podpisy wierszy | rodzaje pasków: w planie JSON | wiersze z paskami albo obracającym się kółkiem | 5 s |
| `wyróżnienie` | tytuł | `tekst` (pisany na żywo), `ikona` bulb/check/star/none, `hasło` (szeryfowy podpis po prawej), `obraz` (karta po prawej), `cps` | kafelek z ikoną i tekstem pojawiającym się znak po znaku | 5 s |
| `ilustracja` | nazwa pliku | `szerokość`, `poświata` (nie: bez poświaty), `kotwica: głowa`, `obrót`, `przezroczystość`, `za: tak`, `wystaje: tak` (może wyjść za kadr); ruch po ścieżce: `path` w planie JSON | obraz z miękką poświatą, np. nad głową; jedzie, rośnie i obraca się wg ścieżki | 3 s |
| `tekst` | tekst; `*wyróżnienie*` świeci żółto, `_kursywa_` to krój szeryfowy, `\n` łamie wiersz | `rozmiar`, `krój` (szeryf, gruby, pogrubiony, półgruby, zwykły), `kolor`, `zaznaczenie` (pędzel, nawias, podkreślenie), `odsłanianie` (zanik, pisanie, słowa), `znacznik` (mała żółta etykieta pod tekstem), `x`, `y` albo `strefa` | tekst z formatowaniem, odsłaniany albo pisany na żywo | 3,5 s |
| `strzałka` | (brak) | `od`, `cel` (punkty), `łuk` (0 = prosta, 0,25 = wyraźny łuk, minus = w drugą stronę), `styl` (ciągła, przerywana, kropkowana), `grot` (otwarty, pełny, brak), `grubość`, `kolor` | linia rysowana na żywo od początku do końca | 3 s |
| `opisy` | `Tekst @ x y > cel_x cel_y; …` (bez `>` sam napis) | `kolor`, `rozmiar`, `krój`, `linia` (ciągła, przerywana, kropkowana, brak), `łuk` | napisy z cienką linią i kropką, które wskazują miejsce | 5 s |
| `lista` | `Etykieta = tekst / komentarz; …`, `+` na początku = odhaczone | `zaznaczenie` (brak, kropka, ramka), `pismo` (szeryf, zwykły), `rozmiar`, `szerokość`, `x`, `y` albo `strefa` | wiersze pojawiające się po kolei, treść „pisana” na żywo | 8 s |
| `porównanie` | `Tytuł: wiersz; wiersz // Tytuł: wiersz` | jak `lista` plus `rule: tak` (kreska między kolumnami), `rule_to` | dwie kolumny z kreską pośrodku | 8 s |
| `pierścień` | (brak) | `x`, `y` (środek), `rx`, `ry`, `kropki`, `luki: 100..260; -80..80` (kąty: 0 to góra, rosną zgodnie ze wskazówkami zegara), `rozmiar`, `kolor` | kropki układają się w pierścień albo łuki wokół wskazanego miejsca | 3,5 s |
| `rozmycie` | (brak) | `siła` (14), `ściemnienie` (0,25) | rozmywa i przyciemnia cały obraz na czas działania, żeby grafiki były czytelne | 3 s |
| `tarcza` | tekst piasty (duży wiersz) | `nad` (mały wiersz nad nim), `szybkość` (znaków na sekundę przy pisaniu, 18), `najazd` (najazd w zbliżeniu na sekundę, 0,0078), `zbliżenie` (sekunda cięcia na zbliżenie, domyślnie 0,3 s przed pierwszym krokiem), `wielkość etykiet` (ułamek promienia piasty, 0,25) | **Motion.** Tarcza schematu z kamerą: rozbudowa na szerokim ujęciu, twarde cięcie na zbliżenie, obroty, finał. Zbiera kolejne `{krok}` i `{finał}` | od znacznika do końca mowy |
| `krok` | etykieta szprychy (1-2 słowa) | (brak) | **Motion.** Hasło na kolejnej szprysze: tarcza obraca się o jedną szprychę (połowa obrotu 0,1 s przed pierwszym znakiem), etykieta wpisuje się od następnego słowa | wpisanie ok. 0,2-0,7 s |
| `finał` | tytuł na końcu | (brak) | **Motion.** Twarde cofnięcie kamery do widoku całości z tytułem, ósmy obrót zamyka okrąg; napisy schodzą pod schemat | do końca filmu |
| `plansza` | (brak: słowa biorą się z mowy) | `x`, `y`, `wyrównanie` (lewo, środek), `czas` | **Motion.** Czarna plansza na cały kadr, twarde cięcie; słowa z mowy wchodzą po kolei, `*wyróżnione*` jako duże żółte. Koniec: `{/plansza}` (plus 0,3 s po ostatnim słowie) | 2 s |
| `błysk` | (brak) | `x`, `y` (środek, domyślnie piasta na szerokim ujęciu) | **Motion.** Krótki jasny błysk przy ważnym słowie | 0,2 s |
| `przejście` | rodzaj: `rozmycie`, `najazd`, `przesunięcie`, `kurtyna`, `błysk` | `kierunek` (lewo, prawo, góra, dół), `moc` (0-3, domyślnie 1), `dokładnie: tak` (bez przyciągania do granicy sceny) | Obróbka obrazu w chwili cięcia: stara scena wychodzi, nowa wchodzi. Nie jest elementem (rozdział „Przejścia”, [PRZEJSCIA.md](PRZEJSCIA.md)) | okno 0,2-0,7 s wokół cięcia |

Obrazy podajesz samą nazwą pliku; plik leży obok scenariusza (w interfejsie wrzucasz je razem ze scenariuszem).
Wspierane: png (także z przezroczystością), jpg, webp.

Poza klamrami działa jeszcze jedno oznaczenie: `*fraza*` w samym tekście mowy (np. „Ale jest *jeszcze jedna rzecz*.”). W trybie motion
takie słowa dostają duży krój: na planszy żółty, w napisach tuszem. W Formacie 3 z wyróżnionych słów powstaje **hasło** (duże słowo
z małymi nad i pod nim, rozdział „Format 3: hasła”). W Formacie 1 i 2 gwiazdki nic nie zmieniają. Gwiazdki nie liczą się do dopasowania
do mowy, a scenariusz z samymi gwiazdkami, bez żadnego `{ }`, jest poprawnym planem.

### Jak to jest dopasowane do mowy

Program porównuje Twój tekst z transkrypcją (bez względu na wielkość liter, polskie znaki i interpunkcję). Słowa, które
rozpoznawanie przekręciło, dostają czas z interpolacji między sąsiednimi trafieniami, więc literówka w transkrypcji nie
psuje czasów. Jeśli w mowie znajdzie mniej niż połowę słów scenariusza, montaż zatrzymuje się z komunikatem „Scenariusz nie
pasuje do nagrania” (to zwykle zły plik albo mocno improwizowany tekst). Improwizację możesz zostawić: liczą się te słowa,
które się zgadzają, a znacznik ląduje przy następnym trafionym słowie.

## Motion: znaczniki

Lektor czyta tekst, a obraz powstaje z grafik (szablon `motion`, opis formatu: [MOTION.md](MOTION.md)). Znaczniki działają
tak samo jak w Formacie 2 (od następnego słowa), ale kilka z nich składa się w jeden element:

- `{tarcza: …}` otwiera tarczę. **`{krok: …}` i `{finał: …}` należą do ostatniej tarczy przed nimi**, więc jedna tarcza na film,
  a każdy `{krok}` bez wcześniejszej `{tarcza}` kończy się komunikatem.
- Czas kroku to początek następnego słowa scenariusza: etykieta zaczyna się wpisywać, gdy to słowo pada, a tarcza obraca się
  o jedną szprychę ok. 0,1 s wcześniej. Pierwszy krok stoi na górze bez obrotu.
- `{finał: Tytuł}` ustawia cofnięcie kamery. Musi paść co najmniej 0,2 s po ostatnim kroku.
- Cięcie na zbliżenie robi się samo 0,3 s przed pierwszym krokiem (`zbliżenie:` zmienia sekundę).
- Tło (papier z siatką kropek) i napisy kinetyczne dokłada szablon: nie wpisujesz ich w scenariusz. Napisy biorą słowa z Twojego
  tekstu, a czasy z mowy (przy zgodności co najmniej 80%).

Ten sam film jako plan JSON (tak scenariusz zamienia się w plan; czasy w sekundach na osi gotowego filmu):

<!-- plan-motion:start -->
```json
{
  "schema": 1,
  "elements": [
    {"type": "backdrop", "at": 0, "dur": 40},
    {"type": "dial", "at": 0, "dur": 38, "hub": ["Formuła", "dobrego briefu"],
     "steps": [{"label": "Cel", "at": 5.4}, {"label": "Odbiorca", "at": 9.5}, {"label": "Miara", "at": 14.8}],
     "finale": {"at": 22.0, "title": "Zrób zrzut ekranu"}},
    {"type": "cutaway", "at": 17.0, "dur": 2.4, "text": "Ale jest *jeszcze jedna rzecz*"},
    {"type": "glint", "at": 5.4},
    {"type": "captions", "style": "kinetic", "max_words": 2, "y": 0.255, "shift": [{"at": 22.0, "dur": 3600, "y": 0.8}]}
  ]
}
```
<!-- plan-motion:end -->

| Pole | Znaczenie |
|---|---|
| `dial`: `hub` | `[mały wiersz, duży wiersz]` albo sam tekst; tekst kurczy się, żeby zmieścić się w piaście (ostrzeżenie przy dłuższym niż ok. 18 znaków) |
| `dial`: `steps` | od 2 do 12 pozycji `{label, at}` z rosnącymi czasami; krok bliżej niż 1 s od poprzedniego daje ostrzeżenie |
| `dial`: `finale` | `{at, title}`; `at` co najmniej 0,2 s po ostatnim kroku |
| `dial`: `closeup_at`, `cps`, `drift`, `label_k` | sekunda cięcia na zbliżenie (nie później niż pierwszy krok), znaki na sekundę, najazd na sekundę, wielkość etykiet jako ułamek promienia piasty |
| `cutaway`: `emphasis`, `text`, `words` | przedziały `[od, do]` (s) słów wyróżnionych; własny tekst z `*wyróżnieniem*` (gdy nie ma mowy w oknie planszy); albo własne słowa `[{w, t, tier}]` z rozmiarem `small`, `big`, `tiny` |
| `cutaway`: `align`, `x`, `y`, `big_color` | wyrównanie (`left`, `center`), położenie bloku (ułamki kadru), rola koloru wyróżnionych słów (domyślnie `highlight`) |
| `glint`: `x`, `y`, `w`, `strength`, `dur` | środek (ułamki kadru), szerokość (ułamek W), siła 0-1, czas (0,2 s) |
| `captions` + `style: kinetic` | `max_words`, `y` (górna linia), `hold`, `emphasis`, `shift` `[{at, dur, y}]` (okna, w których napisy stoją niżej) |

## Format 3: hasła

Szablon `format3` (opis formatu: [FORMAT3.md](FORMAT3.md)) robi cięcia jak Format 1, a napisy, hasła i błysk rysuje warstwa grafik.
**Hasło (`lockup`)** powstaje samo ze słów w gwiazdkach: `Co ma się *zmienić* po tym evencie?` daje duży wiersz „zmienić” (jedno albo
dwa słowa, szeryfowa kursywa, żółty), nad nim do 3 małych słów, pod nim do 3, wyjustowanych do szerokości dużego słowa; każde słowo
wskakuje w chwili, gdy je mówisz. Hasło nie wychodzi poza zdanie, przecinek ani pauzę dłuższą niż 0,45 s, a słowa, które padają zaraz po
ostatnim (i mignęłyby krócej niż 0,25 s), zostają zwykłym napisom. Na czas hasła jego słowa znikają z napisów (`skip`), a napisy się chowają (`hide`).

Ustawienia hasła są w szablonie (`graphics.lockup`): `pre`, `post` (ile małych słów przed i za), `big_max` (ile dużych), `max_gap_s`, `hold`
(przytrzymanie po ostatnim słowie, 0,25 s), `lead` (o ile wcześniej niż mowa, 0,04 s), `min_visible` oraz pola wyglądu z tabeli niżej.
Własne hasło, niezależne od gwiazdek, wpisujesz w planie JSON jako element `lockup`:

<!-- plan-lockup:start -->
```json
{
  "schema": 1,
  "elements": [
    {"type": "lockup", "at": 3.2, "lines": [
      {"tier": "small", "words": [{"w": "Co", "t": 0.0}, {"w": "ma", "t": 0.2}, {"w": "się", "t": 0.35}]},
      {"tier": "big", "words": [{"w": "zmienić", "t": 0.55}]},
      {"tier": "small", "words": [{"w": "po", "t": 1.0}, {"w": "tym", "t": 1.15}, {"w": "evencie?", "t": 1.3}]}
    ]},
    {"type": "captions", "weight": "bold", "max_words": 4, "size": 0.0225, "y": 0.504, "skip": [[3.2, 4.65]], "hide": [[3.16, 4.9]]}
  ]
}
```
<!-- plan-lockup:end -->

| Pole | Znaczenie |
|---|---|
| `lines` | wiersze od góry: `{tier: small albo big, words: [{w, t}]}`; `t` to sekundy od początku elementu, w których słowo wskakuje |
| `dur` | czas trwania (domyślnie czas ostatniego słowa plus 0,55 s; hasła ze scenariusza mają go policzonego z mowy) |
| `color`, `small_color` | role koloru dużych i małych słów (domyślnie `highlight`, czyli żółty, i `text`, czyli biały) |
| `big_font`, `small_font` | krój dużych (domyślnie `serif_italic`; `display` to gruby Bricolage) i małych słów (domyślnie `text`) |
| `size`, `y`, `max_width`, `shadow` | wielkość dużego słowa (ułamek wysokości kadru, 0,101; szeryfowy krój dostaje jeszcze ×1,3), górna krawędź bloku (0,486), największa szerokość (0,78 kadru), siła cienia (0,45) |
| `captions`: `skip`, `hide` | przedziały `[od, do]` w sekundach: słowa z tych przedziałów nie trafiają do napisów, a w przedziałach `hide` napisów nie widać |

Błysk przy wstawkach jest w szablonie: `fx: [{"type": "flash", "edge": "start"}]` na ujęciu daje błysk na jego początku, `"edge": "end"` na końcu.
Szczegóły i krzywa błysku: [PRZEJSCIA.md](PRZEJSCIA.md).

## Przejścia

`{przejście: rodzaj | kierunek: ... | moc: ...}` w scenariuszu albo lista `transitions` w planie JSON (`{"kind": "blur", "at": 4.0}`): stara scena
wychodzi, nowa wchodzi, w oknie 0,2-0,7 s wokół cięcia. Rodzaje: `rozmycie`, `najazd`, `przesunięcie`, `kurtyna`, `błysk`. Przejście ze scenariusza
przyciąga się do najbliższej granicy sceny (do 0,6 s). Pełny opis, liczby ze wzorca i granice: [PRZEJSCIA.md](PRZEJSCIA.md).

## Plan w pliku JSON (dla zaawansowanych)

To samo, co robi scenariusz, w postaci pliku: `--graphics plan.json`. Scenariusz zamienia się w taki plan automatycznie.

```json
{
  "schema": 1,
  "elements": [
    {"type": "title", "at": "brak celu", "text": "Brak celu", "accent": "błąd nr 1", "style": "serif", "zone": "bottom"},
    {"type": "stat", "at": 12.4, "dur": 4, "value": 700, "suffix": "+", "label": "wydarzeń B2B", "zone": "left"},
    {"type": "cards", "at": "trzy przykłady", "until": "z moich realizacji", "zone": "full",
     "items": [{"label": "Wigilia", "kind": "play", "bullets": ["Cel: *integracja*"]}, {"label": "Targi", "image": "targi.jpg"}]}
  ],
  "effects": [{"type": "blur", "at": "trzy przykłady", "until": "z moich realizacji", "sigma": 14, "dim": 0.3}]
}
```

**Czas elementu** to sekundy na osi gotowego filmu albo **fraza z mowy**:

| Pole | Znaczenie |
|---|---|
| `at` | liczba (sekundy) albo fraza: czas, w którym zaczynasz ją mówić |
| `nth` | które wystąpienie frazy (domyślnie 1) |
| `shift` | przesunięcie startu w sekundach |
| `until` | fraza: element trwa do końca jej ostatniego słowa (szukana po starcie); `until_shift` przesuwa koniec |
| `dur` | czas trwania w sekundach (gdy nie ma `until`) |
| `in`, `out` | czas wejścia i wyjścia |
| `zone` | `top`, `left`, `right`, `bottom`, `head`, `full` |
| `x`, `y`, `dx`, `dy` | środek elementu w ułamkach kadru i przesunięcie; wyłączają strefę |
| `active`, `focus_at`, `count_at` | czasy względem startu elementu: liczby albo frazy |

Fraza musi paść w mowie tak, jak ją zapisałeś (wielkość liter, polskie znaki i interpunkcja nie mają znaczenia, drobne
różnice zapisu w dłuższych słowach też nie). Gdy nie znajdzie, komunikat pokaże najbliższy fragment transkrypcji i jego
czas. Plan z frazami wymaga transkrypcji: program rozpozna mowę sam albo weź gotową (`--words`).

Wszystkie pola elementów (tytuł, plakietka, karty, profil z `path` ruchu kursora, pigułki ze stylami, kafelki, kroki, oś,
paski ze spinnerem, wyróżnienie, licznik, ilustracja, tekst, strzałka, opisy, lista, pierścień) opisują komentarze w kodzie:
`src/reelcut/graphics/`.

### Elementy Formatu 2 w planie JSON

Tego, czego scenariusz nie wyrazi (karty w dowolnym miejscu, ścieżka ilustracji), używasz w planie JSON. Pliki obrazów
leżą obok planu.

<!-- plan-f2:start -->
```json
{
  "schema": 1,
  "elements": [
    {"type": "illustration", "at": 2.0, "dur": 20, "image": "schemat.png", "width": 0.6, "glow": false, "behind": true, "bleed": true,
     "path": [[0, 0.5, 0.2, 1.0, 0], [6, 0.8, 0.45, 1.4, 6], [14, 0.8, 0.45, 1.4, 6]]},
    {"type": "cards", "at": 9.0, "dur": 10, "label_style": "serif",
     "items": [{"label": "Pierwsza", "image": "a.jpg", "x": 0.27, "y": 0.22, "w": 0.24, "rot": -4, "views": "153K"},
               {"label": "Druga", "kind": "blank", "x": 0.73, "y": 0.22, "w": 0.21, "rot": 3, "label_style": "yellow", "at": 1.2}]},
    {"type": "arrow", "at": 10.0, "dur": 4, "from": [0.45, 0.3], "to": [0.58, 0.3], "bend": 0.2, "style": "dashed", "head": "filled"},
    {"type": "ring", "at": 11.0, "dur": 4, "x": 0.27, "y": 0.22, "rx": 0.17, "arcs": [[100, 260], [-80, 80]]}
  ]
}
```
<!-- plan-f2:end -->

| Pole | Znaczenie |
|---|---|
| `behind` | `true`: element jest za Twoją sylwetką (dowolny typ) |
| `bleed` | `true`: element może wychodzić poza kadr bez ostrzeżenia (ilustracja wystająca zza krawędzi) |
| ilustracja: `path` | klatki kluczowe `[czas od startu elementu, x, y, skala, obrót]`; skala i obrót są opcjonalne, ruch jest płynny |
| ilustracja: `rot`, `opacity` | stały obrót w stopniach, krycie 0-1 |
| karta: `x`, `y`, `w`, `rot` | środek (ułamki kadru), szerokość (ułamek szerokości kadru) i obrót karty; pozostałe karty układają się w rzędzie |
| karta: `at`, `views`, `label_style` | start tej karty (sekundy od startu elementu), licznik wyświetleń pod kartą, styl podpisu: `bold`, `serif`, `yellow` |

## Marka i kolory

Marka „Linia Kalewski” (`src/reelcut/data/brand_kalewski.json`): tusz `#1B1440`, fiolet `#795DFF`, fiolet ciemny
`#6343FF`, żółty `#FFD346`, papier `#F7F4EC`, biel `#FFFFFF`. Kroje: Bricolage Grotesque (800 tytuły, 500–700 treść) i
Instrument Serif Italic (tytuły szeryfowe), oba na licencji OFL, w paczce.

| Rola | Kolor | Do czego |
|---|---|---|
| `text` | biel | napisy i tekst na grafikach |
| `title` | żółty | tytuły |
| `accent` | fiolet | etykiety, linie, pierścienie |
| `accent_strong` | fiolet ciemny | plakietki, tła kart |
| `highlight` | żółty | **jedyny jasny element naraz**: liczba, kursor, aktywna pozycja, słowo kluczowe |
| `panel` | tusz | tło paneli |

We wzorcach akcentem jest pomarańcz (Dez4fPJCR74) albo żółty (pozostałe trzy rolki). Tutaj rolę jedynego jasnego akcentu
zawsze pełni żółty marki, a fiolet jest kolorem etykiet, linii i tła kart.

Reguła marki: żółty to jeden akcent naraz (najważniejszy element), nie dekoracja. Kolory po kompresji H.264 różnią się
od wzoru o ±2 na kanał (sprawdzone na wyjściu: `#6343FF` wraca jako `#6142FD`, `#FFD346` jako `#FED246`).

Kursywa szeryfowa (Instrument Serif) pochodzi ze wzorca: tytuły z małym słowem-akcentem, podpisy kart (`etykiety: serif`)
i hasło przy wyróżnieniu. Jeśli system marki dopuszcza wyłącznie Bricolage Grotesque, wskaż w `fonts.serif_italic`
pliku marki krój Bricolage, a wszystkie te elementy przełączą się na niego.

Inna marka: skopiuj `brand_kalewski.json`, zmień kolory, role i kroje i podaj `--brand moja_marka.json` (albo `"brand"`
w planie). Pliki krojów podajesz względem folderu `fonts` obok pliku marki.

## Efekty i czytelność

- **Rozmycie obrazu** (`rozmycie`, `rozmycie: tak`): rozmywa i przyciemnia nagranie, gdy pokazujesz karty z tekstem.
  Wejście i wyjście trwają 0,4 s.
- Tytuły, liczniki, wyróżnienia i napisy słowo po słowie mają miękki, ciemny cień (pole `shadow`: 0 wyłącza), więc żółty
  tytuł da się przeczytać także na jasnym tle. Na bardzo ruchliwym tle i tak lepiej wesprzeć się rozmyciem.
- **Kontrola układu przy każdym montażu i podglądzie.** Program rysuje każdy element pod koniec jego życia i ostrzega, gdy
  (1) dwa elementy zajmują tę samą strefę w tym samym czasie, (2) element nie mieści się w kadrze (np. lista kroków w wąskiej
  strefie „prawo”), (3) element zasłania twarz (np. cokolwiek w strefie „całość” bez `x`/`y` ląduje na środku), chyba że
  w tym czasie obraz jest rozmyty. Ostrzeżenia dostajesz w logu i pod filmem, nic nie jest wtedy ukrywane ani poprawiane
  po cichu: przestaw `strefa` (albo `x`/`y`), skróć tekst albo przesuń czas.
- Teksty w wąskich strefach (tytuł, plakietka, licznik, rząd kafelków) **same się zmniejszają**, żeby się zmieścić (do 45% rozmiaru).

## Grafiki za postacią

`za: tak` w scenariuszu albo `"behind": true` w planie rysuje element **pod Twoją sylwetką**: poświatę za głową, ilustrację
wystającą zza ramienia, kartę chowającą się za dłonią. Zasady:

- Sylwetkę wycina model MODNet (Apache-2.0, 26 MB). Program pobiera go **raz** do `~/ReelCut/modele` (suma SHA-256 jest
  sprawdzana), potem działa bez internetu. Własny plik: zmienna `REELCUT_MODNET`.
- Potrzebne są `numpy` i `onnxruntime` (te same co do kadrowania twarzy).
- Sylwetka jest liczona tylko w oknach czasu, w których jest taki element (15 klatek na sekundę), więc koszt rośnie z liczbą
  takich okien, nie z długością filmu.
- Działa tylko w Formacie 2 (jedno ujęcie). Gdy modelu albo pakietów brak, element rysuje się z przodu, a program mówi o tym
  w ostrzeżeniu.
- Podgląd jednej klatki też uwzględnia sylwetkę: `python rolka.py grafiki plan.json --tlo nagranie_rolka.mp4 --klatka 12`.
- Sprawdzone na klatkach z rolek wzorcowych i na zdjęciu, **nie na Twoim nagraniu**. Obejrzyj brzegi (włosy, palce, rękawy).

## Napisy słowo po słowie

Szablon rysuje je sam, w Bricolage Grotesque: do 3 słów naraz, wysokość wersalików 2,0% wysokości kadru (39 px z 1920),
górna krawędź na 54,8% wysokości (klatka piersiowa). Poprawki literówek: edytujesz `*.slowa.json` (pole `w`, czasów nie
ruszaj) i uruchamiasz ponownie z `--words`. W Formacie 3 napisy to porcje do 4 słów (pogrubione, 2,25% kadru, górna krawędź na 50,4%),
a słowa biorą się ze scenariusza, jeśli mowa zgadza się z nim w co najmniej 80%.

## Czego to narzędzie nie robi

- **Domyślnie grafiki leżą obok postaci, nie za nią.** Za postacią stawia je dopiero `za: tak` (wycinanie sylwetki,
  tylko Format 2, patrz wyżej); strefy domyślne są liczone z położenia twarzy.
- **Karty nie odtwarzają wideo.** Pokazują obraz, który podasz, albo zaślepkę w barwach marki (ciemna miniatura z przyciskiem
  odtwarzania, pusta karta z kreskami).
- **Treści są Twoje.** Teksty, liczby i obrazy podajesz Ty. Narzędzie niczego nie wymyśla.
- **Awatar to kwadratowy wycinek Twojej twarzy** z nagrania w kółku, a nie wycięta postać. Bez wykrytej twarzy
  (brak `numpy`/`onnxruntime` albo twarz niewidoczna) pojawia się neutralna sylwetka.
- **Panele „szklane” nie rozmywają tła** (są półprzezroczyste z poświatą).
- **Motion:** jedna tarcza na film, od 2 do 12 szprych, lektora nagrywasz sam (narzędzie nie generuje głosu); granice i uczciwe
  zastrzeżenia: [MOTION.md](MOTION.md).
- **Format 3:** brak cyfrowych najazdów w trakcie ujęcia, kursywa zamiast grubego szeryfu w hasłach, grafiki „za postacią” nie działają
  przy cięciach; granice: [FORMAT3.md](FORMAT3.md). Przejścia obrabiają grafiki, nie nagranie (poza błyskiem): [PRZEJSCIA.md](PRZEJSCIA.md).
- **Wymaga Pillow:** `pip install pillow`. Bez niego montaż działa jak dawniej, a z planem grafik zatrzymuje się z komunikatem.
- **Sprawdzone na materiale syntetycznym i na klatkach wzorca**, nie na Twoich nagraniach. Pierwszy film obejrzyj uważnie
  (kadr twarzy, strefy, czytelność), a rozmieszczenie dostrój polami `strefa`, `x`, `y`.

## Najczęstsze komunikaty

| Komunikat | Co zrobić |
|---|---|
| „Nie znalazłem w mowie frazy „…”. Najbliższy fragment: „…” w 12,4 s” | zapisz frazę tak, jak pada w `.slowa.json` |
| „Scenariusz nie pasuje do nagrania” | sprawdź, czy to ten plik; porównaj z `.slowa.json` |
| „Plan używa fraz z mową…, a nie ma transkrypcji” | uruchom z napisami (rozpoznawanie mowy) albo podaj `--words` |
| „zajmują strefę … w tym samym czasie” | zmień `strefa` jednego z nich albo przesuń czas |
| „nie mieści się w kadrze” | element jest za szeroki na wybraną strefę: inna strefa, krótszy tekst albo mniejszy `rozmiar` |
| „zasłania twarz” | inna strefa albo `rozmycie: tak` na ten czas; `strefa: głowa` i `kotwica: głowa` to świadomy wybór |
| „karty zmieściły się tylko w szerokości … px” | `strefa: całość` i `rozmycie: tak`, krótsze punkty albo mniej kart naraz |
| „Do grafik potrzebny jest pakiet Pillow” | `pip install pillow` |
| „Nie udało się pobrać modelu wycinania postaci… Grafiki za postacią rysuję przed nią” | pobierz model ręcznie z adresu z komunikatu i zapisz jako `~/ReelCut/modele/modnet_fp32.onnx` (albo wskaż plik zmienną `REELCUT_MODNET`); do tego `pip install numpy onnxruntime` |
| „Grafiki za postacią (behind) działają w formacie 2…” | użyj szablonu `format2` (jedno ujęcie) |
| „Znacznik „{…}”: nieznany typ” | lista typów w komunikacie; nazwy jak w tabeli powyżej |
| „Motion potrzebuje lektora, a w pliku nie ma dźwięku” | wskaż nagranie głosu (`.m4a`, `.wav`, `.mp3`) albo wideo z dźwiękiem |
| „Znacznik „{krok: …}” musi stać po znaczniku {tarcza: ...}” | dodaj `{tarcza: …}` przed pierwszym krokiem |
| „Tarcza (dial) wymaga listy steps: co najmniej dwie szprychy” | dodaj drugi `{krok: …}` (tarcza ma od 2 do 12 szprych) |
| „kroki bliżej niż 1 s od poprzedniego, obrót się nie zmieści” | wydłuż mowę między hasłami albo usuń jedno hasło |
| „etykieta za długa… skróć ją” albo „tekst piasty … jest za długi” | hasło ma 1-2 krótkie słowa (do ok. 12 znaków), tekst piasty do ok. 18; komunikat podaje, ile znaków się mieści |
| „Mowa zgadza się ze scenariuszem tylko w …%, więc napisy zostają z rozpoznanej mowy” | mówisz (albo lektor czyta) inny tekst niż scenariusz: popraw tekst albo nagranie |
| „hasło: wyróżnienie „…” ma 4 słów: duże są pierwsze 2…” | w Formacie 3 gwiazdkami oznacz jedno albo dwa słowa; dłuższe wyróżnienie program tnie |
| „lockup … wiersz „…” nie mieści się w bloku: skróć go albo rozdziel hasło na dwa” | w planie JSON rozbij małe słowa na dwa hasła; ze scenariusza: mniej słów między gwiazdkami a końcem zdania nie zmieni układu, ale pomoże krótsze zdanie |
| „przejście potrzebuje rodzaju, np. {przejście: rozmycie}” | po dwukropku podaj `rozmycie`, `najazd`, `przesunięcie`, `kurtyna` albo `błysk` |

## Ściąga komend

```
python rolka.py nagranie.mp4 --template format2                          # surowy montaż z napisami marki
python rolka.py nagranie.mp4 --template format2 --graphics scenariusz.txt # z grafikami
python rolka.py nagranie.mp4 --template format2 --graphics plan.json --brand moja_marka.json
python rolka.py nagranie.mp4 --template format2 --graphics scenariusz.txt --dry-run --words nagranie.slowa.json
python rolka.py grafiki scenariusz.txt --words slowa.json --tlo klip.mp4 --klatka 12    # jedna klatka (PNG)
python rolka.py grafiki plan.json --czas 8 -o podglad.mp4                                # grafiki na ciemnym tle
python rolka.py style format2                                                  # karta stylu szablonu

# Motion: z samego głosu
python rolka.py glos.m4a --template motion --graphics scenariusz.txt -o film.mp4
python rolka.py grafiki scenariusz.txt --template motion --words film.slowa.json --klatka 14   # jedna klatka (PNG)
python rolka.py grafiki scenariusz.txt --template motion --words film.slowa.json --od 10 --czas 8 -o podglad.mp4
python rolka.py style motion                                                  # karta stylu trybu motion

# Format 3: cięcia, hasła ze słów w gwiazdkach, błysk przy wstawce
python rolka.py nagranie.mp4 --template format3 --graphics scenariusz.txt --broll wstawki/ -o film.mp4
python rolka.py grafiki scenariusz.txt --template format3 --words film.slowa.json --tlo klatka.jpg --klatka 12   # hasła i napisy na zdjęciu klatki
python rolka.py style format3                                                 # karta stylu Formatu 3
```

## Dodatek: karta stylu szablonu (wygenerowana)

Zmierzone liczby szablonu `format2`. Odświeżysz ją poleceniem `python rolka.py style format2`.

<!-- karta:start -->
# Karta stylu: Format 2: gadająca głowa (jedno ujęcie, animowane grafiki, napisy marki)

Źródło: https://www.instagram.com/reel/Dez4fPJCR74/ https://www.instagram.com/reel/DeGQ3NAC2f9/ https://www.instagram.com/reel/Dd2i55aj43S/ https://www.instagram.com/reel/DdxAwodlOGG/. Format 1080x1920, 30 kl./s, 61,1 s.

## Montaż i tempo

- Jedno ujęcie bez cięć, 61,1 s. Dynamika pochodzi z warstwy grafik i napisów, nie z montażu.
- Pauzy w mowie: powyżej 0,50 s skracane do 0,35 s.
- Tempo mowy: 4,2 słowa na sekundę.
- Głośność rolki: -14,2 LUFS, szczyt -1,1 dBTP, zakres LRA 2,9 LU (cel w szablonie: -14,0 LUFS).

Rolki wzorcowe tego formatu (4, mediany powyżej); położenie i rozmiary jako ułamki kadru:

| Rolka | Czas (s) | Słów/s | LUFS | LRA | Twarz: wys. | Twarz: x | Twarz: y | Napisy: góra | Napisy: wys. linii |
|---|---|---|---|---|---|---|---|---|---|
| Dez4fPJCR74 | 58,9 | 4,19 | -14,3 | 3,6 | 17,2% | 55,2% | 45,4% | 54,8% | 2,03% |
| DeGQ3NAC2f9 | 63,3 | 3,87 | -14,3 | 3,3 | 15,0% | 48,4% | 46,2% | 54,5% | 2,19% |
| Dd2i55aj43S | 41,8 | 4,14 | -14,1 | 2,3 | 15,7% | 47,6% | 48,2% | 58,1% | 2,19% |
| DdxAwodlOGG | 71,8 | 4,24 | -14,1 | 2,6 | 14,8% | 48,1% | 44,8% | 53,3% | 2,34% |

## Kadry

Rozmiar i położenie twarzy w ujęciach z mową, jako ułamki kadru (x: 0% = lewa krawędź, y: 0% = góra).

| Ujęcie | Czas (s) | Plan | Twarz: wysokość | Twarz: x | Twarz: y | Oczy: y |
|---|---|---|---|---|---|---|
| 1 | 0,0-61,1 | plan ogólny | 15% | 48% | 46% | 44% |

Kadr stały, bez najazdów. Nad czubkiem głowy zostaje ok. 34% wysokości kadru wolnego miejsca na grafiki; napisy stoją na wysokości klatki piersiowej.

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

## Grafiki i napisy

- Napisy rysuje warstwa grafik, w kroju marki: do 3 słów naraz, wysokość wersalików 2,0% wysokości kadru (ok. 39 px z 1920), górna krawędź na 54,8% wysokości.
- Resztę dynamiki daje plan grafik: plik JSON z czasami (`--graphics plan.json` albo przeciągnięcie w interfejsie).
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
- Efekt: `blur` rozmywa i przyciemnia obraz na czas pokazywania kart, żeby grafiki były czytelne.
- Każdy element może stać „za postacią” (`behind: true`, w scenariuszu `za: tak`): program wycina Twoją sylwetkę i rysuje element pod nią, np. poświatę za głową albo kartę za ramieniem.
- Miejsce w kadrze wynika z położenia Twojej twarzy: grafiki trafiają nad głowę, na boki albo pod napisy, nigdy na twarz.

## Opis ujęć

1. (A) Kadr średni, kamera nieruchoma przez cały film. Głowa nieco na lewo od środka i w środku-dolnej części kadru, nad nią ok. 30% wysokości wolnego miejsca na grafiki, napisy na wysokości klatki piersiowej.
<!-- karta:end -->
