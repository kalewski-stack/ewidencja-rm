@echo off
rem Rolka: uruchomienie jednym klikiem. Przy pierwszym uruchomieniu sam instaluje dodatki (potrzebny internet).
cd /d "%~dp0"

set "PY="
python --version >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY py --version >nul 2>nul
if not defined PY if not errorlevel 1 set "PY=py"
if not defined PY goto :nopython

where ffmpeg >nul 2>nul
if not errorlevel 1 goto :ffok
where winget >nul 2>nul
if errorlevel 1 goto :ffmissing
echo.
echo Instaluje ffmpeg, program do montazu. To trwa kilka minut. Nie zamykaj tego okna.
echo.
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"
where ffmpeg >nul 2>nul
if errorlevel 1 goto :ffmissing
:ffok

if exist ".venv\gotowe.txt" goto :run
echo.
echo Pierwsze uruchomienie: instaluje dodatki. To trwa 5-15 minut i wymaga internetu.
echo Nie zamykaj tego okna.
echo.
%PY% -m venv .venv
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo gotowe> ".venv\gotowe.txt"

:run
echo.
echo Rolka dziala. Za chwile otworzy sie strona w przegladarce. Nie zamykaj tego okna, dopoki pracujesz.
echo.
".venv\Scripts\python.exe" rolka.py serve
goto :end

:nopython
echo.
echo Nie znalazlem Pythona. Zainstaluj go wedlug pliku START.md albo Instrukcja_START.pdf, krok 2,
echo a potem kliknij ten plik jeszcze raz.
goto :end

:ffmissing
echo.
echo Nie znalazlem programu ffmpeg. Zainstaluj go wedlug pliku START.md albo Instrukcja_START.pdf, krok 3,
echo a potem kliknij ten plik jeszcze raz.
goto :end

:fail
echo.
echo Instalacja dodatkow sie nie udala. Sprawdz polaczenie z internetem i kliknij ten plik jeszcze raz.
echo Jesli to sie powtarza, zrob zdjecie tego okna i wyslij je do osoby, ktora Ci pomaga.

:end
echo.
pause
