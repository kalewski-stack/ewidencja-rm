"""Format 3 (gadająca głowa v3): hasło z dużym słowem, napisy bez słów hasła, błysk przy wstawce, szablon, scenariusz i montaż."""
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import captions, graphics, media, style  # noqa: E402
from reelcut.graphics import core, glue, lockup, plan as gplan, script, transitions  # noqa: E402
from reelcut.graphics.core import PlanError  # noqa: E402
from reelcut.pipeline import Options, run  # noqa: E402
from reelcut.planner import build_plan as plan_cuts  # noqa: E402
from reelcut.template import list_templates, load_template, parse_template  # noqa: E402

HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
SIZE = (1080, 1920)
YELLOW, WHITE = (255, 211, 70), (255, 255, 255)
FPS = 30


def ctx(words=(), duration=30.0, size=SIZE):
    return graphics.Context(graphics.load_brand(), core.Layout(*size), FPS, None, None, list(words), duration)


def lockup_plan(lines, **kw):
    spec = {"type": "lockup", "at": 0.0, "lines": [{"tier": t, "words": ws} for t, ws in lines], **kw}
    return graphics.build_plan({"schema": 1, "elements": [spec]}, ctx())


def ws(*words, step=0.2):
    return [{"w": w, "t": round(i * step, 3)} for i, w in enumerate(words)]


def bands(layer, floor=200):
    """Pasma poziome z wyraźnym tuszem (bez cienia): (góra, dół, lewa, prawa) w pikselach."""
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


def near(layer, rgb, tol=12):
    return sum(n for n, (r, g, b, a) in layer.img.getcolors(maxcolors=1 << 22)
               if a >= 200 and abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol)


def said(text, step=0.4, dur=0.3):
    return [captions.Word(w, round(i * step, 3), round(i * step + dur, 3)) for i, w in enumerate(text.split())]


def span_of(words, first, last=None):
    """Przedział czasu słów od first do last (teksty zapisane dokładnie tak, jak w mowie)."""
    texts = [w.text for w in words]
    i = texts.index(first)
    j = texts.index(last) if last else i
    return [words[i].start, words[j].end]


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class LockupTests(unittest.TestCase):
    def test_small_lines_are_justified_to_the_width_of_the_big_word(self):
        plan = lockup_plan([("small", ws("One", "of", "the")), ("big", ws("biggest")), ("small", ws("opportunities"))])
        e = plan.elements[0]
        top, mid, low = bands(graphics.render_frame(plan, e.dur - 0.1, SIZE))[:3]
        for band in (top, low):
            self.assertAlmostEqual(band[2], mid[2], delta=0.035 * SIZE[0])
            self.assertAlmostEqual(band[3], mid[3], delta=0.035 * SIZE[0])
        self.assertAlmostEqual((mid[2] + mid[3]) / 2, SIZE[0] / 2, delta=0.02 * SIZE[0])

    def test_block_starts_at_the_measured_height_and_lines_never_touch(self):
        plan = lockup_plan([("small", ws("One", "of", "the")), ("big", ws("biggest")), ("small", ws("opportunities"))])
        found = bands(graphics.render_frame(plan, plan.elements[0].dur - 0.1, SIZE))
        self.assertEqual(len(found), 3, found)
        self.assertAlmostEqual(found[0][0] / SIZE[1], lockup.TOP, delta=0.01)
        for upper, lower in zip(found, found[1:]):
            self.assertGreaterEqual(lower[0] - upper[1], 2, "wiersze zachodzą na siebie (ogonki liter nad następnym wierszem)")

    def test_big_word_is_about_the_measured_share_of_the_width(self):
        plan = lockup_plan([("small", ws("One", "of", "the")), ("big", ws("biggest")), ("small", ws("opportunities"))])
        _, mid, _ = bands(graphics.render_frame(plan, plan.elements[0].dur - 0.1, SIZE))[:3]
        self.assertAlmostEqual((mid[3] - mid[2]) / SIZE[0], 0.57, delta=0.06)

    def test_words_pop_in_at_their_own_time_and_nothing_moves_afterwards(self):
        plan = lockup_plan([("small", ws("One", "of", step=0.5)), ("big", [{"w": "biggest", "t": 1.0}])])
        e = plan.elements[0]
        from PIL import ImageChops

        alphas = [graphics.render_frame(plan, t, SIZE).img.getchannel("A") for t in (0.25, 0.75, 1.25)]
        self.assertTrue(alphas[0].getbbox() and alphas[1].getbbox() and alphas[2].getbbox())
        for before, after in zip(alphas, alphas[1:]):
            self.assertIsNone(ImageChops.subtract(before, after).getbbox(), "to, co już było narysowane, musi zostać na swoim miejscu")
        self.assertNotEqual(alphas[0].getbbox(), alphas[1].getbbox())
        self.assertNotEqual(alphas[1].getbbox(), alphas[2].getbbox())
        self.assertEqual(len(bands(graphics.render_frame(plan, 0.25, SIZE))), 1)
        self.assertEqual(e.dur, 1.0 + lockup.HOLD + 0.3)

    def test_a_word_is_a_single_frame_pop_without_fading(self):
        plan = lockup_plan([("big", [{"w": "biggest", "t": 0.5}])], dur=2.0)
        before = graphics.render_frame(plan, 0.5 - 1 / FPS, SIZE).img.getchannel("A").getbbox()
        first = graphics.render_frame(plan, 0.5, SIZE).img.getchannel("A")
        self.assertIsNone(before)
        self.assertEqual(first.getextrema()[1], 255, "słowo ma od razu pełne krycie")

    def test_big_words_use_the_highlight_color_and_small_ones_the_text_color(self):
        plan = lockup_plan([("small", ws("One", "of")), ("big", ws("biggest"))])
        layer = graphics.render_frame(plan, plan.elements[0].dur - 0.1, SIZE)
        self.assertGreater(near(layer, YELLOW), 3000)
        self.assertGreater(near(layer, WHITE), 600)

    def test_colors_and_fonts_can_be_chosen(self):
        plan = lockup_plan([("big", ws("biggest"))], color="accent", big_font="display")
        layer = graphics.render_frame(plan, plan.elements[0].dur - 0.1, SIZE)
        self.assertGreater(near(layer, (121, 93, 255)), 3000)
        with self.assertRaises(PlanError) as cm:
            lockup_plan([("big", ws("x"))], big_font="nie-ma-takiego")
        self.assertIn("nie ma kroju", str(cm.exception))

    def test_long_words_shrink_the_big_line_but_the_block_stays_inside_the_frame(self):
        plan = lockup_plan([("big", ws("Niezwykle", "długie")), ("small", ws("a"))])
        big, _ = bands(graphics.render_frame(plan, plan.elements[0].dur - 0.1, SIZE))[:2]
        self.assertLessEqual(big[3] - big[2], (lockup.MAX_W + 0.05) * SIZE[0])
        self.assertGreater(big[2], 0.05 * SIZE[0])
        self.assertEqual(plan.warnings, [])

    def test_a_wide_small_line_widens_the_block_instead_of_overlapping_words(self):
        plan = lockup_plan([("small", ws("Dziś", "policzymy", "trzy")), ("big", ws("rzeczy")), ("small", ws("które", "zmieniają", "wszystko."))])
        e = plan.elements[0]
        found = bands(graphics.render_frame(plan, e.dur - 0.1, SIZE))
        self.assertGreater(found[2][3] - found[2][2], found[1][3] - found[1][2] + 0.1 * SIZE[0])
        xs = sorted(w.x for w in e.words if w.y > found[2][0] - 20 and w.y < found[2][1])
        for a, b, wd in zip(xs, xs[1:], [w.sprite.size[0] for w in sorted(e.words, key=lambda w: w.x) if found[2][0] - 20 < w.y < found[2][1]]):
            self.assertGreater(b - a, wd * 0.8, "słowa małego wiersza nie mogą na siebie nachodzić")

    def test_a_cramped_small_line_shrinks_until_its_words_are_apart(self):
        plan = lockup_plan([("small", ws("Jeśli", "odpowiadasz", "przed")), ("big", ws("zarządem")), ("small", ws("za", "wynik", "wydarzenia,"))])
        self.assertEqual(plan.warnings, [])
        layer = graphics.render_frame(plan, plan.elements[0].dur - 0.1, SIZE)
        top = bands(layer)[0]
        row = layer.img.getchannel("A").point(lambda v: 255 if v >= 200 else 0).crop((0, top[0], SIZE[0], top[1]))
        cols = [bool(row.crop((x, 0, x + 1, row.size[1])).getbbox()) for x in range(SIZE[0])]
        gaps, run = [], 0  # przerwy między kolejnymi skupiskami tuszu (litery i słowa)
        first = cols.index(True)
        last = len(cols) - 1 - cols[::-1].index(True)
        for ink in cols[first:last + 1]:
            if ink:
                if run:
                    gaps.append(run)
                run = 0
            else:
                run += 1
        gaps.sort()
        median = gaps[len(gaps) // 2]
        self.assertGreater(gaps[-2], 1.8 * median, gaps)  # dwie największe przerwy to przerwy między słowami i są wyraźnie szersze niż między literami

    def test_a_line_that_cannot_fit_is_reported(self):
        plan = lockup_plan([("big", ws("Niezwykle", "długie")), ("small", ws("a", "tu", "bardzo", "długie", "zdanie", "pomocnicze", "w małym", "wierszu"))])
        self.assertTrue(any("nie mieści się w bloku" in w for w in plan.warnings), plan.warnings)

    def test_default_duration_covers_the_last_word_and_the_hold(self):
        plan = lockup_plan([("small", ws("a", "b", step=0.4)), ("big", [{"w": "C", "t": 1.2}])])
        self.assertAlmostEqual(plan.elements[0].dur, 1.2 + lockup.HOLD + 0.3, places=3)

    def test_wrong_specs_are_refused_with_readable_errors(self):
        for spec, hint in (({"type": "lockup", "at": 0}, "lines"),
                           ({"type": "lockup", "at": 0, "lines": [{"tier": "big", "words": []}]}, "words"),
                           ({"type": "lockup", "at": 0, "lines": [{"tier": "huge", "words": ws("a")}]}, "small albo big"),
                           ({"type": "lockup", "at": 0, "lines": [{"tier": "big", "words": [{"t": 0}]}]}, "{w, t}")):
            with self.assertRaises(PlanError) as cm:
                graphics.build_plan({"schema": 1, "elements": [spec]}, ctx())
            self.assertIn(hint, str(cm.exception))

    def test_plan_listing_shows_the_words_of_the_lockup(self):
        plan = lockup_plan([("small", ws("One", "of", "the")), ("big", ws("biggest"))])
        self.assertIn("One of the / biggest", plan.describe())

    def test_render_is_deterministic(self):
        plan = lockup_plan([("small", ws("One", "of", "the")), ("big", ws("biggest")), ("small", ws("opportunities"))])
        t = plan.elements[0].dur - 0.1
        self.assertEqual(graphics.render_frame(plan, t, SIZE).tobytes(), graphics.render_frame(plan, t, SIZE).tobytes())


class FromEmphasisTests(unittest.TestCase):
    TEXT = "Now I believe one of the biggest opportunities to build a personal brand is audience. Social media no longer exists."

    def setUp(self):
        self.words = said(self.TEXT)

    def lines(self, spec):
        return [(ln["tier"], [w["w"] for w in ln["words"]]) for ln in spec["lines"]]

    def test_the_emphasised_word_is_big_with_small_words_before_and_after_it(self):
        specs, skip, notes = lockup.from_emphasis(self.words, [span_of(self.words, "biggest")])
        self.assertEqual(len(specs), 1)
        self.assertEqual(self.lines(specs[0]), [("small", ["one", "of", "the"]), ("big", ["biggest"]), ("small", ["opportunities", "to", "build"])])
        self.assertEqual(notes, [])
        self.assertEqual(len(skip), 1)

    def test_words_pop_in_at_the_time_they_are_spoken(self):
        spec = lockup.from_emphasis(self.words, [span_of(self.words, "biggest")])[0][0]
        by_text = {w.text: w for w in self.words}
        for ln in spec["lines"]:
            for w in ln["words"]:
                self.assertAlmostEqual(spec["at"] + w["t"], by_text[w["w"]].start - lockup.LEAD_S, places=2)
        self.assertAlmostEqual(spec["at"], by_text["one"].start - lockup.LEAD_S, places=2)

    def test_lockup_never_crosses_the_end_of_a_sentence(self):
        specs, _, _ = lockup.from_emphasis(self.words, [span_of(self.words, "audience.")])
        self.assertEqual(self.lines(specs[0])[-1][1], ["audience."])
        self.assertEqual(len(specs[0]["lines"]), 2)  # po kropce nie ma już nic; przed wyróżnionym są trzy słowa
        low = lockup.from_emphasis(self.words, [span_of(self.words, "media")])[0][0]
        self.assertEqual(self.lines(low), [("small", ["Social"]), ("big", ["media"]), ("small", ["no", "longer", "exists."])])  # „audience.” zamyka zdanie

    def test_commas_and_long_pauses_end_the_lockup_too(self):
        words = said("one two, three four five six")
        specs, _, _ = lockup.from_emphasis(words, [span_of(words, "four")])
        self.assertEqual(self.lines(specs[0])[0], ("small", ["three"]))  # przecinek za „two” zamyka frazę
        slow = [captions.Word(w.text, w.start + (1.0 if i >= 3 else 0.0), w.end + (1.0 if i >= 3 else 0.0)) for i, w in enumerate(said("a b c d e f"))]
        specs, _, _ = lockup.from_emphasis(slow, [span_of(slow, "e")])
        self.assertEqual(self.lines(specs[0]), [("small", ["d"]), ("big", ["e"]), ("small", ["f"])])
        gap = lockup.from_emphasis(slow, [span_of(slow, "b")])[0][0]
        self.assertEqual(self.lines(gap), [("small", ["a"]), ("big", ["b"]), ("small", ["c"])])  # pauza 1 s przed „d” kończy hasło

    def test_two_lockups_share_the_words_between_them(self):
        rng = [span_of(self.words, "biggest"), span_of(self.words, "personal")]
        first, second = lockup.from_emphasis(self.words, rng)[0]
        mid_first, mid_second = self.lines(first)[-1][1], self.lines(second)[0][1]
        self.assertEqual(mid_first + mid_second, ["opportunities", "to", "build", "a"])
        self.assertEqual((len(mid_first), len(mid_second)), (2, 2))
        self.assertLessEqual(first["at"] + first["dur"], second["at"] + 1e-6)

    def test_a_word_belongs_to_one_lockup_only(self):
        rng = [span_of(self.words, "biggest"), span_of(self.words, "opportunities"), span_of(self.words, "personal")]
        specs, skip, _ = lockup.from_emphasis(self.words, rng)
        seen = [(ln["tier"], w["w"]) for sp in specs for ln in sp["lines"] for w in ln["words"]]
        self.assertEqual(len(seen), len({(t, w) for t, w in seen}))
        self.assertEqual(len([w for _, w in seen if w in ("opportunities", "personal", "biggest")]), 3)
        for a, b in zip(skip, skip[1:]):
            self.assertLess(a[1], b[0] + 1e-6)

    def test_a_long_emphasis_keeps_two_big_words_and_says_so(self):
        specs, _, notes = lockup.from_emphasis(self.words, [[self.words[3].start, self.words[6].end]])
        lines = self.lines(specs[0])
        big = [ln for ln in lines if ln[0] == "big"][0]
        self.assertEqual(len(big[1]), 2)
        self.assertTrue(notes and "2" in notes[0], notes)
        self.assertIn(self.words[5].text, [w for _, ws_ in lines for w in ws_])  # reszta wyróżnienia nie ginie

    def test_lockup_leaves_before_the_normal_captions_come_back(self):
        spec, skip, _ = lockup.from_emphasis(self.words, [span_of(self.words, "biggest")])
        e, s = spec[0], skip[0]
        nxt = next(w for w in self.words if w.start > s[1])
        self.assertLessEqual(e["at"] + e["dur"], nxt.start - lockup.LEAD_S + 1e-3)
        last = next(w for w in self.words if w.text == "build")
        self.assertGreaterEqual(e["at"] + e["dur"], last.start + 0.3 - 1e-3)

    def test_trailing_words_that_would_only_flash_by_are_left_to_the_captions(self):
        words = [captions.Word(t, a, b) for t, a, b in (("x", 0.0, 0.3), ("y", 0.4, 0.7), ("KEY", 0.8, 1.2), ("p", 1.3, 1.35), ("q.", 1.36, 1.38), ("z", 1.39, 1.7))]
        spec, skip, _ = lockup.from_emphasis(words, [[0.8, 1.2]])
        self.assertEqual(self.lines(spec[0]), [("small", ["x", "y"]), ("big", ["KEY"])])
        self.assertAlmostEqual(spec[0]["at"] + spec[0]["dur"], 1.3 - lockup.LEAD_S, places=2)  # schodzi, gdy wraca mowa
        self.assertAlmostEqual(skip[0][1], 1.2, places=2)

    def test_the_last_word_of_a_lockup_stays_long_enough_to_read(self):
        specs, _, _ = lockup.from_emphasis(self.words, [span_of(self.words, "biggest")])
        e = specs[0]
        last = [w for ln in e["lines"] for w in ln["words"]][-1]
        self.assertGreaterEqual(e["dur"] - last["t"], lockup.MIN_VISIBLE_S - 1e-3)

    def test_skip_range_covers_exactly_the_words_of_the_lockup(self):
        spec, skip, _ = lockup.from_emphasis(self.words, [span_of(self.words, "biggest")])
        inside = [w.text for w in self.words if skip[0][0] <= (w.start + w.end) / 2 <= skip[0][1]]
        in_lockup = [w["w"] for ln in spec[0]["lines"] for w in ln["words"]]
        self.assertEqual(inside, in_lockup)

    def test_emphasis_outside_the_speech_is_ignored(self):
        self.assertEqual(lockup.from_emphasis(self.words, [[900.0, 901.0]]), ([], [], []))
        self.assertEqual(lockup.from_emphasis([], [[0.0, 1.0]]), ([], [], []))

    def test_style_fields_from_the_template_go_to_the_element(self):
        spec = lockup.from_emphasis(self.words, [span_of(self.words, "biggest")], {"color": "accent", "size": 0.08, "pre": 1, "post": 0})[0][0]
        self.assertEqual((spec["color"], spec["size"]), ("accent", 0.08))
        self.assertEqual(self.lines(spec), [("small", ["the"]), ("big", ["biggest"])])


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class CaptionSkipTests(unittest.TestCase):
    def groups(self, **spec):
        words = said("jeden dwa trzy cztery pięć sześć siedem osiem", step=0.4)
        plan = graphics.build_plan({"schema": 1, "elements": [{"type": "captions", "max_words": 3, **spec}]}, ctx(words))
        return [g.text for g in plan.elements[0].groups]

    def test_words_in_skipped_ranges_are_not_captioned(self):
        everything = " ".join(self.groups())
        self.assertIn("cztery", everything)
        shown = " ".join(self.groups(skip=[[1.2 - 0.001, 2.3]]))  # słowa 4-6
        for gone in ("cztery", "pięć", "sześć"):
            self.assertNotIn(gone, shown)
        for kept in ("jeden", "trzy", "siedem", "osiem"):
            self.assertIn(kept, shown)

    def test_hidden_windows_blank_the_captions_even_for_a_group_that_started_before(self):
        words = said("jeden dwa trzy cztery pięć sześć siedem osiem", step=0.4)
        plan = graphics.build_plan({"schema": 1, "elements": [{"type": "captions", "max_words": 3, "hide": [[1.0, 2.0]]}]}, ctx(words))
        track = plan.elements[0]
        shown = [graphics.render_frame(plan, t, SIZE).img.getchannel("A").getbbox() is not None for t in (0.3, 0.9, 1.0, 1.5, 1.99, 2.0, 2.3)]
        self.assertEqual(shown, [True, True, False, False, False, True, True])
        self.assertTrue(track.hide)

    def test_without_skip_nothing_changes(self):
        self.assertEqual(self.groups(), self.groups(skip=[]))


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class TemplatePlanTests(unittest.TestCase):
    TEXT = FromEmphasisTests.TEXT

    def setUp(self):
        self.tpl = load_template("format3")
        self.words = said(self.TEXT)

    def emphasised(self, *firsts):
        return {"elements": [{"type": "captions", "emphasis": [span_of(self.words, w) for w in firsts]}]}

    def test_emphasised_phrases_become_lockups_and_leave_the_captions(self):
        raw = gplan.with_template(self.emphasised("biggest", "personal"), self.tpl, self.words, 20.0, layer_captions=True)
        kinds = [e["type"] for e in raw["elements"]]
        self.assertEqual(sorted(kinds), ["captions", "lockup", "lockup"])
        cap = next(e for e in raw["elements"] if e["type"] == "captions")
        self.assertEqual(len(cap["skip"]), 2)
        lockups = [e for e in raw["elements"] if e["type"] == "lockup"]
        self.assertEqual(cap["hide"], [[e["at"], round(e["at"] + e["dur"], 3)] for e in lockups])
        for key in ("size", "y", "max_words", "weight"):
            self.assertEqual(cap[key], self.tpl.graphics["captions"][key])
        plan = graphics.build_plan(raw, ctx(self.words))
        self.assertEqual(plan.warnings, [])
        text = " ".join(g.text for g in next(e for e in plan.elements if e.kind == "captions").groups)
        for gone in ("biggest", "personal", "opportunities"):
            self.assertNotIn(gone, text)
        self.assertIn("Now I believe", text)

    def test_templates_without_a_lockup_setting_leave_emphasis_alone(self):
        raw = gplan.with_template(self.emphasised("biggest"), load_template("format2"), self.words, 20.0, layer_captions=True)
        self.assertEqual([e["type"] for e in raw["elements"]], ["captions"])
        self.assertNotIn("skip", raw["elements"][0])

    def test_no_emphasis_means_no_lockups(self):
        raw = gplan.with_template({"elements": []}, self.tpl, self.words, 20.0, layer_captions=True)
        self.assertEqual([e["type"] for e in raw["elements"]], ["captions"])

    def test_a_lockup_written_in_the_plan_stays_and_generated_ones_are_not_doubled(self):
        own = {"type": "lockup", "at": 1.0, "lines": [{"tier": "big", "words": [{"w": "x", "t": 0}]}]}
        raw = {"elements": [dict(own), {"type": "captions", "emphasis": [span_of(self.words, "biggest")]}]}
        once = gplan.with_template(raw, self.tpl, self.words, 20.0, layer_captions=True)
        twice = gplan.with_template(once, self.tpl, self.words, 20.0, layer_captions=True)
        for out in (once, twice):
            lockups = [e for e in out["elements"] if e["type"] == "lockup"]
            self.assertEqual(len(lockups), 2)
            self.assertEqual(sum(1 for e in lockups if e.get("auto")), 1)
            self.assertIn(own, [{k: v for k, v in e.items()} for e in lockups])
        no_emphasis = gplan.with_template({"elements": [dict(own)]}, self.tpl, self.words, 20.0, layer_captions=True)
        self.assertIn("lockup", [e["type"] for e in no_emphasis["elements"]])

    def test_with_captions_off_the_captions_from_the_scenario_go_but_the_lockups_stay(self):
        raw = gplan.with_template(self.emphasised("biggest", "personal"), self.tpl, self.words, 20.0, layer_captions=False)
        self.assertEqual(sorted(e["type"] for e in raw["elements"]), ["lockup", "lockup"])
        plan = graphics.build_plan(raw, ctx(self.words))
        self.assertEqual([e.kind for e in plan.elements], ["lockup", "lockup"])
        self.assertEqual(plan.warnings, [])

    def test_templates_without_layer_captions_keep_a_captions_element_written_in_the_plan(self):
        own = {"type": "captions", "max_words": 2}
        raw = gplan.with_template({"elements": [dict(own)]}, load_template(), self.words, 20.0, layer_captions=False)
        self.assertEqual(raw["elements"], [own])

    def test_too_long_emphasis_is_reported_in_the_plan_warnings(self):
        raw = {"elements": [{"type": "captions", "emphasis": [[self.words[3].start, self.words[6].end]]}]}
        raw = gplan.with_template(raw, self.tpl, self.words, 20.0, layer_captions=True)
        plan = graphics.build_plan(raw, ctx(self.words))
        self.assertTrue(any(w.startswith("hasło:") for w in plan.warnings), plan.warnings)

    def test_scenario_with_only_emphasis_is_a_valid_plan(self):
        text = "Zrób *wynik* z eventu. Dziś policzymy trzy *rzeczy* które zmieniają wszystko."
        spoken = said(" ".join(script.parse(text).words))
        raw = script.to_plan(text, spoken)
        self.assertEqual([e["type"] for e in raw["elements"]], ["captions"])
        self.assertEqual(len(raw["elements"][0]["emphasis"]), 2)
        raw = gplan.with_template(raw, self.tpl, spoken, 20.0, layer_captions=True)
        self.assertEqual(sorted(e["type"] for e in raw["elements"]), ["captions", "lockup", "lockup"])

    def test_text_without_markers_and_without_emphasis_is_still_refused(self):
        with self.assertRaises(PlanError) as cm:
            script.to_plan("Zwykły tekst bez znaczników.", said("Zwykły tekst bez znaczników."))
        self.assertIn("ani jednego znacznika", str(cm.exception))


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.tpl = load_template("format3")

    def test_it_is_a_cuts_template_that_keeps_the_colors_of_the_footage(self):
        t = self.tpl
        self.assertEqual((t.mode, t.keep_colors, t.look, t.fps, t.canvas), ("cuts", True, {}, 30, (1080, 1920)))
        self.assertFalse(t.single_take)
        self.assertEqual((t.hook, t.outro, t.elastic), (1, 3, 16))

    def test_the_shot_pattern_and_length_come_from_the_measured_reel(self):
        t = self.tpl
        self.assertEqual("".join(s.role for s in t.segments), "ABBAAAAAAAAAAABBAAA")
        self.assertEqual(t.total_frames, 1651)
        self.assertAlmostEqual(t.duration_s, 55.03, places=2)
        self.assertEqual(t.segments[t.elastic].frames, 170)
        self.assertTrue(all(s.face is not None for s in t.segments if s.role == "A"))
        self.assertTrue(all(s.face is None for s in t.segments if s.role == "B"))
        self.assertAlmostEqual(t.lufs, -14.6)

    def test_flash_sits_on_the_second_insert_only(self):
        flashes = [(i, f.edge) for i, s in enumerate(self.tpl.segments) for f in s.fx if f.type == "flash"]
        self.assertEqual(flashes, [(14, "start"), (15, "end")])  # wejście w drugą wstawkę i wyjście z niej; pierwsza wstawka ma twarde cięcia
        self.assertEqual((self.tpl.segments[14].role, self.tpl.segments[15].role), ("B", "B"))

    def test_a_wrong_flash_edge_is_refused(self):
        raw = json.loads((HERE.parent / "src" / "reelcut" / "data" / "format3.json").read_text(encoding="utf-8"))
        raw["segments"][14]["fx"] = [{"type": "flash", "edge": "middle"}]
        with self.assertRaises(Exception) as cm:
            parse_template(raw)
        self.assertIn("fx.edge", str(cm.exception))

    def test_dynamics_numbers_match_the_segments(self):
        d, lens = self.tpl.dynamics, [s.frames / 30 for s in self.tpl.segments]
        self.assertEqual(d["cuts"], len(lens) - 1)
        self.assertAlmostEqual(d["duration_s"], sum(lens), places=2)
        self.assertAlmostEqual(d["cuts_per_min"], round((len(lens) - 1) / sum(lens) * 60, 1))
        self.assertEqual((d["shot_s"]["min"], d["shot_s"]["max"]), (round(min(lens), 2), round(max(lens), 2)))
        self.assertEqual(d["pattern"], "".join(s.role for s in self.tpl.segments))

    def test_aliases_find_the_same_template(self):
        for ref in ("format3", "Format 3", "FORMAT-3", "format_3", "  format 3 "):
            self.assertEqual(load_template(ref).name, self.tpl.name, ref)

    def test_it_is_listed_after_format_2_and_before_format_4_and_motion(self):
        ids = [i for i, _ in list_templates()]
        self.assertEqual(ids[:6], ["rolka_DeuOaXKtPBb", "format2", "format3", "format4", "format4h", "motion"])
        self.assertIn("Format 3", dict(list_templates())["format3"])

    def test_captions_and_lockup_settings_are_in_the_template(self):
        c, k = self.tpl.graphics["captions"], self.tpl.graphics["lockup"]
        self.assertEqual((c["max_words"], c["weight"], c["from_script"]), (4, "bold", True))
        self.assertAlmostEqual(c["y"], 0.504)
        self.assertEqual((k["pre"], k["post"], k["big_max"]), (3, 3, 2))
        self.assertEqual(self.tpl.captions, {})  # napisy ASS wyłączone: rysuje je warstwa grafik

    def test_old_templates_do_not_change_their_behavior(self):
        self.assertFalse(load_template().keep_colors)
        self.assertFalse(load_template("format2").keep_colors)
        self.assertNotIn("lockup", load_template("format2").graphics)

    def test_keep_colors_is_read_from_the_file(self):
        raw = json.loads((HERE.parent / "src" / "reelcut" / "data" / "format3.json").read_text(encoding="utf-8"))
        raw["keep_colors"] = False
        self.assertFalse(parse_template(raw).keep_colors)


class PlannerFlashTests(unittest.TestCase):
    def setUp(self):
        self.tpl = load_template("format3")

    def test_a_film_as_long_as_the_reel_gets_the_reel_rhythm_and_both_flashes(self):
        plan = plan_cuts(self.tpl, self.tpl.total_frames, 30, has_broll=True)
        self.assertEqual(plan.mode, "identyczny")
        self.assertEqual([s.frames for s in plan.slots], [s.frames for s in self.tpl.segments])
        self.assertEqual(glue.flash_cuts(plan), [round(sum(s.frames for s in self.tpl.segments[:i]) / 30, 3) for i in (14, 16)])

    def test_a_short_film_stops_before_the_second_insert_and_has_no_flash(self):
        plan = plan_cuts(self.tpl, 900, 30, has_broll=True)
        self.assertEqual(glue.flash_cuts(plan), [])

    def test_a_long_film_repeats_the_body_and_the_flashes_with_it(self):
        plan = plan_cuts(self.tpl, 3000, 30, has_broll=True)
        self.assertGreaterEqual(len(glue.flash_cuts(plan)), 4)
        cuts = glue.flash_cuts(plan)
        self.assertEqual(cuts, sorted(cuts))

    def test_a_repeated_body_never_puts_two_inserts_block_next_to_each_other(self):
        for frames in (1800, 2400, 3000, 3600):
            plan = plan_cuts(self.tpl, frames, 30, has_broll=True)
            roles = "".join(s.role for s in plan.slots)
            self.assertNotIn("BBB", roles, (frames, roles))
            self.assertEqual(sum(s.frames for s in plan.slots), frames)

    def test_the_cycle_rule_leaves_the_plans_of_other_templates_alone(self):
        t1 = load_template()
        plan = plan_cuts(t1, 2000, 30, has_broll=True)
        roles = "".join(s.role for s in plan.slots)
        self.assertEqual(roles[:t1.hook], "".join(s.role for s in t1.segments[:t1.hook]))
        self.assertEqual(sum(s.frames for s in plan.slots), 2000)

    def test_inserts_without_broll_become_details_of_the_footage(self):
        plan = plan_cuts(self.tpl, self.tpl.total_frames, 30, has_broll=False)
        inserts = [s for s in plan.slots if s.role == "B"]
        self.assertTrue(inserts and all(s.source == "A" and s.zoom > 1.3 for s in inserts))


def short_template(tmp: pathlib.Path) -> pathlib.Path:
    """Format 3 w skrócie (5,5 s): hak, wstawka z błyskiem na wejściu i na wyjściu, ujęcie elastyczne i zakończenie."""
    raw = json.loads((HERE.parent / "src" / "reelcut" / "data" / "format3.json").read_text(encoding="utf-8"))
    a = lambda n, h: {"frames": n, "role": "A", "zoom": 1.0, "face": {"h": h, "cx": 0.52, "cy": 0.34, "eye_y": 0.31}}  # noqa: E731
    raw["segments"] = [a(40, 0.2), {"frames": 25, "role": "B", "alt": 1, "fx": [{"type": "flash", "dur": 0.23}, {"type": "flash", "dur": 0.23, "edge": "end"}]},
                       a(60, 0.23), a(40, 0.19)]
    raw["structure"].update({"hook": 1, "outro": 2, "elastic": 2})
    path = tmp / "krotki.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class FlashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_f3_"))
        cls.tpl = load_template(str(short_template(cls.tmp)))
        cls.plan = plan_cuts(cls.tpl, 165, 30, has_broll=True, snap=False)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def job(self, graphics_path=None):
        return glue.prepare(graphics_path, None, self.tpl, self.plan, None, self.tmp / "master.mkv", self.tmp, [], (1080, 1920), 5.5, False,
                            lambda m: None)

    def test_flash_cuts_are_the_starts_of_the_slots_with_a_flash(self):
        self.assertEqual(glue.flash_cuts(self.plan), [round(40 / 30, 3), round(65 / 30, 3)])

    def test_the_flashes_from_the_shot_pattern_become_transitions_of_the_graphics_plan(self):
        job = self.job()
        self.assertIsNotNone(job)
        self.assertEqual([(t.kind, round(t.at, 3)) for t in job.plan.transitions], [("flash", 1.333), ("flash", 2.167)])
        self.assertEqual(job.plan.elements, [])
        self.assertIn("przejście: flash", job.plan.describe())

    def test_the_frame_at_the_cut_is_white_and_the_ones_far_from_it_are_empty(self):
        job = self.job()
        frames = list(job.frames())
        self.assertEqual(len(frames), 165)
        alpha = lambda f: sum(f[3::4][::997]) / len(f[3::4][::997])  # noqa: E731
        peak = alpha(frames[40])  # pierwsza klatka nowego ujęcia: największe krycie (0,86)
        self.assertAlmostEqual(peak / 255, 0.86, delta=0.03)
        self.assertGreater(alpha(frames[39]), 0.5 * 255)
        self.assertEqual(alpha(frames[20]), 0)
        self.assertEqual(alpha(frames[50]), 0)

    def test_a_transition_written_by_the_author_next_to_the_cut_replaces_the_template_flash(self):
        plan_file = self.tmp / "plan.json"
        plan_file.write_text(json.dumps({"schema": 1, "elements": [], "transitions": [{"kind": "blur", "at": 1.36}]}), encoding="utf-8")
        job = self.job(plan_file)
        self.assertEqual(sorted((t.kind, round(t.at, 2)) for t in job.plan.transitions), [("blur", 1.36), ("flash", 2.17)])

    def test_templates_without_flashes_add_no_transitions(self):
        plan = plan_cuts(load_template("format2"), 300, 30)
        self.assertEqual(glue.flash_cuts(plan), [])


@unittest.skipUnless(HAVE_PIL and HAVE_FFMPEG, "brak Pillow albo ffmpeg")
class PipelineTests(unittest.TestCase):
    """Cały montaż Formatu 3 w skrócie na jednolitym tle z tonem zamiast głosu i gotowej transkrypcji: bez rozpoznawania mowy."""

    TEXT = "Zrób *wynik* z eventu. Dziś policzymy trzy *rzeczy* które zmieniają wszystko. Koniec."

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_f3e_"))
        cls.tpl = short_template(cls.tmp)
        cls.video = cls.tmp / "wejscie.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x303030:s=1080x1920:r=25", "-f", "lavfi", "-i",
                        "aevalsrc='0.3*sin(2*PI*180*t)*(0.6+0.4*sin(2*PI*3*t))':s=44100:d=6", "-t", "6", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", str(cls.video)], check=True)
        cls.scenario = cls.tmp / "scenariusz.txt"
        cls.scenario.write_text(cls.TEXT, encoding="utf-8")
        cls.spoken = [w.strip() for w in cls.TEXT.replace("*", "").split()]
        cls.words = cls.tmp / "slowa.json"
        cls.words.write_text(json.dumps([{"w": w, "start": round(i * 0.4, 3), "end": round(i * 0.4 + 0.3, 3)} for i, w in enumerate(cls.spoken)]),
                             encoding="utf-8")
        cls.res = run(cls.video, cls.tmp / "film.mp4", cls.options(), log=lambda m: None)

    @classmethod
    def options(cls, **kw):
        base = dict(template=str(cls.tpl), graphics=cls.scenario, words_file=cls.words, captions="on", framing="off", look=0.0,
                    preset="ultrafast", crf=28)
        return Options(**{**base, **kw})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def frame(self, t, path=None):
        from PIL import Image

        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path or self.res.output), "-frames:v", "1", "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        return Image.frombytes("RGB", (1080, 1920), raw)

    @staticmethod
    def brightness(im):
        small = im.convert("L").resize((24, 40))
        return sum(small.tobytes()) / (24 * 40)

    @staticmethod
    def count(im, rgb, tol=16, box=None):
        im = im.crop(box) if box else im
        return sum(n for n, px in im.getcolors(maxcolors=1 << 22) if all(abs(a - b) <= tol for a, b in zip(px, rgb)))

    def test_the_film_has_the_planned_length_and_the_shots_of_the_template(self):
        info = media.probe(self.res.output)
        self.assertEqual((info.width, info.height), (1080, 1920))
        self.assertAlmostEqual(info.duration, 6.0, delta=0.25)  # długość nagrania: ujęcie elastyczne przejmuje różnicę względem szablonu
        self.assertEqual([s.role for s in self.res.plan.slots], ["A", "B", "A", "A"])

    def test_footage_colors_are_left_alone_and_the_log_says_so(self):
        lines = []
        res = run(self.video, self.tmp / "kolory.mp4", self.options(look=0.8, graphics=None, captions="off"), log=lines.append)
        self.assertTrue(any("Kolory nagrania zostają bez zmian" in m for m in lines), lines)
        self.assertFalse([w for w in res.warnings if "opisu kolorów" in w], res.warnings)

    def test_the_lockups_were_planned_from_the_starred_words(self):
        self.assertTrue(self.res.captions_used)
        self.assertEqual(self.res.graphics["elements"], 2)
        self.assertIn("lockup", self.res.plan_text)
        self.assertIn("Zrób / wynik / z eventu.", self.res.plan_text)
        self.assertEqual(self.res.warnings, [])

    def test_the_big_word_is_yellow_and_sits_below_the_face_zone_when_it_is_spoken(self):
        t = 0.4 + 0.15  # „wynik” wypowiedziane od 0,4 s
        box = (0, int(0.47 * 1920), 1080, int(0.72 * 1920))
        self.assertGreater(self.count(self.frame(t), (255, 211, 70), box=box), 1500)
        self.assertLess(self.count(self.frame(0.1), (255, 211, 70), box=box), 400)

    def test_the_flash_is_in_the_picture_at_the_cut_and_not_around_it(self):
        insert = self.res.plan.slots[1]
        for edge in (insert.start, insert.end):  # błysk na wejściu we wstawkę i na wyjściu z niej
            cut = edge / 30 + 0.02
            peak = self.brightness(self.frame(cut))
            calm = [self.brightness(self.frame(t)) for t in (cut - 0.4, cut + 0.4)]
            self.assertGreater(peak, 190)
            for c in calm:
                self.assertLess(c, peak - 60)

    def test_captions_take_over_after_the_last_lockup(self):
        white, yellow = (255, 255, 255), (255, 211, 70)
        band = (0, int(0.50 * 1920), 1080, int(0.57 * 1920))
        t = 11 * 0.4 + 0.15  # „Koniec.” jest jedynym słowem, które nie wchodzi w żadne hasło
        im = self.frame(t)
        self.assertGreater(self.count(im, white, tol=30, box=band), 250)
        self.assertLess(self.count(im, yellow, box=band), 60)

    def test_the_flash_is_drawn_even_without_captions_and_without_a_scenario(self):
        out = self.tmp / "tylko_blysk.mp4"
        res = run(self.video, out, self.options(graphics=None, captions="off"), log=lambda m: None)
        self.assertTrue(out.exists())
        self.assertEqual(res.graphics["elements"], 0)
        cut = res.plan.slots[1].start / 30 + 0.02
        self.assertGreater(self.brightness(self.frame(cut, out)), 190)

    def test_dry_run_lists_the_flashes_next_to_the_graphics(self):
        res = run(self.video, None, self.options(dry_run=True), log=lambda m: None)
        self.assertIn("przejście: flash", res.plan_text)
        self.assertIn("flash", res.plan_text.split("Grafiki")[0])  # także w tabeli ujęć

    def test_scenario_with_cues_and_emphasis_works_together(self):
        text = "{przejście: rozmycie} Zrób *wynik* z eventu. Dziś policzymy trzy *rzeczy* które zmieniają wszystko. Koniec."
        sc = self.tmp / "razem.txt"
        sc.write_text(text, encoding="utf-8")
        res = run(self.video, None, self.options(graphics=sc, dry_run=True), log=lambda m: None)
        self.assertIn("przejście: blur", res.plan_text)
        self.assertIn("przejście: flash", res.plan_text)


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

    def test_format3_card_in_the_docs_is_current(self):
        text = self.read("FORMAT3.md")
        start, end = "<!-- karta-f3:start -->", "<!-- karta-f3:end -->"
        self.assertTrue(start in text)
        embedded = text.split(start, 1)[1].split(end, 1)[0].strip("\n")
        self.assertEqual(embedded, style.describe(load_template("format3")).strip("\n"),
                         "karta w FORMAT3.md jest nieaktualna: python rolka.py style format3 i wklej między znaczniki")

    def test_card_describes_cuts_lockups_flash_and_brand_colors(self):
        text = style.describe(load_template("format3"))
        for needle in ("`lockup`", "Hasło", "Błysk", "86%", "#FFD346", "#795DFF", "Wzór ujęć: `ABBAAAAAAAAAAABBAAA`", "przejście"):
            self.assertIn(needle, text, needle)
        self.assertNotIn("Szablon nie ma opisu kolorów", text)
        for kind in style.GRAPHICS_ELEMENTS:
            self.assertIn(f"`{kind}`", text)

    def test_numbers_in_format3_md_match_the_template_and_the_code(self):
        doc, tpl = self.read("FORMAT3.md"), load_template("format3")
        d, lens = tpl.dynamics, [s.frames / tpl.fps for s in tpl.segments]
        hs = [s.face.h for s in tpl.segments if s.face]
        a_share = sum(s.frames for s in tpl.segments if s.role == "A") / tpl.total_frames
        wanted = [self.n(tpl.duration_s) + " s", f"{len(tpl.segments)} ujęć", f"{d['cuts']} cięć", self.n(d["cuts_per_min"]),
                  self.n(d["shot_s"]["mean"]) + " s", self.n(d["shot_s"]["median"]) + " s", self.n(d["shot_s"]["min"]), self.n(d["shot_s"]["max"]),
                  f"{a_share * 100:.0f}%", f"{100 - a_share * 100:.0f}%", f"{min(hs) * 100:.0f}%", f"{max(hs) * 100:.0f}%",
                  self.n(tpl.graphics["captions"]["size"] * 100, 2) + "%", f"{round(tpl.graphics['captions']['size'] * 1920)} px",
                  self.n(tpl.graphics["captions"]["y"] * 100) + "%", self.n(lockup.TOP * 100) + "%", f"{lockup.MAX_W * 100:.0f}%",
                  f"{max(transitions.FLASH) * 100:.0f}%", self.n(len(transitions.FLASH) / 30, 2) + " s", self.n(d["speech"]["words_per_s"]) + " słowa",
                  self.n(d["loudness"]["lufs"]).replace("-", "−"), self.n(d["loudness"]["true_peak"]).replace("-", "−"), self.n(d["loudness"]["lra"]),
                  str(d["speech"]["pauses_s"]["count"]), self.n(d["speech"]["pauses_s"]["max"], 2), self.n(lockup.MAX_GAP_S, 2) + " s"]
        for want in wanted:
            self.assertTrue(want in doc, f"w FORMAT3.md brakuje liczby „{want}” z szablonu albo z kodu")
        self.assertAlmostEqual(lockup.SERIF_BOOST, 1.3)
        self.assertTrue("30%" in doc)
        self.assertAlmostEqual(max(lens), 5.67, places=2)

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_example_scenario_in_format3_md_builds_four_lockups_without_warnings(self):
        text = self.fenced("FORMAT3.md", "scenariusz-f3")
        spoken = said(" ".join(script.parse(text).words), step=0.4, dur=0.3)
        raw = script.to_plan(text, spoken)
        tpl = load_template("format3")
        raw = gplan.with_template(raw, tpl, spoken, 0.4 * len(spoken) + 1, layer_captions=True)
        plan = graphics.build_plan(raw, ctx(spoken, duration=0.4 * len(spoken) + 1))
        kinds = [e.kind for e in plan.elements]
        self.assertEqual(kinds.count("lockup"), 4, kinds)
        self.assertIn("pills", kinds)
        self.assertEqual(plan.warnings, [])

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_json_lockup_in_grafiki_md_builds_and_shows_the_big_word(self):
        raw = json.loads(self.fenced("GRAFIKI.md", "plan-lockup"))
        words = said("Nie co ma się zmienić po tym evencie? Tak", step=0.4)
        plan = graphics.build_plan(raw, ctx(words, duration=10))
        self.assertEqual(plan.warnings, [])
        layer = graphics.render_frame(plan, 3.2 + 1.5, SIZE)
        self.assertGreater(near(layer, YELLOW), 3000)

    def test_przejscia_md_numbers_match_the_code(self):
        doc = self.read("PRZEJSCIA.md")
        t = transitions
        wanted = [self.n(t.BLUR_OUT_FRAMES), self.n(t.BLUR_OUT_SIGMA, 0), self.n(t.BLUR_OUT_DECAY, 2), f"{t.BLUR_OUT_WHITE * 100:.0f}%",
                  self.n(t.BLUR_IN_SIGMA, 0), self.n(t.BLUR_IN_TAU), f"{t.BLUR_IN_WHITE * 100:.0f}%",
                  self.n(t.ZOOM_OUT_SCALE + 1, 2), f"{t.ZOOM_OUT_BLUR * 100:.0f}%", self.n(t.ZOOM_IN_START, 2), f"{t.ZOOM_IN_RHO * 100:.0f}%",
                  self.n(t.WHIP_OUT_FRAMES), f"{t.WHIP_OUT_SHIFT * 100:.0f}%", f"{t.WHIP_IN_SHIFT * 100:.0f}%", f"{t.WHIP_IN_RHO * 100:.0f}%",
                  f"{t.WHIP_BLUR * 100:.0f}%", self.n(t.WIPE_S, 2), f"{t.WIPE_BAND * 100:.0f}%", f"{t.WIPE_SOFT * 100:.0f}%", f"{t.WIPE_ALPHA * 100:.0f}%",
                  ", ".join(f"{v * 100:.0f}%" for v in t.FLASH), self.n(script.TRANSITION_SNAP_S)]
        for want in wanted:
            self.assertTrue(want in doc, f"w PRZEJSCIA.md brakuje liczby „{want}” z kodu")
        for frames in (t.window("blur"), t.window("zoom"), t.window("whip")):
            self.assertTrue(all(v > 0 for v in frames))

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_przejscia_md_scenario_snaps_the_second_transition_to_the_end_of_the_card(self):
        text = self.fenced("PRZEJSCIA.md", "scenariusz-przejscia")
        spoken = said(" ".join(script.parse(text).words), step=0.45, dur=0.35)
        raw = script.to_plan(text, spoken)
        card = next(e for e in raw["elements"] if e["type"] == "cutaway")
        first, second = raw["transitions"]
        self.assertEqual(first["at"], card["at"])
        self.assertAlmostEqual(second["at"], card["at"] + card["dur"], places=3)
        tpl = load_template("motion")
        raw = gplan.with_template(raw, tpl, script.words_from_script(text, spoken)[0], 0.45 * len(spoken) + 1, layer_captions=True)
        plan = graphics.build_plan(raw, ctx(spoken, duration=0.45 * len(spoken) + 1))
        self.assertEqual([t.kind for t in plan.transitions], ["blur", "whip"])
        self.assertEqual(plan.warnings, [])

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_json_transitions_in_przejscia_md_build_and_are_listed(self):
        raw = json.loads(self.fenced("PRZEJSCIA.md", "plan-przejscia"))
        plan = graphics.build_plan(raw, ctx(duration=12))
        self.assertEqual([(t.kind, t.at) for t in plan.transitions], [("blur", 4.0), ("whip", 7.0), ("flash", 9.5)])
        self.assertEqual(plan.transitions[1].dir, "left")
        self.assertEqual(plan.warnings, [])

    def test_every_marker_and_field_is_documented_in_grafiki_md(self):
        doc = self.read("GRAFIKI.md")
        self.assertTrue("| `przejście` |" in doc)
        for field in ("lockup", "skip", "hide", "big_font", "min_visible", "edge", "transitions", "dokładnie"):
            self.assertTrue(field in doc, field)
        for want in (self.n(lockup.MAX_GAP_S, 2) + " s", self.n(lockup.MIN_VISIBLE_S, 2) + " s", self.n(lockup.LEAD_S, 2) + " s", self.n(lockup.HOLD, 2) + " s",
                     self.n(lockup.BIG_EM, 3), self.n(lockup.TOP, 3), self.n(lockup.MAX_W, 2), self.n(lockup.SERIF_BOOST, 1)):
            self.assertTrue(want in doc, f"w GRAFIKI.md brakuje liczby „{want}” z lockup.py")

    def test_the_format_name_is_the_same_everywhere(self):
        ui = (HERE.parent / "src" / "reelcut" / "data" / "ui.html").read_text(encoding="utf-8")
        self.assertTrue("Format 3" in ui)
        for name in ("README.md", "WORKFLOW.md", "GRAFIKI.md", "FORMAT3.md", "CLAUDE.md", "FORMAT2.md", "MOTION.md", "STYL.md"):
            self.assertTrue("Format 3" in self.read(name), f"w {name} brakuje nazwy „Format 3”")
        for name in ("README.md", "CLAUDE.md", "FORMAT2.md", "MOTION.md", "STYL.md", "GRAFIKI.md"):
            self.assertTrue("FORMAT3.md" in self.read(name), f"{name} nie odsyła do FORMAT3.md")
        for name in ("README.md", "CLAUDE.md", "GRAFIKI.md", "FORMAT3.md", "WORKFLOW.md", "MOTION.md"):
            self.assertTrue("PRZEJSCIA.md" in self.read(name), f"{name} nie odsyła do PRZEJSCIA.md")

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_intro_scenario_builds_five_lockups_and_one_graphic_without_warnings(self):
        text = self.fenced("INTRO.md", "scenariusz-intro")
        words = script.parse(text).words
        spoken = said(" ".join(words), step=1 / 3.2, dur=0.25)
        raw = script.to_plan(text, spoken)
        tpl = load_template("format3")
        raw = gplan.with_template(raw, tpl, script.words_from_script(text, spoken)[0], len(words) / 3.2 + 1, layer_captions=True)
        plan = graphics.build_plan(raw, ctx(spoken, duration=len(words) / 3.2 + 1))
        kinds = [e.kind for e in plan.elements]
        self.assertEqual((kinds.count("lockup"), kinds.count("pills")), (5, 1), kinds)
        self.assertEqual(plan.warnings, [])
        big = [[w["w"] for ln in e["lines"] if ln["tier"] == "big" for w in ln["words"]] for e in raw["elements"] if e["type"] == "lockup"]
        self.assertEqual([" ".join(b).rstrip(".,").lower() for b in big], ["festyn", "trzy strony", "pomiaru", "policzyć", "zarządem"])

    def test_intro_scenario_keeps_to_the_brand_canon(self):
        text = self.fenced("INTRO.md", "scenariusz-intro")
        body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        spoken = re.sub(r"\{[^{}]*\}", "", body)
        self.assertEqual(re.findall(r"\d", spoken), [], "liczby w mowie piszemy słowami (kanon podaje je w decyzjach z 30.09.2026)")
        for banned in ("specjalist", "pomagam firmom", "kompleksowo", "niezapomnian", "—", "–"):
            self.assertFalse(banned in body.lower(), banned)
        n = len(script.parse(text).words)
        self.assertTrue(150 <= n <= 190, n)  # wzorzec ma 181 słów w 55 s
        for must in ("dwanaście lat", "ponad siedemset wydarzeń", "ponad czterysta wystąpień na scenie", "trzech tysięcy osób", "czterdzieści osiem godzin"):
            self.assertTrue(must in body.lower(), must)
        doc = self.read("INTRO.md")
        for must in ("Kanon marki", "30.09.2026", "Radzie Sektorowej", "Decyzje do podjęcia", "FORMAT3.md"):
            self.assertTrue(must in doc, must)

    def test_old_numbering_is_gone(self):
        for name in ("README.md", "WORKFLOW.md", "GRAFIKI.md", "CLAUDE.md"):
            self.assertFalse("Formaty 1, 2 i 3" in self.read(name), name)
            self.assertFalse("Formaty 2 i 3)" in self.read(name), name)


if __name__ == "__main__":
    unittest.main()
