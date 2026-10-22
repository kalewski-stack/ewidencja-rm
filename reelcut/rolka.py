#!/usr/bin/env python3
"""Start bez instalacji:  python rolka.py moje_wideo.mp4   albo   python rolka.py serve"""
import pathlib
import sys

if sys.version_info < (3, 9):
    sys.exit("Ta wersja Pythona jest za stara. Zainstaluj Python 3.9 lub nowszy: https://www.python.org/downloads/")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from reelcut.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
