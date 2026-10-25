#!/bin/bash
# Rolka: uruchomienie jednym klikiem. Przy pierwszym uruchomieniu sam instaluje dodatki (potrzebny internet).
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

stop() {
  echo
  echo "$1"
  echo
  read -n 1 -s -r -p "Nacisnij dowolny klawisz, zeby zamknac to okno..."
  echo
  exit 1
}

command -v python3 >/dev/null 2>&1 || stop "Nie znalazlem Pythona. Zainstaluj go wedlug pliku START.md albo Instrukcja_START.pdf, krok 2, i kliknij ten plik jeszcze raz."

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo
    echo "Instaluje ffmpeg, program do montazu. To trwa kilka minut. Nie zamykaj tego okna."
    echo
    brew install ffmpeg
  fi
fi
{ command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; } || stop "Nie znalazlem programu ffmpeg. Zainstaluj go wedlug pliku START.md albo Instrukcja_START.pdf, krok 3, i kliknij ten plik jeszcze raz."

if [ ! -f .venv/gotowe.txt ]; then
  echo
  echo "Pierwsze uruchomienie: instaluje dodatki. To trwa 5-15 minut i wymaga internetu."
  echo "Nie zamykaj tego okna."
  echo
  python3 -m venv .venv || stop "Nie udalo sie przygotowac srodowiska Pythona."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt || stop "Instalacja dodatkow sie nie udala. Sprawdz polaczenie z internetem i kliknij ten plik jeszcze raz."
  echo gotowe > .venv/gotowe.txt
fi

echo
echo "Rolka dziala. Za chwile otworzy sie strona w przegladarce. Nie zamykaj tego okna, dopoki pracujesz."
echo
.venv/bin/python rolka.py serve
echo
read -n 1 -s -r -p "Nacisnij dowolny klawisz, zeby zamknac to okno..."
echo
