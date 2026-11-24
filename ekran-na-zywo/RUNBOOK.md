# RUNBOOK operatora (25.11.2026, Radom)

Trzy okna: `/ops` (laptop operatora), `/screen` (komputer przy projektorze, pełny ekran F11), `/mod` (tablet moderatora).
Pasek u góry `/ops` ma być zielony: „Połączono" i „Ekran żyje". Nic nie przełącza się samo według zegara.

## Przebieg dnia

| Godzina | Co klikasz w /ops | Co widać |
|---|---|---|
| 8:30 | Sprawdź pasek stanu. Telefony: Poczekalnia. Scena 1 (plansza tytułowa). | ekran: tytuł konferencji |
| 9:00 | **Dalej** (spacja): krok 9:00. | ekran: infografiki w pętli, w rogu QR i licznik. Ankieta otwarta, telefony: ankieta |
| 9:30 | **Dalej**: krok 9:30. | ekran: ankieta na żywo, słupki rosną |
| ok. 9:43 | **Zamknij ankietę (finał)**, potwierdź. Potem „Pobierz planszę PNG". | ekran: wynik końcowy, zwycięska odpowiedź podświetlona |
| 9:45 | **Dalej**: krok 9:45. | ekran: plansza tytułowa. Telefony: podziękowanie |
| 12:45 | **Dalej**: krok 12:45. | ekran: QR, licznik pytań, zatwierdzone karty. Telefony: formularz pytań |
| 12:45 do 13:10 | Zakładka Pytania: **Zatwierdź na ekran** dla dobrych, **Ukryj** dla reszty. Pytania ustne: „Dodaj pytanie ręcznie". | nowe karty wjeżdżają na ekran |
| 13:10 | **Dalej**: krok 13:10. | ekran: wynik ankiety jako punkt odniesienia |
| 13:10 do 14:00 | Moderator układa kolejkę „Na panel" w `/mod`. Ty wpisujesz rekomendacje, jeśli dyktuje (zakładka Rekomendacje, zapis automatyczny). | ekran bez zmian |
| 14:00 | **Dalej**: krok 14:00. Potem **Następne na ekran** dla każdego pytania, po odpowiedzi „Oznacz aktualne jako zadane". | ekran: jedno pytanie na całą planszę |
| 14:05 | **Dalej**: krok 14:05. W zakładce Rekomendacje klikaj **Następna** w rytm moderatora (5 razy). | rekomendacje wchodzą po jednej |
| 14:10 | **Dalej**: krok 14:10. | ekran: wszystkie 5, statycznie, do zdjęć |
| 14:30 | **Dalej**: krok 14:30. Zakładka Eksport: **Pobierz wszystko (ZIP)**. | ekran: plansza tytułowa. Telefony: zamknięte |

Skróty: 1 do 9 sceny, 0 blackout, spacja „Dalej". Nie działają, gdy kursor jest w polu tekstowym.
Akcje niebezpieczne (zamknięcie, zerowanie, wpis ręczny) zawsze pytają o potwierdzenie. Zerowanie ankiety wymaga wpisania słowa RESET.

## Awarie

**1. Czerwony baner „BRAK POŁĄCZENIA" w /ops (sieć operatora).**
Ekran zostaje na aktualnej scenie, nic się nie psuje. Przyciski są zablokowane, żadna akcja nie ginie po cichu. Przełącz laptop na hotspot z telefonu. Baner zniknie sam. Jeśli trzeba zmienić scenę natychmiast: na komputerze przy ekranie Shift + strzałka w prawo lub w lewo (zmiana sceny lokalnie), Shift + B (wygaszenie), Esc (powrót do sterowania z /ops).

**2. Telefony uczestników nie łączą się (Wi-Fi sali).**
Ankieta: moderator prosi o podniesienie rąk, liczysz, w `/ops` otwierasz „Wpis ręczny wyników", wpisujesz liczby, potwierdzasz. Ekran pokaże je jak zwykły wynik. Pytania: osoba z obsługi przyjmuje pytania ustnie, wpisujesz je przez „Dodaj pytanie ręcznie".

**3. Ekran nie odpowiada albo animacje się tną („Ekran nie odpowiada" w pasku).**
Najpierw odśwież `/screen` (F5), działa z pamięci podręcznej nawet bez internetu. Jeśli animacje się tną: w `/ops` „Włącz ekran statyczny" (albo Shift + S przy ekranie). Jeśli system padł całkowicie: otwórz `plansze.pdf` z pendrive'a w trybie pełnoekranowym i prowadź konferencję dalej (ankieta rękami, pytania ustnie, rekomendacje na slajdzie).

Powrót do poprzedniej wersji systemu: `npx wrangler rollback` (robi osoba techniczna, dane zostają).
