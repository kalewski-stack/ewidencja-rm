"""Motion: tarcza z kamerą, plansze, napisy kinetyczne, scenariusz ze znacznikami, szablon i montaż z samym lektorem."""
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import captions, graphics, media, style  # noqa: E402
from reelcut.graphics import core, elements, motion, script  # noqa: E402
from reelcut.graphics.core import PlanError  # noqa: E402
from reelcut.pipeline import AUDIO_EXT, Options, run  # noqa: E402
from reelcut.planner import build_plan as plan_cuts  # noqa: E402
from reelcut.template import TemplateError, list_templates, load_template, parse_template  # noqa: E402

HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
ASSETS = HERE / "assets"
SIZE = (540, 960)
# kolory marki „Linia Kalewski”
INK, PAPER, YELLOW, VIOLET = (27, 20, 64), (247, 244, 236), (255, 211, 70), (121, 93, 255)

DIAL = {"type": "dial", "at": 0, "dur": 30, "hub": ["Formuła", "dobrego briefu"],
        "steps": [{"label": "Cel", "at": 3.0}, {"label": "Odbiorca", "at": 6.0}, {"label": "Miara", "at": 9.0}, {"label": "Budżet", "at": 12.0}],
        "finale": {"at": 15.0, "title": "Zrób zrzut ekranu"}}

# scenariusz do testów: lektor czyta wszystko, co poza klamrami i gwiazdkami
SCRIPT = """
# uwaga: ta linia nie jest mową
{tarcza: dobrego briefu | nad: Formuła} Skopiuj tę formułę, jeśli chcesz wyniku.
Pierwsza jest {krok: Cel} cel. Druga to {krok: Odbiorca} odbiorca. Trzecia to {krok: Miara} miara.
{plansza} Ale jest *jeszcze jedna rzecz*. {/plansza}
Czwarta to {krok: Budżet} budżet.
{finał: Zrób zrzut ekranu} To cała formuła.
"""


def ctx(size=SIZE, words=(), duration=30.0):
    return graphics.Context(graphics.load_brand(), core.Layout(*size), 30, ASSETS, None, list(words), duration)


def plan_of(*specs, size=SIZE, words=()):
    return graphics.build_plan({"schema": 1, "elements": list(specs)}, ctx(size, words))


def frame(plan, t, size=SIZE):
    return graphics.render_frame(plan, t, size)


def box(layer, floor=24):
    """Obwiednia wyraźnie widocznych pikseli (bez ledwo dostrzegalnych ogonów rozmycia)."""
    return layer.img.getchannel("A").point(lambda v: 255 if v >= floor else 0).getbbox()


def near(layer, rgb, tol=12, region=None):
    """Ile prawie nieprzezroczystych pikseli ma kolor rgb (z tolerancją), opcjonalnie tylko w prostokącie region."""
    im = layer.img.crop(region) if region else layer.img
    return sum(n for n, (r, g, b, a) in im.getcolors(maxcolors=1 << 22)
               if a >= 200 and abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol)


def spoken(words, step=0.5, dur=0.4, start=0.0):
    return [captions.Word(w, start + i * step, start + i * step + dur) for i, w in enumerate(words)]


class CurveTests(unittest.TestCase):
    def test_power_easing_is_symmetric_monotonic_and_hits_the_ends(self):
        for p in (3.0, 4.0, 5.0):
            xs = [i / 200 for i in range(201)]
            ys = [motion.ease_pow(x, p) for x in xs]
            self.assertEqual((ys[0], ys[-1]), (0.0, 1.0))
            self.assertAlmostEqual(motion.ease_pow(0.5, p), 0.5)
            self.assertTrue(all(b >= a for a, b in zip(ys, ys[1:])), p)
            for x in (0.1, 0.3, 0.45):
                self.assertAlmostEqual(motion.ease_pow(x, p) + motion.ease_pow(1 - x, p), 1.0)
        self.assertEqual((motion.ease_pow(-1, 5), motion.ease_pow(9, 5)), (0.0, 1.0))

    def test_rotation_shape_matches_the_measured_motion(self):
        ts = [i / 2000 * motion.ROT_S for i in range(2001)]

        def first(level):
            return next(t for t in ts if motion.ease_pow(t / motion.ROT_S, motion.ROT_POW) >= level)

        self.assertAlmostEqual(first(0.99) - first(0.01), 0.67, delta=0.05)  # ruch widoczny ok. 0,67 s
        self.assertAlmostEqual(first(0.9) - first(0.1), 0.36, delta=0.05)  # 10-90% w ok. 0,36 s

    def test_build_up_keyframes_grow_the_hub_from_small_to_full(self):
        vals = [motion.keyed(motion.HUB_BUILD, i / 100) for i in range(0, 260)]
        self.assertAlmostEqual(vals[0], motion.HUB_BUILD[0][1])
        self.assertAlmostEqual(vals[-1], 1.0)
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(vals, vals[1:])))
        self.assertTrue(0.2 <= min(vals) and max(vals) <= 1.0 + 1e-9)

    def test_measured_numbers_are_the_ones_in_the_template(self):
        tpl = load_template("motion")
        self.assertEqual(tpl.dynamics["motion"].get("wide_hub_r"), motion.measured()["wide_hub_r"])
        for key, value in motion.measured().items():
            self.assertEqual(tpl.dynamics["motion"][key], value, key)
        self.assertEqual(motion.measured()["zoom_ratio"], round(motion.R_CLOSE / motion.R_WIDE_FINAL, 2))


class TemplateTests(unittest.TestCase):
    def test_motion_is_a_motion_template_with_kinetic_captions_from_the_script(self):
        tpl = load_template("motion")
        self.assertEqual((tpl.mode, tpl.motion, tpl.single_take), ("motion", True, True))
        self.assertEqual((tpl.canvas, tpl.fps), ((1080, 1920), 30))
        self.assertEqual([s.role for s in tpl.segments], ["A"])
        cap = tpl.graphics["captions"]
        self.assertEqual((cap["style"], cap["max_words"], cap["from_script"]), ("kinetic", 2, True))
        self.assertFalse(load_template("format2").motion)
        self.assertFalse(load_template("format1").motion)

    def test_aliases_find_the_same_template(self):
        names = {load_template(ref).name for ref in ("motion", "Motion", " MOTION ", "mo-tion")}
        self.assertEqual(len(names), 1)
        self.assertIn("Motion", names.pop())
        listed = dict(list_templates())  # interfejs i API pokazują szablony z tej listy: motion jest trzeci
        self.assertEqual(list(listed)[:4], ["rolka_DeuOaXKtPBb", "format2", "format3", "motion"])
        self.assertTrue(listed["motion"].startswith("Motion"))

    def test_motion_mode_keeps_the_single_segment_rule(self):
        raw = json.loads((HERE.parent / "src" / "reelcut" / "data" / "motion.json").read_text(encoding="utf-8"))
        with self.assertRaises(TemplateError):
            parse_template(dict(raw, segments=raw["segments"] * 2))
        with self.assertRaises(TemplateError):
            parse_template(dict(raw, segments=[dict(raw["segments"][0], role="B")]))
        self.assertEqual(parse_template(raw).mode, "motion")

    def test_planner_makes_one_graphics_slot_for_any_length(self):
        tpl = load_template("motion")
        for frames in (150, 900, 3000):
            plan = plan_cuts(tpl, frames, 30)
            self.assertEqual((len(plan.slots), plan.total_frames, plan.mode), (1, frames, "motion"))
        from reelcut.planner import describe_plan

        self.assertIn("grafiki", describe_plan(plan_cuts(tpl, 300, 30)))


class ScriptTests(unittest.TestCase):
    WORDS = script.parse(SCRIPT).words

    def test_new_markers_are_parsed_in_polish_and_english(self):
        s = script.parse(SCRIPT)
        self.assertEqual([c.kind for c in s.cues], ["dial", "step", "step", "step", "cutaway", "step", "finale"])
        dial = s.cues[0].spec
        self.assertEqual((dial["hub_main"], dial["hub_top"]), ("dobrego briefu", "Formuła"))
        self.assertEqual([c.spec["label"] for c in s.cues if c.kind == "step"], ["Cel", "Odbiorca", "Miara", "Budżet"])
        self.assertEqual(s.cues[-1].spec["title"], "Zrób zrzut ekranu")
        for head, kind in (("tarcza", "dial"), ("TARCZA", "dial"), ("dial", "dial"), ("krok", "step"), ("step", "step"), ("finał", "finale"),
                           ("final", "finale"), ("plansza", "cutaway"), ("cutaway", "cutaway"), ("błysk", "glint"), ("glint", "glint")):
            self.assertEqual(script.parse("{" + head + ": X} a").cues[0].kind, kind, head)

    def test_plansza_covers_the_words_between_its_markers(self):
        s = script.parse(SCRIPT)
        cut = next(c for c in s.cues if c.kind == "cutaway")
        covered = self.WORDS[cut.word:cut.end_word + 1]
        self.assertEqual(covered, ["Ale", "jest", "jeszcze", "jedna", "rzecz."])

    def test_emphasis_marks_exactly_the_starred_words(self):
        s = script.parse(SCRIPT)
        self.assertEqual([w for w, e in zip(s.words, s.emph) if e], ["jeszcze", "jedna", "rzecz."])
        again = script.parse("{plansza} Ale *celu*. Potem dalej. {/plansza}")  # gwiazdka zamyka się przed kropką
        self.assertEqual([w for w, e in zip(again.words, again.emph) if e], ["celu."])

    def test_plan_collects_steps_and_finale_into_the_last_dial(self):
        raw = script.to_plan(SCRIPT, spoken(self.WORDS))
        self.assertEqual([e["type"] for e in raw["elements"]], ["dial", "cutaway", "captions"])
        dial = raw["elements"][0]
        self.assertEqual([s["label"] for s in dial["steps"]], ["Cel", "Odbiorca", "Miara", "Budżet"])
        ats = [s["at"] for s in dial["steps"]]
        self.assertEqual(ats, sorted(ats))
        self.assertGreater(dial["finale"]["at"], ats[-1])
        self.assertEqual((dial["hub"], dial["finale"]["title"]), (["Formuła", "dobrego briefu"], "Zrób zrzut ekranu"))
        # czas kroku to chwila, w której pada następne słowo scenariusza: „Cel” stoi przed słowem „cel.”
        self.assertAlmostEqual(ats[0], 0.5 * self.WORDS.index("cel."), places=2)

    def test_cutaway_and_captions_get_the_emphasis_ranges_from_speech(self):
        raw = script.to_plan(SCRIPT, spoken(self.WORDS))
        cut, caps = raw["elements"][1], raw["elements"][2]
        i = self.WORDS.index("jeszcze")
        want = [round(0.5 * i, 3), round(0.5 * (i + 2) + 0.4, 3)]
        self.assertEqual(cut["emphasis"], [want])
        self.assertEqual(caps["emphasis"], [want])
        self.assertGreater(cut["dur"], 0.5 * 4 + 0.4)  # od pierwszego do ostatniego słowa plus chwila po puencie
        self.assertEqual(caps["shift"], [{"at": raw["elements"][0]["finale"]["at"], "dur": 3600, "y": script.CAPTIONS_FINALE_Y}])

    def test_marker_errors_are_readable(self):
        words = spoken("a b c d e f g h".split())
        for text, hint in (("a {krok: Cel} b c d", "tarcza"), ("a {finał: Koniec} b c", "tarcza"),
                           ("{tarcza: x} a {krok} b c d e f", "nazwy")):
            with self.assertRaises(PlanError, msg=text) as cm:
                script.to_plan(text, words)
            self.assertIn(hint, str(cm.exception))

    def test_words_for_captions_keep_the_spelling_of_the_script_and_the_timing_of_speech(self):
        heard = spoken([w.lower().strip(".,") for w in self.WORDS], step=0.4)
        fixed, coverage = script.words_from_script(SCRIPT, heard)
        self.assertEqual(coverage, 1.0)
        self.assertEqual([w.text for w in fixed], self.WORDS)  # pisownia i wielkie litery ze scenariusza
        self.assertEqual([round(w.start, 2) for w in fixed], [round(w.start, 2) for w in heard])
        _, partial = script.words_from_script(SCRIPT, heard[::2])  # co drugie słowo słyszane: pokrycie spada
        self.assertLess(partial, 0.8)

    def test_emphasis_is_ignored_by_the_alignment(self):
        plain = script.parse("{tarcza: x} Ala ma kota").words
        starred = script.parse("{tarcza: x} Ala *ma* kota").words
        self.assertEqual(plain, starred)


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class RegistryTests(unittest.TestCase):
    def test_motion_elements_and_the_kinetic_variant_are_registered(self):
        self.assertEqual(set(style.MOTION_ELEMENTS), {"backdrop", "dial", "cutaway", "glint"})
        self.assertTrue(set(style.MOTION_ELEMENTS) <= set(graphics.REGISTRY))
        self.assertIn(("captions", "kinetic"), elements.VARIANTS)

    def test_captions_pick_the_variant_by_style(self):
        words = spoken("Ala ma kota".split())
        kinetic = plan_of({"type": "captions", "style": "kinetic"}, words=words).elements[0]
        plain = plan_of({"type": "captions"}, words=words).elements[0]
        self.assertIsInstance(kinetic, motion.KineticCaptions)
        self.assertNotIsInstance(plain, motion.KineticCaptions)
        self.assertEqual((kinetic.kind, plain.kind), ("captions", "captions"))

    def test_motion_elements_do_not_trigger_layout_warnings(self):
        plan = plan_of({"type": "backdrop", "at": 0}, DIAL, {"type": "cutaway", "at": 2, "dur": 2, "text": "Ale *tak*"},
                       {"type": "glint", "at": 1})
        self.assertEqual(plan.warnings, [])


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class BackdropTests(unittest.TestCase):
    def test_paper_with_dots_only_inside_the_vignette(self):
        layer = frame(plan_of({"type": "backdrop", "at": 0}), 1.0)
        W, H = SIZE
        self.assertEqual(layer.img.getchannel("A").getextrema(), (255, 255))
        self.assertEqual(layer.img.getpixel((2, 2))[:3], PAPER)  # róg: czysty papier
        self.assertEqual(layer.img.getpixel((W - 3, H - 3))[:3], PAPER)

        def deviation(region):  # największe odchylenie od koloru papieru w prostokącie
            return max(max(abs(a - b) for a, b in zip(px[:3], PAPER)) for _, px in layer.img.crop(region).getcolors(maxcolors=1 << 20))

        self.assertGreater(deviation((W // 4, H // 4, 3 * W // 4, 3 * H // 4)), 25)  # w środku kropki wyraźnie widać
        self.assertLessEqual(deviation((0, 0, W // 16, H // 16)), 4)  # w rogu winieta je wygasza prawie do zera

    def test_dark_variant_is_ink(self):
        layer = frame(plan_of({"type": "backdrop", "at": 0, "dark": True}), 1.0)
        self.assertEqual(layer.img.getpixel((2, 2))[:3], INK)

    def test_backdrop_lives_for_the_whole_film(self):
        plan = plan_of({"type": "backdrop", "at": 0})
        self.assertTrue(plan.active(0.0) and plan.active(1800.0))


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class DialTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_of(DIAL)
        self.dial = self.plan.elements[0]
        self.W, self.H = SIZE

    # --- poprawność planu ---
    def test_rejects_wrong_dials_with_readable_errors(self):
        one = dict(DIAL, steps=DIAL["steps"][:1])
        many = dict(DIAL, steps=[{"label": f"K{i}", "at": 3.0 + i * 2.0} for i in range(13)], finale=None)
        backwards = dict(DIAL, steps=[{"label": "A", "at": 5.0}, {"label": "B", "at": 4.0}])
        nameless = dict(DIAL, steps=[{"label": "A", "at": 5.0}, {"label": " ", "at": 7.0}])
        early = dict(DIAL, closeup_at=4.0)
        late_finale = dict(DIAL, finale={"at": 12.1, "title": "x"})
        for spec, hint in ((one, "co najmniej dwie"), (many, "12"), (backwards, "rosnąć"), (nameless, "label"), (early, "po pierwszym kroku"),
                           (late_finale, "po ostatnim kroku")):
            with self.assertRaises(PlanError, msg=hint) as cm:
                plan_of(spec)
            self.assertIn(hint, str(cm.exception))

    def test_hub_text_that_would_be_unreadable_is_flagged(self):
        self.assertEqual(plan_of(dict(DIAL, hub=["Formuła", "dobrego briefu"])).warnings, [])
        self.assertEqual(plan_of(dict(DIAL, hub="Brief")).warnings, [])  # sam tekst to duży wiersz
        flagged = plan_of(dict(DIAL, hub=["Temat", "projekt eventu firmowego"]))
        self.assertTrue(any("tekst piasty" in w and "za długi" in w for w in flagged.warnings), flagged.warnings)

    def test_a_first_step_that_cuts_the_build_short_is_flagged(self):
        early = plan_of(dict(DIAL, steps=[{"label": "A", "at": 1.0}, {"label": "B", "at": 4.0}, {"label": "C", "at": 7.0}], finale=None))
        self.assertTrue(any("rozbudowa" in w and "zdanie wstępne" in w for w in early.warnings), early.warnings)
        self.assertEqual(plan_of(DIAL).warnings, [])  # pierwszy krok po 3 s: rozbudowa trwa pełne 2,7 s

    def test_close_steps_are_flagged_but_still_build(self):
        plan = plan_of(dict(DIAL, steps=[{"label": "A", "at": 3.0}, {"label": "B", "at": 3.6}, {"label": "C", "at": 6.0}], finale=None))
        self.assertTrue(any("1 s" in w for w in plan.warnings), plan.warnings)

    def test_the_closeup_defaults_to_just_before_the_first_step(self):
        self.assertAlmostEqual(self.dial.closeup_at, 3.0 - 0.3)
        self.assertAlmostEqual(plan_of(dict(DIAL, closeup_at=1.0)).elements[0].closeup_at, 1.0)

    # --- kamera ---
    def test_camera_phases_follow_the_measured_radii(self):
        W, H = self.W, self.H
        build = self.dial.camera(1.9, W, H)
        self.assertEqual(build.phase, "build")
        self.assertAlmostEqual(build.R / W, motion.R_WIDE_BUILD * motion.keyed(motion.HUB_BUILD, 1.9), places=4)
        self.assertAlmostEqual(build.cy / H, motion.CY_WIDE)
        close = self.dial.camera(self.dial.closeup_at + motion.SETTLE_S, W, H)
        self.assertEqual(close.phase, "close")
        self.assertAlmostEqual(close.R / W, motion.R_CLOSE, places=4)
        self.assertAlmostEqual(close.cy / H, motion.CY_CLOSE, places=4)
        final = self.dial.camera(DIAL["finale"]["at"] + 1.0, W, H)
        self.assertEqual(final.phase, "final")
        self.assertAlmostEqual(final.R / W, motion.R_WIDE_FINAL, places=4)
        self.assertAlmostEqual(final.cy / H, motion.CY_WIDE)
        self.assertEqual(final.blur, 0.0)

    def test_closeup_is_a_hard_cut_that_settles_and_then_drifts(self):
        W, H = self.W, self.H
        c0 = self.dial.closeup_at
        before, cut = self.dial.camera(c0 - 0.01, W, H), self.dial.camera(c0, W, H)
        self.assertGreater(cut.R / before.R, 2.0)  # nie ma najazdu: kamera przeskakuje
        self.assertAlmostEqual(cut.R / W, motion.R_CLOSE * motion.CUT_SCALE, places=4)
        self.assertAlmostEqual(cut.blur / W, motion.CUT_BLUR, places=4)
        self.assertEqual(self.dial.camera(c0 + 0.2, W, H).blur, 0.0)
        settled = self.dial.camera(c0 + motion.SETTLE_S, W, H)
        later = self.dial.camera(c0 + motion.SETTLE_S + 5.0, W, H)
        self.assertAlmostEqual(later.R / settled.R, 1 + 5 * motion.DRIFT, places=4)

    def test_pull_back_starts_a_little_smaller_and_clears_the_blur(self):
        W, H = self.W, self.H
        f0 = DIAL["finale"]["at"]
        start, end = self.dial.camera(f0, W, H), self.dial.camera(f0 + 0.9, W, H)
        self.assertAlmostEqual(start.R / (motion.R_WIDE_FINAL * W), 0.955, places=3)
        self.assertAlmostEqual(start.blur / W, motion.FINAL_BLUR, places=4)
        self.assertEqual((end.blur, end.R), (0.0, motion.R_WIDE_FINAL * W))

    # --- obroty i pisanie ---
    def test_dial_turns_one_spoke_per_step_and_closes_the_circle_in_the_finale(self):
        d, delta = self.dial, 90.0
        self.assertEqual(d.delta, delta)
        self.assertEqual(d.angle(0.0), 0.0)
        self.assertEqual(d.angle(DIAL["steps"][0]["at"] + 1.0), 0.0)  # pierwsza szprycha stoi na górze, bez obrotu
        for k in (1, 2, 3):
            at = DIAL["steps"][k]["at"]
            self.assertAlmostEqual(d.angle(at - motion.ROT_LEAD), delta * (k - 0.5), places=6)  # połowa obrotu tuż przed hasłem
            self.assertAlmostEqual(d.angle(at + 1.0), delta * k, places=6)
        f0 = DIAL["finale"]["at"]
        self.assertAlmostEqual(d.angle(f0 - 0.01), 3 * delta, places=6)
        self.assertAlmostEqual(d.angle(f0 + 3.0), 360.0, places=6)  # ósmy obrót (tu czwarty) zamyka okrąg
        angles = [d.angle(i / 20) for i in range(0, 400)]
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(angles, angles[1:])))

    def test_labels_type_at_the_measured_speed(self):
        d = self.dial
        for k, (label, st) in enumerate((s["label"], s) for s in DIAL["steps"]):
            at = st["at"]
            self.assertEqual(d.typed(k, at - 0.5), 0.0)
            self.assertAlmostEqual(d.typed(k, at + len(label) / motion.TYPE_CPS / 2), 0.5, places=6)
            self.assertEqual(d.typed(k, at + len(label) / motion.TYPE_CPS + 0.01), 1.0)
        self.assertEqual(d.typed(3, DIAL["finale"]["at"]), 1.0)  # po finale wszystko jest napisane

    def test_labels_fit_the_frame_after_the_finale_and_long_ones_are_flagged(self):
        eight = dict(DIAL, steps=[{"label": w, "at": 3.0 + 2.5 * i} for i, w in
                                  enumerate("Cel Odbiorca Miara Budżet Termin Ryzyko Dostawca Decyzja".split())], finale={"at": 25.0, "title": "Koniec"})
        plan = plan_of(eight)
        self.assertEqual(plan.warnings, [])
        self.assertLessEqual(plan.elements[0].label_k, motion.LABEL_K)
        self.assertGreaterEqual(plan.elements[0].label_k, motion.LABEL_MIN_K)
        bb = box(frame(plan, 28.0), floor=60)
        self.assertGreater(bb[0], 0.02 * self.W)  # etykiety zostają w kadrze z marginesem
        self.assertLess(bb[2], 0.98 * self.W)
        self.assertEqual(plan_of(DIAL).elements[0].label_k, motion.LABEL_K)  # krótkie etykiety zostają przy zmierzonym rozmiarze
        long = dict(DIAL, steps=[{"label": "Zrozumienie odbiorcy", "at": 3.0}, {"label": "Mierzalny cel biznesowy", "at": 6.0},
                                 {"label": "Budżet wynikający z celu", "at": 9.0}, {"label": "Termin i harmonogram", "at": 12.0}])
        flagged = plan_of(long)
        self.assertEqual(flagged.elements[0].label_k, motion.LABEL_MIN_K)  # nie kurczymy poniżej czytelnego rozmiaru
        self.assertTrue(any("za długa" in w and "Mierzalny cel biznesowy" in w for w in flagged.warnings), flagged.warnings)

    # --- obraz ---
    def test_hub_is_ink_and_sits_where_the_camera_puts_it(self):
        for t in (1.9, 4.5, 16.5):
            cam = self.dial.camera(t, self.W, self.H)
            layer = frame(self.plan, t)
            x, y = int(cam.cx), int(cam.cy - 0.55 * cam.R)
            self.assertEqual(layer.img.getpixel((x, y))[:3], INK, t)
            self.assertEqual(layer.img.getpixel((x, y))[3], 255, t)

    def test_active_dot_is_yellow_only_while_a_label_is_typed_in_the_closeup(self):
        build, typing, final = (near(frame(self.plan, t), YELLOW) for t in (1.9, 3.3, 16.5))
        self.assertEqual((build, final), (0, 0))
        self.assertGreater(typing, 150)

    def test_dial_uses_brand_colors(self):
        brand = (INK, VIOLET, YELLOW, PAPER, (255, 255, 255), (99, 67, 255))
        for t in (4.5, 16.5):
            solid = [(n, px[:3]) for n, px in frame(self.plan, t).img.getcolors(maxcolors=1 << 22) if px[3] == 255]
            ours = sum(n for n, px in solid if any(max(abs(a - b) for a, b in zip(px, c)) <= 6 for c in brand))
            self.assertGreater(ours / sum(n for n, _ in solid), 0.95, t)  # reszta to wygładzenia krawędzi i przyciemniony tekst piasty
            self.assertNotIn((0, 0, 0), [px for _, px in solid])

    def test_label_appears_letter_by_letter(self):
        region = (int(0.1 * self.W), int(0.33 * self.H), int(0.9 * self.W), int(0.46 * self.H))  # tuż nad kropką w zbliżeniu

        def right_edge(t):  # napis rośnie w prawo od stałej lewej krawędzi, a kursor idzie za ostatnią literą
            mask = frame(self.plan, t).img.crop(region).getchannel("A").point(lambda v: 255 if v >= 128 else 0)
            return mask.getbbox()[2]

        at = DIAL["steps"][1]["at"]  # „Odbiorca”: 8 liter, 0,44 s; obrót kończy się ok. 0,23 s po haśle, więc liczymy dopiero potem
        edges = {dt: right_edge(at + dt) for dt in (0.28, 0.36, 0.6, 1.1)}
        self.assertLess(edges[0.28], edges[0.36])
        self.assertLess(edges[0.36], edges[0.6])
        self.assertLessEqual(edges[1.1], edges[0.6])  # po dopisaniu napis stoi, a kursor gaśnie
        self.assertGreater(edges[1.1], edges[0.36])

    def test_title_shows_only_after_the_finale(self):
        region = (0, int(0.2 * self.H), self.W, int(0.34 * self.H))
        before = near(frame(self.plan, DIAL["finale"]["at"] - 0.5), INK, tol=30, region=region)
        after = near(frame(self.plan, DIAL["finale"]["at"] + 1.5), INK, tol=30, region=region)
        self.assertGreater(after, before + 150)

    def test_render_is_deterministic(self):
        for t in (0.4, 3.2, 15.3):
            self.assertEqual(frame(self.plan, t).tobytes(), frame(self.plan, t).tobytes(), t)

    def test_blur_after_the_cut_changes_the_picture(self):
        c0 = self.dial.closeup_at
        cut, settled = frame(self.plan, c0 + 0.01), frame(self.plan, c0 + 0.5)
        sharp = lambda layer: layer.img.getchannel("A").point(lambda v: 255 if v == 255 else 0).histogram()[255]  # noqa: E731
        self.assertLess(sharp(cut), sharp(settled))  # po cięciu obraz jest rozmyty, więc mniej pikseli ma pełne krycie


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class CutawayTests(unittest.TestCase):
    CUT = {"type": "cutaway", "at": 1.0, "dur": 2.5,
           "words": [{"w": "Ale", "t": 0.1, "tier": "small"}, {"w": "jest", "t": 0.3, "tier": "small"}, {"w": "WIELKIE", "t": 0.9, "tier": "big"},
                     {"w": "dopisek", "t": 1.4, "tier": "tiny"}]}

    def test_card_is_a_hard_cut_on_dark_ink(self):
        plan = plan_of(self.CUT)
        self.assertFalse(plan.active(0.99))
        self.assertTrue(plan.active(1.0) and plan.active(3.49))
        self.assertFalse(plan.active(3.51))
        first = frame(plan, 1.0)
        self.assertEqual(first.img.getchannel("A").getextrema(), (255, 255))  # cały kadr od pierwszej klatki, bez wejścia
        self.assertEqual(first.img.getpixel((2, 2))[:3], INK)

    def test_words_arrive_one_after_another_and_big_ones_are_yellow(self):
        plan = plan_of(self.CUT)
        self.assertEqual(near(frame(plan, 1.05), PAPER, tol=40, region=(40, 200, 500, 700)), 0)  # jeszcze nic nie powiedziano
        small_only = frame(plan, 1.6)
        self.assertGreater(near(small_only, PAPER, tol=40, region=(40, 200, 500, 700)), 100)
        self.assertEqual(near(small_only, YELLOW), 0)
        big = frame(plan, 2.4)
        self.assertGreater(near(big, YELLOW), 300)

    def test_words_and_emphasis_can_come_straight_from_speech(self):
        words = spoken("Ale jest jeszcze jedna rzecz".split(), step=0.4, dur=0.3, start=1.0)
        plan = plan_of({"type": "cutaway", "at": 1.0, "dur": 3.0, "emphasis": [[2.2, 3.1]]}, words=words)
        tokens = plan.elements[0].block.items
        self.assertEqual(len(tokens), 5)
        self.assertEqual([round(it.t0, 2) for it in tokens], [1.0, 1.4, 1.8, 2.2, 2.6])
        self.assertGreater(tokens[3].px, tokens[0].px)  # wyróżnione słowa mają większy krój
        self.assertEqual(tokens[3].px, tokens[4].px)

    def test_text_without_speech_is_spread_over_the_card(self):
        plan = plan_of({"type": "cutaway", "at": 1.0, "dur": 3.0, "text": "Ale *jeszcze jedna* rzecz"})
        times = [it.t0 for it in plan.elements[0].block.items]
        self.assertEqual(len(times), 4)
        self.assertEqual(times, sorted(times))
        self.assertGreaterEqual(times[0], 1.0)
        self.assertLess(times[-1], 4.0)

    def test_card_without_words_says_so(self):
        plan = plan_of({"type": "cutaway", "at": 1.0, "dur": 2.0})
        self.assertTrue(any("nie ma słów" in n for n in plan.elements[0].notes), plan.elements[0].notes)

    def test_unknown_word_size_is_refused(self):
        with self.assertRaises(PlanError):
            plan_of({"type": "cutaway", "at": 1.0, "dur": 2.0, "words": [{"w": "x", "t": 0.1, "tier": "gigantyczny"}]})


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class KineticCaptionsTests(unittest.TestCase):
    WORDS = spoken("Skopiuj tę formułę jeśli chcesz wyniku".split(), step=0.5, dur=0.4, start=1.0)

    def caps(self, **over):
        spec = {"type": "captions", "style": "kinetic", "max_words": 2, "y": 0.255}
        return plan_of(dict(spec, **over), words=self.WORDS)

    def test_one_or_two_words_at_a_time_in_the_upper_part_of_the_frame(self):
        plan = self.caps()
        units = plan.elements[0].units
        self.assertTrue(all(1 <= len(u.tokens) <= 2 for u in units), [len(u.tokens) for u in units])
        self.assertEqual([t[0] for u in units for t in u.tokens], [w.text for w in self.WORDS])
        self.assertIsNone(box(frame(plan, 0.5)))  # przed pierwszym słowem pusto
        bb = box(frame(plan, 1.6))
        centre = (bb[1] + bb[3]) / 2 / SIZE[1]
        self.assertTrue(0.18 < centre < 0.34, centre)
        self.assertGreater(near(frame(plan, 1.6), INK, tol=30), 200)  # napisy w kolorze tuszu

    def test_a_word_appears_at_its_own_time_and_leaves_with_the_next_group(self):
        plan = self.caps()
        first = plan.elements[0].units[0]
        self.assertIsNone(box(frame(plan, first.start - 0.1)))
        self.assertIsNotNone(box(frame(plan, first.start + 0.3)))
        nxt = plan.elements[0].units[1]
        self.assertNotEqual(frame(plan, first.start + 0.3).tobytes(), frame(plan, nxt.start + 0.3).tobytes())

    def test_there_is_no_blank_frame_between_groups_that_follow_each_other(self):
        plan = self.caps()
        units = plan.elements[0].units
        for a, b in zip(units, units[1:]):
            self.assertAlmostEqual(a.end, b.start, places=6)  # słowa idą jedno za drugim, więc grupy stykają się
            for eps in (0.001, 0.01, 0.03):
                self.assertIsNotNone(box(frame(plan, b.start - eps)), f"pusta klatka {eps} s przed grupą od {b.start}")

    def test_emphasised_phrase_is_bigger_and_goes_under_the_small_words(self):
        plan = self.caps(emphasis=[[2.0, 2.9]])
        tiers = [[t[1] for t in u.tokens] for u in plan.elements[0].units]
        self.assertTrue(any("big" in ts and "small" in ts for ts in tiers), tiers)
        unit = next(u for u in plan.elements[0].units if any(t[1] == "big" for t in u.tokens))
        small = [it for it in unit.block.items if it.px == motion.TIER_CAP["small"][1] * SIZE[0]]
        big = [it for it in unit.block.items if it.px == motion.TIER_CAP["big"][1] * SIZE[0]]
        self.assertTrue(small and big)
        self.assertGreater(min(it.y for it in big), max(it.y for it in small))  # duży krój stoi pod małym

    def test_shift_window_moves_captions_under_the_diagram(self):
        plan = self.caps(shift=[{"at": 3.0, "dur": 100, "y": 0.8}])
        early = box(frame(plan, 1.6))
        late = box(frame(plan, 3.6))
        self.assertLess((early[1] + early[3]) / 2, 0.4 * SIZE[1])
        self.assertGreater((late[1] + late[3]) / 2, 0.7 * SIZE[1])

    def test_without_speech_nothing_is_drawn_and_nothing_breaks(self):
        plan = plan_of({"type": "captions", "style": "kinetic"})
        self.assertIsNone(box(frame(plan, 1.0)))


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class GlintTests(unittest.TestCase):
    def test_flash_is_short_bright_and_stays_at_the_requested_spot(self):
        plan = plan_of({"type": "backdrop", "at": 0}, {"type": "glint", "at": 2.0, "x": 0.3, "y": 0.6, "dur": 0.2, "strength": 1.0})
        from PIL import ImageChops

        before = frame(plan, 1.9)
        self.assertEqual(frame(plan, 2.3).img.tobytes(), before.img.tobytes())  # po błysku wraca czyste tło
        peak = frame(plan, 2.07)
        changed = ImageChops.difference(before.img.convert("L"), peak.img.convert("L")).point(lambda v: 255 if v > 6 else 0).getbbox()
        self.assertIsNotNone(changed)
        w, h = SIZE
        self.assertAlmostEqual((changed[0] + changed[2]) / 2 / w, 0.3, delta=0.05)
        self.assertAlmostEqual((changed[1] + changed[3]) / 2 / h, 0.6, delta=0.05)


class DocsTests(unittest.TestCase):
    @staticmethod
    def fenced(path, marker):
        text = (HERE.parent / path).read_text(encoding="utf-8")
        block = text.split(f"<!-- {marker}:start -->", 1)[1].split(f"<!-- {marker}:end -->", 1)[0]
        return block.split("```", 2)[1].split("\n", 1)[1]

    def test_motion_card_in_the_docs_is_current(self):
        text = (HERE.parent / "MOTION.md").read_text(encoding="utf-8")
        start, end = "<!-- karta-motion:start -->", "<!-- karta-motion:end -->"
        self.assertIn(start, text)
        embedded = text.split(start, 1)[1].split(end, 1)[0].strip("\n")
        self.assertEqual(embedded, style.describe(load_template("motion")).strip("\n"),
                         "karta w MOTION.md jest nieaktualna: python rolka.py style motion i wklej między znaczniki")

    def test_card_describes_the_motion_template_and_lists_its_elements(self):
        text = style.describe(load_template("motion"))
        for kind in style.MOTION_ELEMENTS:
            self.assertIn(f"`{kind}`", text)
        for color in ("#795DFF", "#FFD346", "#1B1440", "#F7F4EC"):
            self.assertIn(color, text)
        self.assertNotIn("cięć na minutę", text)

    def test_numbers_in_motion_md_match_the_template(self):
        doc = (HERE.parent / "MOTION.md").read_text(encoding="utf-8")
        d = load_template("motion").dynamics["motion"]
        n = lambda v: str(v).replace(".", ",")  # noqa: E731
        for want in (n(d["rotation_nominal_s"]), n(round(d["drift_per_s"] * 100, 2)), str(d["spokes"]), n(d["zoom_ratio"]), str(round(d["type_cps"])),
                     n(round(d["cut_scale"] * 100, 1)), n(d["settle_s"]), n(round(d["wide_hub_r"] * 100, 1)), n(round(d["close_hub_r"] * 100, 1)),
                     n(round(d["wide_final_hub_r"] * 100, 1))):
            self.assertIn(want, doc, f"w MOTION.md brakuje liczby {want} z szablonu motion")

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_example_scenario_in_motion_md_builds_without_warnings(self):
        text = self.fenced("MOTION.md", "scenariusz-motion")
        words = script.parse(text).words
        raw = script.to_plan(text, spoken(words, step=0.42, dur=0.34))
        plan = graphics.build_plan(raw, ctx((1080, 1920), words=script.words_from_script(text, spoken(words, step=0.42, dur=0.34))[0],
                                            duration=0.42 * len(words) + 1))
        self.assertEqual([e.kind for e in plan.elements][:2], ["dial", "cutaway"])
        self.assertEqual(plan.warnings, [])
        dial = plan.elements[0]
        self.assertGreaterEqual(dial.n, 6)
        self.assertIsNotNone(dial.finale_at)

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_json_plan_in_grafiki_md_builds_and_shows_something_in_every_phase(self):
        raw = json.loads(self.fenced("GRAFIKI.md", "plan-motion"))
        words = spoken("Ale jest jeszcze jedna rzecz".split(), step=0.4, dur=0.3, start=17.0)
        plan = graphics.build_plan(raw, ctx((1080, 1920), words=words, duration=40.0))
        self.assertEqual([e.kind for e in plan.elements], ["backdrop", "dial", "cutaway", "glint", "captions"])
        self.assertEqual(plan.warnings, [])
        for t in (1.0, 6.0, 18.0, 25.0):
            self.assertEqual(frame(plan, t, (1080, 1920)).img.getchannel("A").getextrema(), (255, 255), t)

    def test_every_new_marker_is_documented_in_grafiki_md(self):
        doc = (HERE.parent / "GRAFIKI.md").read_text(encoding="utf-8")
        for name in ("tarcza", "krok", "finał", "plansza", "błysk"):
            self.assertIn(f"| `{name}` |", doc, name)
            self.assertIn(script.TYPES[script._fold(name)] if script.TYPES[script._fold(name)] in graphics.REGISTRY else "dial",
                          set(graphics.REGISTRY) | {"dial"})
        self.assertIn("*wyróżnienie*", doc)

    def test_the_format_name_is_the_same_everywhere(self):
        ui = (HERE.parent / "src" / "reelcut" / "data" / "ui.html").read_text(encoding="utf-8")
        self.assertIn("Motion", ui)
        for name in ("README.md", "WORKFLOW.md", "GRAFIKI.md", "MOTION.md", "CLAUDE.md"):
            self.assertTrue("Motion" in (HERE.parent / name).read_text(encoding="utf-8"), f"w {name} brakuje nazwy „Motion”")
        for name in ("README.md", "CLAUDE.md"):
            self.assertTrue("MOTION.md" in (HERE.parent / name).read_text(encoding="utf-8"), f"{name} nie odsyła do MOTION.md")


@unittest.skipUnless(HAVE_PIL and HAVE_FFMPEG, "brak Pillow albo ffmpeg")
class PipelineTests(unittest.TestCase):
    """Cały montaż trybu motion na samym głosie (ton z falowaną głośnością) i gotowej transkrypcji: bez rozpoznawania mowy."""

    TEXT = ("{tarcza: brief | nad: Formuła} Skopiuj tę formułę. Pierwsza jest {krok: Cel} cel. Druga to {krok: Miara} miara. "
            "{plansza} Ale *uwaga*. {/plansza} {finał: Gotowe} To cała formuła.")
    SECONDS = 8.0

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_motion_"))
        cls.voice = cls.tmp / "glos.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"aevalsrc='0.3*sin(2*PI*180*t)*(0.6+0.4*sin(2*PI*3*t))':s=44100:d={cls.SECONDS}", str(cls.voice)], check=True)
        cls.scenario = cls.tmp / "scenariusz.txt"
        cls.scenario.write_text(cls.TEXT, encoding="utf-8")
        words = script.parse(cls.TEXT).words
        cls.words = cls.tmp / "slowa.json"
        cls.words.write_text(json.dumps([{"w": w.lower().strip(".,"), "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(words)]),
                             encoding="utf-8")
        cls.res = run(cls.voice, cls.tmp / "film.mp4", cls.options(), log=lambda m: None)

    @classmethod
    def options(cls, **kw):
        base = dict(template="motion", graphics=cls.scenario, words_file=cls.words, captions="on", preset="ultrafast", crf=28)
        return Options(**{**base, **kw})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def frame(self, t):
        from PIL import Image

        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(self.res.output), "-frames:v", "1", "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        return Image.frombytes("RGB", (1080, 1920), raw)

    def test_voice_only_input_gives_a_vertical_film_of_the_same_length_with_sound(self):
        info = media.probe(self.res.output)
        self.assertEqual((info.width, info.height), (1080, 1920))
        self.assertAlmostEqual(info.fps, 30, delta=0.01)
        self.assertAlmostEqual(info.duration, self.SECONDS, delta=0.2)
        self.assertTrue(info.has_audio)
        self.assertEqual(self.res.plan.mode, "motion")
        self.assertFalse([w for w in self.res.warnings if "obrazu" in w], self.res.warnings)
        tags = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_space", "-of", "default=nw=1",
                               str(self.res.output)], capture_output=True, text=True).stdout
        self.assertIn("color_space=bt709", tags)

    def test_graphics_and_captions_were_drawn_from_the_script(self):
        self.assertTrue(self.res.captions_used)
        self.assertEqual(self.res.graphics["elements"], 3)  # tło (dokładane samo), tarcza i plansza; napisy liczą się osobno
        self.assertTrue(self.res.graphics["captions"])

    def test_picture_is_made_of_brand_colors_paper_then_ink_card_then_paper(self):
        near_rgb = lambda px, rgb, tol: all(abs(a - b) <= tol for a, b in zip(px, rgb))  # noqa: E731
        self.assertTrue(near_rgb(self.frame(0.4).getpixel((20, 20)), PAPER, 8))
        card_t = 0.5 * script.parse(self.TEXT).words.index("Ale") + 0.35
        self.assertTrue(near_rgb(self.frame(card_t).getpixel((20, 20)), INK, 12), self.frame(card_t).getpixel((20, 20)))
        self.assertTrue(near_rgb(self.frame(7.6).getpixel((20, 20)), PAPER, 8))

    def test_active_dot_is_yellow_in_the_closeup(self):
        at = 0.5 * script.parse(self.TEXT).words.index("cel.")
        im = self.frame(at + 0.35)
        yellow = sum(n for n, px in im.getcolors(maxcolors=1 << 22) if all(abs(a - b) <= 14 for a, b in zip(px, YELLOW)))
        self.assertGreater(yellow, 400)

    def test_dry_run_plans_without_rendering(self):
        out = self.tmp / "dry.mp4"
        res = run(self.voice, out, self.options(dry_run=True), log=lambda m: None)
        self.assertIsNone(res.output)
        self.assertFalse(out.exists())
        self.assertEqual((res.plan.mode, len(res.plan.slots)), ("motion", 1))
        self.assertIn("Grafiki", res.plan_text)
        self.assertIn("dial", res.plan_text)

    def test_video_input_works_too_but_its_picture_is_not_used(self):
        video = self.tmp / "wideo.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25", "-f", "lavfi", "-i", "sine=f=220:d=6",
                        "-t", "6", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)], check=True)
        res = run(video, None, self.options(dry_run=True, captions="off"), log=lambda m: None)
        self.assertTrue(any("tylko dźwięk" in w for w in res.warnings), res.warnings)

    def test_without_a_scenario_there_is_nothing_to_draw_so_the_run_stops_early(self):
        with self.assertRaises(media.MediaError) as cm:
            run(self.voice, None, self.options(graphics=None, dry_run=True), log=lambda m: None)
        self.assertIn("--graphics", str(cm.exception))

    def test_silent_video_is_refused_with_a_hint(self):
        silent = self.tmp / "cichy.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=5", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", str(silent)], check=True)
        with self.assertRaises(media.MediaError) as cm:
            run(silent, None, self.options(dry_run=True), log=lambda m: None)
        self.assertIn("lektora", str(cm.exception))

    def test_other_templates_still_need_a_picture(self):
        with self.assertRaises(media.MediaError) as cm:
            run(self.voice, None, Options(template="format2", dry_run=True, captions="off"), log=lambda m: None)
        self.assertIn("nie ma obrazu", str(cm.exception))

    def test_audio_extensions_are_listed_for_the_interface(self):
        for ext in (".wav", ".m4a", ".mp3"):
            self.assertIn(ext, AUDIO_EXT)


if __name__ == "__main__":
    unittest.main()
