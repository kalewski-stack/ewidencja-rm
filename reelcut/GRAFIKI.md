# GRAFIKI: krótka gadająca głowa z animowanymi elementami w Twoich kolorach

Wzorzec: <https://www.instagram.com/reel/Dez4fPJCR74/> (jeden ciągły take 58,9 s, zero cięć, kamera nieruchoma).
Cała dynamika tej rolki to **animowane grafiki nałożone na mówiącą głowę** i małe napisy słowo po słowie. Narzędzie
odtwarza ten **zestaw elementów i gramatykę animacji** (wejście ze skalą, wjazd i rozmyciem, kolejne karty co ułamek
sekundy, liczniki, tekst pisany na żywo, kursor jadący po kadrze), ale w kolorach i kroju marki **Linia Kalewski**.
Nie ma tu obrazu ani treści rolki wzorcowej: elementy dostają Twoje teksty i Twoje obrazy.

## W skrócie

1. **Scenariusz ze znacznikami**: piszesz tekst, który powiesz, i wpisujesz w `{ }` grafiki (rozdział niżej).
2. **Nagranie**: jeden ciągły take, pion, statyw (zasady kadru niżej).
3. **Montaż**: jedna komenda albo przeciągnięcie plików w interfejsie. Program rozpoznaje mowę, dopasowuje do niej Twój
   scenariusz i sam ustawia czasy grafik na słowach.
4. **Kontrola** jednej klatki albo fragmentu bez pełnego renderu.

```
python rolka.py nagranie.mp4 --template rolka_Dez4fPJCR74 --graphics scenariusz.txt
```

W interfejsie (`python rolka.py serve`): w ustawieniach wybierz szablon „Rolka Dez4fPJCR74…”, w kroku 3 („Grafiki”)
przeciągnij `scenariusz.txt` razem z obrazami, których używa, i kliknij **Potnij**.

Szablon `rolka_Dez4fPJCR74` robi jedno ujęcie bez cięć (kadruje Twoją twarz jak we wzorcu, skraca pauzy powyżej 0,5 s do
0,35 s, ustawia głośność −14 LUFS), rysuje napisy słowo po słowie w kroju marki i nakłada grafiki ze scenariusza.
Kolorów nagrania nie zmienia: kolory marki mają grafiki i napisy.

## Rytm wzorca

Z przeglądu klatek co 2 s (30 próbek, oglądane, nie mierzone komputerowo):

- grafika jest na ekranie w 28 z 30 próbek; pierwsza wchodzi w 2. sekundzie (wcześniej jest sama głowa i napisy);
- często jest kilka elementów naraz (np. chip profilu z licznikiem, karty z podpisami i tytuł), a nowy wchodzi mniej
  więcej co kilka sekund;
- cały obraz jest rozmyty i przyciemniony tylko przy kartach z długim tekstem (w próbkach raz, ok. 29–32 s); poza tym głowa
  jest ostra;
- napisy słowo po słowie idą przez cały film w jednym miejscu, na wysokości klatki piersiowej.

Pisząc scenariusz, celuj w podobną gęstość: pierwszy element w ok. 2. sekundzie, potem nowy co 2–6 s, rozmycie tylko tam,
gdzie karta ma dużo tekstu.

## Szybka pętla: najpierw surowiec, potem grafiki

Rozpoznawanie mowy trwa najdłużej, a grafiki liczą się w sekundach. Dlatego:

```
# 1. surowy montaż z napisami (raz): powstaje nagranie_rolka.mp4 i nagranie_rolka.slowa.json
python rolka.py nagranie.mp4 --template rolka_Dez4fPJCR74

# 2. ocena grafik na klatce albo fragmencie (kilka sekund), tłem jest ten surowy montaż
python rolka.py grafiki scenariusz.txt --words nagranie_rolka.slowa.json --tlo nagranie_rolka.mp4 --klatka 12 --twarz 0.17,0.55,0.45
python rolka.py grafiki scenariusz.txt --words nagranie_rolka.slowa.json --tlo nagranie_rolka.mp4 --od 8 --czas 10 -o podglad.mp4

# 3. film końcowy bez ponownego rozpoznawania mowy
python rolka.py nagranie.mp4 --template rolka_Dez4fPJCR74 --graphics scenariusz.txt --words nagranie_rolka.slowa.json -o final.mp4
```

`--twarz H,X,Y` w podglądzie to położenie Twojej twarzy w kadrze (wysokość, środek x, środek y, ułamki). Wartości, które
zmierzył montaż, program wypisuje w logu („Twarz widoczna… wysokość 17% kadru, środek (55%, 40%)”). Bez `--twarz` podgląd
przyjmuje kadr wzorca. Tło `--tlo` może też być zdjęciem (png, jpg).

## Jak nagrać

| Co | Wartość (z wzorca) | Dlaczego |
|---|---|---|
| Format | pion 9:16, najlepiej 4K lub 1080p | wynik 1080×1920 |
| Kamera | nieruchoma, jeden take | cięć nie ma, zmiany robią grafiki |
| Twarz | wysokość ok. 17% kadru, środek ok. 55% szerokości i 45% wysokości | tak ustawia ją montaż |
| Nad głową | ok. 30% wysokości wolnego miejsca | tam lądują tytuły, karty, liczniki |
| Po bokach głowy | wolne pasy | tam lecą liczniki i profil |
| Poziom klatki piersiowej | napisy słowo po słowie (ok. 55% wysokości) | dół zostaje na listy i pigułki |
| Tempo | ok. 4 słowa na sekundę, pauzy do 0,5 s | tak mówi wzorzec; dłuższe pauzy program skraca |
| Tło | spokojne, raczej ciemne | grafiki mają miękki cień, ale jasne, ruchliwe tło zawsze obniża czytelność |

Grafiki **nie chowają się za głową**: strefy kadru wyznacza położenie Twojej twarzy i elementy trafiają obok niej.
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
| `karty` | `Etykieta = punkt / punkt; Etykieta; …` (w punktach `*wyróżnienie*` świeci żółto) | `obrazy: a.jpg; ; c.png` (puste = miniatura-zaślepka), `etykiety: serif` (podpisy kursywą szeryfową zamiast pogrubionego kroju), `fokus: 1`, `focus_at: 2,5`, `układ: grid`, `kolumny`, `strefa` | rząd miniatur 9:16 wjeżdżających kolejno, jedna może się powiększyć | 4 s |
| `profil` | podpis | `tryb` mini/full, `licznik: 25; 60`, `jednostka`, `pasek: 0,3; 1`, `znacznik`, `korona: tak`, `kursor: nie`, `badge: clock` | chip z Twoją twarzą (wycięta z nagrania), licznikiem, paskiem i kursorem | 6 s |
| `pigułki` | `Tekst = znacznik; …` | `rozmiar`; style i ikona przy każdej: w planie JSON | etykiety wlatujące na przemian z lewej i prawej | 4 s |
| `kafelki` | `Etykieta = wartość; …` | `chip_w` | małe kafelki z odliczaną wartością | 4 s |
| `kroki` | `Tytuł = opis; …` | `aktywne: fraza; fraza; …` (kiedy zmienia się aktywny krok; frazy muszą paść w mowie), `szerokość` | lista w szklanym panelu, aktywny krok pośrodku | 6 s |
| `oś` | podpisy od najniższego | `step` | wykres schodkowy w kształcie litery L, ostatni punkt żółty | 6 s |
| `paski` | podpisy wierszy | rodzaje pasków: w planie JSON | wiersze z paskami albo obracającym się kółkiem | 5 s |
| `wyróżnienie` | tytuł | `tekst` (pisany na żywo), `ikona` bulb/check/star/none, `hasło` (szeryfowy podpis po prawej), `obraz` (karta po prawej), `cps` | kafelek z ikoną i tekstem pojawiającym się znak po znaku | 5 s |
| `ilustracja` | nazwa pliku | `szerokość`, `poświata`, `kotwica: głowa` | obraz z miękką poświatą, np. nad głową | 3 s |
| `rozmycie` | (brak) | `siła` (14), `ściemnienie` (0,25) | rozmywa i przyciemnia cały obraz na czas działania, żeby grafiki były czytelne | 3 s |

Obrazy podajesz samą nazwą pliku; plik leży obok scenariusza (w interfejsie wrzucasz je razem ze scenariuszem).
Wspierane: png (także z przezroczystością), jpg, webp.

### Jak to jest dopasowane do mowy

Program porównuje Twój tekst z transkrypcją (bez względu na wielkość liter, polskie znaki i interpunkcję). Słowa, które
rozpoznawanie przekręciło, dostają czas z interpolacji między sąsiednimi trafieniami, więc literówka w transkrypcji nie
psuje czasów. Jeśli w mowie znajdzie mniej niż połowę słów scenariusza, montaż zatrzymuje się z komunikatem „Scenariusz nie
pasuje do nagrania” (to zwykle zły plik albo mocno improwizowany tekst). Improwizację możesz zostawić: liczą się te słowa,
które się zgadzają, a znacznik ląduje przy następnym trafionym słowie.

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
paski ze spinnerem, wyróżnienie, licznik, ilustracja) opisują komentarze w kodzie: `src/reelcut/graphics/`.

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

We wzorcu kolorem grafik jest pomarańcz. Tutaj jego rolę (jedyny jasny akcent) przejmuje żółty marki, a fiolet jest
kolorem etykiet, linii i tła kart.

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

## Napisy słowo po słowie

Szablon rysuje je sam, w Bricolage Grotesque: do 3 słów naraz, wysokość wersalików 1,9% wysokości kadru (36 px z 1920),
górna krawędź na 54,8% wysokości (klatka piersiowa). Poprawki literówek: edytujesz `*.slowa.json` (pole `w`, czasów nie
ruszaj) i uruchamiasz ponownie z `--words`.

## Czego to narzędzie nie robi

- **Grafiki nie wchodzą za głowę.** We wzorcu niektóre elementy chowają się za postacią; tu zawsze leżą obok twarzy (strefy
  liczone z jej położenia).
- **Karty nie odtwarzają wideo.** Pokazują obraz, który podasz, albo zaślepkę w barwach marki (ciemna miniatura z przyciskiem
  odtwarzania, pusta karta z kreskami).
- **Treści są Twoje.** Teksty, liczby i obrazy podajesz Ty. Narzędzie niczego nie wymyśla.
- **Awatar to kwadratowy wycinek Twojej twarzy** z nagrania w kółku, a nie wycięta postać. Bez wykrytej twarzy
  (brak `numpy`/`onnxruntime` albo twarz niewidoczna) pojawia się neutralna sylwetka.
- **Panele „szklane” nie rozmywają tła** (są półprzezroczyste z poświatą).
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
| „Znacznik „{…}”: nieznany typ” | lista typów w komunikacie; nazwy jak w tabeli powyżej |

## Ściąga komend

```
python rolka.py nagranie.mp4 --template rolka_Dez4fPJCR74                          # surowy montaż z napisami marki
python rolka.py nagranie.mp4 --template rolka_Dez4fPJCR74 --graphics scenariusz.txt # z grafikami
python rolka.py nagranie.mp4 --template rolka_Dez4fPJCR74 --graphics plan.json --brand moja_marka.json
python rolka.py nagranie.mp4 --template rolka_Dez4fPJCR74 --graphics scenariusz.txt --dry-run --words nagranie.slowa.json
python rolka.py grafiki scenariusz.txt --words slowa.json --tlo klip.mp4 --klatka 12    # jedna klatka (PNG)
python rolka.py grafiki plan.json --czas 8 -o podglad.mp4                                # grafiki na ciemnym tle
python rolka.py style rolka_Dez4fPJCR74                                                  # karta stylu szablonu
```

## Dodatek: karta stylu szablonu (wygenerowana)

Zmierzone liczby szablonu `rolka_Dez4fPJCR74`. Odświeżysz ją poleceniem `python rolka.py style rolka_Dez4fPJCR74`.

<!-- karta:start -->
# Karta stylu: Rolka Dez4fPJCR74: gadająca głowa w jednym ujęciu, grafiki i napisy marki

Źródło: https://www.instagram.com/reel/Dez4fPJCR74/. Format 1080x1920, 30 kl./s, 58,9 s.

## Montaż i tempo

- Jedno ujęcie bez cięć, 58,9 s. Dynamika pochodzi z warstwy grafik i napisów, nie z montażu.
- Pauzy w mowie: powyżej 0,50 s skracane do 0,35 s.
- Tempo mowy: 4,2 słowa na sekundę.
- Głośność rolki: -14,4 LUFS, szczyt -0,8 dBTP, zakres LRA 3,6 LU (cel w szablonie: -14,0 LUFS).

## Kadry

Rozmiar i położenie twarzy w ujęciach z mową, jako ułamki kadru (x: 0% = lewa krawędź, y: 0% = góra).

| Ujęcie | Czas (s) | Plan | Twarz: wysokość | Twarz: x | Twarz: y | Oczy: y |
|---|---|---|---|---|---|---|
| 1 | 0,0-58,9 | plan ogólny | 17% | 55% | 45% | 43% |

Kadr stały, bez najazdów. Nad czubkiem głowy zostaje ok. 32% wysokości kadru wolnego miejsca na grafiki; napisy stoją na wysokości klatki piersiowej.

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

- Napisy rysuje warstwa grafik, w kroju marki: do 3 słów naraz, wysokość wersalików 1,9% wysokości kadru (ok. 36 px z 1920), górna krawędź na 54,8% wysokości.
- Resztę dynamiki daje plan grafik: plik JSON z czasami (`--graphics plan.json` albo przeciągnięcie w interfejsie).
- Elementy planu:
  - `title`: duży napis (żółty, szeryfowy kursywą albo krojem marki) z małym słowem-akcentem nad prawym końcem
  - `badge`: plakietka: numer w kole i tytuł obok, np. „1 Scenariusz”
  - `cards`: rząd miniatur 9:16 z etykietami i punktami pod spodem, jedna karta może się powiększyć
  - `profile`: chip z awatarem (Twoja twarz z nagrania), licznikiem, paskiem postępu i kursorem jadącym po kadrze
  - `pills`: krótkie hasła z ikoną, wlatujące jedna po drugiej (biała, szklana, fioletowa, żółta)
  - `chips`: małe kafelki z etykietą i liczbą, np. wartości do porównania
  - `steps`: lista kroków w szklanym panelu, która przewija się do aktywnego kroku
  - `axis`: wykres schodkowy z podpisanymi punktami (rosnący trend)
  - `bars`: wiersze z etykietami (podwójne, pojedyncze, ze spinnerem)
  - `callout`: wyróżnienie: ikona, tytuł i tekst „pisany” na żywo, opcjonalnie karta po prawej
  - `stat`: duża liczba odliczana od zera z podpisem i paskiem
  - `illustration`: obraz z miękką poświatą, np. nad głową
- Efekt: `blur` rozmywa i przyciemnia obraz na czas pokazywania kart, żeby grafiki były czytelne.
- Miejsce w kadrze wynika z położenia Twojej twarzy: grafiki trafiają nad głowę, na boki albo pod napisy, nigdy na twarz.

## Opis ujęć

1. (A) Kadr średni, kamera nieruchoma przez cały film. Głowa w środku-dolnej części kadru, nad nią ok. 30% wysokości wolnego miejsca na grafiki, napisy na wysokości klatki piersiowej.
<!-- karta:end -->
