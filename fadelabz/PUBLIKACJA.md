# FadeLabz Barber Shop — www.fadelabz.pl: publikacja krok po kroku

Jeden plik `index.html`, wszystkie dane na sztywno, zero CMS, zero kosztów hostingu.
Hosting: GitHub Pages (darmowy, własna domena, HTTPS za darmo). Kalendarz: Kalendarz Google właściciela (darmowy).

## Co jest w folderze

| Plik | Po co |
|---|---|
| `index.html` | cała strona: treści, cennik, kalendarz, mapa, SEO (JSON-LD BarberShop + FAQ) |
| `img/logo.jpg` | logo (z materiałów salonu) |
| `img/cennik-plakat.jpg` | plakat z cennikiem, na razie nieużywany na stronie (zostawiony do social mediów) |
| `CNAME` | mówi GitHubowi, że strona ma działać pod `www.fadelabz.pl` |
| `.github/workflows/pages.yml` | automatyczna publikacja po każdej zmianie w repozytorium |
| `.nojekyll` | wyłącza zbędne przetwarzanie plików przez GitHub |

## Krok 1. Repozytorium i hosting (15 minut)

1. github.com → **New repository** → nazwa `fadelabz`, widoczność **Public** → Create.
2. **Add file → Upload files** → przeciągnij całą zawartość folderu `fadelabz/` (z podfolderami `img/` i `.github/`).
   Jeśli przeglądarka nie łapie ukrytego folderu `.github`, wgraj go osobno albo pomiń: wtedy w kroku 3 wybierz „Deploy from a branch”.
   Commit changes.
3. **Settings → Pages → Build and deployment**:
   - z workflow: Source → **GitHub Actions** (workflow z folderu `.github` zrobi resztę),
   - bez workflow: Source → **Deploy from a branch** → `main` / `(root)` → Save.
4. Po 1–2 minutach strona działa pod `https://TWOJ-LOGIN.github.io/fadelabz/`.

## Krok 2. Domena www.fadelabz.pl (10 minut + czas propagacji DNS)

U operatora domeny (tam, gdzie kupiliście fadelabz.pl) w ustawieniach DNS:

| Typ | Nazwa | Wartość |
|---|---|---|
| CNAME | `www` | `TWOJ-LOGIN.github.io` |
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |

Rekordy A sprawiają, że `fadelabz.pl` bez `www` też zadziała (GitHub przekieruje na `www`).

Potem w GitHub: **Settings → Pages → Custom domain** → wpisz `www.fadelabz.pl` → Save → po chwili zaznacz **Enforce HTTPS**.
Plik `CNAME` w repozytorium już zawiera `www.fadelabz.pl`, więc GitHub nie zgubi domeny przy kolejnych wgraniach.

DNS propaguje się od kilku minut do 24 godzin. Sprawdzenie: wejdź na `https://www.fadelabz.pl`.

## Krok 3. Kalendarz Google z wolnymi terminami (20 minut, jednorazowo)

Cel: klienci widzą na stronie, kiedy fotel jest wolny, i zapisują się sami. Każdy zapis ląduje w kalendarzu
właściciela, a zajęte godziny (również prywatne wydarzenia w jego kalendarzu) automatycznie znikają z listy.

Rozwiązanie: **Harmonogram spotkań w Kalendarzu Google** (darmowy na zwykłym koncie Gmail, 1 strona rezerwacji na konto).

1. Na komputerze (nie w aplikacji) wejdź na calendar.google.com, zaloguj się na konto właściciela salonu.
2. **Utwórz → Harmonogram spotkań**.
3. Ustaw:
   - Nazwa: `Wizyta w FadeLabz`
   - Czas trwania: `45 min` (albo osobno: 30 min strzyżenie / 60 min combo – darmowe konto ma 1 harmonogram, więc wybierz jeden średni czas, np. 45 min)
   - Ogólna dostępność: godziny pracy salonu, np. Pn–Pt 9:00–18:00, Sob 9:00–14:00
   - Zaplanowane okno: np. „do 30 dni naprzód”, minimalne wyprzedzenie „2 godziny”
   - Kalendarze sprawdzane pod kątem dostępności: zaznacz główny kalendarz właściciela (dzięki temu prywatne wpisy blokują terminy)
   - Formularz rezerwacji: imię i nazwisko, telefon (ustaw jako wymagane), opcjonalnie „Jaka usługa?”
   - Powiadomienia e-mail: włącz, przypomnienie 1 dzień wcześniej
4. Zapisz. Otwórz harmonogram → **Udostępnij** → zakładka **Wstaw na stronie** → opcja „Wbudowana strona rezerwacji” → skopiuj z kodu adres z `src="..."`.
   Wygląda tak: `https://calendar.google.com/calendar/appointments/schedules/AcZss...?gv=true`
5. W `index.html` znajdź linię z `TWOJ-LINK-DO-KALENDARZA` (komentarz `TODO KALENDARZ`) i wklej tam skopiowany adres. Zapisz, wgraj plik na GitHub (Upload files, nadpisz).

Od tej chwili sekcja „Wolne terminy” pokazuje prawdziwy kalendarz. Nowe rezerwacje przychodzą właścicielowi mailem i do kalendarza w telefonie.

**Wariant prostszy (tylko podgląd zajętości, bez samodzielnego zapisu):** w ustawieniach kalendarza właściciela
→ „Uprawnienia dostępu do wydarzeń” → „Udostępnij publicznie” → **„Tylko informacje o dostępności (ukryj szczegóły)”**.
Potem w `index.html` wklej jako `src`:
`https://calendar.google.com/calendar/embed?src=ADRES@gmail.com&ctz=Europe%2FWarsaw&mode=WEEK&hl=pl`
Klient widzi bloki „Zajęte”, resztę ustala telefonicznie. Prywatne nazwy wydarzeń nie są widoczne.

## Krok 4. Uzupełnienia na starcie (lista TODO w pliku)

W `index.html` wpisz w wyszukiwarkę (Ctrl+F) słowo `TODO`:

1. `TODO KALENDARZ` – adres z kroku 3.
2. `TODO GODZINY` – prawdziwe godziny otwarcia. Na stronie wpisane są robocze: Pn–Pt 9–18, Sob 9–14. Popraw w dwóch miejscach: tabela w sekcji Kontakt i `openingHoursSpecification` w JSON-LD na górze pliku.
3. `TODO ZDJĘCIA` – 6 zdjęć prac + 1 portret barbera. Format pionowy 4:5 (np. 800×1000 px), JPG do 300 KB każde. Wrzuć do `img/`, w galerii zamień każdy `<div class="ph">…</div>` na `<img …>` według wzoru w komentarzu.
4. `TODO FACEBOOK` – adres strony FadeLabz Barber na Facebooku (dwa miejsca: sekcja Opinie i stopka). Dopisz też do listy `sameAs` w JSON-LD.
5. Sekcja Opinie: wklej 2–4 prawdziwe opinie z Facebooka / Google (imię, miasto).

Kod pocztowy 19-400 i współrzędne w JSON-LD są dla Olecka; jeśli Google Maps pokaże pinezkę obok, popraw `latitude`/`longitude` na te z Google Maps (kliknij prawym na pinezkę → pierwsza linia).

## Aktualizacje

Zmiana ceny, godzin, zdjęcia: edytuj `index.html` (na GitHubie: kliknij plik → ołówek → zmień → Commit changes).
Strona odświeża się sama w 1–2 minuty.

## Dlaczego tak, a nie Wix / WordPress

- 0 zł miesięcznie, bez reklam, bez „powered by”.
- Jeden plik HTML: nie ma czego aktualizować, nie ma wtyczek, nie ma włamań.
- Strona ładuje się w ułamku sekundy na telefonie, a 90% klientów barbera wchodzi z telefonu.
- Kalendarz jest tam, gdzie właściciel i tak go ma: w Google w telefonie.
