import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from reelcut import captions as C  # noqa: E402
from reelcut.template import DATA_DIR, load_template  # noqa: E402


def words(spec: str, step: float = 0.3, start: float = 0.0, gaps: dict | None = None) -> list[C.Word]:
    """'ala ma kota.' -> kolejne słowa co `step` s; gaps = {indeks_słowa: pauza_przed_nim}."""
    out, t = [], start
    for i, text in enumerate(spec.split()):
        t += (gaps or {}).get(i, 0.0)
        out.append(C.Word(text, t, t + step * 0.9))
        t += step
    return out


class GroupingTests(unittest.TestCase):
    def test_short_words_bind_forward(self):
        g = C.group_words(words("w marcu zarabiałam dla fanu"))
        self.assertEqual([x.text for x in g], ["w marcu", "zarabiałam", "dla fanu"])

    def test_long_words_stand_alone(self):
        g = C.group_words(words("robiłam instagrama obserwujących"))
        self.assertEqual([x.text for x in g], ["robiłam", "instagrama", "obserwujących"])

    def test_punctuation_stops_binding(self):
        g = C.group_words(words("tu, jest ok"))
        self.assertEqual([x.text for x in g][0], "tu,")

    def test_max_two_words(self):
        g = C.group_words(words("i w to na"))
        self.assertTrue(all(len(x.words) <= 2 for x in g))

    def test_long_pause_stops_binding(self):
        g = C.group_words(words("w marcu", gaps={1: 0.6}))
        self.assertEqual(len(g), 2)

    def test_stack_lines_allow_three_words_chain(self):
        lines = C._line_groups(words("może warto w to iść"))
        self.assertEqual([" ".join(w.text for w in ln) for ln in lines], ["może", "warto", "w to iść"])


class WordsTests(unittest.TestCase):
    def test_clean_words_attaches_punctuation_tokens(self):
        ws = C.clean_words([C.Word("tak", 0, 0.3), C.Word("—", 0.3, 0.35), C.Word("nie", 0.4, 0.6)])
        self.assertEqual([w.text for w in ws], ["tak—", "nie"])

    def test_clean_words_fixes_overlaps(self):
        ws = C.clean_words([C.Word("a", 1.0, 1.2), C.Word("b", 0.5, 0.9)])
        self.assertGreaterEqual(ws[1].start, ws[0].start)
        self.assertGreater(ws[1].end, ws[1].start)

    def test_roundtrip_json(self):
        ws = words("ala ma kota.")
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "w.json"
            C.save_words(ws, p)
            back = C.load_words(p)
        self.assertEqual([w.text for w in back], [w.text for w in ws])
        self.assertAlmostEqual(back[1].start, ws[1].start, places=2)

    def test_word_breaks_strengths(self):
        ws = words("koniec zdania. potem przecinek, a to zwykłe", gaps={})
        br = dict(C.word_breaks(ws, 25))
        strengths = sorted(br.values(), reverse=True)
        self.assertEqual(strengths[0], 3.0)
        self.assertIn(2.0, strengths)
        self.assertIn(1.0, strengths)


class EmphasisTests(unittest.TestCase):
    cfg = C.merge_cfg(load_template().captions)

    def test_number_phrase_is_preferred(self):
        text = ("dzisiaj opowiem o czymś ważnym. w marcu zarabiałam trzy koła. potem poszło lepiej niż myślałam. "
                "rok później było dużo spokojniej i ciszej.")
        ws = words(text, step=0.45, gaps={5: 0.4})
        picks = C.pick_emphasis(ws, ws[-1].end, self.cfg)
        joined = " ".join(" ".join(w.text for w in p.words) for p in picks)
        self.assertIn("trzy", joined)

    def test_no_emphasis_for_very_short_material(self):
        ws = words("krótki test")
        self.assertEqual(C.pick_emphasis(ws, 3.0, self.cfg), [])

    def test_mega_goes_to_short_punchline_after_pause(self):
        ws = words("a to jest długa opowieść o tym jak było kiedyś i jak jest teraz dla wszystkich. nie był. "
                   "potem było już tylko lepiej dla każdego z nas wszędzie.", step=0.35, gaps={16: 0.8})
        picks = C.pick_emphasis(ws, ws[-1].end, self.cfg)
        mega = [p for p in picks if p.style == "mega"]
        self.assertEqual(len(mega), 1)
        self.assertEqual([w.text for w in mega[0].words], ["nie", "był."])

    def test_picks_do_not_overlap_in_time_or_words(self):
        ws = words(" ".join(["słowo numer %d jest ważne." % i for i in range(30)]))
        picks = C.pick_emphasis(ws, ws[-1].end, self.cfg)
        for a, b in zip(picks, picks[1:]):
            self.assertLessEqual(a.end, b.start + 1e-6)

    def test_style_order_follows_template(self):
        ws = words(" ".join(["trzy razy dziesięć i sto. " for _ in range(14)]))
        picks = C.pick_emphasis(ws, ws[-1].end, self.cfg)
        stacks = [p.style for p in picks if p.style != "mega"]
        self.assertEqual(stacks[:4], ["center_build", "right_top", "right_bottom", "center_stack"][:len(stacks[:4])])


class AssTests(unittest.TestCase):
    def build(self, ws, duration=None):
        return C.build_ass(ws, load_template().captions, (1080, 1920), duration or ws[-1].end + 0.5)

    def test_header_and_events(self):
        ass, info = self.build(words("ala ma kota a kot ma ale"))
        self.assertIn("PlayResX: 1080", ass)
        self.assertIn("PlayResY: 1920", ass)
        self.assertIn("Style: Cap,Anton,100", ass)
        self.assertGreater(ass.count("Dialogue:"), 0)
        self.assertEqual(info["words"], 7)

    def test_text_is_uppercase_and_escaped(self):
        ass, _ = self.build([C.Word("ąęł{x}", 0.0, 0.4), C.Word("dobrze", 0.5, 0.9)])
        self.assertIn("ĄĘŁX", ass)
        self.assertNotIn("{x}", ass)

    def test_accent_colour_used_for_center_build(self):
        ws = words("w marcu zarabiałam trzy koła. potem już tylko dalej szliśmy razem przez cały rok do końca.")
        ass, info = self.build(ws, 40.0)
        if "center_build" in info["styles"]:
            self.assertIn("&H77FBE2&", ass)

    @staticmethod
    def _events(ass: str):
        """(start, end, fontsize, text) dla głównej warstwy napisów."""
        import re

        def secs(t):
            h, m, rest = t.split(":")
            return int(h) * 3600 + int(m) * 60 + float(rest)

        out = []
        for line in ass.splitlines():
            if line.startswith("Dialogue: 1,"):
                parts = line.split(",", 9)
                out.append((secs(parts[1]), secs(parts[2]), float(re.search(r"\\fs([\d.]+)", parts[9]).group(1)),
                            re.sub(r"\{.*?\}", "", parts[9])))
        return out

    def test_running_captions_suppressed_under_blocking_stack(self):
        ws = words("a to jest długa opowieść o tym jak było kiedyś i jak jest teraz dla wszystkich. nie był. "
                   "moja rada dla ciebie to czekaj aż urośnie ci konto.", step=0.35, gaps={16: 0.8})
        ass, info = C.build_ass(ws, load_template().captions, (1080, 1920), ws[-1].end)
        self.assertIn("mega", info["styles"])
        ev = self._events(ass)
        mega = [e for e in ev if e[2] > 300]
        running = [e for e in ev if abs(e[2] - 116.4) < 2]
        self.assertTrue(mega and running)
        for m in mega:
            for r in running:
                self.assertFalse(r[0] < m[1] and r[1] > m[0], f"napis bieżący {r} nakłada się na mega {m}")

    def test_running_captions_continue_under_top_stack(self):
        ws = words("tu mówię dużo bez akcentu a potem trzy razy dziesięć daje sto dwadzieścia procent wzrostu "
                   "i mówię jeszcze trochę o różnych rzeczach do końca", step=0.4)
        ass, info = C.build_ass(ws, load_template().captions, (1080, 1920), ws[-1].end)
        ev = self._events(ass)
        self.assertTrue(any(abs(e[2] - 116.4) < 2 for e in ev))

    def test_times_are_nonnegative_and_ordered(self):
        ass, _ = self.build(words("zaczynamy od razu bez żadnej pauzy na wstępie i tak dalej"))
        for line in ass.splitlines():
            if line.startswith("Dialogue:"):
                parts = line.split(",", 3)
                self.assertLess(parts[1], parts[2])


@unittest.skipUnless(shutil.which("ffmpeg"), "brak ffmpeg")
class AssRenderTests(unittest.TestCase):
    """Render przez libass i pomiar: napis bieżący ma mieć ~57 px wersalika w pasie 1211-1267 (jak w rolce)."""

    def render(self, ass_text: str, t: float):
        import numpy as np
        from PIL import Image  # noqa: F401  (test wymaga Pillow; pomijamy, gdy go brak)

        with tempfile.TemporaryDirectory() as d:
            dd = pathlib.Path(d)
            (dd / "fonts").mkdir()
            shutil.copy(DATA_DIR / "Anton-Regular.ttf", dd / "fonts")
            (dd / "c.ass").write_text(ass_text, encoding="utf-8")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x1c1c20:s=1080x1920:r=25:d=6",
                            "-vf", "ass=c.ass:fontsdir=fonts", "-ss", str(t), "-frames:v", "1", "frame.png"],
                           cwd=d, check=True)
            return np.asarray(Image.open(dd / "frame.png").convert("L")).astype(int)

    def test_running_caption_geometry_matches_reference(self):
        try:
            import numpy  # noqa: F401
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("brak numpy/Pillow")
        ass, _ = C.build_ass([C.Word("zarobiłam", 1.0, 1.8)], load_template().captions, (1080, 1920), 3.0)
        a = self.render(ass, 1.5)
        ys, xs = (a >= 235).nonzero()
        height, width, cx = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1, (xs.min() + xs.max()) / 2
        self.assertAlmostEqual(height, 57, delta=3)
        self.assertAlmostEqual(ys.min(), 1211, delta=3)
        self.assertAlmostEqual(cx, 540, delta=4)
        self.assertAlmostEqual(width, 311, delta=311 * 0.06)  # w rolce "ZAROBIŁAM" miało 311 px


if __name__ == "__main__":
    unittest.main()
