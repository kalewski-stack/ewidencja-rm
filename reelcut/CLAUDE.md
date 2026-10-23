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

Aliasy w `--template`, w interfejsie i w API: `format1`, `format2` (wielkość liter, spacje i myślniki bez znaczenia).

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
- Dokumentacja pilnowana testami: karty osadzone w STYL.md i GRAFIKI.md, przykładowy scenariusz w FORMAT2.md i przykładowy plan
  JSON w GRAFIKI.md (znaczniki `<!-- scenariusz:start -->`, `<!-- plan-f2:start -->`), liczby w FORMAT2.md względem szablonu.
- Odpowiedzi dla użytkownika po polsku, zwięźle, rzeczowo.
