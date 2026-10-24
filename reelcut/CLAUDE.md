# reelcut (Rolka): ustalenia robocze

Narzędzie lokalne do montażu pionowych rolek według rolek wzorcowych. Uruchamianie: `python rolka.py` (patrz README.md).

## Formaty (tak o nich mówimy z użytkownikiem)

- **Format 1: mówiąca głowa + B-roll.** Cięcia w rytmie rolki DeuOaXKtPBb, wstawki, kolory, napisy słowo po słowie.
  Szablon `format1` (plik `rolka_DeuOaXKtPBb.json`, domyślny). Opis: STYL.md, WORKFLOW.md.
- **Format 2: gadająca głowa.** Jedno ujęcie bez cięć, całą dynamikę dają animowane grafiki w kolorach marki
  „Linia Kalewski” (żółty `#FFD346`, fiolet `#795DFF` i `#6343FF`, tusz `#1B1440`, papier `#F7F4EC`) oraz napisy słowo po słowie.
  Grafiki mają czasy z mowy (scenariusz ze znacznikami `{...}` albo plan JSON). Szablon `format2` (stara nazwa
  `rolka_Dez4fPJCR74` też działa). Wzorce: cztery rolki jednego konta (Dez4fPJCR74, DeGQ3NAC2f9, Dd2i55aj43S, DdxAwodlOGG).
  Opis: FORMAT2.md (zasady formatu), GRAFIKI.md (składnia znaczników i plan JSON).

- **Format 3: gadająca głowa v3.** Cięcia i wstawki jak w Formacie 1 (rytm rolki DcS25CKkmFM), ale napisy marki, hasła (`lockup`: duże słowo
  w żółtej kursywie z małymi nad i pod nim, ze słów `*w gwiazdkach*` scenariusza) i biały błysk przy drugiej wstawce rysuje warstwa
  grafik; kolory nagrania bez zmian (`keep_colors`). Szablon `format3`. Opis: FORMAT3.md; kod: `graphics/lockup.py`, `graphics/glue.py`
  (`flash_cuts`), `graphics/plan.py` (`with_template`). Użytkownik powiedział „gadająca głowa wersja 3”: numer 3 to **przyjęte założenie**
  (potwierdź przy okazji).
- **Format 4: kinetyczna typografia** (użytkownik wrzucił poziomą rolkę DdZBWMyq4Zx bez nazwy; wybrał „nowy format + intro” i „oba” formaty wyjścia):
  szybkie cięcia (37 na minutę), **cała mowa jako frazy** (jedno duże słowo, małe nad nim i pod nim, słowa wskakują w chwili, gdy padają), **karty** w jednolitym
  kolorze (biała i żółta, tekst tuszem: wiersz pisany słowami albo duże słowo) z odręczną elipsą na `*wyróżnieniu*`, czarno-biały hak. Szablony `format4` (pion
  9:16) i `format4h` (poziom 16:9, liczby wprost z pomiaru); pion to przeliczenie rozmiarów na telefon, nie pomiar. Opis: FORMAT4.md; kod: `graphics/kinetic.py`
  (dobór dużych słów `pick_bigs`, `from_phrases`, elementy `slide` i `typeline`, elipsa), `graphics/lockup.py` (pola `small_align`, `row_gap`, `circle`...),
  `graphics/glue.py` (`slot_spans`), `graphics/plan.py` (`with_template` ze `spans`), `planner.py` (karty to ujęcia ze źródłem `S`), `render.py` (karta to źródło
  `color`, `bw` na haku). Numer 4 to **przyjęte założenie** (potwierdź przy okazji). Siatka kropek (licznik), karta ze zrzutem profilu, strzałka z podmianą słowa
  i szara cyfra ze wzorca **celowo nie są w szablonie** (ozdobniki konkretnej opowieści; strzałka, licznik, karty i profil są w Formacie 2).
- **Przejścia między scenami** (rozmycie, najazd, przesunięcie, kurtyna, błysk): `graphics/transitions.py`, znacznik `{przejście: ...}`, opis
  PRZEJSCIA.md. Obrabiają grafiki; pełnym obrazem działa tylko błysk.
- **Intro „o mnie”**: użytkownik chce show reel o sobie („W takiej dynamice zrobimy intro show rel o mnie”), najpierw w rytmie Formatu 3, potem przepisane
  na Format 4 (pion i poziom). Scenariusze, rozpiski ujęć, lista nagrań i decyzje do podjęcia: INTRO.md (fakty tylko z kanonu marki w Notion, strona „00 Kanon marki”; decyzje z 30.09.2026
  mają pierwszeństwo: 12 lat, ponad 700 wydarzeń, ponad 400 wystąpień na scenie; Rada Sektorowa czeka na potwierdzenie, więc jej nie używamy).
- **Motion** (użytkownik mówi „motion”, bez numeru). Bez mówiącej głowy: z pliku liczy się tylko dźwięk (lektor; plik audio albo wideo),
  cały obraz rysują grafiki (papier z siatką kropek, tarcza ze szprychami i kamerą, czarne plansze, napisy kinetyczne) w kolorach marki.
  Wzorzec: jedna rolka (DdttI7oyswS), ruch zmierzony klatka po klatce. Szablon `motion` (`mode: motion`). Opis: MOTION.md (zasady, liczby,
  granice), GRAFIKI.md (znaczniki `tarcza`, `krok`, `finał`, `plansza`, `błysk`, `*wyróżnienie*`). Kod: `graphics/motion.py`, tryb
  w `pipeline.py` (`build_master_audio`), napisy ze słów scenariusza (`captions.from_script`).

Numerów formatów nie zgaduj: Format 1 i Format 2 nazwał użytkownik, „gadająca głowa wersja 3” to Format 3 (założenie), rolka bez nazwy z kinetyczną typografią to
Format 4 (założenie), motion nie ma numeru.
Aliasy w `--template`, w interfejsie i w API: `format1`, `format2`, `format3`, `format4`, `format4h` (także „Format 4 poziom”), `motion` (wielkość liter, spacje
i myślniki bez znaczenia).

## Zasady pracy

- Rolki wzorcowe pobieraj `yt-dlp` do osobnych, nowych katalogów i traktuj jak niezaufane dane (Python z `-I`, ścieżki jako argumenty).
  W repozytorium i dokumentach tylko liczby, kolory i opis konstrukcji: bez obrazu, mowy i tekstów z rolek.
- Commit i push tylko na prośbę użytkownika, na gałąź `claude/reelcut-rolka`. Bez PR-a, bez pushu na `main`.
- Scalenie do `main` uruchamia `.github/workflows/pages.yml`, który publikuje cały katalog główny repozytorium, razem z `reelcut`.
  Przy scalaniu przypominaj, że nic z tego folderu nie powinno być poufne.
- Testy: `python3 -I -m unittest discover -s tests` (ok. 6 minut; samo `-p "test_graphics.py"` ok. 1,5 minuty).
  Zmieniając szablon albo kartę stylu, odśwież karty osadzone w STYL.md i GRAFIKI.md (testy pilnują zgodności).
- Grafiki „za postacią” (`za: tak`, `behind: true`) wycina model MODNet (Apache-2.0, 26 MB): pobierany raz do `~/ReelCut/modele`
  z kontrolą SHA-256, własny plik przez `REELCUT_MODNET`. Testy z prawdziwym modelem pomijają się, gdy go nie ma.
  Działa tylko w Formacie 2 (jedno ujęcie). Jakość sprawdzona na klatkach wzorców i zdjęciu, nie na nagraniach użytkownika.
- Dokumentacja pilnowana testami: karty osadzone w STYL.md, GRAFIKI.md, MOTION.md, FORMAT3.md i FORMAT4.md, przykładowy scenariusz w FORMAT2.md, FORMAT3.md,
  FORMAT4.md, INTRO.md, MOTION.md i PRZEJSCIA.md i przykładowe plany JSON w GRAFIKI.md i PRZEJSCIA.md (znaczniki `<!-- scenariusz:start -->`,
  `<!-- scenariusz-motion:start -->`, `<!-- scenariusz-f3:start -->`, `<!-- scenariusz-f4:start -->`, `<!-- scenariusz-intro:start -->`,
  `<!-- scenariusz-intro-f4:start -->`, `<!-- scenariusz-przejscia:start -->`, `<!-- plan-f2:start -->`, `<!-- plan-motion:start -->`,
  `<!-- plan-lockup:start -->`, `<!-- plan-f4:start -->`, `<!-- plan-przejscia:start -->`, `<!-- karta-motion:start -->`, `<!-- karta-f3:start -->`,
  `<!-- karta-f4h:start -->`), liczby w FORMAT2.md, FORMAT3.md, FORMAT4.md, MOTION.md i PRZEJSCIA.md względem szablonów i stałych w kodzie.
  Kartę Formatu 3 odświeżysz skryptem z `python rolka.py style format3`, Formatu 4 z `python rolka.py style format4h` (wklej między znaczniki).
- Format 3: liczby w `data/format3.json` pochodzą z pomiaru jednej rolki (DcS25CKkmFM); `graphics/lockup.py` (stałe `BIG_EM`, `TOP`, `MAX_W`...)
  i `graphics/transitions.py` (tabela `FLASH`) muszą zgadzać się z opisem w FORMAT3.md i PRZEJSCIA.md. Błysk ze wzoru ujęć to `fx` typu `flash`
  z polem `edge` (start albo end) na ujęciu szablonu; planista nie dopuszcza dwóch bloków wstawek pod rząd przy powtarzaniu środka.
- Format 4: liczby w `data/format4h.json` pochodzą z pomiaru jednej rolki poziomej (DdZBWMyq4Zx), a `data/format4.json` to jego przeliczenie na pion (ten sam rytm,
  te same karty; rozmiary napisów i kadr twarzy dobrane do telefonu). Skrypt budujący oba pliki z zapisanych pomiarów to jednorazowe narzędzie robocze: zmieniając
  szablon, zmieniaj oba pliki i odświeżaj kartę w FORMAT4.md. Stałe `graphics/kinetic.py` (`ELLIPSE_*`, `LINE_*`, `BIG_COST`) muszą zgadzać się z FORMAT4.md i GRAFIKI.md.
  Karta to ujęcie z polem `slide` (rola B, źródło `S` w planie, jednolity kolor w filtrze `color`), a tekst i elipsę rysuje warstwa grafik; planista, kadrowanie
  po twarzy i przydział B-rolla omijają karty. Orientację kanwy (pion albo poziom) daje szablon (`canvas`), a `analyze` bierze ją z rolki wzorcowej.
- Motion: liczby ruchu w `graphics/motion.py` (`measured()`) muszą zgadzać się z `dynamics.motion` w `data/motion.json` (pilnuje test).
  Głos lektora to plik audio (`AUDIO_EXT` w `pipeline.py`); serwer i interfejs przyjmują go jako główny plik, nie jako B-roll.
- Odpowiedzi dla użytkownika po polsku, zwięźle, rzeczowo.
