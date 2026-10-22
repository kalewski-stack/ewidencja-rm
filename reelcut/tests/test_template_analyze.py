import copy
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from reelcut import analyze, template  # noqa: E402
from reelcut.planner import build_plan  # noqa: E402

RAW = json.loads(template.DEFAULT_TEMPLATE.read_text(encoding="utf-8"))


class TemplateTests(unittest.TestCase):
    def test_bundled_template_matches_the_measured_reference(self):
        t = template.load_template()
        self.assertEqual(t.total_frames, 850)
        self.assertAlmostEqual(t.duration_s, 34.0)
        self.assertEqual(len(t.segments), 15)
        self.assertEqual("".join(s.role for s in t.segments), "AABBABABBABAAAA")
        self.assertEqual((t.hook, t.outro, t.elastic), (2, 3, 13))
        self.assertAlmostEqual(t.max_zoom, 1.75)
        self.assertEqual(t.captions["accent_color"], "#E2FB77")

    def test_load_by_name_and_unknown(self):
        self.assertEqual(template.load_template("rolka_DeuOaXKtPBb").name, template.load_template().name)
        with self.assertRaises(template.TemplateError):
            template.load_template("nie_ma_takiego")

    def test_validation_errors(self):
        def broken(mutate):
            raw = copy.deepcopy(RAW)
            mutate(raw)
            with self.assertRaises(template.TemplateError):
                template.parse_template(raw)

        broken(lambda r: r.update(schema=2))
        broken(lambda r: r.update(segments=r["segments"][:2]))
        broken(lambda r: r["segments"][0].update(role="C"))
        broken(lambda r: r["segments"][0].update(frames=0))
        broken(lambda r: r["segments"][0].update(zoom=0.5))
        broken(lambda r: r["structure"].update(elastic=2))  # poza sekcją outro
        broken(lambda r: r["segments"][13].update(role="B"))  # elastyczne musi być A
        broken(lambda r: r.update(fps=0))

    def test_user_templates_are_listed_and_loadable(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "moj.json").write_text(json.dumps(RAW), encoding="utf-8")
            old = template.USER_DIR
            template.USER_DIR = pathlib.Path(d)
            try:
                ids = [i for i, _ in template.list_templates()]
                self.assertIn("rolka_DeuOaXKtPBb", ids)
                self.assertIn("user/moj", ids)
                self.assertEqual(template.load_template("user/moj").total_frames, 850)
            finally:
                template.USER_DIR = old


class AnalyzeTests(unittest.TestCase):
    LENGTHS = [30, 20, 50, 25, 40, 35]  # klatki przy 25 kl./s

    @classmethod
    def setUpClass(cls):
        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("brak ffmpeg")
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_an_"))
        # kolejne ujęcia różnią się jasnością (wskaźnik zmiany sceny w ffmpeg liczy się z luminancji)
        colors = ["black", "white", "gray", "white", "black", "gray"]
        parts = []
        for i, (c, n) in enumerate(zip(colors, cls.LENGTHS)):
            f = cls.tmp / f"p{i}.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={c}:s=270x480:r=25",
                            "-frames:v", str(n), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(f)],
                           check=True)
            parts.append(f)
        (cls.tmp / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in parts))
        cls.ref = cls.tmp / "ref.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-i", "list.txt", "-c", "copy", str(cls.ref)],
                       check=True, cwd=cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_detects_exact_segment_lengths_and_writes_loadable_template(self):
        out = self.tmp / "t.json"
        analyze.analyze_reference(self.ref, out, log=lambda m: None)
        t = template.load_template(out)
        self.assertEqual([s.frames for s in t.segments], self.LENGTHS)
        plan = build_plan(t, 200, snap=False)  # szablon da się od razu użyć
        self.assertEqual(sum(s.frames for s in plan.slots), 200)

    def test_roles_option_is_validated(self):
        with self.assertRaises(Exception):
            analyze.analyze_reference(self.ref, self.tmp / "x.json", roles="AAB", log=lambda m: None)
        out = analyze.analyze_reference(self.ref, self.tmp / "y.json", roles="AABABA", log=lambda m: None)
        t = template.load_template(out)
        self.assertEqual("".join(s.role for s in t.segments), "AABABA")

    def test_too_few_cuts_gives_helpful_error(self):
        flat = self.tmp / "flat.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=270x480:r=25:d=4", "-pix_fmt",
                        "yuv420p", str(flat)], check=True)
        with self.assertRaises(Exception) as cm:
            analyze.analyze_reference(flat, self.tmp / "z.json", log=lambda m: None)
        self.assertIn("--threshold", str(cm.exception))

    def test_pick_cuts_merges_close_peaks_keeping_the_stronger(self):
        scores = [0.0] * 60
        scores[20], scores[22], scores[40] = 0.5, 0.9, 0.7
        self.assertEqual(analyze.pick_cuts(scores, 0.2, 10), [22, 40])

    def test_dump_template_keeps_segments_on_single_lines(self):
        text = analyze.dump_template(RAW)
        seg_lines = [ln for ln in text.splitlines() if ln.strip().startswith('{"frames"')]
        self.assertEqual(len(seg_lines), 15)
        self.assertEqual(json.loads(text), RAW)


if __name__ == "__main__":
    unittest.main()
