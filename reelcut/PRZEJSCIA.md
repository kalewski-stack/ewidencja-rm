# PRZEJŚCIA: jak jedna scena zmienia się w drugą

Przejście to obróbka obrazu w chwili cięcia: tuż przed nim stara scena wychodzi (rozmywa się, najeżdża, ucieka), tuż po nim nowa
wchodzi. Wzorce: rolka DekGW1-tCoi (rozmycie, najazd, przesunięcie, kurtyna) i rolka DcS25CKkmFM (błysk), liczby zmierzone klatka po
klatce przy 30 kl./s. W repozytorium są tylko liczby i opis konstrukcji, bez obrazu i tekstów z rolek.

## Gdzie to działa

**Scena to wszystko, co leży w kadrze poza tłem**: tytuł, plansza, tarcza, lista. Tło (papier z siatką kropek w trybie motion) stoi
w miejscu, a przejście obrabia to, co na nim leży. Dlatego pełny zestaw przejść jest do **motion** i do filmów, w których grafiki
same są obrazem. Gdy pod grafikami leży **nagranie** (Formaty 1-3), działa pełnym obrazem tylko **błysk**; rozmycie, najazd,
przesunięcie i kurtyna obrabiają same grafiki i nie ruszają nagrania, więc tam je dawaj tylko wtedy, gdy zmienia się scena grafik.
Cięcia między ujęciami nagrania zostają twarde (tak jest we wzorcu).

## Rodzaje

| Znacznik | Co się dzieje | Okno: przed / po cięciu | Liczby ze wzorca |
|---|---|---|---|
| `rozmycie` (`blur`) | stara scena rozmywa się i blednie do papieru, nowa się wyostrza | 5,5 kl. / 9 kl. | wyjście: rozmycie σ = 80 px · e^(−0,45 (f−1)) przy szerokości 1080, zanik do 48% w ostatniej klatce (× 0,55 na klatkę wstecz); wejście: σ = 40 px · e^(−s/2,6), zanik 25% · e^(−s/2) |
| `najazd` (`zoom`) | stara scena najeżdża i się rozmywa, nowa startuje mała i rośnie | 6 kl. / 18 kl. | wyjście: do ×1,30 w 6 klatkach, rozmycie 4% szerokości; wejście: od ×0,28, co klatkę zostaje 80% dystansu do skali 1 |
| `przesunięcie` (`whip`) | stara scena ucieka w bok z rozmyciem ruchu, nowa wjeżdża z przeciwnej strony | 4,5 kl. / 22 kl. | wyjście: 55% szerokości w 4,5 klatki; wejście: od 42% szerokości, co klatkę zostaje 85% dystansu; smuga to 35% przesunięcia |
| `kurtyna` (`wipe`) | półprzezroczysty szary pas przesuwa się po kadrze, za nim stoi nowa scena, przed nim jeszcze stara | 0 / 0,17 s | pas 45% kadru, miękka krawędź 10%, szary (150, 150, 150) z kryciem 32% |
| `błysk` (`flash`) | biała nakładka na całym obrazie, także na nagraniu | 4 kl. / 4 kl. | krycie w kolejnych klatkach: 25%, 58%, 82%, 86%, 82%, 58%, 25%; szczyt (86%) w pierwszej klatce nowej sceny |

Okno to czas, w którym przejście coś robi: wcześniej i później klatka jest dokładnie taka, jaka byłaby bez przejścia.

## Jak to wpisać

W scenariuszu: `{przejście: rodzaj | kierunek: ... | moc: ...}`. **Czas to chwila, w której zaczynasz mówić następne słowo.** Przy motion
zwykle stoi tuż przed `{plansza}` (wtedy przejście i plansza zaczynają się na tym samym słowie).

- `kierunek`: `lewo`, `prawo`, `góra`, `dół`. Dla `przesunięcia` kierunek, w którym ucieka stara scena (domyślnie `prawo`), dla `kurtyny`
  kierunek ruchu pasa (domyślnie `góra`). Pozostałe rodzaje go ignorują.
- `moc`: od 0 do 3 (domyślnie 1 = wzorzec). Skaluje rozmycie, przesunięcie, najazd i krycie błysku (błysk nie mocniejszy niż 100%).
- **Przyciąganie.** Scena kończy się zwykle kilka dziesiątych sekundy od słowa (plansza zostaje 0,3 s po ostatnim słowie), więc przejście ze
  scenariusza przyciąga się do najbliższego początku albo końca elementu, jeśli ten leży w odległości do 0,6 s. Nie musisz trafiać co do klatki.
  Nie chcesz przyciągania: `dokładnie: tak`.

<!-- scenariusz-przejscia:start -->
```
# Film ok. 20 s (Motion): przejścia na planszę i z powrotem (tekst hipotetyczny)
{tarcza: brief | nad: Formuła} Skopiuj tę formułę, jeśli chcesz wyniku. Pierwsza jest {krok: Cel} cel. Druga to {krok: Miara} miara.
{przejście: rozmycie} {plansza} Ale jest *jeszcze jedna rzecz*. {/plansza}
{przejście: przesunięcie | kierunek: lewo} Trzecia to {krok: Budżet} budżet.
{finał: Zrób zrzut ekranu} To cała formuła.
```
<!-- scenariusz-przejscia:end -->

W planie JSON przejścia to osobna lista `transitions`. **Czas `at` jest tam dokładny** (sekundy na osi gotowego filmu albo fraza z mowy,
jak przy elementach), bez przyciągania:

<!-- plan-przejscia:start -->
```json
{
  "schema": 1,
  "elements": [
    {"type": "backdrop", "at": 0, "dur": 12},
    {"type": "title", "at": 0.5, "dur": 3.5, "text": "Brief", "zone": "top"},
    {"type": "cutaway", "at": 4.0, "dur": 3.0, "text": "Ale jest *jeszcze jedna rzecz*"},
    {"type": "title", "at": 7.0, "dur": 4.0, "text": "Cel", "zone": "top"}
  ],
  "transitions": [
    {"kind": "blur", "at": 4.0},
    {"kind": "whip", "at": 7.0, "dir": "left", "strength": 1.0},
    {"kind": "flash", "at": 9.5}
  ]
}
```
<!-- plan-przejscia:end -->

| Pole | Znaczenie |
|---|---|
| `kind` | `blur`, `zoom`, `whip`, `wipe`, `flash` (albo polskie nazwy z tabeli) |
| `at` | czas cięcia, czyli pierwszej klatki nowej sceny: sekundy albo fraza z mowy (`nth`, `shift` jak przy elementach) |
| `dir` | `left`, `right`, `up`, `down` (albo `lewo`, `prawo`, `góra`, `dół`) |
| `strength` | moc, (0, 3] |

## Jak to jest zrobione

- W oknie przejścia program rysuje scenę osobno (bez tła), obrabia ją i dopiero kładzie na tle. Elementy, które kończą się dokładnie
  w chwili cięcia, po cięciu nie są już rysowane, żeby nowa scena nie nakładała się na starą.
- Rozmycie liczone jest na obrazie z przemnożoną przezroczystością, więc rozmyta scena nie ma ciemnych obwódek.
- Kurtyna: nowa scena widoczna jest za pasem, a stara (zamrożona w chwili tuż przed cięciem) przed nim.
- Błysk jest białą nakładką na całej warstwie grafik, więc w montażu z nagraniem bieli także to, co pod spodem.
- Film bez żadnego przejścia renderuje się bajt w bajt tak jak wcześniej. Okno przejścia kosztuje kilkanaście klatek obróbki.

## Przejścia w szablonach z nagraniem

Format 3 ma błysk wpisany w szablon: ujęcie z `fx: flash` daje błysk na swoim początku, ujęcie z `fx: flash` i `edge: end` na swoim końcu
(wstawka dostaje więc błysk na wejściu i na wyjściu). Błysk przy cięciu, które sam wskażesz, to `{przejście: błysk}`.
Przejście wpisane przez Ciebie w odległości 0,1 s od cięcia z szablonu zastępuje błysk z szablonu.

## Granice

- Rozmycie, najazd, przesunięcie i kurtyna nie obrabiają **nagrania**, tylko grafiki (patrz „Gdzie to działa”).
- Krzywe są zmierzone na jednej rolce (błysk na drugiej). Moc 1 odtwarza wzorzec; inne wartości to skalowanie, nie pomiar.
- Tło (`backdrop`) zawsze stoi w miejscu. Jeśli chcesz, żeby się ruszało, wpisz je jako zwykły element.
- Czas trwania przejścia jest stały (okna w tabeli); dłuższego albo krótszego nie ma. Moc zmienia siłę, nie czas.
