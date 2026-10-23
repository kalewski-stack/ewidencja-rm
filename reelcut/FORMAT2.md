# FORMAT 2: gadająca głowa

Jeden ciągły take, kamera nieruchoma, zero cięć. Całą dynamikę dają **animowane grafiki nałożone na mówiącą głowę**
(tytuły, listy pisane na żywo, karty z liczbami, strzałki, opisy, ilustracje) i małe napisy słowo po słowie.
Narzędzie robi je w Twoich kolorach i kroju marki „Linia Kalewski”, a czasy grafik ustawia na słowach, które mówisz.

- **Format 1** to mówiąca głowa z cięciami i B-rollem (rolka DeuOaXKtPBb): szablon `format1`, opis w [STYL.md](STYL.md).
- **Format 2** to ten plik: szablon `format2` (stara nazwa `rolka_Dez4fPJCR74` też działa), składnia znaczników w
  [GRAFIKI.md](GRAFIKI.md).

Wzorce: cztery rolki jednego konta (Dez4fPJCR74, DeGQ3NAC2f9, Dd2i55aj43S, DdxAwodlOGG). W repozytorium są
tylko liczby, kolory i opis konstrukcji, bez obrazu, mowy i tekstów z tych rolek.

## W skrócie

Mediany czterech rolek (w nawiasie rozstęp). Tabela per rolka jest w karcie stylu: `python rolka.py style format2`.

| Wymiar | Wzorzec |
|---|---|
| Długość | 61 s (od 42 do 72 s), jedno ujęcie, zero cięć, pion 9:16 |
| Twarz | wysokość 15,4% kadru (13,6–19,5%), środek 48,3% szerokości i 45,8% wysokości, oczy na 43,6% |
| Napisy | słowo po słowie, do 3 słów, białe, półgrube, wielkość liter jak w mowie; wysokość wersalików 2,0% kadru (39 px z 1920), górna krawędź na 54,8% (53–58%) |
| Mowa | 4,2 słowa na sekundę (3,9–4,2), żadna pauza nie jest dłuższa niż 0,5 s |
| Dźwięk | −14,2 LUFS, zakres głośności 2,9 LU (2,3–3,6), szczyt −1,1 dBTP |
| Grafiki | od 1.–2. sekundy do końca; w próbkach co 2 s prawie zawsze coś jest na ekranie, a każdy kolejny stan różni się od poprzedniego (oglądane, nie mierzone) |
| Kolory | biel i jeden jasny akcent (żółty, w jednej rolce pomarańczowy), szeryfowa kursywa w nagłówkach; w narzędziu zawsze kolory marki |

## Jak zbudowany jest film

Pięć zasad widocznych w rolkach wzorcowych (z oglądania klatek co 2 s, nie z pomiaru; zasadę 5 najwyraźniej widać w jednej z rolek):

1. **Grafika od pierwszej sekundy.** Już w 1.–2. sekundzie na ekranie jest tytuł, nagłówki kolumn albo ilustracja.
   Sama głowa bez niczego to stracone sekundy.
2. **Jedno płótno, które rośnie.** Nagłówek zostaje na ekranie przez 30–40 s, a pod nim dochodzą kolejne wiersze,
   opisy i karty. Elementy dokładasz, rzadko wymieniasz. Dzięki temu widz „czyta” film oczami, nie tylko uszami.
3. **Jeden punkt, jedna zmiana na ekranie.** Co 2–4 s coś nowego: wiersz, etykieta, karta, strzałka. Element
   pojawia się w chwili, gdy wypowiadasz słowo, którego dotyczy, nie wcześniej.
4. **Jedna metafora wizualna.** Cały film trzyma się jednego obrazu: dwie kolumny porównania, schemat z opisanymi
   częściami, seria kart z liczbami, lista kontrolna. Ilustracja może jechać po kadrze, rosnąć i wychodzić za kadr.
5. **Finał na pełnym płótnie.** W końcówce zostaje na ekranie wszystko, co zbudowałeś (kolumny, karty, podpisy),
   a puenta pada na pełnym obrazie, nie na pustej głowie.

Rozmycie obrazu (`rozmycie: tak`) tylko tam, gdzie karta ma dużo tekstu. Poza tym głowa jest ostra.

## Słownik elementów: co widać w rolkach i jak to zrobić tutaj

| Co widać | Element (znacznik) | Najważniejsze pola |
|---|---|---|
| Duży tytuł z małym słowem-akcentem | `tytuł` | `akcent`, `styl: serif` |
| Tekst z żółtym słowem, pędzlem pod liczbą, nawiasem „[ ]” przy nagłówku, podkreśleniem | `tekst` | `*wyróżnienie*`, `_kursywa_`, `zaznaczenie: pędzel / nawias / podkreślenie`, `odsłanianie: pisanie` |
| Dwie kolumny porównania z pionową żółtą kreską, wiersze „Etykieta: treść” pisane po kolei | `porównanie` | kolumny rozdzielasz `//`, `rule: tak` |
| Lista kontrolna: żółte etykiety, pola do odhaczenia, drobny komentarz pod wierszem | `lista` | `+` na początku = odhaczone, `zaznaczenie: ramka / kropka`, `Etykieta = tekst / komentarz` |
| Miniatury 9:16 z podpisem nad kartą i licznikiem wyświetleń pod spodem | `karty` | `wyświetlenia`, `etykiety: szeryf / żółte`, w JSON `x`, `y`, `w`, `rot`, `at` przy każdej karcie |
| Dwie karty i przerywana strzałka między nimi | `karty` + `strzałka` | współrzędne kart w JSON, `styl: przerywana` |
| Opis z cienką linią do wskazanego miejsca | `opisy` | `Tekst @ x y > cel_x cel_y` |
| Łukowata strzałka wskazująca głowę albo element | `strzałka` | `od`, `cel`, `łuk`, `grot: otwarty / pełny`, `styl` |
| Pierścień z kropek wokół karty | `pierścień` | `x`, `y`, `rx`, `kropki`, `luki` |
| Duża ilustracja, która jedzie po kadrze, rośnie i wychodzi za kadr | `ilustracja` | `obrót`, `za: tak`, `wystaje: tak`, w JSON `path` (klatki kluczowe) |
| Chip z awatarem, licznikiem i kursorem | `profil` | patrz GRAFIKI.md |
| Liczby odliczane, kafelki z wartościami | `licznik`, `kafelki` | `podpis`, `przyrostek` |
| Kroki w szklanym panelu | `kroki` | `aktywne: fraza; fraza` |

Wartości położenia podajesz jako ułamek kadru albo w procentach (`x: 30%`). Środek kadru to 50% i 50%, twarz jest
mniej więcej na 48% i 46%.

Czego nie ma: makiet cudzych profili społecznościowych, wykresów słupkowych (lejek), zdjęć i ikon z biblioteki.
Takie rzeczy dostarczasz jako obraz (`ilustracja`, `karty` z `obrazy:`), a narzędzie je animuje.

## Jak zrobić film w Formacie 2

1. **Wybierz metaforę** (jedna z listy wyżej) i rozpisz 4–7 punktów. Do każdego punktu wybierz jedną grafikę.
2. **Napisz scenariusz ze znacznikami**: tekst, który powiesz, z grafikami w `{ }` (przykład niżej). Na 45–60 s to
   ok. 190–250 słów.
3. **Nagraj** jednym ciągłym ujęciem, w pionie, na statywie. Twarz mniej więcej w środku, nad głową około jednej
   trzeciej kadru wolnego miejsca, pod napisami dół zostaje na listy.
4. **Surowiec** (raz, to trwa najdłużej): `python rolka.py nagranie.mp4 --template format2`.
5. **Podgląd grafik** w sekundach: `python rolka.py grafiki scenariusz.txt --words nagranie_rolka.slowa.json --tlo nagranie_rolka.mp4 --klatka 12`.
6. **Film**: `python rolka.py nagranie.mp4 --template format2 --graphics scenariusz.txt --words nagranie_rolka.slowa.json`.
   W interfejsie (`python rolka.py serve`) wybierz „Format 2: gadająca głowa” i w kroku 3 przeciągnij scenariusz.

Program ostrzega, gdy element nie mieści się w kadrze, zasłania twarz albo dwa elementy zajmują to samo miejsce.

### Szkielet scenariusza (hipotetyczny, podmień na swój temat)

<!-- scenariusz:start -->
```
# Film ok. 25 s: „Ten sam event, dwa różne cele” (skrócony szkielet, tekst hipotetyczny; na 45-60 s dopisz kolejne punkty)
{tytuł: Ten sam event | akcent: dwa cele | styl: serif} Ten sam event może mieć dwa zupełnie różne cele, zależnie od tego, kto go zamówił.
{porównanie: Marketing: Cel = rozpoznawalność; Mierzy = zasięg i leady // HR: Cel = zaangażowanie; Mierzy = retencję i opinie | rule: tak | do: zaczynają się problemy} Marketing chce rozpoznawalności i liczy zasięg, a HR chce zaangażowania i liczy retencję. I tu zaczynają się problemy.
{tekst: Jeden brief, *dwa* cele | rozmiar: 6% | zaznaczenie: pędzel | x: 50% | y: 17% | czas: 3} Bo jeden brief próbuje obsłużyć oba cele naraz, a potem nikt nie wie, czy event się udał.
{licznik: 700+ | podpis: wydarzeń B2B | strefa: lewo} Zrobiłem ich ponad siedemset i ten błąd widziałem w każdej branży.
{strzałka: | od: 22%; 30% | cel: 40%; 36% | łuk: 0,25 | grot: pełny | czas: 2} Dlatego zanim cokolwiek zaplanujesz, ustal trzy rzeczy.
{lista: + Cel = jeden na event; + Odbiorca = jedna grupa; Miara = ustalona przed eventem | zaznaczenie: ramka | x: 8% | y: 9% | czas: 6} Jeden cel na event, jedna grupa odbiorców i miara ustalona przed eventem.
{tekst: Jeden event, *jeden* cel | rozmiar: 6% | zaznaczenie: podkreślenie | strefa: dół | czas: 3} Zapisz te trzy rzeczy w briefie, zanim zadzwonisz do pierwszej agencji.
```
<!-- scenariusz:end -->

Znacznik działa od następnego słowa. Koniec elementu wyznacza `do: fraza`, `{/typ}` albo `czas: sekundy`. Pełna
składnia i wszystkie pola: [GRAFIKI.md](GRAFIKI.md).

## Grafiki „za postacią”

W rolkach wzorcowych część elementów jest **za Twoją sylwetką**: ilustracja wystaje zza ramienia, poświata leży za
głową, karta chowa się za dłonią. Tu robi to jedno słowo: `za: tak` (w planie JSON `"behind": true`).

- Sylwetkę wycina model MODNet (licencja Apache-2.0). Pobiera się **raz**, przy pierwszym użyciu (26 MB, do
  `~/ReelCut/modele`), potem działa bez internetu. Własny plik modelu wskażesz zmienną `REELCUT_MODNET`.
- Potrzebne są `numpy` i `onnxruntime` (`pip install numpy onnxruntime`), te same co do kadrowania twarzy.
- Sylwetkę program liczy **tylko w oknach czasu, w których jest taki element** (15 klatek na sekundę), więc film
  z jedną poświatą za głową renderuje się prawie tak szybko jak bez niej.
- Działa tylko w Formacie 2 (jedno ujęcie). Gdy brakuje modelu, pakietów albo internetu, element rysuje się z przodu,
  a program mówi o tym w ostrzeżeniu. Nic nie jest ukrywane po cichu.
- Obejrzyj brzegi (włosy, palce, rękawy) na jednej klatce: `python rolka.py grafiki plan.json --tlo nagranie_rolka.mp4 --klatka 12`.
  Sprawdzone na klatkach z rolek wzorcowych i na zdjęciu, nie na Twoim nagraniu.

## Granice

- Karty pokazują obraz, który podasz, albo zaślepkę w barwach marki. Nie odtwarzają wideo.
- Ilustracje, makiety i zdjęcia dostarczasz Ty (PNG z przezroczystością, JPG, WebP). Narzędzie niczego nie wymyśla.
- Rytm grafik (pierwszy element w 1.–2. sekundzie, zmiana co 2–4 s) to opis z oglądania czterech rolek, nie pomiar.
- Kolory mają wyłącznie grafiki i napisy, z marki. Nagranie zostaje nietknięte.
- Kursywa szeryfowa (Instrument Serif) pochodzi ze wzorców. Jeśli system marki dopuszcza tylko Bricolage Grotesque,
  wskaż go w `fonts.serif_italic` pliku marki, a wszystkie nagłówki szeryfowe przełączą się na niego.
