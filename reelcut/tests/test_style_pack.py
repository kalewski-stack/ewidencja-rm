"""Pakiet stylu: blok kolorów, twarzy i dynamiki w analyze oraz karta stylu (komenda style)."""
import contextlib
import copy
import importlib.util
import io
import json
import pathlib
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import analyze, cli, look, style, template  # noqa: E402
from reelcut.captions import Word  # noqa: E402

HAVE_ORT = all(importlib.util.find_spec(m) for m in ("numpy", "onnxruntime"))
HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_FFMPEG = shutil.which("ffmpeg") is not None
ASSET = HERE / "assets" / "face_nasa_astronaut.jpg"
RAW = json.loads(template.DEFAULT_TEMPLATE.read_text(encoding="utf-8"))
STYL = HERE.parent / "STYL.md"


class StyleCardTests(unittest.TestCase):
    def test_card_reports_the_measured_numbers(self):
        card = style.describe(template.load_template())
        for needle in ("24,7 cięć na minutę", "`AABBABABBABAAAA`", "średnio 2,27 s", "Hak 5,2 s, rozwinięcie 19,2 s, zakończenie 9,5 s",
                       "plan ogólny", "zbliżenie", "bardzo ciemny (low-key)", "#E2FB77", "-14,7 LUFS", "## Napisy"):
            self.assertIn(needle, card)
        self.assertEqual(card.count("\n| "), 1 + 9)  # nagłówek tabeli i 9 ujęć z twarzą (separator zaczyna się od |-)

    def test_card_is_compact(self):
        self.assertLess(len(style.describe(template.load_template())), 9000)

    def test_card_works_for_a_bare_template(self):
        raw = copy.deepcopy(RAW)
        for key in ("look", "dynamics", "captions"):
            raw.pop(key)
        for seg in raw["segments"]:
            seg.pop("face", None)
        card = style.describe(template.parse_template(raw))
        self.assertIn("Szablon nie ma pomiaru twarzy", card)
        self.assertIn("Szablon nie ma opisu kolorów", card)
        self.assertIn("## Cięcia i tempo", card)

    def test_shot_class_thresholds(self):
        self.assertEqual([style.shot_class(z) for z in (1.0, 1.2, 1.5, 2.0, 2.01, 3.1)],
                         ["plan ogólny", "plan ogólny", "plan średni", "plan średni", "zbliżenie", "zbliżenie"])

    def test_cli_prints_and_writes_the_card(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(cli.main(["style"]), 0)
        self.assertEqual(buf.getvalue(), style.describe(template.load_template()))
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "sub" / "karta.md"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["style", "rolka_DeuOaXKtPBb", "-o", str(out)]), 0)
            self.assertEqual(out.read_text(encoding="utf-8"), style.describe(template.load_template()))

    def test_styl_md_embeds_the_current_card(self):
        self.assertTrue(STYL.exists(), "brak STYL.md")
        text = STYL.read_text(encoding="utf-8")
        start, end = "<!-- karta:start -->", "<!-- karta:end -->"
        self.assertIn(start, text)
        embedded = text.split(start, 1)[1].split(end, 1)[0].strip("\n")
        self.assertEqual(embedded, style.describe(template.load_template()).strip("\n"),
                         "karta w STYL.md jest nieaktualna: python rolka.py style -o /tmp/karta.md i wklej między znaczniki")


class BundledTemplateTests(unittest.TestCase):
    def test_dynamics_block_agrees_with_the_segments(self):
        t = template.load_template()
        d = t.dynamics
        lens = [s.frames / t.fps for s in t.segments]
        self.assertEqual(d["cuts"], len(lens) - 1)
        self.assertAlmostEqual(d["cuts_per_min"], (len(lens) - 1) / t.duration_s * 60, places=1)
        self.assertAlmostEqual(d["shot_s"]["mean"], statistics.fmean(lens), places=2)
        self.assertAlmostEqual(d["shot_s"]["median"], statistics.median(lens), places=2)
        self.assertAlmostEqual(d["shot_s"]["min"], min(lens), places=2)
        self.assertAlmostEqual(d["shot_s"]["max"], max(lens), places=2)
        self.assertEqual(d["pattern"], "".join(s.role for s in t.segments))
        self.assertAlmostEqual(sum(d["sections_s"].values()), t.duration_s, places=1)
        self.assertAlmostEqual(d["share"]["A"] + d["share"]["B"], 1.0, places=2)

    def test_look_block_has_palettes_skin_and_accents(self):
        look_block = template.load_template().look
        for key in ("palette_A", "palette_B"):
            self.assertEqual(len(look_block[key]), 8)
            self.assertAlmostEqual(sum(p["share"] for p in look_block[key]), 1.0, delta=0.02)
            for p in look_block[key]:
                self.assertRegex(p["hex"], r"^#[0-9A-F]{6}$")
        self.assertTrue(30 < look_block["skin"]["hue"] < 60)
        self.assertEqual(sorted(look_block["accents"]), ["A", "B"])


@unittest.skipUnless(HAVE_FFMPEG and HAVE_ORT and HAVE_PIL and ASSET.exists(), "brak ffmpeg, numpy, onnxruntime, Pillow albo obrazu testowego")
class AnalyzeStylePackTests(unittest.TestCase):
    """Rolka syntetyczna ze znanymi ujęciami: twarz w trzech rozmiarach (A) i pomarańczowe plansze bez twarzy (B)."""

    FPS = 25
    SHOTS = [("A", 0.12, 0.50, 0.45, 50), ("A", 0.20, 0.45, 0.35, 50), ("B", 0, 0, 0, 38), ("A", 0.30, 0.55, 0.30, 62),
             ("B", 0, 0, 0, 38), ("A", 0.16, 0.40, 0.40, 50)]  # rola, wysokość twarzy, x, y, klatki

    @classmethod
    def setUpClass(cls):
        import numpy as np
        from PIL import Image

        from reelcut import faces

        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_style_"))
        img = Image.open(ASSET).convert("RGB")
        f = faces.FaceDetector().detect(np.asarray(img))[0]
        W, H = 540, 960
        inputs, filt = [], []
        for i, (role, h, cx, cy, frames) in enumerate(cls.SHOTS):
            dur = frames / cls.FPS
            canvas = Image.new("RGB", (W, H), (230, 95, 25) if role == "B" else ((24, 26, 30) if i % 4 == 1 else (70, 50, 38)))
            if role == "A":
                k = h * H / (f.h * img.height)
                big = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
                canvas.paste(big, (round(cx * W - (f.x + f.w / 2) * big.width), round(cy * H - (f.y + f.h / 2) * big.height)))
            canvas.save(cls.tmp / f"s{i}.png")
            inputs += ["-loop", "1", "-framerate", str(cls.FPS), "-t", str(dur), "-i", str(cls.tmp / f"s{i}.png")]
            filt.append(f"[{i}:v]format=yuv420p[v{i}]")
        n = len(cls.SHOTS)
        total = sum(s[4] for s in cls.SHOTS) / cls.FPS
        graph = ";".join(filt) + ";" + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
        cls.ref = cls.tmp / "ref.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-f", "lavfi", "-i", f"sine=f=330:d={total}", "-filter_complex", graph,
                        "-map", "[v]", "-map", f"{n}:a", "-t", str(total), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(cls.ref)], check=True)
        cls.out = cls.tmp / "t.json"
        cls.log: list[str] = []
        analyze.analyze_reference(cls.ref, cls.out, name="syntetyczna", log=cls.log.append)
        cls.raw = json.loads(cls.out.read_text(encoding="utf-8"))
        cls.tpl = template.load_template(cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_cuts_and_roles_come_from_the_video(self):
        self.assertEqual([s.frames for s in self.tpl.segments], [x[4] for x in self.SHOTS])
        self.assertEqual("".join(s.role for s in self.tpl.segments), "".join(x[0] for x in self.SHOTS))

    def test_face_targets_match_what_was_drawn(self):
        a_shots = [x for x in self.SHOTS if x[0] == "A"]
        a_segs = [s for s in self.tpl.segments if s.role == "A"]
        for (_, h, cx, cy, _), seg in zip(a_shots, a_segs):
            self.assertIsNotNone(seg.face)
            self.assertAlmostEqual(seg.face.h, h, delta=0.025)
            self.assertAlmostEqual(seg.face.cx, cx, delta=0.03)
            self.assertAlmostEqual(seg.face.cy, cy, delta=0.03)
        self.assertTrue(all(s.face is None for s in self.tpl.segments if s.role == "B"))

    def test_zoom_ladder_is_face_size_relative_to_the_widest_shot(self):
        a_shots = [x for x in self.SHOTS if x[0] == "A"]
        want = [x[1] / 0.12 for x in a_shots]
        got = [s.zoom for s in self.tpl.segments if s.role == "A"]
        for w, g in zip(want, got):
            self.assertAlmostEqual(g, w, delta=0.35)
        self.assertAlmostEqual(self.tpl.ladder_max, 0.30 / 0.12, delta=0.35)

    def test_look_block_separates_a_and_b(self):
        lk = self.tpl.look
        self.assertGreater(lk["B"]["chroma"], lk["A"]["chroma"] + 15)  # pomarańczowe plansze są żywsze niż ujęcia z twarzą
        self.assertGreaterEqual(len(lk["palette_B"]), 1)
        self.assertEqual(lk["accents"].get("B", "")[:1], "#")
        stats = look.LookStats.from_dict(lk["A"])
        self.assertEqual(len(stats.luma), len(look.PCTS))
        self.assertIn("skin", lk)

    def test_dynamics_block_is_measured(self):
        d = self.tpl.dynamics
        total = sum(x[4] for x in self.SHOTS) / self.FPS
        self.assertEqual(d["cuts"], len(self.SHOTS) - 1)
        self.assertAlmostEqual(d["duration_s"], total, places=1)
        self.assertAlmostEqual(d["share"]["B"], 76 / (total * self.FPS), delta=0.01)
        self.assertEqual(d["pattern"], "AABABA")
        self.assertIn("loudness", d)
        self.assertLess(d["loudness"]["lufs"], 0)
        self.assertEqual(self.tpl.lufs, round(min(-11.0, max(-20.0, d["loudness"]["lufs"])), 1))

    def test_log_reports_what_was_measured(self):
        text = "\n".join(self.log)
        for needle in ("Kadry: zmierzyłem twarz w 4 ujęciach", "Kolory:", "Tempo:", "Dźwięk:"):
            self.assertIn(needle, text)

    def test_generated_template_drives_the_planner(self):
        from reelcut.planner import build_plan

        plan = build_plan(self.tpl, 300, snap=False)
        self.assertEqual(sum(s.frames for s in plan.slots), 300)


@unittest.skipUnless(HAVE_FFMPEG and importlib.util.find_spec("numpy"), "brak ffmpeg albo numpy")
class MeasureHelpersTests(unittest.TestCase):
    def test_motion_energy_tells_moving_from_still(self):
        from reelcut import media

        with tempfile.TemporaryDirectory() as d:
            src = pathlib.Path(d) / "m.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=216x384:r=25:d=1",
                            "-f", "lavfi", "-i", "color=c=gray:s=216x384:r=25:d=1", "-filter_complex",
                            "[0:v]format=yuv420p[a];[1:v]format=yuv420p[b];[a][b]concat=n=2:v=1:a=0",
                            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(src)], check=True)
            info = media.probe(src)
            energy = analyze._motion_energy(src, info, 25, [0, 25, 50])
        self.assertGreater(energy[0], 1.0)
        self.assertLess(energy[1], 0.2)

    def test_speech_block_counts_words_pauses_and_words_per_shot(self):
        words = [Word(f"s{i}", 0.2 * i, 0.2 * i + 0.15) for i in range(10)] + [Word(f"t{i}", 3.0 + 0.2 * i, 3.15 + 0.2 * i) for i in range(10)]
        from reelcut import captions

        old = captions.transcribe
        old_read = analyze.media.read_pcm
        captions.transcribe = lambda pcm, **kw: words
        analyze.media.read_pcm = lambda path: b""
        try:
            block = analyze._speech_block(pathlib.Path("x.mp4"), [0, 50, 125], 25, "small", "pl", lambda m: None)
        finally:
            captions.transcribe, analyze.media.read_pcm = old, old_read
        self.assertEqual(block["words"], 20)
        self.assertEqual(block["words_per_shot"], [10, 10])
        self.assertEqual(block["pauses_s"]["count"], 1)
        self.assertAlmostEqual(block["pauses_s"]["max"], 3.0 - 1.95, places=2)
        self.assertAlmostEqual(block["words_per_s"], 20 / (3.0 + 1.95 - 0.0), places=1)


if __name__ == "__main__":
    unittest.main()
