# STYL: styl rolki wzorcowej do przeniesienia na inne tematy

To jest opis **Formatu 1** (mówiąca głowa + B-roll, cięcia w rytmie rolki; szablon `format1`). Format 2 (gadająca głowa,
jeden take z animowanymi grafikami): [FORMAT2.md](FORMAT2.md).

Ten dokument opisuje to, co **zmierzyłem** w rolce <https://www.instagram.com/reel/DeuOaXKtPBb/>: kolory, kadry, cięcia
i dynamikę. Z tego da się nagrać nowy materiał w tym samym stylu (rozdziały: kolory, kadry, cięcia), napisać do niego
scenariusz (rozdział: format scenariusza) i zmontować go automatycznie (rozdział: jak to zastosować).
Nie ma tu obrazu ani treści rolki, tylko liczby, kolory i opis konstrukcji. Przykładowy scenariusz jest **hipotetyczny**.

## W skrócie

| Wymiar | Wzorzec |
|---|---|
| Rytm | 24,7 cięć na minutę, ujęcie średnio 2,27 s (od 0,88 do 5,64 s) |
| Konstrukcja | hak 5,2 s (2 ujęcia) → rozwinięcie 19,2 s (10 ujęć) → zakończenie 9,5 s (3 ujęcia) |
| Wstawki | 35% czasu, krótkie (1,2–3,1 s), głos z ujęcia z mową leci pod nimi |
| Kadry | twarz 12% → 15–21% → 27–36% wysokości kadru, pionowo 9:16, zmiana kadru wyłącznie cięciem |
| Jasność | ciemno: mediana L* 21 (na waveformie ok. 20%), cienie 8%, światła do 72–78% |
| Kolor | stonowany (C* 10 przy mowie, 25 we wstawkach), ciepłe półtony, zielonkawe światła, winieta (rogi 66%) |
| Napisy | Anton, 1–2 słowa naraz, 5 wyróżnionych fraz na 34 s, akcent `#E2FB77` |
| Dźwięk | sam głos, −14,7 LUFS, zakres głośności (LRA) 2,9 LU |
| Mowa | 3,6 słowa na sekundę, 123 słowa w 34 s, pauzy ≤ 0,35 s (jedna 0,76 s tuż przed puentą) |

Pełne zestawienie w formie tabel jest w dodatku na końcu: [Karta stylu](#dodatek-karta-stylu-wygenerowana).

## Jak to zastosować

**Ten sam styl na nowym temacie.** Nagraj mówiącą głowę (zasady poniżej), potem:

```
python rolka.py moje_wideo.mp4                  # cięcia, kadry, kolory, napisy, dźwięk
python rolka.py moje_wideo.mp4 --dry-run        # tylko plan: ile ujęć, jakie zbliżenia
python rolka.py moje_wideo.mp4 --look 0.6       # słabsze dopasowanie kolorów
python rolka.py moje_wideo.mp4 --no-snap        # cięcia dokładnie w sekundach wzorca (przy 34 s materiału)
```

**Inny styl, z innej rolki.** Każda rolka wzorcowa zamienia się w taki sam pakiet:

```
python rolka.py analyze inna_rolka.mp4 -o moj_styl        # cięcia, role, kadry twarzy, kolory, tempo, głośność
python rolka.py analyze inna_rolka.mp4 -o moj_styl --speech   # dodatkowo tempo mowy (potrzebny faster-whisper)
python rolka.py style user/moj_styl                       # karta stylu do przeczytania (tabele jak w dodatku)
python rolka.py moje_wideo.mp4 --template user/moj_styl   # montaż w tym stylu
```

Pakiet stylu to jeden plik JSON z blokami, które obsługują różne części montażu:

| Blok szablonu | Co opisuje | Czym sterujesz |
|---|---|---|
| `segments`, `structure` | długości ujęć, role A/B, hak, zakończenie, ujęcie elastyczne | `--no-snap`, `--dry-run` |
| `segments[].face` | rozmiar i położenie twarzy w każdym ujęciu z mową | `--framing auto/on/off`, `--max-zoom` |
| `look` | rozkład jasności, barwa i nasycenie, winieta, paleta, kolor skóry | `--look 0–1` |
| `captions` | krój, rozmiary, pozycje, kolory, rytm wyróżnień | `--captions`, `--emphasis` |
| `audio`, `pauses` | docelowa głośność, skracanie pauz | `--no-normalize`, `--no-tighten` |
| `dynamics` | tempo, udział A/B, ruch w kadrze, głośność, (opcjonalnie) tempo mowy | opisowy: czyta go `style` |

## Kolory

### Ekspozycja: gdzie ma leżeć obraz

Rozkład jasności ujęć z mową, przeliczony na wartości 8-bit (sRGB) i procent waveformu. To jest najważniejszy
pomiar: wzorzec jest **ciemniejszy**, niż większość nagrań, i **nie ma prawdziwej bieli**.

| Percentyl pikseli | L* | 8-bit | Waveform |
|---|--:|--:|--:|
| 5. (cienie) | 6 | 20 | 8% |
| 25. | 11 | 30 | 12% |
| 50. (mediana) | 21 | 51 | 20% |
| 75. | 34 | 79 | 31% |
| 90. | 50 | 118 | 46% |
| 99. (światła) | 75 | 184 | 72% |

- Najjaśniejszy duży element to biała koszulka: L* ok. 70–75, czyli ok. 72% waveformu. Praktycznie nic nie przekracza ok. 78% (99,5. percentyl).
- Skóra twarzy: L* 33, C* 18, odcień 36°, czyli ok. 30% waveformu. To mocno niedoświetlona skóra (kafelek „dark skin"
  wzornika ColorChecker ma L* 38, C* 20, odcień 46°). Przy normalnym oświetleniu twarz leży zwykle na 50–70%.
- Wstawki są odrobinę jaśniejsze (mediana L* 24) i dużo żywsze (C* 25).

### Barwa i nasycenie

- **Ujęcia z mową:** stonowane, średnie C* 10. Cienie (L* poniżej 10) neutralne, ciemne półtony (L* 15–45) ciepłe
  (odcień 40–60°, pomarańczowo-brązowy), jasne partie (L* powyżej 60) lekko zielonkawo-żółte (odcień ok. 100–110°).
  Czyli: ciepłe drewno i skóra, chłodno-zielonkawe ściany i światła.
- **Wstawki:** czerń z ciepłym bokeh albo gorący pomarańcz na jednolitym tle (C* do 84), reszta stonowana.
- **Winieta:** jasność trzech pierścieni od środka to 90%, 73%, 66% (A) oraz 95%, 87%, 78% (B).

### Paleta robocza (hex z pomiaru, udział pikseli)

| Rola | Kolor | Gdzie |
|---|---|---|
| Ciemne tło | `#191B1D` (35%) | cień, ciemna część pokoju |
| Ciepłe drewno | `#5A392A` (17%), `#362722` (16%) | meble, półki, cień po ciepłej stronie |
| Ściana / tło chłodne | `#3F4948` (13%), `#6B7A77` (8%) | zielono-turkusowe, szarawe ściany |
| Skóra w średnim świetle | `#8E6856` (6%) | twarz, dłonie |
| Najjaśniejszy element | `#ABB3A4` (3%) | biała koszulka, światło na ścianie |
| Ciepłe światło | `#B35928` (2%) | lampa w kadrze, bokeh |
| Wstawki: czerń | `#191616` (36%) | tło wstawek |
| Wstawki: pomarańcz | `#EA5113` (8%), `#B83911` (8%), `#8D280D` (8%) | jednolite tło pod rekwizyt |
| Napisy | `#FFFFFF`, akcent `#E2FB77` | wyróżnienia (środkowy, największy wiersz stosu) |

### Jak to odtworzyć

- **Na planie (najlepsza jakość):** ekspozycja na światła, nie na twarz. Mediana obrazu na 20% waveformu, najjaśniejszy
  duży element (biała koszulka) na ok. 72%, praktycznie nic powyżej ok. 78%. Ciepłe lampy w kadrze (źródła i bokeh), chłodne
  zielonkawe ściany w tle, brak jasnego, płaskiego światła z przodu, płytka głębia ostrości. Wstawki: czarne albo
  pomarańczowe tło, rekwizyt w jednym kolorze.
- **W montażu (jeśli nagrałeś jaśniej):** `--look 1.0`. Narzędzie mierzy Twój materiał, dopasowuje percentyle jasności
  (krzywa tonalna), nasycenie w funkcji jasności, lekkie przesunięcie barwy w szarych partiach i winietę do wzorca
  i nakłada to jedną tablicą LUT 3D. Odcień skóry jest chroniony: przesunięcie barwy działa tylko na piksele
  mało nasycone (ściany, ubrania, cienie).
- **Do innego programu:** `python rolka.py moje.mp4 --keep-temp` zostawia plik `look.cube` (LUT 3D, format .cube)
  w katalogu tymczasowym, którego ścieżkę wypisze na końcu. Winieta nie jest w LUT (jest osobnym filtrem).

## Kadry: lista ujęć do nagrania

Wspólne zasady: pion 9:16, kamera nieruchoma na statywie, oczy w górnej połowie kadru, **dolna część kadru wolna**
(stół, laptop, ciemna płaszczyzna), bo tam lądują napisy (napis bieżący zaczyna się na 63% wysokości kadru).

| # | Plan | Twarz: wysokość | Twarz: środek (x, y) | Ujęcia we wzorcu | Do czego służy |
|---|---|---|---|---|---|
| 1 | Ogólny: osoba przy stole, stół na pierwszym planie, widać pokój | 12% | 51%, 48% | 1 (2,6 s) | początek haka, stos napisów z akcentem |
| 2 | Średni, inne ustawienie kamery | 16% | 48%, 44% | 2 (2,7 s) | dokończenie haka |
| 3 | Średni, bliżej, twarz wyżej, ręce złożone | 21% | 52%, 36% | 5 (2,8 s) | pierwszy punkt zwrotny |
| 4 | Średni, osoba po lewej, pokój po prawej | 18% | 41%, 27% | 7 (1,7 s) | decyzja |
| 5 | Średni, akcja do kamery (rekwizyt w stronę obiektywu) | 15% | 36%, 31% | 10 (1,0 s) | wybór, ruch |
| 6 | Zbliżenie, twarz tuż pod górną krawędzią, dół = czarna płaszczyzna | 36% | 53%, 20% | 12 (1,9 s) | „sufit" przed puentą |
| 7 | Zbliżenie z góry (kamera nad twarzą), wejście z rozmycia | 36% | 59%, 41% | 13 (0,9 s) | puenta |
| 8 | Zbliżenie, monolog, twarz lekko na prawo | 27% | 58%, 35% | 14 (5,6 s) | rada |
| 9 | Zbliżenie, zamknięcie, wejście z rozmycia | 30% | 61%, 38% | 15 (3,0 s) | wezwanie do działania |

**Wstawki B** (każda 1,2–3,1 s, w sumie 35% czasu, głos leci dalej): detal makro (kawa, ziarno, 1,6 s), ekran
telefonu (1,2 s), światło i klimat (1,8 s), rekwizyt na jednolitym pomarańczowym tle (3,1 s), rekwizyt i ruch ręki
(1,7 s), dłonie na klawiaturze (2,5 s). Zawsze ruch lub żywy kolor: wstawka ma „obudzić" kadr po ujęciu z mową.

- **Ile materiału nagrać:** wzorzec to kilka ustawień kamery tej samej wypowiedzi. Z jednego nagrania narzędzie zrobi
  zbliżenia cyfrowo (kadruje po Twojej twarzy: dobiera zoom i położenie okna tak, by twarz miała docelowy rozmiar
  i miejsce w kadrze), ale zoom sięga do ok. 2,6× tylko przy 4K; przy 1080p do ok. 1,6×. Chcesz bliskie plany
  w pełnej jakości: nagraj drugie podejście bliżej.
- **Zasada kadru:** sąsiednie ujęcia z mową zawsze różnią się wyraźnie (co najmniej 10% zoomu albo przesunięcie
  o 12% kadru), inaczej cięcie wygląda jak błąd. Narzędzie samo tego pilnuje.

## Cięcia i dynamika: reguły

1. **Rytm.** 24,7 cięć na minutę. Ujęcie trwa średnio 2,27 s, mediana 1,88 s. Najkrótsze 0,88 s (puenta), najdłuższe
   5,64 s (rada). Rdzeń rytmu: 9 z 15 ujęć trwa 1,6–2,8 s.
2. **Konstrukcja.** Hak (2 ujęcia, 5,2 s, 15%) → środek (10 ujęć, 19,2 s, 57%) → zakończenie (3 ujęcia, 9,5 s, 28%).
   Wstawki B pojawiają się dopiero po haku i przeplatają z A w parach (BB, A, B, A, BB, A, B, A).
3. **Cięcie idzie za mową.** 12 z 14 cięć wypada w pauzie lub na końcu frazy (±0,06 s), jedno na początku słowa,
   jedno w środku słowa. Narzędzie dosuwa cięcia do granic zdań (maks. ok. 0,5 s) i nie tnie w pół słowa.
4. **Tnie się obraz, dźwięk jest jednym torem.** Wstawki B zakrywają mówiącą osobę, a głos się nie przerywa.
5. **Statyczna kamera w ujęciach z mową.** Tło stoi w miejscu: sprawdziłem to śledzeniem tła i na klatkach
   (ujęcia 2 i 14 od początku do końca w tym samym kadrze). W ujęciach statycznych drgania to poniżej 1 px przy
   szerokości 1080. Kadr zmienia się wyłącznie cięciem, bez najazdów i bez ruchu kamery w trakcie ujęcia, więc
   **nie dodaję sztucznego ruchu kamery ani „shake"**: rolka go nie ma. Ruch jest we wstawkach (ręka, ekran,
   przeostrzanie): średnia różnica kolejnych klatek to 1,4 w ujęciach z mową i 2,5 we wstawkach (skala 0–255).
6. **Efekty: jedno.** Przeostrzanie. W ujęciach 13 (puenta) i 15 (wezwanie) pierwsza klatka jest mocno rozmyta,
   a ostrość wraca w ok. 0,3 s: narzędzie odtwarza to efektem „wejście z rozmycia". Podobne przeostrzanie robi sama
   kamera w ujęciu 4 (ekran telefonu) i na początku ujęcia 14 (dłoń przy obiektywie, ostrość przechodzi na twarz):
   to trzeba **nagrać**, nie da się tego dorobić w montażu. Poza tym tylko twarde cięcia: zero przejść,
   zero zoomów w trakcie ujęcia.
7. **Mowa.** 3,6 słowa na sekundę. Pauzy skrócone do ≤ 0,35 s, jedyny wyjątek: 0,76 s tuż przed puentą (to ona robi
   efekt). Najszybciej w radzie: 4,6 słowa/s, najwolniej w „wyborze" i puencie (ok. 2 słowa/s). Uwaga na narzędzie: skraca
   każdą pauzę dłuższą niż 0,5 s do 0,35 s, więc pauzę przed puentą nagraj na ok. 0,5 s albo użyj `--no-tighten`
   (wtedy żadna pauza nie jest skracana).
8. **Napisy.** Słowo po słowie, 1–2 słowa naraz (ok. 2,1 zmian na sekundę), krótkie słowa (do 3 liter) wiążą się
   z następnym. 5 wyróżnionych fraz na 34 s, ok. co 6,8 s, w układach: stos środkowy z akcentem, prawy górny,
   prawy dolny, środkowy, na końcu duży napis puenty. W stosie „środkowym z akcentem" największy, środkowy wiersz jest w kolorze `#E2FB77`.
9. **Dźwięk.** Sam głos, bez muzyki i efektów, −14,7 LUFS, LRA 2,9 LU (wyrównany). Narzędzie normalizuje do −14 LUFS.
10. **Długość.** Rytm skaluje się tak, że hak i zakończenie zostają, środek się powtarza, a jedno ujęcie elastyczne
    przejmuje resztę. Tabela poniżej pokazuje, co z tego wychodzi dla różnych długości materiału po skróceniu pauz.

| Materiał | Ujęć | Cięć na minutę | Uwaga |
|--:|--:|--:|---|
| 12–15 s | 5 | 16–20 | sam hak i zakończenie, bez wstawek B (za krótko) |
| 16 s | 6 | 18,8 | pierwsza wstawka B |
| 18 s | 7 | 20,0 | para wstawek |
| 28 s | 12 | 23,6 | |
| **34 s** | **15** | **24,7** | **dokładnie wzorzec (z `--no-snap` co do klatki)** |
| 45 s | 21 | 26,7 | środek powtórzony 1,6 razy |
| 60 s | 29 | 28,0 | |
| 90 s | 44 | 28,7 | tempo o ok. 16% wyższe niż we wzorcu |

Dłuższy materiał jest więc nieco szybszy niż wzorzec, bo hak i zakończenie to stała część. Jeśli chcesz inny rytm
dla innej długości, zrób szablon z rolki o tej długości (`analyze`).

## Format scenariusza

Rolka ma 123 słowa na 34 s. Konstrukcja to osiem beatów. Poniższa mapa mówi, **ile słów i jaką funkcję** ma
każdy beat; tekst dobierasz sam, a cięcia i kadry i tak podążają za mową.

| Beat | Ujęcia | Czas (s) | Słów | Funkcja |
|---|---|---|--:|---|
| 1. Hak: wynik przed/po | 1–2 (A) | 0,0–5,2 | 18 | Konkretna liczba w pierwszych ok. 2,5 s i kontrast „kiedyś → teraz". Napisy: stos środkowy z limonkowym akcentem. |
| 2. Kwalifikator | 3 (B) | 5,2–6,8 | 5 | „…i to mimo/bez…": obniża dystans, uwiarygadnia skromny start. |
| 3. Początek i pierwszy sygnał | 4–6 (B, A, B) | 6,8–12,6 | 18 | Skąd się zaczęło (bez ambicji) i pierwszy mały dowód, że działa. |
| 4. Decyzja i stawka | 7–10 (A, B, B, A) | 12,6–20,1 | 26 | Co straciłem lub zaryzykowałem, zakład bez odwrotu, alternatywa „albo… albo…" i wybór dwoma słowami. Wstawki: jednolite pomarańczowe tło. |
| 5. Wynik w liczbach | 11 (B) | 20,1–22,6 | 10 | Dwa–trzy kolejne wyniki w następnych okresach. |
| 6. Sufit i puenta | 12–13 (A) | 22,6–25,4 | 9 | „Myślałem, że to już koniec wzrostu", pauza 0,76 s, dwa słowa zaprzeczenia. Puenta w dużym napisie, wejście z rozmycia. |
| 7. Rada | 14 (A) | 25,4–31,0 | 26 | Jedna rada do widza w trzech krokach (nie czekaj na X, naucz się Y, pokaż to). Najdłuższe ujęcie (5,6 s), najszybsza mowa. |
| 8. Wezwanie | 15 (A) | 31,0–34,0 | 11 | Lekkie, z humorem, o profilu/kontakcie. Wejście z rozmycia. |

### Budżet słów na ujęcie

`9, 9, 5, 4, 8, 6, 7, 13, 4, 2, 10, 7, 2, 26, 11` (razem 123). Zasady pisania, które z tego wynikają:

- **Jedno ujęcie = jedna fraza.** Cięcie wypada na końcu zdania, przecinku albo spójniku, więc pisz krótkimi członami
  (2–13 słów) i kończ je tam, gdzie ma być zmiana kadru.
- **Liczby w pierwszych 5 sekundach** i potem jeszcze raz w beacie 5. Konkretne kwoty, daty, razy, nie „dużo".
- **Jeden zwrot akcji i jedna puenta z dwóch słów** po pauzie. Puenta zaprzecza poprzedniemu zdaniu.
- **Rada w trzech krokach rozkazujących** w jednym ujęciu (to ono ma 26 słów), potem lekkie zamknięcie.
- **Wstawki B przykrywają zdania o rzeczach**, które da się pokazać (ekran, rekwizyt, dłonie), a nie o emocjach.

### Przykład (hipotetyczny: liczby i fakty wymyślone, żeby pokazać budżet słów)

Temat: konferencja B2B, której frekwencja urosła przy tym samym budżecie. Każdy wiersz to jedno ujęcie, a liczba słów
jest równa budżetowi wzorca (razem 123).

| # | Rola | Tekst | Słów |
|--:|:-:|---|--:|
| 1 | A | Rok temu na naszą konferencję przyszło tylko osiemdziesiąt osób. | 9 |
| 2 | A | W tym roku trzysta, przy tym samym budżecie reklamowym. | 9 |
| 3 | B | I to bez agencji eventowej. | 5 |
| 4 | B | Zaczęło się od ankiety, | 4 |
| 5 | A | ale kiedy pierwsi uczestnicy sami zaprosili swoich kolegów, | 8 |
| 6 | B | zrozumieliśmy, że to naprawdę może działać. | 6 |
| 7 | A | Dlatego skreśliłem z planu połowę płatnych reklam. | 7 |
| 8 | B | Zaryzykowałem wtedy całą resztę budżetu. Albo uczestnicy sami zrobią nam promocję na LinkedInie, | 13 |
| 9 | B | albo wracamy do reklam. | 4 |
| 10 | A | Zaufałem uczestnikom. | 2 |
| 11 | B | Po pierwszym miesiącu mieliśmy sto dwadzieścia zgłoszeń. Po drugim dwieście. | 10 |
| 12 | A | I byłem pewien, że to już szczyt. | 7 |
| 13 | A | Było więcej. | 2 |
| 14 | A | Zapamiętaj trzy rzeczy, zanim zaczniesz wydawać na reklamy. Najpierw zbuduj program, o którym ludzie chcą opowiadać. Potem ułatw im polecanie. Na końcu pokaż, że to działa. | 26 |
| 15 | A | Jeśli chcesz zobaczyć, jak to robimy, zajrzyj na profil, nie gryzie. | 11 |

Wstawki dla tego przykładu: 3 identyfikator uczestnika w makro, 4 ekran telefonu z ankietą, 6 światło sali,
8 i 9 rekwizyt (karta) na pomarańczowym tle, 11 dłonie na klawiaturze (panel rejestracji).

### Inne długości i formaty

Szacunek: słów ≈ 3,6 × sekundy, czyli 65 słów na 18 s, 123 na 34 s, 215 na 60 s.

- **15–20 s (zajawka):** beaty 1, 6, 8 (hak, puenta, wezwanie), ok. 55–70 słów. Pamiętaj, że poniżej 16 s
  narzędzie nie wstawia B (tabela wyżej). Krótki format w pełnym stylu: zrób szablon z krótkiej rolki wzorcowej.
- **34 s:** pełna mapa, jak wyżej.
- **45–60 s:** hak i wezwanie zostają, beaty 3–5 powtarzasz jako kolejny „punkt zwrotny" z własną stawką i liczbą
  (środek wzorca i tak się powtarza w montażu), rada zostaje jedna.
- **Inna konstrukcja beatów** (np. lista, poradnik, case): nagraj lub weź rolkę wzorcową w tej formie i uruchom
  `analyze --speech`. Dostaniesz liczbę słów na każde ujęcie i tempo mowy, czyli taki sam budżet jak wyżej.

## Co się przenosi, a co nie

| Element | Przenosi się? | Zależy od Ciebie |
|---|---|---|
| Rytm cięć, wzór A/B, hak i zakończenie | tak, 1:1 | długość materiału (tabela wyżej) |
| Wielkość i położenie twarzy w kadrze | tak, względem Twojej twarzy | rozdzielczość źródła ogranicza zoom; twarz musi być widoczna |
| Kolor: jasność, nasycenie, barwa, winieta | tak, jako dopasowanie statystyk | światło na planie; z bardzo jasnego obrazu wyjdzie szum w cieniach |
| Napisy: krój, rozmiary, pozycje, akcent | tak | rozpoznanie mowy (faster-whisper) i poprawka literówek |
| Poziom dźwięku | tak (−14 LUFS) | barwa głosu, pogłos pomieszczenia, mikrofon |
| Ruch kamery | nie ma czego przenosić (statyw) | |
| Treść ujęć: pokój, rekwizyty, B-roll, muzyka | nie | to Twój materiał |

## Ograniczenia (uczciwie)

- **Jedna rolka to jedna próbka.** Statystyki pochodzą z 15 ujęć i 34 s jednej osoby w jednym mieszkaniu. To styl
  tej rolki, nie uniwersalna reguła „jak wygląda dobry reel".
- **Dopasowanie kolorów jest statystyczne, nie parowane.** Nie mam Twojego nagrania przed i po, tylko rozkład wzorca.
  Sprawdziłem je na trzy sposoby. (1) Zdjęcia i filmy syntetyczne: rozkład jasności trafia w ok. 1–3 jednostki L*,
  odcień skóry zostaje w ok. 3°. (2) Klatki samej rolki, które sztucznie rozjaśniłem i przesyciłem: średni błąd koloru
  względem oryginału spada z ΔE 26 do 2 (dla obrazu ciepłego i płaskiego z 13 do 4), a skóra i ściany wyglądają
  naturalnie. (3) Pełny przebieg na rozjaśnionej rolce: wynik wraca do ciemnego, stonowanego wyglądu wzorca. Test (2) jest
  optymistyczny, bo takie zniekształcenie da się odwrócić. **Na Twoim nagraniu go nie sprawdzałem:** zrób próbkę 10 s
  i obejrzyj. Jeśli twarz wychodzi zbyt ciemna: `--look 0.6`. Wzorzec ma skórę na ok. 30% waveformu.
- **Kadrowanie po twarzy** wymaga pakietów numpy i onnxruntime; bez nich zostają stałe zoomy z szablonu. Śledzi
  największą twarz, więc kilka osób w kadrze to kłopot. Pomiar twarzy w ujęciu z szybkim ruchem (ujęcie 10 we wzorcu)
  jest niepewny: ujęcie ma 1 s i twarz zmienia w nim rozmiar.
- **Winieta i LUT działają na cały kadr**, także na B-roll, który podasz, i zawsze według profilu ujęć z mową (profil
  wstawek wzorca to głównie pomarańczowa scenografia, więc go nie stosuję). Jeśli wstawki mają zostać w swoich kolorach,
  zrób je poza narzędziem albo ustaw `--look 0`.
- **Zoom cyfrowy zmiękcza obraz.** Przy 36% wysokości twarzy (3× od najszerszego kadru) potrzebujesz 4K albo osobnego
  bliskiego ujęcia.
- **Napisy:** dobór wyróżnionych fraz jest heurystyczny (liczby, końce zdań, krótka puenta po pauzie).

## Dodatek: karta stylu (wygenerowana)

Tabele poniżej generuje komenda `python rolka.py style` z szablonu, więc zawsze zgadzają się z liczbami, których używa
montaż. Jeśli zmienisz szablon, wygeneruj kartę ponownie i wklej między znaczniki (test sprawdza, że karta jest aktualna).

<!-- karta:start -->
# Karta stylu: Format 1: mówiąca głowa + B-roll, cięcia w rytmie rolki, napisy słowo po słowie

Źródło: https://www.instagram.com/reel/DeuOaXKtPBb/. Format 1080x1920, 25 kl./s, 34,0 s.

## Cięcia i tempo

- 14 cięć w 34,0 s, czyli 24,7 cięć na minutę.
- Ujęcie trwa średnio 2,27 s (mediana 1,88, od 0,88 do 5,64 s).
- Hak 5,2 s, rozwinięcie 19,2 s, zakończenie 9,5 s.
- Mówiąca głowa (A) to 65% czasu, wstawki (B) 35%.
- Wzór ujęć: `AABBABABBABAAAA`. Ujęcie elastyczne (przejmuje różnicę długości): nr 14, 5,64 s.
- Rytm (s): 2,56A, 2,68A, 1,60B, 1,16B, 2,76A, 1,80B, 1,72A, 3,08B, 1,68B, 1,04A, 2,52B, 1,88A, 0,88A, 5,64A, 3,00A.
- Pauzy w mowie: powyżej 0,50 s skracane do 0,35 s.
- Ruch w kadrze (średnia różnica kolejnych klatek, skala 0-255): mówiąca głowa 1,4, wstawki 2,5. Im bliżej zera, tym bardziej statyczny kadr.
- Głośność rolki: -14,7 LUFS, szczyt -0,7 dBTP, zakres LRA 2,9 LU (cel w szablonie: -14,0 LUFS).

## Kadry

Rozmiar i położenie twarzy w ujęciach z mową, jako ułamki kadru (x: 0% = lewa krawędź, y: 0% = góra).

| Ujęcie | Czas (s) | Plan | Twarz: wysokość | Twarz: x | Twarz: y | Oczy: y |
|---|---|---|---|---|---|---|
| 1 | 0,0-2,6 | plan ogólny | 12% | 51% | 48% | 47% |
| 2 | 2,6-5,2 | plan średni | 16% | 48% | 44% | 42% |
| 5 | 8,0-10,8 | plan średni | 21% | 52% | 36% | 34% |
| 7 | 12,6-14,3 | plan średni | 18% | 41% | 27% | 26% |
| 10 | 19,0-20,1 | plan średni | 15% | 36% | 31% | 29% |
| 12 | 22,6-24,5 | zbliżenie | 36% | 53% | 20% | 17% |
| 13 | 24,5-25,4 | zbliżenie | 36% | 59% | 41% | 40% |
| 14 | 25,4-31,0 | zbliżenie | 27% | 58% | 35% | 33% |
| 15 | 31,0-34,0 | zbliżenie | 30% | 61% | 38% | 36% |

Drabinka: najszerszy kadr ma twarz 12% wysokości, zbliżenia do 36% (3,1 raza więcej). Środek twarzy leży między 20% a 48% wysokości kadru, więc dół kadru zostaje wolny na napisy.

Gdy nie ma osobnego materiału na wstawkę B, wycinamy ją z nagrania z mową:
- detal 1: detal: twarz i oczy (zbliżenie na twarz), zoom x1,60
- detal 2: detal: klatka piersiowa i dłonie (pod twarzą), zoom x1,45

## Kolory

L* to jasność w skali 0-100, C* to nasycenie (0 = szarość, ok. 100 = skrajnie żywy kolor), odcień w stopniach (0° czerwień, 90° żółć, 180° zieleń-cyjan, 270° błękit). Skala CIE Lab, D65.

**Ujęcia z mową (A)**

- Jasność: bardzo ciemny (low-key). Mediana L* 21, połowa kadru mieści się między L* 11 a L* 34, cienie (5. percentyl) L* 6, światła (99. percentyl) L* 75.
- Nasycenie: mocno stonowane, średnie C* 10.
- Winieta: kolejne pierścienie od środka mają 90%, 73% i 66% jasności środka (w rogach 66%).
- Paleta (udział pikseli): `#191B1D` 35%, `#5A392A` 17%, `#362722` 16%, `#3F4948` 13%, `#6B7A77` 8%, `#8E6856` 6%, `#ABB3A4` 3%, `#B35928` 2%.

**Wstawki (B)**

- Jasność: bardzo ciemny (low-key). Mediana L* 24, połowa kadru mieści się między L* 9 a L* 40, cienie (5. percentyl) L* 5, światła (99. percentyl) L* 76.
- Nasycenie: umiarkowane, średnie C* 25.
- Winieta: kolejne pierścienie od środka mają 95%, 87% i 78% jasności środka (w rogach 78%).
- Paleta (udział pikseli): `#191616` 36%, `#3E3733` 16%, `#7A503A` 11%, `#8D280D` 8%, `#EA5113` 8%, `#B83911` 8%, `#60190C` 6%, `#9B998D` 6%.

**Skóra**: L* 33, C* 18, odcień 36°. Jaśniej: kafelek „dark skin” wzornika ColorChecker ma L* 38, C* 20, odcień 46°, a „light skin” L* 66, C* 25, odcień 50°.

**Akcenty**: napisy `#E2FB77`, ciepłe światło w ujęciach z mową `#B35928`, tło wstawek `#EA5113`.

## Napisy

- Krój Anton, wersaliki, kolor #FFFFFF, akcent #E2FB77.
- Napisy biegnące: słowo po słowie, do 2 słów naraz, wysokość wersalików 57 px, górna krawędź na 1211 px z 1920.
- Wyróżnienia: fraza 2-5 słów mniej więcej co 6,8 s (nie częściej niż co 4,5 s). Kolejność układów: center_build, right_top, right_bottom, center_stack, mega.

## Opis ujęć

1. (A) Plan ogólny: szeroki kadr, stół na pierwszym planie, twarz w środku. Haczyk: duże liczby w napisach.
2. (A) Plan średni: inne ustawienie kamery, twarz minimalnie na lewo od środka.
3. (B) B-roll makro (detal), głos leci dalej.
4. (B) B-roll: ekran telefonu.
5. (A) Plan bliski: twarz wyżej w kadrze, ręce złożone.
6. (B) B-roll: światło / klimat.
7. (A) Plan średni: postać stoi po lewej, pokój po prawej.
8. (B) B-roll: rekwizyt na jednolitym tle.
9. (B) B-roll: rekwizyt, ruch ręki.
10. (A) Plan średni: postać po lewej, akcja do kamery (rekwizyt w stronę obiektywu).
11. (B) B-roll: dłonie na klawiaturze.
12. (A) Zbliżenie: twarz tuż pod górną krawędzią, dolna połowa to czarna płaszczyzna na napisy.
13. (A) Zbliżenie: puenta: kamera z góry, wejście z rozmycia, duży napis.
14. (A) Zbliżenie: monolog, twarz lekko na prawo od środka.
15. (A) Zbliżenie: zamknięcie, twarz na prawo od środka, wejście z rozmycia, wezwanie do działania.
<!-- karta:end -->
