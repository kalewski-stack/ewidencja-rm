"""Instrukcja dla laika (START.md), pliki startowe i gotowy tekst intro: odwołania istnieją, nazwy zgadzają się z interfejsem, tekst jest z INTRO.md."""
import os
import pathlib
import shutil
import subprocess
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

from reelcut.graphics import script  # noqa: E402
from reelcut.template import list_templates  # noqa: E402

GUIDE = (ROOT / "START.md").read_text(encoding="utf-8")
BANNED = ("Kalloway", "Sandcastles", "Residency", "Pavlov", "780,237", "REPRESENT", "kallaway")


class GuideTests(unittest.TestCase):
    def test_every_file_the_guide_points_to_exists(self):
        for name in ("start.bat", "start.command", "requirements.txt", "rolka.py", "INTRO.md", "PODCAST.md", "FORMAT2.md", "FORMAT3.md", "FORMAT4.md", "MOTION.md",
                     "WORKFLOW.md", "gotowe_teksty/intro_o_mnie_scenariusz.txt", "docs/podcast_rama.png"):
            self.assertTrue((ROOT / name).exists(), name)
        for name in ("start.bat", "start.command", "intro_o_mnie_scenariusz.txt", "INTRO.md", "FORMAT4.md", "PODCAST.md", "Instrukcja_START.pdf", "Benchmark_podcastu.pdf"):
            self.assertIn(name, GUIDE + (ROOT / "start.bat").read_text(encoding="ascii"), name)

    def test_the_interface_labels_in_the_guide_are_the_real_ones(self):
        ui = (ROOT / "src" / "reelcut" / "data" / "ui.html").read_text(encoding="utf-8")
        for label in ("Potnij", "Pobierz MP4", "Szablon montażu", "Ustawienia", "Twoje nagranie", "B-roll", "Grafiki", "Kolory jak we wzorcu", "Napisy", "Zawsze", "Gotowe"):
            self.assertIn(label, ui, label)
            self.assertIn(label, GUIDE, label)
        titles = [t[1] for t in list_templates()]
        for start in ("Format 1: mówiąca głowa + B-roll", "Format 2: gadająca głowa", "Format 3: gadająca głowa v3", "Format 4: kinetyczna typografia (pion 9:16)",
                      "Format 4: kinetyczna typografia (poziom 16:9)", "Motion"):
            self.assertTrue(any(t.startswith(start) for t in titles), f"w interfejsie nie ma szablonu „{start}”")
            self.assertIn(start, GUIDE, start)

    def test_the_guide_names_the_python_that_works_and_where_to_get_it(self):
        self.assertIn("https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe", GUIDE)
        self.assertIn("https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg", GUIDE)
        self.assertIn("Add python.exe to PATH", GUIDE)
        self.assertIn("winget install Gyan.FFmpeg", GUIDE)
        self.assertIn("brew install ffmpeg", GUIDE)
        self.assertIn("dużego żółtego przycisku", GUIDE)

    def test_the_guide_covers_every_part_the_user_needs(self):
        for part in ("Część 1. Instalacja", "Część 2. Test", "Część 3. Pierwszy prawdziwy film", "Część 4. Kolejne filmy", "Część 5. Podcast", "Gdy coś nie działa",
                     "Aktualizacja programu", "Słowniczek"):
            self.assertIn(part, GUIDE, part)
        for system in ("**Windows:**", "**Mac:**"):
            self.assertIn(system, GUIDE, system)
        for step in range(1, 9):
            self.assertIn(f"### Krok {step}.", GUIDE, f"brak kroku {step}")

    def test_the_guide_explains_the_update_and_the_old_ffmpeg_error(self):
        self.assertIn("rolka-aktualizacja.zip", GUIDE)
        self.assertIn("Cannot select channel layout", GUIDE)
        update = GUIDE.split("## Aktualizacja programu", 1)[1].split("## Słowniczek", 1)[0]
        for system in ("**Mac:**", "**Windows:**"):
            self.assertIn(system, update, system)
        self.assertIn("src", update)
        self.assertIn("Wersje: Rolka", update)  # tak samo nazywa się wiersz w stopce strony (ui.html)
        ui = (ROOT / "src" / "reelcut" / "data" / "ui.html").read_text(encoding="utf-8")
        self.assertIn("Wersje: Rolka", ui)

    def test_the_guide_stays_free_of_reference_material_and_long_dashes(self):
        self.assertNotIn("—", GUIDE)
        for banned in BANNED:
            self.assertNotIn(banned, GUIDE, banned)


class LauncherTests(unittest.TestCase):
    def test_start_command_is_executable_and_valid_bash(self):
        path = ROOT / "start.command"
        self.assertTrue(os.access(path, os.X_OK), "start.command musi mieć prawo wykonania")
        text = path.read_text(encoding="ascii")
        self.assertTrue(text.startswith("#!/bin/bash"))
        for must in (".venv/bin/python", "requirements.txt", "gotowe.txt", "rolka.py serve", "brew install ffmpeg", "python3 -m venv", "START.md", "Instrukcja_START.pdf"):
            self.assertIn(must, text, must)
        if shutil.which("bash"):
            res = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)

    def test_start_bat_is_plain_ascii_with_windows_line_endings(self):
        raw = (ROOT / "start.bat").read_bytes()
        raw.decode("ascii")  # bez polskich liter: cmd.exe źle czyta UTF-8
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "wszystkie końce wierszy mają być CRLF")
        text = raw.decode("ascii")
        for must in (r".venv\Scripts\python.exe", "requirements.txt", ":nopython", ":ffmissing", ":fail", ":end", "rolka.py serve", "winget install --id Gyan.FFmpeg", "START.md", "Instrukcja_START.pdf"):
            self.assertIn(must, text, must)
        # %PATH% rozwijane w bloku z nawiasami psuje się, gdy PATH ma „(x86)”: zmiana PATH ma stać poza blokami
        depth = 0
        for line in text.splitlines():
            stripped = line.strip()
            if "%PATH%" in stripped:
                self.assertEqual(depth, 0, "rozwijanie %PATH% wewnątrz bloku z nawiasami: " + stripped)
            depth += stripped.count("(") - stripped.count(")") if stripped.startswith(("if ", "for ")) or stripped.endswith("(") or stripped == ")" else 0

    def test_the_requirements_cover_what_the_guide_promises(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        for pkg in ("faster-whisper", "pillow", "numpy", "onnxruntime"):
            self.assertTrue(any(line.startswith(pkg) for line in req.splitlines()), pkg)


class ReadyTextTests(unittest.TestCase):
    def test_the_ready_intro_text_is_the_scenario_from_intro_md(self):
        md = (ROOT / "INTRO.md").read_text(encoding="utf-8")
        block = md.split("<!-- scenariusz-intro-f4:start -->", 1)[1].split("<!-- scenariusz-intro-f4:end -->", 1)[0]
        body = block.split("```", 2)[1].split("\n", 1)[1].rstrip("\n")
        text = (ROOT / "gotowe_teksty" / "intro_o_mnie_scenariusz.txt").read_text(encoding="utf-8")
        self.assertTrue(text.endswith(body + "\n"), "gotowy tekst różni się od scenariusza w INTRO.md")
        head = text[: -len(body) - 1].strip().splitlines()
        self.assertTrue(head and all(line.startswith("#") for line in head), "wiersze przed scenariuszem mają być komentarzami")
        self.assertIn("POMIŃ", head[0])

    def test_the_comments_are_not_read_as_words_and_the_text_builds(self):
        text = (ROOT / "gotowe_teksty" / "intro_o_mnie_scenariusz.txt").read_text(encoding="utf-8")
        parsed = script.parse(text)
        self.assertEqual(len(parsed.words), 190)
        self.assertFalse([w for w in parsed.words if w.startswith("#") or w in ("TEN", "WIERSZ")])

    def test_the_other_docs_point_to_the_guide(self):
        for name in ("README.md", "WORKFLOW.md", "CLAUDE.md"):
            self.assertIn("START.md", (ROOT / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
