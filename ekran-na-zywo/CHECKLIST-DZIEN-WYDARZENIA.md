# Checklista: dzień wydarzenia (25.11.2026, Radom, Hotel Garden Inn)

## Dzień wcześniej

- [ ] Wdrożenie produkcyjne działa, `/health` zwraca `ok: true`.
- [ ] `PUBLIC_URL` ustawiony na docelowy krótki adres, QR prowadzi na stronę telefonu.
- [ ] Sekrety wgrane, linki `/ops`, `/mod`, `/screen` zapisane w menedżerze haseł i sprawdzone.
- [ ] Logotypy WUP, EURES, UE i tekst finansowania w motywie (albo świadoma decyzja o motywie roboczym).
- [ ] Slajdy: tylko pozycje z potwierdzonym źródłem i rokiem. Osoba po stronie klienta zatwierdziła dane.
- [ ] Lista ekspertów panelu wpisana w `/ops` (Eksport i ustawienia).
- [ ] Teksty zatwierdzone przez klienta: pytanie ankiety, etykiety, informacja o danych pod formularzem.
- [ ] Plansze awaryjne wygenerowane po ostatniej zmianie motywu (`npm run export:static`) i wdrożone.
- [ ] Pendrive: katalog `static/` (PNG) i `plansze.pdf`. Drugi egzemplarz na laptopie operatora.
- [ ] Wydruki QR na stojaki (`/print/qr`): rejestracja i wejście na salę. Kod min. 8 cm boku.
- [ ] `npm test` i `npm run loadtest` przeszły na wdrożeniu (potem ankieta wyzerowana).
- [ ] Naładowane: laptop operatora, tablet moderatora, powerbank, hotspot w telefonie jako zapas.

## Rano, przed 8:30

- [ ] Dojazd do Radomia z zapasem, na miejscu najpóźniej o 7:30.
- [ ] Kontakt do obsługi technicznej hotelu zapisany w telefonie: ______________________
- [ ] Komputer przy projektorze: `/screen?k=...`, pełny ekran (F11), wyłączone usypianie, powiadomienia i aktualizacje.
- [ ] Obraz Full HD 1920×1080, 16:9, nic nie jest ucięte przy krawędziach (margines bezpieczeństwa 5%).
- [ ] Wi-Fi sali: nazwa i hasło spisane, laptop operatora i tablet moderatora podłączone. Hotspot gotowy.
- [ ] `/ops`: „Połączono" i „Ekran żyje". Przełącz wszystkie sceny po kolei (klawisze 1 do 9, 0).
- [ ] Test QR z ekranu z ok. 12 metrów: iPhone (aparat), Android (aparat i Google Lens), przy świetle sali.
- [ ] Test QR ze stojaków.
- [ ] Próba generalna z min. 20 prawdziwymi telefonami przez Wi-Fi hotelu: głosy pojawiają się na ekranie poniżej sekundy, licznik zgadza się z liczbą głosujących.
- [ ] Próba pytań: wyślij 3 pytania z telefonu, zatwierdź w `/mod`, pokaż na ekranie, oznacz jako zadane.
- [ ] Próba rekomendacji: wpisz testową, odsłoń, usuń.
- [ ] Tryby awaryjne raz na sucho: (1) wyłącz Wi-Fi w laptopie operatora, czerwony baner, ekran zostaje; (2) wpis ręczny wyniku ankiety; (3) „Ekran statyczny" i sterowanie Shift + strzałki przy ekranie; (4) `plansze.pdf` z pendrive'a.
- [ ] Po próbach: **Wyzeruj ankietę** (słowo RESET), ukryj pytania testowe, wyczyść rekomendacje, scena 1, telefony: Poczekalnia.
- [ ] Moderator ma otwarty `/mod` na tablecie i wie, gdzie jest kolejka „Na panel".
- [ ] Osoba z obsługi wie, że przyjmuje pytania ustnie od osób bez zasięgu.

## Po wydarzeniu

- [ ] `/ops`, Eksport: „Pobierz wszystko (ZIP)". Plik w dwóch miejscach.
- [ ] Plansza rekomendacji 1080×1350 przekazana do rozesłania uczestnikom.
- [ ] Telefony: Zamknięte.
- [ ] Przypomnienie w kalendarzu: usunięcie danych po 30 dniach (`npm run purge -- --yes`), potwierdzenie do dokumentacji.
