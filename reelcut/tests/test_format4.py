"""Format 4 (kinetyczna typografia): frazy z dużym słowem, karty, wiersz pisany słowami, odręczna elipsa, szablony pionowy i poziomy, montaż."""
import importlib.util
import json
import math
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import captions, graphics, media, render, style  # noqa: E402
from reelcut.graphics import core, glue, kinetic, lockup, plan as gplan, script  # noqa: E402
from reelcut.graphics.core import PlanError  # noqa: E402
from reelcut.pipeline import Options, run  # noqa: E402
from reelcut.planner import build_plan as plan_cuts, describe_plan  # noqa: E402
from reelcut.template import list_templates, load_template, parse_template, resolve_alias  # noqa: E402

HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
FPS = 25
SIZE_V, SIZE_H = (1080, 1920), (1920, 1080)
INK, PAPER, YELLOW, WHITE = (27, 20, 64), (247, 244, 236), (255, 211, 70), (255, 255, 255)


def ctx(words=(), duration=30.0, size=SIZE_V):
    return graphics.Context(graphics.load_brand(), core.Layout(*size), FPS, None, None, list(words), duration)


def said(text, step=0.4, dur=0.3, start=0.0):
    return [captions.Word(w, round(start + i * step, 3), round(start + i * step + dur, 3)) for i, w in enumerate(text.split())]


def ws(*words, step=0.2):
    return [{"w": w, "t": round(i * step, 3)} for i, w in enumerate(words)]


def one(spec, size=SIZE_V):
    return graphics.build_plan({"schema": 1, "elements": [spec]}, ctx(size=size))


def frame(plan, t, size=SIZE_V):
    return graphics.render_frame(plan, t, size)


def bbox(layer, floor=200):
    return layer.img.getchannel("A").point(lambda v: 255 if v >= floor else 0).getbbox()


def near(layer, rgb, tol=12):
    return sum(n for n, (r, g, b, a) in layer.img.getcolors(maxcolors=1 << 22)
               if a >= 200 and abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol)


def bands(layer, floor=200):
    """Pasma poziome z wyraźnym tuszem: (góra, dół, lewa, prawa)."""
    a = layer.img.getchannel("A").point(lambda v: 255 if v >= floor else 0)
    W, H = a.size
    rows = [bool(a.crop((0, y, W, y + 1)).getbbox()) for y in range(H)]
    out, y = [], 0
    while y < H:
        if not rows[y]:
            y += 1
            continue
        y0 = y
        while y < H and rows[y]:
            y += 1
        bb = a.crop((0, y0, W, y)).getbbox()
        out.append((y0, y, bb[0], bb[2]))
    return out


def rgb_triples(im):
    """Piksele obrazu RGB jako trójki (bez przestarzałego getdata)."""
    raw = im.convert("RGB").tobytes()
    return list(zip(raw[0::3], raw[1::3], raw[2::3]))


def phrase_cfg(**over):
    cfg = dict(load_template("format4h").graphics["phrases"])
    cfg.update(over)
    return cfg


class EllipseTests(unittest.TestCase):
    def test_the_stroke_goes_clockwise_from_the_upper_left_and_the_end_tucks_in_over_the_start(self):
        pts = kinetic.ellipse_points(500, 300, 200, 80, seed=1)
        ang = lambda p: math.atan2((p[1] - 300) / 80, (p[0] - 500) / 200)  # noqa: E731
        start, quarter = ang(pts[0]), ang(pts[len(pts) // 4])
        self.assertTrue(pts[0][0] < 500 and pts[0][1] < 300, "początek kreski jest w lewej górnej ćwiartce")
        self.assertGreater((quarter - start) % (2 * math.pi), 0)  # rośnie kąt przy osi y w dół: zgodnie z ruchem wskazówek zegara
        self.assertLess((quarter - start) % (2 * math.pi), math.pi)
        r = lambda p: math.hypot((p[0] - 500) / 200, (p[1] - 300) / 80)  # noqa: E731
        self.assertGreater(r(pts[0]), 0.95)
        self.assertLess(r(pts[-1]), 0.93, "koniec kreski zachodzi do środka")
        sweep = (ang(pts[-1]) - ang(pts[0])) % (2 * math.pi)
        self.assertLess(sweep, 0.5 * math.pi, "koniec mija początek o niewielki kąt (zakładka), a nie o pół obiegu")

    def test_it_is_deterministic_and_differs_between_seeds(self):
        self.assertEqual(kinetic.ellipse_points(0, 0, 10, 5, 3), kinetic.ellipse_points(0, 0, 10, 5, 3))
        self.assertNotEqual(kinetic.ellipse_points(0, 0, 10, 5, 3), kinetic.ellipse_points(0, 0, 10, 5, 4))

    def test_axes_follow_the_measured_proportions_of_one_line_of_text(self):
        cx, cy, a, b = kinetic.ellipse_axes((400, 500, 1000, 600))
        self.assertAlmostEqual(cx, 700)
        self.assertAlmostEqual(cy, 550)
        self.assertAlmostEqual(2 * a / 600, 1.12 + 0.56 * 100 / 600, places=2)  # szerokość: 1,12 tekstu plus zapas od wysokości
        self.assertGreater(2 * b / 100, 2.55)  # wysokość ok. 2,7 wysokości jednego wiersza
        self.assertLess(2 * b / 100, 2.85)

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_drawing_takes_its_time_and_grows_from_nothing_to_the_whole_ring(self):
        c = ctx(size=SIZE_H)
        box = (700, 480, 1220, 600)
        boxes = []
        for lt in (-0.1, 0.0, 0.1, 0.2, 0.4, 1.0):
            layer = graphics.Layer(SIZE_H) if hasattr(graphics, "Layer") else core.Layer(SIZE_H)
            kinetic.draw_ellipse(layer, box, c, lt, 0.4, INK)
            boxes.append(layer.img.getchannel("A").getbbox())
        self.assertIsNone(boxes[0])
        self.assertIsNone(boxes[1])
        areas = [(b[2] - b[0]) * (b[3] - b[1]) if b else 0 for b in boxes]
        self.assertTrue(all(x <= y for x, y in zip(areas, areas[1:])), areas)
        self.assertLess(areas[2], 0.8 * areas[-1])
        self.assertEqual(boxes[-2], boxes[-1], "po czasie rysowania kreska już się nie zmienia")
        x0, y0, x1, y1 = boxes[-1]
        self.assertLess(x0, box[0])
        self.assertGreater(x1, box[2])
        self.assertLess(y0, box[1])
        self.assertGreater(y1, box[3])

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_the_stroke_is_thin_and_in_the_requested_color(self):
        layer = core.Layer(SIZE_H)
        kinetic.draw_ellipse(layer, (700, 480, 1220, 600), ctx(size=SIZE_H), 1.0, 0.4, INK)
        self.assertGreater(near(layer, INK, tol=6), 400)
        a = layer.img.getchannel("A")
        w, h = a.size
        col = [a.getpixel((960, y)) for y in range(h)]  # przekrój przez środek: dwa przecięcia z kreską (góra i dół)
        runs = len([1 for i in range(1, h) if col[i] >= 128 > col[i - 1]])
        self.assertIn(runs, (2, 3))  # (3, gdy zakładka kreski wypada na środku)
        self.assertLessEqual(sum(1 for v in col if v >= 128), 3 * math.ceil(kinetic.ELLIPSE_W * SIZE_H[1]) + 6)


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class LockupFormat4Tests(unittest.TestCase):
    """Nowe pola `lockup` używane w Formacie 4; ustawienia domyślne (Format 3) sprawdza test_format3.py."""

    def test_edges_puts_a_small_word_at_the_left_edge_above_and_the_right_edge_below(self):
        spec = {"type": "lockup", "at": 0, "lines": [{"tier": "small", "words": ws("jak")}, {"tier": "big", "words": ws("będzie")},
                                                      {"tier": "small", "words": ws("tu")}],
                "big_font": "display", "size": 0.09, "small_ratio": 0.4, "small_align": "edges", "row_gap": 0.012, "y": 0.4}
        plan = one(spec, SIZE_H)
        top, mid, low = bands(frame(plan, plan.elements[0].dur - 0.1, SIZE_H))[:3]
        self.assertAlmostEqual(top[2], mid[2], delta=0.012 * SIZE_H[0])  # lewy brzeg małego słowa = lewy brzeg dużego
        self.assertAlmostEqual(low[3], mid[3], delta=0.012 * SIZE_H[0])  # prawy brzeg małego słowa = prawy brzeg dużego
        self.assertLess(top[3], mid[3] - 0.5 * (mid[3] - mid[2]))  # i nie jest rozciągnięte na całą szerokość

    def test_small_words_in_one_row_keep_natural_spacing_in_edges_mode(self):
        spec = {"type": "lockup", "at": 0, "lines": [{"tier": "small", "words": ws("co", "to", "jest")}, {"tier": "big", "words": ws("kłopotliwe")}],
                "big_font": "display", "size": 0.1, "small_ratio": 0.3, "small_align": "edges", "row_gap": 0.012, "y": 0.4}
        plan = one(spec, SIZE_H)
        top, mid = bands(frame(plan, plan.elements[0].dur - 0.1, SIZE_H))[:2]
        self.assertAlmostEqual(top[2], mid[2], delta=0.012 * SIZE_H[0])
        self.assertLess(top[3] - top[2], 0.8 * (mid[3] - mid[2]), "wiersz małych słów nie jest wyjustowany do szerokości dużego")

    def test_row_gap_keeps_the_ink_of_neighbouring_rows_apart_even_with_tall_letters(self):
        for gap in (0.004, 0.012):
            spec = {"type": "lockup", "at": 0, "lines": [{"tier": "small", "words": ws("co", "to")}, {"tier": "big", "words": ws("dłubał")},
                                                          {"tier": "small", "words": ws("gdy")}],
                    "big_font": "display", "size": 0.12, "small_ratio": 0.3, "small_align": "edges", "row_gap": gap, "y": 0.3}
            plan = one(spec, SIZE_H)
            found = bands(frame(plan, plan.elements[0].dur - 0.1, SIZE_H), floor=64)
            self.assertEqual(len(found), 3, (gap, found))
            for upper, lower in zip(found, found[1:]):
                self.assertAlmostEqual(lower[0] - upper[1], gap * SIZE_H[1], delta=0.006 * SIZE_H[1] + 3)

    def test_cy_centers_the_block_in_height_and_cx_in_width(self):
        spec = {"type": "lockup", "at": 0, "lines": [{"tier": "small", "words": ws("a")}, {"tier": "big", "words": ws("kropka")}],
                "big_font": "display", "size": 0.1, "small_align": "edges", "cy": 0.5, "cx": 0.35, "shadow": 0}
        plan = one(spec, SIZE_H)
        x0, y0, x1, y1 = bbox(frame(plan, plan.elements[0].dur - 0.1, SIZE_H))
        self.assertAlmostEqual((y0 + y1) / 2 / SIZE_H[1], 0.5, delta=0.02)
        self.assertAlmostEqual((x0 + x1) / 2 / SIZE_H[0], 0.35, delta=0.02)

    def test_a_line_can_have_its_own_color(self):
        spec = {"type": "lockup", "at": 0, "lines": [{"tier": "small", "words": ws("to")}, {"tier": "big", "words": ws("festyn"), "color": "accent"}],
                "big_font": "display", "color": "text", "shadow": 0}
        layer = frame(one(spec), 0.3)
        self.assertGreater(near(layer, (121, 93, 255)), 3000)
        self.assertGreater(near(layer, WHITE), 100)

    def test_circle_comes_after_the_second_word_and_goes_around_the_whole_block(self):
        spec = {"type": "lockup", "at": 0, "lines": [{"tier": "small", "words": ws("to", "jest", step=0.3)}, {"tier": "big", "words": [{"w": "festyn", "t": 0.6}]}],
                "big_font": "display", "size": 0.12, "small_align": "edges", "cy": 0.5, "circle": True, "circle_at": 1.0, "color": "panel", "small_color": "panel", "shadow": 0, "dur": 3.0}
        plan = one(spec, SIZE_H)
        e = plan.elements[0]
        before = bbox(frame(plan, 0.25, SIZE_H), floor=100)
        words_only = bbox(frame(plan, 0.7, SIZE_H), floor=100)
        full = bbox(frame(plan, 2.0, SIZE_H), floor=100)
        self.assertIsNotNone(before)
        self.assertLessEqual(before[2] - before[0], words_only[2] - words_only[0])
        self.assertLess(full[0], words_only[0] - 10)  # elipsa wystaje poza napis z każdej strony
        self.assertGreater(full[2], words_only[2] + 10)
        self.assertLess(full[1], words_only[1] - 10)
        self.assertGreater(full[3], words_only[3] + 10)
        self.assertTrue(e.circle and e.box[2] > e.box[0])

    def test_phrase_styles_pass_through_from_emphasis(self):
        words = said("Zrób wynik z eventu.", step=0.4)
        specs, skips, _ = lockup.from_emphasis(words, [[0.4, 0.7]], {"size": 0.1, "small_align": "edges", "row_gap": 0.006, "small_ratio": 0.4, "cy": 0.5,
                                                                      "big_track": -0.03, "circle": True})
        s = specs[0]
        for key, want in (("small_align", "edges"), ("row_gap", 0.006), ("small_ratio", 0.4), ("cy", 0.5), ("big_track", -0.03), ("circle", True)):
            self.assertEqual(s[key], want, key)


class PickBigsTests(unittest.TestCase):
    def picks(self, text, marks=(), pre=2, post=1, **kw):
        words = said(text, step=0.3, dur=0.25)
        spans = kinetic.pick_bigs(words, marks, {"pre": pre, "post": post, **kw})
        return words, spans, [" ".join(w.text for w in words[i0:i1 + 1]) for i0, i1 in spans]

    def test_content_words_are_big_and_the_words_between_them_are_small(self):
        _, _, big = self.picks("Tylko co konkretnie zmieni się w głowach i decyzjach ludzi których zapraszasz", pre=2, post=1)
        self.assertEqual(big, ["konkretnie", "głowach", "decyzjach", "zapraszasz"])

    def test_function_words_are_big_only_when_the_rules_of_reach_force_it(self):
        _, _, big = self.picks("To jest kolejność", pre=2, post=1)
        self.assertEqual(big, ["kolejność"])
        _, _, big = self.picks("to jest", pre=2, post=1)
        self.assertEqual(len(big), 1)  # samych słów łączących też nie zostawimy bez dużego słowa

    def test_every_word_is_within_reach_of_a_big_word_for_any_text(self):
        rnd = random.Random(11)
        vocab = ["a", "i", "w", "się", "to", "jest", "event", "firma", "zmienia", "decyzję", "budżet", "ludzi", "który", "naprawdę", "700", "AI"]
        for pre, post in ((0, 0), (1, 1), (2, 1), (3, 2)):
            for _ in range(25):
                n = rnd.randint(1, 14)
                toks = [rnd.choice(vocab) + rnd.choice(["", "", "", ",", "."]) for _ in range(n)]
                words, spans, _ = self.picks(" ".join(toks), pre=pre, post=post)
                breaks = [i for i, t in enumerate(toks) if t.endswith((",", "."))] + [n - 1]
                lo = 0
                for br in breaks:
                    inside = [(i0, i1) for i0, i1 in spans if lo <= i0 <= br]
                    for i in range(lo, br + 1):
                        self.assertTrue(any(i0 - pre <= i <= i1 + post for i0, i1 in inside), (toks, pre, post, spans, i))
                    lo = br + 1

    def test_words_marked_in_the_script_are_always_big(self):
        words = said("Chodzi o to żeby event zmieniał ludzi", step=0.3, dur=0.25)
        marks = [[words[2].start, words[2].end]]  # „to” (słowo funkcyjne) wyróżnione
        spans = kinetic.pick_bigs(words, marks, {"pre": 2, "post": 1})
        self.assertIn((2, 2), spans)

    def test_a_marked_pair_is_one_big_row_but_no_more_than_big_max(self):
        words = said("Event zmienia bardzo duże rzeczy", step=0.3, dur=0.25)
        marks = [[words[2].start, words[4].end]]  # trzy słowa wyróżnione z rzędu
        self.assertIn((2, 3), kinetic.pick_bigs(words, marks, {"pre": 2, "post": 1, "big_max": 2}))
        self.assertIn((2, 2), kinetic.pick_bigs(words, marks, {"pre": 2, "post": 1, "big_max": 1}))

    def test_sentences_commas_and_long_pauses_end_a_fragment(self):
        words = said("Najpierw cel, potem miara.", step=0.3, dur=0.25)
        spans = kinetic.pick_bigs(words, [], {"pre": 3, "post": 3})
        self.assertGreaterEqual(len(spans), 2, "przecinek rozdziela frazy: nie ma jednego dużego słowa na całe zdanie")
        late = said("Raz dwa", step=0.3, dur=0.25) + said("trzy cztery", step=0.3, dur=0.25, start=3.0)
        self.assertGreaterEqual(len(kinetic.pick_bigs(late, [], {"pre": 3, "post": 3})), 2, "pauza dłuższa niż max_gap_s też")

    def test_numbers_beat_longer_words(self):
        _, _, big = self.picks("tych spraw jest 700", pre=3, post=3)
        self.assertEqual(big, ["700"])

    def test_empty_speech_gives_nothing(self):
        self.assertEqual(kinetic.pick_bigs([], [], {}), [])
        self.assertEqual(kinetic.from_phrases([], [], phrase_cfg())[0], [])


class FromPhrasesTests(unittest.TestCase):
    TEXT = ("Dwanaście lat robię wydarzenia. Ponad siedemset firmowych eventów, ponad czterysta wystąpień na scenie. "
            "I wiem jedno: event, który niczego nie zmienia, to festyn. Niezależnie od budżetu.")

    def setUp(self):
        self.words = said(self.TEXT, step=0.32, dur=0.26, start=0.3)
        self.cfg = phrase_cfg()
        self.festyn = next(w for w in self.words if w.text == "festyn.")

    def test_without_scopes_all_speech_gets_the_footage_preset_and_every_word_is_covered(self):
        els, skips, hides, notes = kinetic.from_phrases(self.words, [], self.cfg)
        self.assertEqual({e["type"] for e in els}, {"lockup"})
        for w in self.words:
            mid = (w.start + w.end) / 2
            self.assertTrue(any(lo <= mid <= hi for lo, hi in skips), w.text)
        self.assertTrue(all(e["size"] == self.cfg["A"]["size"] for e in els))
        self.assertEqual(hides, [])

    def test_phrases_do_not_overlap_in_time_and_each_has_a_big_row(self):
        els, *_ = kinetic.from_phrases(self.words, [], self.cfg)
        els.sort(key=lambda e: e["at"])
        for a, b in zip(els, els[1:]):
            self.assertLessEqual(a["at"] + a["dur"], b["at"] + 1e-6, (a, b))
        for e in els:
            self.assertEqual([ln["tier"] for ln in e["lines"]].count("big"), 1)

    def test_phrases_do_not_cross_a_cut_and_use_the_preset_of_their_shot(self):
        cut = 3.0
        scopes = [{"at": 0.0, "end": cut, "kind": "A"}, {"at": cut, "end": 99.0, "kind": "B"}]
        els, *_ = kinetic.from_phrases(self.words, [], self.cfg, scopes)
        for e in els:
            self.assertFalse(e["at"] < cut - 1e-6 < e["at"] + e["dur"] - 1e-6, e)
            self.assertEqual(e["size"], self.cfg["B" if e["at"] >= cut - 1e-6 else "A"]["size"])

    def test_a_word_that_began_before_the_cut_does_not_start_its_phrase_early(self):
        w = self.words[3]
        cut = (w.start + w.end) / 2 - 0.02  # środek słowa po cięciu, początek przed nim
        els, *_ = kinetic.from_phrases(self.words, [], self.cfg, [{"at": 0.0, "end": cut, "kind": "A"}, {"at": cut, "end": 99.0, "kind": "B"}])
        later = [e for e in els if e["at"] >= cut - 1e-6]
        self.assertTrue(later)
        self.assertTrue(all(e["at"] >= cut - 1e-6 for e in els if e["at"] + e["dur"] > cut + 0.01 and e["size"] == self.cfg["B"]["size"]))

    def test_marked_big_words_get_the_mark_color_on_footage(self):
        els, *_ = kinetic.from_phrases(self.words, [[self.festyn.start, self.festyn.end]], self.cfg)
        colored = [(e, ln) for e in els for ln in e["lines"] if ln.get("color")]
        self.assertEqual(len(colored), 1)
        e, ln = colored[0]
        self.assertEqual(ln["color"], "highlight")
        self.assertEqual([w["w"] for w in ln["words"]], ["festyn."])
        self.assertNotIn("circle", e)

    def test_a_slide_scope_makes_a_card_writes_what_is_said_and_takes_over_from_captions(self):
        a, b = 1.0, 4.5
        scopes = [{"at": 0.0, "end": a, "kind": "A"}, {"at": a, "end": b, "kind": "slide", "style": "line", "color": "#F7F4EC"}, {"at": b, "end": 99.0, "kind": "A"}]
        els, skips, hides, _ = kinetic.from_phrases(self.words, [], self.cfg, scopes)
        slide = next(e for e in els if e["type"] == "slide")
        self.assertEqual((slide["at"], slide["dur"], slide["color"]), (a, round(b - a, 3), "#F7F4EC"))
        lines = [e for e in els if e["type"] == "typeline"]
        self.assertTrue(lines)
        self.assertTrue(all(a - 1e-6 <= e["at"] and e["at"] + e["dur"] <= b + 1e-6 for e in lines))
        self.assertIn([a, b], skips)
        self.assertIn([a, b], hides)
        self.assertTrue(all(e["type"] != "lockup" or e["at"] + e["dur"] <= a + 1e-6 or e["at"] >= b - 1e-6 for e in els))

    def test_a_yellow_title_card_writes_a_big_word_with_small_ones_in_ink(self):
        scopes = [{"at": 0.0, "end": 4.0, "kind": "slide", "style": "title", "color": "#FFD346"}]
        els, *_ = kinetic.from_phrases(self.words, [], self.cfg, scopes)
        phrases = [e for e in els if e["type"] == "lockup"]
        self.assertTrue(phrases)
        self.assertTrue(all(e["color"] == "panel" and e["small_color"] == "panel" and e["shadow"] == 0 for e in phrases))
        self.assertTrue(all(e["size"] == self.cfg["slide"]["size"] for e in phrases))
        self.assertTrue(all(e["z"] > kinetic.SLIDE_Z for e in els if e["type"] == "lockup"))

    def test_a_marked_word_on_a_card_gets_the_ellipse_instead_of_a_color(self):
        mark = [[self.festyn.start, self.festyn.end]]
        end = self.festyn.end + 1.0
        for style_, kind in (("title", "lockup"), ("line", "typeline")):
            scopes = [{"at": 0.0, "end": self.festyn.start - 1.5, "kind": "A"}, {"at": self.festyn.start - 1.5, "end": end, "kind": "slide", "style": style_}]
            els, *_ = kinetic.from_phrases(self.words, mark, self.cfg, scopes)
            circled = [e for e in els if e.get("circle")]
            self.assertEqual([e["type"] for e in circled], [kind], style_)
            marked = [w for w in (circled[0]["words"] if kind == "typeline" else [w for ln in circled[0]["lines"] for w in ln["words"]]) if w["w"] == "festyn."]
            self.assertEqual(circled[0]["circle_at"], marked[0]["t"], "elipsa zaczyna się rysować, gdy pada wyróżnione słowo")
            self.assertFalse(any(ln.get("color") for e in els if e["type"] == "lockup" for ln in e["lines"]), "na karcie wyróżnienie to elipsa, nie kolor")

    def test_a_card_without_speech_is_just_a_color(self):
        els, skips, hides, _ = kinetic.from_phrases(self.words, [], self.cfg, [{"at": 50.0, "end": 52.0, "kind": "slide", "style": "line"}])
        self.assertEqual([e["type"] for e in els], ["slide"])
        self.assertEqual(skips, [[50.0, 52.0]])

    def test_lines_on_a_card_break_after_a_sentence_a_comma_a_pause_or_six_words(self):
        words = said("Raz dwa trzy cztery pięć sześć siedem osiem dziewięć, dziesięć jedenaście. Dwanaście", step=0.3, dur=0.25)
        rows = kinetic.split_lines(words, {"break_words": 6})
        self.assertEqual([(a, b) for a, b in rows], [(0, 5), (6, 8), (9, 10), (11, 11)])
        late = said("Raz dwa", step=0.3, dur=0.25) + said("trzy", step=0.3, dur=0.25, start=3.0)
        self.assertEqual(kinetic.split_lines(late, {}), [(0, 1), (2, 2)])

    def test_every_element_is_clamped_to_its_shot(self):
        scopes = [{"at": 2.0, "end": 3.0, "kind": "B"}]
        els, *_ = kinetic.from_phrases(self.words, [], self.cfg, scopes)
        for e in els:
            self.assertGreaterEqual(e["at"], 2.0 - 1e-6)
            self.assertLessEqual(e["at"] + e["dur"], 3.0 + 1e-6)


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class TypeLineTests(unittest.TestCase):
    def line(self, words, **kw):
        return one({"type": "typeline", "at": 0.0, "dur": 3.0, "words": [{"w": w, "t": t} for w, t in words], **kw}, SIZE_H)

    def test_words_come_in_when_they_are_spoken_and_the_line_is_recentered_each_time(self):
        plan = self.line([("this", 0.2), ("is", 0.6), ("how", 1.0)])
        boxes = [bbox(frame(plan, t, SIZE_H), floor=128) for t in (0.1, 0.3, 0.7, 1.1)]
        self.assertIsNone(boxes[0])
        widths = [b[2] - b[0] for b in boxes[1:]]
        self.assertTrue(widths[0] < widths[1] < widths[2], widths)
        for b in boxes[1:]:
            self.assertAlmostEqual((b[0] + b[2]) / 2, SIZE_H[0] / 2, delta=0.01 * SIZE_H[0])
        self.assertAlmostEqual((boxes[3][1] + boxes[3][3]) / 2, SIZE_H[1] / 2, delta=0.03 * SIZE_H[1])

    def test_text_is_ink_on_brand_by_default_and_the_size_is_the_measured_one(self):
        plan = self.line([("this", 0.0), ("is", 0.0), ("how", 0.0)])
        layer = frame(plan, 1.0, SIZE_H)
        self.assertGreater(near(layer, INK, tol=8), 1500)
        b = bbox(layer, floor=128)
        self.assertAlmostEqual((b[2] - b[0]) / SIZE_H[0], 0.27, delta=0.05)  # „this is how” zajmuje ok. 27% szerokości kadru we wzorcu

    def test_a_long_line_wraps_and_words_never_jump_between_rows(self):
        text = ("Zanim zapłacisz za scenę odpowiedz na jedno pytanie dotyczące celu").split()
        plan = self.line([(w, 0.2 * i) for i, w in enumerate(text)], max_width=0.5)
        e = plan.elements[0]
        self.assertGreaterEqual(len(e.rows), 2)
        rows_at_end = [row[:] for row in e.rows]
        frame(plan, 0.2 * 4, SIZE_H)
        self.assertEqual(e.rows, rows_at_end)
        found = bands(frame(plan, 3.0, SIZE_H), floor=128)
        self.assertGreaterEqual(len(found), 2)
        for x0, x1 in [(f[2], f[3]) for f in found]:
            self.assertLessEqual(x1 - x0, 0.52 * SIZE_H[0])
        centers = [(f[2] + f[3]) / 2 for f in found]
        self.assertTrue(all(abs(c - SIZE_H[0] / 2) < 0.02 * SIZE_H[0] for c in centers))

    def test_a_word_wider_than_the_field_shrinks_the_type(self):
        plan = self.line([("Niesamowicieskomplikowane", 0.0)], max_width=0.3)
        b = bbox(frame(plan, 1.0, SIZE_H), floor=128)
        self.assertLessEqual(b[2] - b[0], 0.32 * SIZE_H[0])

    def test_the_ellipse_goes_around_the_visible_text_and_grows_with_it(self):
        plan = self.line([("festyn", 0.2), ("niezależnie", 0.7), ("od", 1.1), ("budżetu", 1.5)], circle=True)
        a = bbox(frame(plan, 1.0, SIZE_H), floor=100)
        b = bbox(frame(plan, 2.4, SIZE_H), floor=100)
        self.assertLess(b[0], a[0] - 40)
        self.assertGreater(b[2], a[2] + 40)
        text_only = bbox(frame(self.line([("festyn", 0.2), ("niezależnie", 0.7), ("od", 1.1), ("budżetu", 1.5)]), 2.4, SIZE_H), floor=100)
        self.assertLess(b[0], text_only[0] - 10)
        self.assertGreater(b[2], text_only[2] + 10)

    def test_marked_words_can_have_their_own_color(self):
        plan = self.line([("to", 0.0), ("festyn", 0.0)], marks=[1], mark_color="accent_strong")
        layer = frame(plan, 1.0, SIZE_H)
        self.assertGreater(near(layer, (99, 67, 255), tol=8), 1000)
        self.assertGreater(near(layer, INK, tol=8), 300)

    def test_wrong_specs_are_refused_with_readable_errors(self):
        for spec in ({"type": "typeline", "at": 0}, {"type": "typeline", "at": 0, "words": []}, {"type": "typeline", "at": 0, "words": [{"w": " "}]}):
            with self.assertRaises(PlanError) as cm:
                one(spec)
            self.assertIn("typeline", str(cm.exception))

    def test_listing_shows_the_card_and_the_line(self):
        plan = graphics.build_plan({"schema": 1, "elements": [{"type": "slide", "at": 0, "dur": 2}, {"type": "typeline", "at": 0.2, "dur": 1.8,
                                                              "words": ws("this", "is")}]}, ctx(size=SIZE_H))
        self.assertIn("slide", plan.describe())
        self.assertIn("typeline", plan.describe())
        self.assertEqual(plan.warnings, [])


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class SlideTests(unittest.TestCase):
    def test_a_card_covers_the_whole_frame_with_one_opaque_color(self):
        for color, rgb in (("paper", PAPER), ("yellow", YELLOW), ("#1B1440", INK), ("highlight", YELLOW)):
            layer = frame(one({"type": "slide", "at": 0, "dur": 1, "color": color}, SIZE_H), 0.5, SIZE_H)
            self.assertEqual(layer.img.getcolors(), [(SIZE_H[0] * SIZE_H[1], rgb + (255,))], color)

    def test_a_card_starts_and_ends_at_the_cut_with_no_fade(self):
        plan = one({"type": "slide", "at": 1.0, "dur": 1.0, "color": "paper"}, SIZE_H)
        self.assertIsNone(frame(plan, 0.96, SIZE_H).img.getchannel("A").getbbox())
        self.assertEqual(frame(plan, 1.0, SIZE_H).img.getchannel("A").getextrema(), (255, 255))
        self.assertEqual(frame(plan, 1.96, SIZE_H).img.getchannel("A").getextrema(), (255, 255))

    def test_the_text_of_the_card_lies_above_it_and_a_card_raises_no_layout_warnings(self):
        plan = graphics.build_plan({"schema": 1, "elements": [
            {"type": "typeline", "at": 0.0, "dur": 2.0, "words": ws("this", "is", "how")}, {"type": "slide", "at": 0.0, "dur": 2.0, "color": "paper"}]},
            ctx(size=SIZE_H))
        self.assertEqual(plan.warnings, [])
        self.assertGreater(near(frame(plan, 1.0, SIZE_H), INK, tol=8), 1000)
        self.assertEqual([e.kind for e in plan.active(1.0)], ["slide", "typeline"])

    def test_a_wrong_color_is_refused(self):
        with self.assertRaises(PlanError):
            one({"type": "slide", "at": 0, "dur": 1, "color": "#12"})


DATA = HERE.parent / "src" / "reelcut" / "data"


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.v, self.h = load_template("format4"), load_template("format4h")

    def test_one_reel_gives_a_vertical_and_a_horizontal_template_with_the_same_rhythm(self):
        self.assertEqual((self.v.canvas, self.h.canvas), ((1080, 1920), (1920, 1080)))
        self.assertEqual((self.v.horizontal, self.h.horizontal), (False, True))
        self.assertEqual([s.frames for s in self.v.segments], [s.frames for s in self.h.segments])
        for t in (self.v, self.h):
            self.assertEqual((t.mode, t.keep_colors, t.look, t.fps), ("cuts", True, {}, 25))
            self.assertEqual((t.total_frames, len(t.segments)), (1654, 42))
            self.assertAlmostEqual(t.duration_s, 66.16, places=2)
            self.assertEqual((t.hook, t.outro, t.elastic), (6, 4, 41))
            self.assertEqual(t.segments[t.elastic].role, "A")
            self.assertEqual(t.captions, {})  # napisy ASS wyłączone: rysuje je warstwa grafik

    def test_the_shot_pattern_comes_from_the_measured_reel(self):
        kinds = "".join("S" if s.slide else s.role for s in self.h.segments)
        self.assertEqual(kinds, "BBBSSSABBABBBBAASSABABSSBBBASBABASSABBASSA")
        self.assertEqual(self.h.dynamics["pattern"], kinds)
        self.assertEqual(sum(1 for s in self.h.segments if s.slide), 12)
        self.assertEqual([s.slide for s in self.h.segments if s.slide], ["white", "orange", "white", "white", "orange", "white", "orange", "orange",
                                                                          "white", "orange", "white", "orange"])

    def test_cards_come_in_two_colors_and_two_ways_of_writing(self):
        for t in (self.v, self.h):
            self.assertEqual(t.slide_colors, {"white": "#F7F4EC", "orange": "#FFD346"})
            styles = {(s.slide, s.slide_style or t.graphics["slides"]["styles"][s.slide]) for s in t.segments if s.slide}
            self.assertEqual(styles, {("white", "line"), ("orange", "line"), ("orange", "title")})
            self.assertTrue(all(s.role == "B" and s.zoom == 1.0 and s.face is None for s in t.segments if s.slide))

    def test_the_first_two_shots_are_black_and_white(self):
        for t in (self.v, self.h):
            bw = [i for i, s in enumerate(t.segments) if any(f.type == "bw" for f in s.fx)]
            self.assertEqual(bw, [0, 1])

    def test_faces_follow_the_measured_ladder_and_the_vertical_frame_leaves_room_for_captions(self):
        hs_h = [s.face.h for s in self.h.segments if s.face]
        hs_v = [s.face.h for s in self.v.segments if s.face]
        self.assertEqual(len(hs_h), 12)
        self.assertAlmostEqual(min(hs_h), 0.231)
        self.assertAlmostEqual(max(hs_h), 0.368)
        self.assertAlmostEqual(max(hs_v) / min(hs_v), max(hs_h) / min(hs_h), delta=0.02)  # ta sama drabinka zbliżeń
        for s in self.h.segments:
            if s.face:
                self.assertAlmostEqual(s.face.cx, 0.5, delta=0.07)
                self.assertAlmostEqual(s.face.cy, 0.28, delta=0.02)
        self.assertTrue(all(0.3 < s.face.cy < 0.4 for s in self.v.segments if s.face))

    def test_dynamics_numbers_match_the_segments(self):
        for t in (self.v, self.h):
            d, lens = t.dynamics, [s.frames / 25 for s in t.segments]
            self.assertEqual(d["cuts"], 41)
            self.assertAlmostEqual(d["duration_s"], sum(lens), places=2)
            self.assertAlmostEqual(d["cuts_per_min"], round(41 / sum(lens) * 60, 1))
            self.assertEqual((d["shot_s"]["min"], d["shot_s"]["max"]), (round(min(lens), 2), round(max(lens), 2)))
            self.assertAlmostEqual(sum(d["share"].values()), 1.0, delta=0.002)
            a = sum(s.frames for s in t.segments if s.role == "A") / t.total_frames
            self.assertAlmostEqual(d["share"]["A"], a, delta=0.001)
            self.assertAlmostEqual(d["share"]["S"], sum(s.frames for s in t.segments if s.slide) / t.total_frames, delta=0.001)

    def test_aliases_find_the_same_template(self):
        for ref in ("format4", "Format 4", "FORMAT-4", "format_4", "  format 4 "):
            self.assertEqual(load_template(ref).name, self.v.name, ref)
        for ref in ("format4h", "Format 4h", "format-4-h", "Format 4 poziom", "format 4 poziomy"):
            self.assertEqual(load_template(ref).name, self.h.name, ref)
        self.assertEqual(resolve_alias("Format 4"), "format4")

    def test_both_are_listed_between_format_3_and_motion_with_readable_names(self):
        listed = dict(list_templates())
        self.assertIn("Format 4", listed["format4"])
        self.assertIn("9:16", listed["format4"])
        self.assertIn("16:9", listed["format4h"])

    def test_phrase_and_card_settings_are_in_the_template(self):
        for t in (self.v, self.h):
            ph = t.graphics["phrases"]
            self.assertEqual((ph["A"]["pre"], ph["A"]["post"], ph["B"]["pre"], ph["B"]["post"]), (2, 1, 3, 2))
            self.assertEqual((ph["big_font"], ph["small_align"], ph["mark_color"]), ("display", "edges", "highlight"))
            self.assertIsNone(ph["slide"]["mark_color"])
            self.assertTrue(ph["slide"]["mark_circle"])
        ph = self.h.graphics["phrases"]
        self.assertAlmostEqual(ph["A"]["size"], 0.087)
        self.assertAlmostEqual(ph["A"]["y"], 0.57)
        self.assertAlmostEqual(ph["B"]["size"], 0.17)
        self.assertAlmostEqual(ph["slide"]["size"], 0.19)
        self.assertAlmostEqual(ph["line"]["size"], 0.087)

    def test_a_card_must_be_an_insert_and_its_style_a_known_one(self):
        raw = json.loads((DATA / "format4h.json").read_text(encoding="utf-8"))
        raw["segments"][6]["slide"] = "white"  # to ujęcie z twarzą (A)
        with self.assertRaises(Exception) as cm:
            parse_template(raw)
        self.assertIn("karta", str(cm.exception))
        raw = json.loads((DATA / "format4h.json").read_text(encoding="utf-8"))
        raw["segments"][3]["slide_style"] = "ozdobna"
        with self.assertRaises(Exception) as cm:
            parse_template(raw)
        self.assertIn("slide_style", str(cm.exception))

    def test_older_templates_have_no_cards_and_keep_their_behavior(self):
        for ref in ("rolka_DeuOaXKtPBb", "format2", "format3", "motion"):
            t = load_template(ref)
            self.assertFalse(any(s.slide for s in t.segments), ref)
            self.assertNotIn("phrases", t.graphics, ref)
            self.assertEqual(t.slide_colors, {}, ref)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.tpl = load_template("format4h")

    def test_a_film_as_long_as_the_reel_gets_exactly_the_reel_rhythm(self):
        plan = plan_cuts(self.tpl, self.tpl.total_frames, 25, has_broll=True)
        self.assertEqual(plan.mode, "identyczny")
        self.assertEqual([s.frames for s in plan.slots], [s.frames for s in self.tpl.segments])
        self.assertEqual([bool(s.slide) for s in self.tpl.segments], [s.source == "S" for s in plan.slots])

    def test_cards_have_a_solid_color_and_never_take_a_broll_clip(self):
        plan = plan_cuts(self.tpl, self.tpl.total_frames, 25, has_broll=True)
        cards = [s for s in plan.slots if s.source == "S"]
        self.assertEqual(len(cards), 12)
        self.assertEqual({(c.slide, c.slide_rgb) for c in cards}, {("white", "#F7F4EC"), ("orange", "#FFD346")})
        self.assertTrue(all(c.role == "B" and c.zoom == 1.0 for c in cards))
        clips = [media.MediaInfo(f"b{i}.mp4", 20.0, 1080, 1920, 25.0, True, False) for i in range(5)]
        picks = render.assign_broll(plan.slots, clips, 25)
        self.assertEqual(sorted(picks), [s.index for s in plan.slots if s.source == "B"])
        self.assertEqual(len(picks), 18)

    def test_without_broll_inserts_become_details_of_the_footage_but_cards_stay_cards(self):
        plan = plan_cuts(self.tpl, self.tpl.total_frames, 25, has_broll=False)
        self.assertEqual({s.source for s in plan.slots}, {"A", "S"})
        details = [s for s in plan.slots if s.role == "B" and s.source == "A"]
        self.assertEqual(len(details), 18)
        self.assertTrue(all(s.zoom > 1.2 for s in details), [s.zoom for s in details])  # (dwa takie same detale pod rząd różnią się zoomem o 10%)

    def test_a_shorter_film_keeps_the_hook_and_the_ending_and_cuts_the_body(self):
        plan = plan_cuts(self.tpl, 25 * 30, 25, has_broll=True)
        self.assertEqual(sum(s.frames for s in plan.slots), 750)
        self.assertEqual([s.tpl_index for s in plan.slots[:6]], [0, 1, 2, 3, 4, 5])
        self.assertEqual(plan.slots[-1].tpl_index, 41)
        self.assertTrue(plan.slots[-1].elastic)

    def test_a_long_film_repeats_the_body_and_never_stacks_two_insert_blocks(self):
        plan = plan_cuts(self.tpl, 25 * 150, 25, has_broll=True)
        self.assertEqual(sum(s.frames for s in plan.slots), 25 * 150)
        kinds = "".join("S" if s.source == "S" else s.role for s in plan.slots)
        self.assertNotIn("BBBBBBB", kinds)
        self.assertGreater(kinds.count("S"), 12)

    def test_a_very_short_clip_starts_with_a_talking_head_even_though_the_hook_is_an_insert(self):
        plan = plan_cuts(self.tpl, 10, 25, has_broll=True)
        self.assertEqual(len(plan.slots), 1)
        self.assertEqual((plan.slots[0].role, plan.slots[0].source), ("A", "A"))

    def test_the_plan_table_names_cards_and_the_black_and_white_hook(self):
        text = describe_plan(plan_cuts(self.tpl, self.tpl.total_frames, 25, has_broll=True))
        self.assertIn("karta", text)
        self.assertIn("kolor karty: white", text)
        self.assertIn("kolor karty: orange", text)
        self.assertIn("bw", text)

    def test_cards_are_left_alone_by_the_face_framing(self):
        from reelcut import faces, framing

        est = faces.FaceEstimate(h=0.18, cx=0.5, cy=0.3, eye_y=0.28, n=5, w=0.14)
        plan = plan_cuts(self.tpl, self.tpl.total_frames, 25, has_broll=False)

        class Track:
            def global_estimate(self):
                return est

            def estimate(self, a, b):
                return est

        framing.apply_framing(plan.slots, self.tpl, Track(), 25, 1.6)
        for c in (s for s in plan.slots if s.source == "S"):
            self.assertEqual((c.zoom, c.face_h), (1.0, None))


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class TemplatePlanTests(unittest.TestCase):
    TEXT = ("Dwanaście lat robię wydarzenia. Ponad siedemset firmowych eventów, ponad czterysta wystąpień na scenie. "
            "I wiem jedno: event, który niczego nie zmienia, to festyn. Niezależnie od budżetu.")

    def setUp(self):
        self.tpl = load_template("format4h")
        self.words = said(self.TEXT, step=0.32, dur=0.26, start=0.3)
        self.plan = plan_cuts(self.tpl, 25 * 14, 25, has_broll=True, snap=False)
        self.spans = glue.slot_spans(self.tpl, self.plan)

    def test_spans_describe_every_shot_of_the_film(self):
        self.assertEqual(len(self.spans), len(self.plan.slots))
        self.assertAlmostEqual(self.spans[0]["at"], 0.0)
        self.assertAlmostEqual(self.spans[-1]["end"], 14.0)
        for a, b in zip(self.spans, self.spans[1:]):
            self.assertAlmostEqual(a["end"], b["at"])
        kinds = [sp["kind"] for sp in self.spans]
        self.assertEqual(kinds, ["slide" if s.source == "S" else ("B" if s.role == "B" else "A") for s in self.plan.slots])
        card = next(sp for sp in self.spans if sp["kind"] == "slide")
        self.assertEqual((card["style"], card["color"]), ("line", "#F7F4EC"))

    def test_speech_becomes_phrases_cards_and_captions_that_step_aside(self):
        raw = gplan.with_template({"elements": []}, self.tpl, self.words, 14.0, layer_captions=True, spans=self.spans)
        kinds = [e["type"] for e in raw["elements"]]
        self.assertEqual({"lockup", "slide", "typeline", "captions"}, set(kinds))
        self.assertEqual(kinds.count("slide"), sum(1 for sp in self.spans if sp["kind"] == "slide"))
        cap = next(e for e in raw["elements"] if e["type"] == "captions")
        self.assertTrue(cap["skip"] and cap["hide"])
        for sp in self.spans:
            if sp["kind"] == "slide":
                self.assertIn([round(sp["at"], 3), round(sp["end"], 3)], cap["hide"])
        plan = graphics.build_plan(raw, ctx(self.words, duration=14.0, size=SIZE_H))
        self.assertEqual(plan.warnings, [])
        text = " ".join(g.text for g in next(e for e in plan.elements if e.kind == "captions").groups)
        self.assertEqual(text, "", "każde słowo mowy ma swoją frazę albo kartę, więc zwykłe napisy nie mają co pokazać")

    def test_marked_words_come_from_the_scenario_and_are_big(self):
        festyn = next(w for w in self.words if w.text == "festyn.")
        raw = {"elements": [{"type": "captions", "emphasis": [[festyn.start, festyn.end]]}]}
        raw = gplan.with_template(raw, self.tpl, self.words, 14.0, layer_captions=True, spans=self.spans)
        big = [[w["w"] for ln in e["lines"] if ln["tier"] == "big" for w in ln["words"]] for e in raw["elements"] if e["type"] == "lockup"]
        typed = [[w["w"] for w in e["words"]] for e in raw["elements"] if e["type"] == "typeline"]
        self.assertTrue(["festyn."] in big or any("festyn." in t for t in typed), (big, typed))

    def test_without_captions_nothing_is_written_and_the_cards_are_left_to_the_video(self):
        raw = gplan.with_template({"elements": []}, self.tpl, self.words, 14.0, layer_captions=False, spans=self.spans)
        self.assertEqual(raw["elements"], [])

    def test_generated_elements_are_not_doubled_when_the_plan_is_completed_twice(self):
        once = gplan.with_template({"elements": []}, self.tpl, self.words, 14.0, layer_captions=True, spans=self.spans)
        twice = gplan.with_template(once, self.tpl, self.words, 14.0, layer_captions=True, spans=self.spans)
        self.assertEqual(sorted(e["type"] for e in once["elements"]), sorted(e["type"] for e in twice["elements"]))

    def test_elements_written_in_the_plan_stay(self):
        own = {"type": "arrow", "at": 1.0, "from": [0.2, 0.2], "to": [0.4, 0.3]}
        raw = gplan.with_template({"elements": [dict(own)]}, self.tpl, self.words, 14.0, layer_captions=True, spans=self.spans)
        self.assertIn(own, raw["elements"])

    def test_the_old_formats_do_not_get_phrases_or_cards(self):
        for ref in ("format2", "format3"):
            raw = gplan.with_template({"elements": []}, load_template(ref), self.words, 14.0, layer_captions=True)
            self.assertEqual({e["type"] for e in raw["elements"]}, {"captions"}, ref)

    def test_plain_text_without_any_marker_is_a_valid_scenario_only_for_format_4(self):
        text = "Dwanaście lat robię wydarzenia. Ponad siedemset firmowych eventów."
        spoken = said(text)
        self.assertEqual(script.to_plan(text, spoken, allow_plain=True), {"schema": 1, "elements": [], "effects": []})
        with self.assertRaises(PlanError):
            script.to_plan(text, spoken)
        path = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_f4s_")) / "tekst.txt"
        try:
            path.write_text(text, encoding="utf-8")
            plan = gplan.load_plan(path, size=SIZE_H, words=spoken, template=self.tpl)
            self.assertIn("lockup", [e.kind for e in plan.elements])
            with self.assertRaises(PlanError):
                gplan.load_plan(path, size=SIZE_V, words=spoken, template=load_template("format3"))
        finally:
            shutil.rmtree(path.parent, ignore_errors=True)

    def test_the_graphics_job_has_the_cards_and_the_phrases_on_the_right_frames(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_f4g_"))
        try:
            job = glue.prepare(None, None, self.tpl, self.plan, None, tmp / "master.mkv", tmp, self.words, SIZE_H, 14.0, True, lambda m: None)
            self.assertIsNotNone(job)
            self.assertEqual(job.size, SIZE_H)
            cards = [e for e in job.plan.elements if e.kind == "slide"]
            self.assertEqual(len(cards), sum(1 for s in self.plan.slots if s.source == "S"))
            card = cards[0]
            layer = graphics.render_frame(job.plan, card.start + 0.01, SIZE_H)
            self.assertEqual(layer.img.getpixel((5, 5)), PAPER + (255,))
            slot = next(s for s in self.plan.slots if s.source == "S" and abs(s.start / 25 - card.start) < 1e-3)
            self.assertEqual(slot.slide_rgb, "#F7F4EC")
            a_slot = next(s for s in self.plan.slots if s.source == "A" and s.role == "A")
            mid = (a_slot.start + a_slot.end) / 2 / 25
            self.assertGreater(len(job.plan.active(mid)), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class RenderGraphTests(unittest.TestCase):
    def graph(self, tpl_name="format4h", frames=1654, broll=False):
        tpl = load_template(tpl_name)
        plan = plan_cuts(tpl, frames, 25, has_broll=broll)
        ms = tpl.canvas
        picks = {s.index: render.BrollPick(f"b{s.index}.mp4", 0.0) for s in plan.slots if s.source == "B"}
        idx = {s.index: 1 + k for k, s in enumerate(x for x in plan.slots if x.source == "B")}
        return plan, render.build_final_graph(plan, ms, tpl.canvas, picks, idx, look_chain=None, ass_file=None, fonts_dir=None)

    def test_cards_are_solid_color_sources_of_the_length_of_their_shots(self):
        plan, g = self.graph()
        cards = [s for s in plan.slots if s.source == "S"]
        for c in cards:
            self.assertIn(f"color=c=0x{c.slide_rgb.lstrip('#')}:s=1920x1080:r=25,format=yuv420p,setsar=1,trim=end_frame={c.frames},setpts=PTS-STARTPTS[s{c.index}]", g)
        self.assertEqual(g.count("color=c=0xF7F4EC"), 6)
        self.assertEqual(g.count("color=c=0xFFD346"), 6)

    def test_only_the_hook_shots_are_desaturated_and_the_graph_stays_wired(self):
        plan, g = self.graph()
        self.assertEqual(g.count("hue=s=0"), 2)
        for i in (0, 1):
            self.assertIn(f"[b{i}]hue=s=0,format=yuv420p[s{i}]", g)
        labels = re.findall(r"\[(s\d+)\]", g.split("concat=")[0])
        self.assertEqual(len(plan.slots), len(set(labels)))
        self.assertIn(f"concat=n={len(plan.slots)}:v=1:a=0", g)

    def test_a_blurred_entry_is_computed_on_the_desaturated_picture(self):
        tpl = load_template("format4h")
        plan = plan_cuts(tpl, 1654, 25)
        from reelcut.template import Fx

        plan.slots[0].effects = plan.slots[0].effects + (Fx("blur_in", 0.3),)
        g = render.build_final_graph(plan, tpl.canvas, tpl.canvas, {}, {}, look_chain=None, ass_file=None, fonts_dir=None)
        self.assertIn("[b0]hue=s=0,format=yuv420p[w0]", g)
        self.assertIn("[w0]split[ba0][bb0]", g)

    def test_horizontal_footage_keeps_its_size_and_vertical_footage_is_cropped_to_a_band(self):
        g = render.master_geometry(3840, 2160, (1920, 1080))
        self.assertEqual((g.crop[:2], g.size), ((3840, 2160), (2880, 1620)))
        g = render.master_geometry(1920, 1080, (1920, 1080))
        self.assertEqual((g.crop, g.size), ((1920, 1080, 0, 0), (1920, 1080)))
        g = render.master_geometry(1080, 1920, (1920, 1080))
        self.assertEqual(g.crop[:2], (1080, 608))
        self.assertEqual(render.master_geometry(1080, 1920, (1080, 1920)).size, (1080, 1920))
        self.assertEqual(render.master_geometry(3840, 2160, (1080, 1920)).size[1], 2160)


def short_template(tmp: pathlib.Path, horizontal: bool = False) -> pathlib.Path:
    """Format 4 w skrócie (7,8 s, mała kanwa): czarno-biały hak, karta biała (wiersz), karta żółta (duże słowo), ujęcie z twarzą i zakończenie."""
    raw = json.loads((DATA / ("format4h.json" if horizontal else "format4.json")).read_text(encoding="utf-8"))
    face = lambda n, h: {"frames": n, "role": "A", "zoom": 1.0, "face": {"h": h, "cx": 0.5, "cy": 0.3, "eye_y": 0.28}}  # noqa: E731
    raw["segments"] = [{"frames": 25, "role": "B", "alt": 1, "fx": [{"type": "bw", "dur": 0.0}]},
                       {"frames": 30, "role": "B", "slide": "white", "slide_style": "line"},
                       {"frames": 30, "role": "B", "slide": "orange", "slide_style": "title"}, face(50, 0.25), face(60, 0.24)]
    raw["structure"].update({"hook": 3, "outro": 1, "elastic": 4})
    raw["canvas"] = [640, 360] if horizontal else [360, 640]
    path = tmp / ("krotki_poziom.json" if horizontal else "krotki_pion.json")
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


@unittest.skipUnless(HAVE_PIL and HAVE_FFMPEG, "brak Pillow albo ffmpeg")
class PipelineTests(unittest.TestCase):
    """Cały montaż Formatu 4 w skrócie, w pionie i w poziomie: jednolite nagranie z tonem zamiast głosu i gotowa transkrypcja (bez rozpoznawania mowy)."""

    TEXT = "Zrób *wynik* z eventu. Dziś policzymy trzy *rzeczy* które zmieniają wszystko. Pierwsza jest prosta, druga trudniejsza, a trzecia kosztuje. Koniec."

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_f4e_"))
        cls.words = cls.tmp / "slowa.json"
        spoken = [w.strip() for w in cls.TEXT.replace("*", "").split()]
        cls.words.write_text(json.dumps([{"w": w, "start": round(i * 0.38, 3), "end": round(i * 0.38 + 0.28, 3)} for i, w in enumerate(spoken)]),
                             encoding="utf-8")
        cls.scenario = cls.tmp / "scenariusz.txt"
        cls.scenario.write_text(cls.TEXT, encoding="utf-8")
        cls.runs = {}
        for horizontal in (False, True):
            src = cls.tmp / ("wejscie_h.mp4" if horizontal else "wejscie_v.mp4")
            size = "640x360" if horizontal else "360x640"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0xC04020:s={size}:r=25", "-f", "lavfi", "-i",
                            "aevalsrc='0.3*sin(2*PI*180*t)*(0.6+0.4*sin(2*PI*3*t))':s=44100:d=8", "-t", "8", "-c:v", "libx264", "-preset", "ultrafast",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)], check=True)
            tpl = short_template(cls.tmp, horizontal)
            cls.runs[horizontal] = (src, tpl, run(src, cls.tmp / ("film_h.mp4" if horizontal else "film_v.mp4"), cls.options(tpl), log=lambda m: None))

    @classmethod
    def options(cls, tpl, **kw):
        base = dict(template=str(tpl), graphics=cls.scenario, words_file=cls.words, captions="on", framing="off", look=0.0, tighten=False,
                    preset="ultrafast", crf=28)
        return Options(**{**base, **kw})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def frame_at(video, t, size):
        from PIL import Image

        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        return Image.frombytes("RGB", size, raw)

    @staticmethod
    def share(im, rgb, tol=18, box=None):
        im = im.crop(box) if box else im
        total = im.size[0] * im.size[1]
        return sum(n for n, px in im.getcolors(maxcolors=1 << 22) if all(abs(a - b) <= tol for a, b in zip(px, rgb))) / total

    def each(self):
        for horizontal, (src, tpl, res) in self.runs.items():
            yield horizontal, src, tpl, res, ((640, 360) if horizontal else (360, 640))

    def test_the_film_has_the_canvas_the_length_and_the_shots_of_the_template(self):
        for horizontal, src, tpl, res, size in self.each():
            info = media.probe(res.output)
            self.assertEqual((info.width, info.height), size)
            self.assertAlmostEqual(info.duration, 8.0, delta=0.25)
            self.assertEqual([(s.source, s.slide) for s in res.plan.slots], [("A", ""), ("S", "white"), ("S", "orange"), ("A", ""), ("A", "")])
            self.assertEqual(res.warnings, [], horizontal)

    def test_the_white_card_is_paper_with_ink_text_and_the_yellow_card_is_yellow(self):
        for horizontal, src, tpl, res, size in self.each():
            white, yellow = res.plan.slots[1], res.plan.slots[2]
            im_w = self.frame_at(res.output, (white.start + white.end) / 2 / 25, size)
            im_y = self.frame_at(res.output, (yellow.start + yellow.end) / 2 / 25, size)
            self.assertGreater(self.share(im_w, PAPER), 0.85, horizontal)
            self.assertGreater(self.share(im_y, YELLOW), 0.75, horizontal)
            self.assertGreater(self.share(im_w, INK, tol=40), 0.0008, "na białej karcie jest tekst tuszem")
            self.assertGreater(self.share(im_y, INK, tol=40), 0.003, "na żółtej karcie jest tekst tuszem")

    def test_the_hook_is_black_and_white_and_the_rest_keeps_the_colors_of_the_footage(self):
        for horizontal, src, tpl, res, size in self.each():
            hook = self.frame_at(res.output, 0.35, size)
            later = self.frame_at(res.output, 6.5, size)
            sat = lambda im: sum(abs(r - b) for r, g, b in rgb_triples(im.resize((24, 24)))) / 576  # noqa: E731
            self.assertLess(sat(hook), 14, horizontal)
            self.assertGreater(sat(later), 60, horizontal)

    def test_the_big_word_of_a_phrase_is_white_below_the_face_zone_of_the_footage(self):
        for horizontal, src, tpl, res, size in self.each():
            slot = res.plan.slots[3]
            t = slot.start / 25 + 0.45  # ujęcie z twarzą: fraza na wysokości klatki piersiowej
            im = self.frame_at(res.output, t, size)
            y0 = int((0.50 if not horizontal else 0.55) * size[1])
            box = (0, y0, size[0], y0 + int(0.2 * size[1]))
            self.assertGreater(self.share(im, WHITE, tol=40, box=box), 0.004, horizontal)

    def test_without_captions_the_cards_are_still_colored_but_empty(self):
        for horizontal, src, tpl, res, size in self.each():
            out = self.tmp / f"bez_{int(horizontal)}.mp4"
            r = run(src, out, self.options(tpl, captions="off", graphics=None, words_file=None), log=lambda m: None)
            white = r.plan.slots[1]
            im = self.frame_at(out, (white.start + white.end) / 2 / 25, size)
            self.assertGreater(self.share(im, PAPER), 0.97, horizontal)
            self.assertLess(self.share(im, INK, tol=60), 0.001)
            self.assertLess(sum(1 for px in rgb_triples(self.frame_at(out, 0.35, size).resize((16, 16))) if abs(px[0] - px[2]) > 30), 3)

    def test_the_plan_text_lists_cards_phrases_and_the_whole_graphics_schedule(self):
        for horizontal, src, tpl, res, size in self.each():
            self.assertIn("karta", res.plan_text)
            self.assertIn("slide", res.plan_text)
            self.assertIn("typeline", res.plan_text)
            self.assertIn("lockup", res.plan_text)
            self.assertTrue(res.captions_used)

    def test_dry_run_plans_the_cards_without_rendering(self):
        src, tpl, _ = self.runs[True]
        res = run(src, None, self.options(tpl, dry_run=True), log=lambda m: None)
        self.assertIsNone(res.output)
        self.assertIn("kolor karty: white", res.plan_text)
        self.assertIn("slide", res.plan_text)

    def test_vertical_footage_for_a_horizontal_template_is_cropped_to_a_band_and_the_log_says_so(self):
        src_v, _, _ = self.runs[False]
        _, tpl_h, _ = self.runs[True]
        res = run(src_v, None, self.options(tpl_h, dry_run=True), log=lambda m: None)
        self.assertTrue(any("pionowe" in w and "16:9" in w for w in res.warnings), res.warnings)
        src_h, tpl_v, _ = self.runs[True][0], self.runs[False][1], None
        res = run(src_h, None, self.options(tpl_v, dry_run=True), log=lambda m: None)
        self.assertTrue(any("poziome" in w and "9:16" in w for w in res.warnings), res.warnings)
        res = run(src_h, None, self.options(self.runs[True][1], dry_run=True), log=lambda m: None)
        self.assertEqual([w for w in res.warnings if "pionowe" in w or "poziome" in w], [])


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class CommandLineTests(unittest.TestCase):
    def test_the_graphics_preview_has_the_canvas_of_the_template(self):
        from reelcut import cli
        from PIL import Image

        tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_f4c_"))
        try:
            plan = tmp / "plan.json"
            plan.write_text(json.dumps({"schema": 1, "elements": [{"type": "slide", "at": 0, "dur": 3, "color": "yellow"}]}), encoding="utf-8")
            for ref, size in (("format4h", (1920, 1080)), ("format4", (1080, 1920)), ("format3", (1080, 1920))):
                out = tmp / f"{ref}.png"
                self.assertEqual(cli.main(["grafiki", str(plan), "--template", ref, "--klatka", "1.0", "-o", str(out)]), 0)
                with Image.open(out) as im:
                    self.assertEqual(im.size, size, ref)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_style_command_prints_the_card_of_both_templates(self):
        from reelcut import cli
        import contextlib
        import io

        for ref, needle in (("format4", "1080x1920"), ("format4h", "1920x1080")):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(cli.main(["style", ref]), 0)
            self.assertIn("Karta stylu: Format 4", buf.getvalue())
            self.assertIn(needle, buf.getvalue())


class AssCanvasTests(unittest.TestCase):
    """Napisy ASS (Format 1 i szablony z `analyze`) mają piksele w kanwie 1080x1920; w innej kanwie są przeliczane, żeby nie wypadały poza kadr."""

    @staticmethod
    def positions(ass):
        return [(float(x), float(y)) for x, y in re.findall(r"\\pos\(([\d.]+),([\d.]+)\)", ass)]

    def test_a_horizontal_canvas_keeps_every_caption_inside_the_frame(self):
        words = said("Zanim zapłacisz za scenę odpowiedz na jedno pytanie dotyczące celu " * 4, step=0.5, dur=0.4)
        for canvas in ((1920, 1080), (1080, 1920), (1280, 720)):
            ass, stats = captions.build_ass(words, None, canvas, words[-1].end + 1)
            pos = self.positions(ass)
            self.assertTrue(pos and stats["groups"] > 5, canvas)
            self.assertTrue(all(0 < x < canvas[0] and 0 < y < canvas[1] for x, y in pos), canvas)

    def test_the_vertical_canvas_is_left_exactly_as_it_was(self):
        cfg = captions.merge_cfg(None)
        self.assertIs(captions.scale_cfg(cfg, (1080, 1920)), cfg)
        wide = captions.scale_cfg(cfg, (1920, 1080))
        self.assertAlmostEqual(wide["running"]["cap_top_px"], cfg["running"]["cap_top_px"] * 1080 / 1920)
        self.assertAlmostEqual(wide["styles"]["center_build"]["x"], 960)
        self.assertEqual(cfg, captions.merge_cfg(None), "przeliczenie nie zmienia oryginału")


@unittest.skipUnless(HAVE_FFMPEG, "brak ffmpeg")
class AnalyzeOrientationTests(unittest.TestCase):
    LENGTHS = [30, 20, 50, 25, 40, 35]

    def make(self, tmp, size):
        parts = []
        for i, (c, n) in enumerate(zip(["black", "white", "gray", "white", "black", "gray"], self.LENGTHS)):
            f = tmp / f"p{i}.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={c}:s={size}:r=25", "-frames:v", str(n), "-c:v", "libx264",
                            "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(f)], check=True)
            parts.append(f)
        (tmp / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in parts))
        ref = tmp / f"ref_{size}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-i", "list.txt", "-c", "copy", str(ref)], check=True, cwd=tmp)
        return ref

    def test_a_horizontal_reel_gives_a_horizontal_template_and_a_vertical_one_a_vertical_template(self):
        from reelcut import analyze

        tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_f4a_"))
        try:
            for size, canvas in (("480x270", (1920, 1080)), ("270x480", (1080, 1920))):
                ref = self.make(tmp, size)
                out = analyze.analyze_reference(ref, tmp / f"t_{size}.json", log=lambda m: None)
                self.assertEqual(load_template(out).canvas, canvas, size)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class DocsTests(unittest.TestCase):
    @staticmethod
    def read(name):
        return (HERE.parent / name).read_text(encoding="utf-8")

    @classmethod
    def fenced(cls, name, marker):
        block = cls.read(name).split(f"<!-- {marker}:start -->", 1)[1].split(f"<!-- {marker}:end -->", 1)[0]
        return block.split("```", 2)[1].split("\n", 1)[1]

    @staticmethod
    def n(value, nd=1):
        return f"{value:.{nd}f}".replace(".", ",")

    def test_format4_card_in_the_docs_is_current(self):
        text = self.read("FORMAT4.md")
        start, end = "<!-- karta-f4h:start -->", "<!-- karta-f4h:end -->"
        self.assertTrue(start in text)
        embedded = text.split(start, 1)[1].split(end, 1)[0].strip("\n")
        self.assertEqual(embedded, style.describe(load_template("format4h")).strip("\n"),
                         "karta w FORMAT4.md jest nieaktualna: python rolka.py style format4h i wklej między znaczniki")

    def test_card_describes_rhythm_phrases_cards_ellipse_and_brand_colors(self):
        for ref in ("format4", "format4h"):
            text = style.describe(load_template(ref))
            for needle in ("Wzór ujęć: `BBBSSSABBABBBBAASSABABSSBBBASBABASSABBASSA`", "karty w jednolitym kolorze (S) 24%", "`slide`", "`typeline`", "`lockup`", "Elipsa",
                           "biała `#F7F4EC`", "żółta `#FFD346`", "Hak: ujęcia 1 i 2 są czarno-białe", "#FFD346", "#795DFF", "Fraza:", "Wiersz", "Duże słowo"):
                self.assertIn(needle, text, (ref, needle))
            self.assertNotIn("Szablon nie ma opisu kolorów", text)
            for kind in style.GRAPHICS_ELEMENTS:
                self.assertIn(f"`{kind}`", text)
        self.assertIn("1920x1080", style.describe(load_template("format4h")))
        self.assertIn("1080x1920", style.describe(load_template("format4")))

    def test_older_cards_are_unchanged_by_the_card_kind(self):
        for ref in ("format3", "format2", "motion"):
            text = style.describe(load_template(ref))
            self.assertNotIn("(S)", text, ref)
            self.assertNotIn("karty w jednolitym kolorze", text, ref)

    def test_numbers_in_format4_md_match_the_template_and_the_code(self):
        doc, tpl, vert = self.read("FORMAT4.md"), load_template("format4h"), load_template("format4")
        d, lens = tpl.dynamics, [s.frames / tpl.fps for s in tpl.segments]
        ph, H = tpl.graphics["phrases"], tpl.canvas[1]
        a, b = [s for s in tpl.segments if s.role == "A"], [s for s in tpl.segments if s.role == "B" and not s.slide]
        white, orange = [s for s in tpl.segments if s.slide == "white"], [s for s in tpl.segments if s.slide == "orange"]
        mean = lambda seg: sum(x.frames for x in seg) / len(seg) / tpl.fps  # noqa: E731
        hs = [s.face.h for s in a]
        fixed = sum(s.frames for s in tpl.segments[:tpl.hook]) + sum(s.frames for i, s in enumerate(tpl.segments) if i >= len(tpl.segments) - tpl.outro and i != tpl.elastic)
        wanted = [self.n(tpl.duration_s) + " s", f"{len(tpl.segments)} ujęcia", f"{d['cuts']} cięć", self.n(d["cuts_per_min"]), self.n(d["shot_s"]["mean"], 2) + " s",
                  self.n(d["shot_s"]["median"], 2) + " s", self.n(d["shot_s"]["min"], 2), self.n(d["shot_s"]["max"], 2),
                  f"{d['share']['A'] * 100:.0f}% czasu mówiąca głowa (A, {len(a)} ujęć)", f"{d['share']['B'] * 100:.0f}% wstawki (B, {len(b)} ujęć)",
                  f"{d['share']['S'] * 100:.0f}% karty w jednolitym kolorze (S, {len(white) + len(orange)} ujęć)",
                  f"{len(white)} białych (średnio {self.n(mean(white), 2)} s)", f"{len(orange)} żółtych (średnio {self.n(mean(orange), 2)} s)",
                  self.n(d["sections_s"]["hook"]) + " s", f"{min(hs) * 100:.0f}%", f"{max(hs) * 100:.0f}%",
                  f"duże słowo {self.n(ph['A']['size'] * 100)}% wysokości kadru ({round(ph['A']['size'] * H)} px z {H}), małe {ph['A']['small_ratio'] * 100:.0f}%",
                  f"blok od {ph['A']['y'] * 100:.0f}% wysokości", f"duże słowo {ph['B']['size'] * 100:.0f}% wysokości ({round(ph['B']['size'] * H)} px z {H}), małe {ph['B']['small_ratio'] * 100:.0f}%",
                  f"blok od {ph['B']['y'] * 100:.0f}% wysokości", f"{self.n(ph['line']['size'] * 100)}% wysokości kadru; nowy wiersz po zdaniu, przecinku, pauzie albo {ph['line']['break_words']} słowach",
                  f"{ph['slide']['size'] * 100:.0f}% wysokości kadru ({round(ph['slide']['size'] * H)} px z {H})",
                  f"kreska {self.n(kinetic.ELLIPSE_W * 100, 2)}% wysokości kadru, rysowana {self.n(kinetic.ELLIPSE_DUR)} s",
                  self.n(d["speech"]["words_per_s"]) + " słowa na sekundę", f"{d['speech']['words']} słów", self.n(d["loudness"]["lufs"]).replace("-", "−") + " LUFS",
                  "+" + self.n(d["loudness"]["true_peak"]) + " dBTP", self.n(d["loudness"]["lra"]) + " LU", tpl.slide_colors["white"], tpl.slide_colors["orange"],
                  f"Co najmniej {round(fixed / tpl.fps + tpl.elastic_min_s)} sekund", f"pauza dłuższa niż {self.n(ph['max_gap_s'])} s",
                  f"fraza schodzi {self.n(ph['hold'], 2)} s po ostatnim słowie".replace("fraza schodzi", "a fraza schodzi")]
        self.assertEqual([w for w in wanted if w not in doc], [], "w FORMAT4.md brakuje liczb z szablonu albo z kodu")
        # tabela pionu
        vp, vh = vert.graphics["phrases"], vert.canvas[1]
        vs = [s.face.h for s in vert.segments if s.face]
        wanted_v = [f"wysokość {min(vs) * 100:.0f}–{max(vs) * 100:.0f}%", f"{self.n(vp['A']['size'] * 100)}% wysokości ({round(vp['A']['size'] * vh)} px), blok od {vp['A']['y'] * 100:.0f}%",
                    f"{self.n(vp['B']['size'] * 100)}% wysokości ({round(vp['B']['size'] * vh)} px), blok od {vp['B']['y'] * 100:.0f}%",
                    f"{self.n(vp['line']['size'] * 100)}% wysokości ({round(vp['line']['size'] * vh)} px)", f"{vp['slide']['size'] * 100:.0f}% wysokości ({round(vp['slide']['size'] * vh)} px)"]
        self.assertEqual([w for w in wanted_v if w not in doc], [], "w tabeli pionu w FORMAT4.md brakuje liczb")
        self.assertTrue("37 na minutę" not in doc and "1,6 s" in doc)

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_example_scenario_in_format4_md_builds_phrases_and_cards_in_both_orientations(self):
        text = self.fenced("FORMAT4.md", "scenariusz-f4")
        parsed = script.parse(text)
        self.assertEqual(sum(parsed.emph), 4)  # „zmienić”, „przeciętny”, „pierwszą rozmową” (dwa słowa)
        self.assertEqual(script.to_plan(text, said(" ".join(parsed.words)), allow_plain=True)["elements"][0]["type"], "captions")
        spoken = said(" ".join(parsed.words), step=0.3, dur=0.22)
        for ref, size in (("format4h", SIZE_H), ("format4", SIZE_V)):
            tpl = load_template(ref)
            dur = 0.3 * len(spoken) + 1
            vp = plan_cuts(tpl, int(dur * 25), 25, has_broll=True, snap=False)
            raw = script.to_plan(text, spoken)
            raw = gplan.with_template(raw, tpl, script.words_from_script(text, spoken)[0], dur, layer_captions=True, spans=glue.slot_spans(tpl, vp))
            plan = graphics.build_plan(raw, ctx(spoken, duration=dur, size=size))
            kinds = [e.kind for e in plan.elements]
            self.assertGreater(kinds.count("lockup"), 8, ref)
            self.assertGreaterEqual(kinds.count("slide"), 1, ref)
            self.assertEqual(plan.warnings, [], (ref, plan.warnings))

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_json_in_grafiki_md_builds_and_draws_cards_with_ellipses(self):
        raw = json.loads(self.fenced("GRAFIKI.md", "plan-f4"))
        plan = graphics.build_plan(raw, ctx(duration=8, size=SIZE_H))
        self.assertEqual(plan.warnings, [])
        self.assertEqual([e.kind for e in plan.elements], ["slide", "typeline", "slide", "lockup"])
        white = graphics.render_frame(plan, 3.0, SIZE_H)
        self.assertEqual(white.img.getpixel((5, 5)), PAPER + (255,))
        self.assertGreater(near(white, INK, tol=8), 800)
        yellow = graphics.render_frame(plan, 5.0, SIZE_H)
        self.assertEqual(yellow.img.getpixel((5, 5)), YELLOW + (255,))
        self.assertGreater(near(yellow, INK, tol=8), 3000)
        self.assertEqual(graphics.render_frame(plan, 0.5, SIZE_H).img.getchannel("A").getbbox(), None)

    def test_every_new_element_and_field_is_documented_in_grafiki_md(self):
        doc = self.read("GRAFIKI.md")
        for field in ("slide", "typeline", "small_align", "small_ratio", "big_track", "row_gap", "circle", "circle_at", "circle_dur", "circle_color", "marks", "mark_color", "words",
                      "graphics.phrases", "graphics.slides", "mark_circle", "break_words", "max_gap_s", "min_visible", "hold", "lead", "edges", "format4h", "Format 4"):
            self.assertTrue(field in doc, field)
        for want in (self.n(kinetic.LINE_EM, 3), self.n(kinetic.LINE_MAX_W, 1), self.n(kinetic.ELLIPSE_DUR, 1) + " s", self.n(lockup.SMALL_RATIO, 2)):
            self.assertTrue(want in doc, f"w GRAFIKI.md brakuje liczby „{want}” z kodu")
        tpl = load_template("format4h").graphics["phrases"]
        for want in (self.n(tpl["max_gap_s"], 1) + " s", self.n(tpl["hold"], 2) + " s", self.n(tpl["lead"], 2) + " s", self.n(tpl["min_visible"], 2) + " s"):
            self.assertTrue(want in doc, f"w GRAFIKI.md brakuje ustawienia „{want}” z szablonu")

    def test_the_format_name_is_the_same_everywhere(self):
        ui = (HERE.parent / "src" / "reelcut" / "data" / "ui.html").read_text(encoding="utf-8")
        self.assertTrue("Format 4" in ui)
        for name in ("README.md", "WORKFLOW.md", "GRAFIKI.md", "FORMAT4.md", "CLAUDE.md", "FORMAT3.md", "FORMAT2.md", "MOTION.md", "STYL.md", "INTRO.md"):
            self.assertTrue("Format 4" in self.read(name), f"w {name} brakuje nazwy „Format 4”")
        for name in ("README.md", "CLAUDE.md", "GRAFIKI.md", "FORMAT3.md", "FORMAT2.md", "MOTION.md", "STYL.md", "INTRO.md", "WORKFLOW.md"):
            self.assertTrue("FORMAT4.md" in self.read(name), f"{name} nie odsyła do FORMAT4.md")
        for name in ("README.md", "WORKFLOW.md", "GRAFIKI.md", "FORMAT4.md", "CLAUDE.md"):
            for ref in ("format4", "format4h"):
                self.assertTrue(ref in self.read(name), f"w {name} brakuje szablonu {ref}")
        self.assertTrue("założenie" in self.read("CLAUDE.md") and "założenie" in self.read("FORMAT4.md"), "numer 4 jest założeniem: ma to być napisane")

    def test_the_docs_keep_the_reference_material_out_of_the_repo(self):
        for name in ("FORMAT4.md", "INTRO.md", "GRAFIKI.md"):
            self.assertTrue("bez obrazu" in self.read(name) or name != "FORMAT4.md", name)
        for banned in ("Bradford", "60,000", "bradfordmarais", "followers"):
            for name in ("FORMAT4.md", "GRAFIKI.md", "CLAUDE.md", "README.md", "INTRO.md", "WORKFLOW.md"):
                self.assertNotIn(banned, self.read(name), (name, banned))
            for path in (DATA / "format4.json", DATA / "format4h.json"):
                self.assertNotIn(banned, path.read_text(encoding="utf-8"))

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_intro_scenario_in_format4_builds_in_both_orientations_with_the_six_marked_words_big(self):
        text = self.fenced("INTRO.md", "scenariusz-intro-f4")
        parsed = script.parse(text)
        spoken = said(" ".join(parsed.words), step=1 / 3.3, dur=0.22)
        dur = len(parsed.words) / 3.3 + 8
        for ref, size in (("format4h", SIZE_H), ("format4", SIZE_V)):
            tpl = load_template(ref)
            vp = plan_cuts(tpl, int(dur * 25), 25, has_broll=True, snap=False)
            raw = script.to_plan(text, spoken)
            raw = gplan.with_template(raw, tpl, script.words_from_script(text, spoken)[0], dur, layer_captions=True, spans=glue.slot_spans(tpl, vp))
            plan = graphics.build_plan(raw, ctx(spoken, duration=dur, size=size))
            self.assertEqual(plan.warnings, [], (ref, plan.warnings))
            big = {w["w"].rstrip(".,").lower() for e in raw["elements"] if e["type"] == "lockup" for ln in e["lines"] if ln["tier"] == "big" for w in ln["words"]}
            typed = {w["w"].rstrip(".,").lower() for e in raw["elements"] if e["type"] == "typeline" for w in e["words"]}
            for must in ("festyn", "siedemset", "czterysta", "pomiaru", "policzyć", "zarządem"):
                self.assertTrue(must in big or must in typed, (ref, must))

    def test_intro_scenario_in_format4_keeps_to_the_brand_canon(self):
        text = self.fenced("INTRO.md", "scenariusz-intro-f4")
        body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        spoken = re.sub(r"\{[^{}]*\}", "", body)
        self.assertEqual(re.findall(r"\d", spoken), [], "liczby w mowie piszemy słowami (kanon podaje je w decyzjach z 30.09.2026)")
        for banned in ("specjalist", "pomagam firmom", "kompleksowo", "niezapomnian", "—", "–"):
            self.assertFalse(banned in body.lower(), banned)
        n = len(script.parse(text).words)
        self.assertTrue(180 <= n <= 200, n)
        self.assertEqual(sum(script.parse(text).emph), 6)
        for must in ("dwanaście lat", "ponad *siedemset* wydarzeń", "ponad *czterysta* wystąpień na scenie", "trzech tysięcy osób", "czterdzieści osiem godzin", "pięć ruchów",
                     "dziewięć do dwunastu tygodni", "pomiar od pierwszej rozmowy", "kalewski.com", "wejście od zaplecza"):
            self.assertTrue(must in body.lower(), must)
        self.assertTrue("rada sektorow" not in body.lower() and "radzie sektorow" not in body.lower())
        doc = self.read("INTRO.md")
        for must in ("Kanon marki", "30.09.2026", "Radzie Sektorowej", "Decyzje do podjęcia", "FORMAT4.md", "FORMAT3.md", "pion", "poziom", "Pion czy poziom"):
            self.assertTrue(must in doc, must)

    def test_the_timetable_of_the_intro_matches_the_planner(self):
        text = self.fenced("INTRO.md", "scenariusz-intro-f4")
        words, t = [], 0.0
        for w in script.parse(text).words:
            words.append(captions.Word(w, round(t, 3), round(t + 0.72 / 3.3, 3)))
            t += 1 / 3.3
            if w.endswith((".", "?", "!", "”.")):
                t += 0.3
            elif w.endswith(","):
                t += 0.1
        dur = words[-1].end + 0.3
        tpl = load_template("format4h")
        plan = plan_cuts(tpl, int(dur * 25), 25, has_broll=True, breaks=captions.word_breaks(words, 25))
        doc = self.read("INTRO.md")
        self.assertTrue(f"film trwa ok. {dur:.0f} s, a plan ma {len(plan.slots)} ujęcia: {sum(1 for s in plan.slots if s.source == 'S')} kart, "
                        f"{sum(1 for s in plan.slots if s.role == 'B' and s.source != 'S')} wstawek i "
                        f"{sum(1 for s in plan.slots if s.role == 'A')} ujęć z Tobą" in doc, (dur, len(plan.slots)))
        for a, b in ((1, 6), (7, 15), (16, 23), (24, 32), (33, 40), (41, 43)):
            self.assertTrue(f"| {a}–{b}" in doc, (a, b))
            t0, t1 = plan.slots[a - 1].start / 25, plan.slots[b - 1].end / 25
            self.assertTrue(f"| {self.n(t0)}–{self.n(t1)} |" in doc, (a, b, t0, t1))
