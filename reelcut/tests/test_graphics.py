"""Warstwa grafik: marka, układ kadru, plan, elementy, renderowanie oraz wpięcie w montaż (ffmpeg, bez modelu mowy)."""
import contextlib
import importlib.util
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import captions, cli, graphics, media, style  # noqa: E402
from reelcut.graphics import core  # noqa: E402
from reelcut.graphics.render import iter_frames  # noqa: E402
from reelcut.pipeline import Options, run  # noqa: E402
from reelcut.planner import build_plan as plan_cuts  # noqa: E402
from reelcut.template import TemplateError, load_template, parse_template  # noqa: E402

HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
HAVE_ORT = all(importlib.util.find_spec(m) for m in ("numpy", "onnxruntime"))
ASSETS = HERE / "assets"
PHOTO = ASSETS / "face_nasa_astronaut.jpg"
TEMPLATE = "format2"

# kolory marki „Linia Kalewski” (z systemu marki)
VIOLET, VIOLET_DARK, YELLOW, INK = (121, 93, 255), (99, 67, 255), (255, 211, 70), (27, 20, 64)

SAMPLES = {
    "title": {"type": "title", "at": 1, "dur": 3, "text": "Content Strategy", "accent": "akcent", "style": "serif"},
    "badge": {"type": "badge", "at": 1, "dur": 3, "number": 2, "text": "Scenariusz", "zone": "top"},
    "cards": {"type": "cards", "at": 1, "dur": 4, "focus": 2, "focus_at": 1.5,
              "items": [{"label": "Jeden", "kind": "play", "bullets": ["*Ważne* punkty"]}, {"label": "Dwa", "kind": "blank"},
                        {"label": "Trzy", "image": "face_nasa_astronaut.jpg"}]},
    "profile": {"type": "profile", "at": 1, "dur": 4, "mode": "full", "label": "Info", "count": [10, 60], "unit": "s",
                "bar": [0.3, 1.0], "tag": "60 s"},
    "pills": {"type": "pills", "at": 1, "dur": 4,
              "items": [{"text": "Pierwsza", "icon": "trend", "style": "white"}, {"text": "Druga", "style": "glass"},
                        {"text": "Trzecia", "style": "accent"}, {"text": "Czwarta", "style": "yellow"}]},
    "chips": {"type": "chips", "at": 1, "dur": 4,
              "items": [{"label": "Klient", "value": 15834, "suffix": " zł"}, {"label": "Drugi", "value": 9082, "suffix": " zł"}]},
    "steps": {"type": "steps", "at": 1, "dur": 5, "active": [1.0, 2.0, 3.0],
              "items": [{"title": "Krok pierwszy", "sub": "opis"}, {"title": "Drugi", "sub": "opis"}, {"title": "Trzeci", "sub": "opis"}]},
    "axis": {"type": "axis", "at": 1, "dur": 5, "items": ["A", "B", "C", "D"]},
    "bars": {"type": "bars", "at": 1, "dur": 4, "rows": ["Pierwszy", {"label": "Drugi", "kind": "single"}, {"label": "Trzeci", "kind": "spinner"}]},
    "callout": {"type": "callout", "at": 1, "dur": 5, "icon": "bulb", "title": "Wniosek", "text": "jedna myśl na film",
                "kicker": "prosty\nwniosek", "image": "face_nasa_astronaut.jpg"},
    "stat": {"type": "stat", "at": 1, "dur": 4, "value": 700, "suffix": "+", "label": "wydarzeń"},
    "illustration": {"type": "illustration", "at": 1, "dur": 4, "image": "face_nasa_astronaut.jpg", "anchor": "head", "width": 0.2},
    "arrow": {"type": "arrow", "at": 1, "dur": 3, "from": [0.3, 0.5], "to": [0.7, 0.7], "bend": 0.2, "style": "dotted", "head": "filled"},
    "labels": {"type": "labels", "at": 1, "dur": 4, "items": [{"text": "Cel", "x": 0.25, "y": 0.12, "tx": 0.45, "ty": 0.16},
                                                              {"text": "Odbiorca", "x": 0.75, "y": 0.2, "tx": 0.55, "ty": 0.18}]},
    "text": {"type": "text", "at": 1, "dur": 4, "text": "Idealna *strategia*\n_treści_", "marker": "bracket", "reveal": "type"},
    "list": {"type": "list", "at": 1, "dur": 6, "marker": "box", "rows": [{"label": "Cel", "text": "jasny", "state": "done"}, {"text": "konkretny"}]},
    "ring": {"type": "ring", "at": 1, "dur": 4, "x": 0.5, "y": 0.5, "rx": 0.22, "dots": 24},
}


def make_ctx(size=(540, 960), words=None, layout=None):
    lay = layout or core.Layout(size[0], size[1])
    return graphics.Context(graphics.load_brand(), lay, 30, ASSETS, None, list(words or []), 20.0)


def alpha_box(layer):
    return layer.img.getchannel("A").getbbox()


def solid_box(layer):
    """Obwiednia wyraźnie widocznych pikseli (bez ledwo dostrzegalnych ogonów cienia i poświaty)."""
    return layer.img.getchannel("A").point(lambda v: 255 if v >= 24 else 0).getbbox()


class CoreTests(unittest.TestCase):
    def test_easings_start_at_zero_and_end_at_one(self):
        for name, fn in core.EASINGS.items():
            self.assertAlmostEqual(fn(0.0), 0.0, places=6, msg=name)
            self.assertAlmostEqual(fn(1.0), 1.0, places=6, msg=name)

    def test_life_envelope(self):
        before = core.life(0.5, 1.0, 3.0)
        self.assertEqual((before.k_in, before.alpha), (0.0, 0.0))
        mid = core.life(2.5, 1.0, 3.0)
        self.assertEqual((mid.k_in, mid.k_out, mid.alpha), (1.0, 1.0, 1.0))
        end = core.life(4.0, 1.0, 3.0)
        self.assertEqual(end.alpha, 0.0)
        self.assertAlmostEqual(end.lt, 3.0)

    def test_hex_rgb_parses_and_rejects(self):
        self.assertEqual(core.hex_rgb("#795DFF"), VIOLET)
        self.assertEqual(core.hex_rgb("fff"), (255, 255, 255))
        for bad in ("#12", "#GG0000", "kolor"):
            with self.assertRaises(core.PlanError):
                core.hex_rgb(bad)

    def test_default_brand_is_linia_kalewski(self):
        b = graphics.load_brand()
        self.assertEqual(b.name, "Linia Kalewski")
        self.assertEqual(b.rgb("accent"), VIOLET)
        self.assertEqual(b.rgb("badge"), VIOLET_DARK)
        self.assertEqual(b.rgb("highlight"), YELLOW)
        self.assertEqual(b.rgb("title"), YELLOW)
        self.assertEqual(b.rgb("panel"), INK)
        self.assertEqual(b.rgb("text"), (255, 255, 255))
        self.assertEqual(b.rgb("#102030"), (16, 32, 48))

    def test_brand_by_name_file_and_errors(self):
        self.assertEqual(graphics.load_brand("kalewski").name, "Linia Kalewski")
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "m.json"
            raw = json.loads((core.DEFAULT_BRAND).read_text(encoding="utf-8"))
            raw["name"] = "Inna"
            raw["colors"]["violet"] = "#112233"
            p.write_text(json.dumps(raw), encoding="utf-8")
            b = graphics.load_brand(p)
            self.assertEqual((b.name, b.rgb("accent")), ("Inna", (17, 34, 51)))
            raw["schema"] = 2
            p.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(core.PlanError):
                graphics.load_brand(p)
        with self.assertRaises(core.PlanError):
            graphics.load_brand("nie-ma-takiej")

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_brand_can_replace_the_serif_font(self):
        raw = json.loads(core.DEFAULT_BRAND.read_text(encoding="utf-8"))
        bricolage = core.FONTS_DIR / "BricolageGrotesque_800ExtraBold.ttf"
        raw["fonts"]["serif_italic"] = str(bricolage)  # ścieżka bezwzględna działa w dowolnym folderze
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "m.json"
            p.write_text(json.dumps(raw), encoding="utf-8")
            brand = graphics.load_brand(p)
            self.assertTrue(brand.font("serif_italic", 40).path.endswith("BricolageGrotesque_800ExtraBold.ttf"))
            ctx = graphics.Context(brand, core.Layout(540, 960), 30, ASSETS, None, [], 20.0)
            plan = graphics.build_plan({"elements": [SAMPLES["title"]]}, ctx)  # tytuł szeryfowy rysuje się wybranym krojem
            self.assertIsNotNone(alpha_box(graphics.render_frame(plan, 2.5, (540, 960))))

    def test_zones_keep_clear_of_the_face(self):
        for lay in (core.Layout(1080, 1920), core.Layout(1080, 1920, 0.45, 0.50, 0.14), core.Layout(1080, 1920, 0.58, 0.44, 0.18)):
            head_l = (lay.face_cx - lay.head_half_w) * lay.W
            head_r = (lay.face_cx + lay.head_half_w) * lay.W
            self.assertLessEqual(lay.zone("top")[3], lay.head_top * lay.H + 1)
            self.assertLessEqual(lay.zone("left")[2], head_l + 1)
            self.assertGreaterEqual(lay.zone("right")[0], head_r - 1)
            self.assertGreaterEqual(lay.zone("bottom")[1], lay.caption_bottom * lay.H)
            for name in ("top", "left", "right", "bottom", "captions", "head", "full"):
                x0, y0, x1, y1 = lay.zone(name)
                self.assertTrue(0 <= x0 < x1 <= lay.W and 0 <= y0 < y1 <= lay.H, name)
        with self.assertRaises(core.PlanError):
            core.Layout(1080, 1920).zone("sufit")

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_gradient_and_shadow_helpers(self):
        g = core.vgradient(20, 40, (255, 0, 0, 255), (0, 0, 255, 255))
        self.assertEqual(g.size, (20, 40))
        self.assertGreater(g.getpixel((5, 0))[0], g.getpixel((5, 39))[0])
        self.assertGreater(g.getpixel((5, 39))[2], g.getpixel((5, 0))[2])
        sprite = core.rounded_rect(30, 20, 5, fill=(255, 255, 255, 255))
        out, (ox, oy) = core.shadowed(sprite, 6, 0.6, dy=2)
        self.assertGreater(out.size[0], sprite.size[0])
        self.assertEqual(out.getpixel((ox + 15, oy + 10))[:3], (255, 255, 255))  # oryginał leży na swoim miejscu
        same, off = core.shadowed(sprite, 0, 0.6)
        self.assertIs(same, sprite)
        self.assertEqual(off, (0, 0))

    @unittest.skipUnless(HAVE_PIL, "brak Pillow")
    def test_missing_pillow_is_reported_not_crashed(self):
        old = core.HAVE_PIL
        core.HAVE_PIL = False
        try:
            with self.assertRaises(core.GraphicsUnavailable):
                graphics.build_plan({"elements": [SAMPLES["title"]]}, make_ctx())
        finally:
            core.HAVE_PIL = old


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class PlanTests(unittest.TestCase):
    def build(self, *elements, effects=()):
        return graphics.build_plan({"schema": 1, "elements": list(elements), "effects": list(effects)}, make_ctx())

    def test_every_registered_type_has_a_sample(self):
        self.assertEqual(set(SAMPLES) | {"captions"}, set(graphics.REGISTRY))

    def test_errors_are_readable_and_say_which_element(self):
        cases = [
            ({"type": "kometa", "at": 0}, "nieznany typ"),
            ({"type": "title", "text": "Bez czasu"}, "czasu startu"),
            ({"type": "title", "at": 0, "dur": 0, "text": "Zero"}, "dur"),
            ({"type": "title", "at": 0}, "text"),
            ({"type": "badge", "at": 0}, "text"),
            ({"type": "cards", "at": 0}, "items"),
            ({"type": "cards", "at": 0, "items": [{"label": "x", "kind": "hologram"}]}, "nieznany typ"),
            ({"type": "cards", "at": 0, "items": [{"label": "x"}], "focus": 4}, "focus"),
            ({"type": "cards", "at": 0, "items": [{"label": "x", "kind": "image"}]}, "image"),
            ({"type": "axis", "at": 0, "items": ["jedna"]}, "dwóch"),
            ({"type": "stat", "at": 0}, "value"),
            ({"type": "illustration", "at": 0}, "image"),
            ({"type": "illustration", "at": 0, "image": "nie_ma_takiego.png"}, "nie_ma_takiego.png"),
            ({"type": "title", "at": 0, "text": "Zła strefa", "zone": "sufit"}, None),
        ]
        for spec, needle in cases:
            with self.subTest(spec=spec):
                with self.assertRaises(core.PlanError) as cm:
                    plan = self.build(spec)
                    graphics.render_frame(plan, 0.5, (540, 960))  # strefy sprawdzane są dopiero przy rysowaniu
                if needle:
                    self.assertIn("Element 1", str(cm.exception))
                    self.assertIn(needle, str(cm.exception))

    def test_schema_and_effects_are_validated(self):
        with self.assertRaises(core.PlanError):
            graphics.build_plan({"schema": 2, "elements": []}, make_ctx())
        with self.assertRaises(core.PlanError):
            graphics.build_plan([], make_ctx())
        with self.assertRaises(core.PlanError):
            self.build(effects=[{"type": "blur", "at": 1}])
        with self.assertRaises(core.PlanError):
            self.build(effects=[{"type": "sepia", "at": 1, "dur": 1}])
        plan = self.build(effects=[{"type": "blur", "at": 1, "dur": 2}])
        self.assertEqual(plan.effects[0]["sigma"], 14.0)
        self.assertAlmostEqual(plan.duration, 3.0)

    def test_overlap_lint_flags_same_zone_in_the_same_time_only(self):
        a = dict(SAMPLES["badge"], zone="top", at=1, dur=4)
        b = dict(SAMPLES["stat"], zone="top", at=3, dur=4)
        self.assertEqual(len(self.build(a, b).warnings), 1)
        self.assertIn("strefę „top”", self.build(a, b).warnings[0])
        self.assertEqual(self.build(a, dict(b, zone="left")).warnings, [])  # inna strefa
        self.assertEqual(self.build(a, dict(b, at=5.0)).warnings, [])  # po kolei, nie naraz
        self.assertEqual(self.build(a, dict(b, x=0.5, y=0.3)).warnings, [])  # wskazane miejsce
        self.assertEqual(self.build(a, dict(SAMPLES["profile"], path=[[0, 0.2, 0.6], [2, 0.8, 0.6]], zone="top")).warnings, [])

    def test_phrases_become_times_from_the_context_transcript(self):
        words = [captions.Word("siedemset", 4.0, 4.5), captions.Word("wydarzeń", 4.6, 5.2), captions.Word("dziękuję", 9.0, 9.6)]
        raw = {"elements": [dict(SAMPLES["stat"], at="siedemset wydarzeń", until="dziękuję", zone="left")],
               "effects": [{"type": "blur", "at": "dziękuję", "dur": 1.0}]}
        plan = graphics.build_plan(raw, make_ctx(words=words))
        e = plan.elements[0]
        self.assertAlmostEqual(e.start, 4.0, places=2)
        self.assertAlmostEqual(e.end, 9.6, places=2)
        self.assertAlmostEqual(plan.effects[0]["at"], 9.0, places=2)
        self.assertIn("po słowach „siedemset wydarzeń”", plan.describe())
        with self.assertRaises(core.PlanError):
            graphics.build_plan(raw, make_ctx())  # fraza bez transkrypcji

    def test_script_steps_follow_the_spoken_phrases(self):
        from reelcut.graphics import script

        words = [captions.Word(w, i * 0.8, i * 0.8 + 0.5) for i, w in enumerate("najpierw plan potem nagranie na koniec montaż".split())]
        text = "{kroki: Plan; Nagranie; Montaż | aktywne: najpierw plan; potem nagranie; na koniec | zone: bottom} najpierw plan potem nagranie na koniec montaż"
        plan = graphics.build_plan(script.to_plan(text, words), make_ctx(words=words))
        steps = plan.elements[0]
        self.assertEqual([round(a, 2) for a in steps.active_at], [0.0, 1.6, 3.2])  # czasy względem startu elementu

    def test_files_saved_with_a_utf8_bom_are_read(self):
        words_json = json.dumps([{"w": "Dzisiaj", "start": 0.1, "end": 0.5}, {"w": "o", "start": 0.6, "end": 0.7}, {"w": "tym", "start": 0.8, "end": 1.0}])
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)  # Notatnik w starszych Windowsach zapisuje UTF-8 z BOM
            (d / "s.txt").write_bytes("\ufeff{tytuł: X} Dzisiaj o tym".encode("utf-8"))
            (d / "p.json").write_bytes(b"\xef\xbb\xbf" + json.dumps({"elements": [dict(SAMPLES["badge"], at=1)]}).encode("utf-8"))
            (d / "w.json").write_bytes(b"\xef\xbb\xbf" + words_json.encode("utf-8"))
            words = captions.load_words(d / "w.json")
            self.assertAlmostEqual(graphics.load_plan(d / "s.txt", size=(540, 960), words=words).elements[0].start, 0.1, places=2)
            self.assertAlmostEqual(graphics.load_plan(d / "p.json", size=(540, 960)).elements[0].start, 1.0, places=2)
            self.assertTrue(graphics.plan_needs_words(d / "s.txt"))

    def test_load_plan_resolves_phrases_with_the_given_words(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "p.json"
            p.write_text(json.dumps({"elements": [dict(SAMPLES["badge"], at="start")]}), encoding="utf-8")
            plan = graphics.load_plan(p, size=(540, 960), words=[captions.Word("start", 2.0, 2.4)])
            self.assertAlmostEqual(plan.elements[0].start, 2.0, places=2)

    def test_layout_notes_flag_clipped_and_face_covering_elements(self):
        clipped = self.build(dict(SAMPLES["steps"], zone="right"))
        self.assertTrue(any("nie mieści się w kadrze" in w and "„right”" in w for w in clipped.warnings), clipped.warnings)
        covers = self.build(dict(SAMPLES["title"], zone="full"))
        self.assertTrue(any("zasłania twarz" in w for w in covers.warnings), covers.warnings)
        blurred = self.build(dict(SAMPLES["title"], zone="full"), effects=[{"type": "blur", "at": 0.5, "dur": 5}])
        self.assertFalse(any("zasłania twarz" in w for w in blurred.warnings), blurred.warnings)  # rozmyty obraz tłumaczy układ
        on_head = self.build(dict(SAMPLES["title"], zone="head"), dict(SAMPLES["illustration"], at=10))
        self.assertEqual(on_head.warnings, [])  # strefa head i kotwica nad głową to świadomy wybór
        self.assertEqual(self.build(SAMPLES["stat"]).warnings, [])  # domyślne miejsca są w porządku

    def test_describe_lists_elements_in_time_order(self):
        plan = self.build(dict(SAMPLES["stat"], at=5), dict(SAMPLES["badge"], at=1))
        lines = plan.describe().splitlines()
        self.assertTrue(lines[0].strip().startswith("1.00") and "badge" in lines[0])
        self.assertTrue("stat" in lines[1])


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class RenderTests(unittest.TestCase):
    def test_every_element_draws_inside_the_frame_at_start_middle_and_end(self):
        size = (540, 960)
        for kind, spec in SAMPLES.items():
            with self.subTest(kind=kind):
                plan = graphics.build_plan({"elements": [spec]}, make_ctx(size))
                at, dur = spec["at"], spec["dur"]
                for t in (at + 0.02, at + dur / 2, at + dur - 0.05):
                    layer = graphics.render_frame(plan, t, size)
                    self.assertEqual(layer.img.size, size)
                self.assertIsNotNone(alpha_box(graphics.render_frame(plan, at + dur / 2, size)), "pusta klatka w środku życia elementu")
                self.assertFalse(plan.active(at - 0.5))
                self.assertFalse(plan.active(at + dur + 0.5))

    def test_rendering_is_deterministic(self):
        size = (540, 960)
        for kind, spec in SAMPLES.items():
            with self.subTest(kind=kind):
                plan = graphics.build_plan({"elements": [spec]}, make_ctx(size))
                t = spec["at"] + spec["dur"] / 2
                self.assertEqual(graphics.render_frame(plan, t, size).tobytes(), graphics.render_frame(plan, t, size).tobytes())

    def test_elements_animate(self):
        size = (540, 960)
        for kind in ("title", "badge", "cards", "stat", "steps", "callout"):
            spec = SAMPLES[kind]
            plan = graphics.build_plan({"elements": [spec]}, make_ctx(size))
            a = graphics.render_frame(plan, spec["at"] + 0.1, size).tobytes()
            b = graphics.render_frame(plan, spec["at"] + spec["dur"] / 2, size).tobytes()
            self.assertNotEqual(a, b, kind)

    def test_text_elements_shrink_to_fit_narrow_side_zones(self):
        size = (1080, 1920)
        lay = core.Layout(1080, 1920, 0.55, 0.40, 0.17)
        for kind, extra in (("stat", {}), ("title", {"style": "bold"}), ("badge", {})):
            for zone in ("left", "right"):
                with self.subTest(kind=kind, zone=zone):
                    spec = dict(SAMPLES[kind], zone=zone, **extra)
                    plan = graphics.build_plan({"elements": [spec]}, make_ctx(size, layout=lay))
                    x0, _, x1, _ = lay.zone(zone)
                    bb = solid_box(graphics.render_frame(plan, spec["at"] + spec["dur"] * 0.8, size))
                    self.assertGreaterEqual(bb[0], x0 - 0.03 * size[0])
                    self.assertLessEqual(bb[2], x1 + 0.03 * size[0])
                    self.assertEqual(plan.warnings, [])

    def test_three_chips_share_a_row_instead_of_overflowing(self):
        size = (1080, 1920)
        items = [{"label": f"Klient {i}", "value": 1000 * i, "suffix": " zł"} for i in (1, 2, 3)]
        plan = graphics.build_plan({"elements": [{"type": "chips", "at": 0, "dur": 5, "items": items}]}, make_ctx(size))
        bb = solid_box(graphics.render_frame(plan, 3.0, size))
        self.assertGreater(bb[0], 0)
        self.assertLess(bb[2], size[0])
        self.assertEqual(plan.warnings, [])

    def test_graphics_scale_with_the_canvas(self):
        spec = SAMPLES["badge"]
        small = graphics.render_frame(graphics.build_plan({"elements": [spec]}, make_ctx((360, 640))), 2.0, (360, 640))
        big = graphics.render_frame(graphics.build_plan({"elements": [spec]}, make_ctx((1080, 1920))), 2.0, (1080, 1920))
        ws, wb = (alpha_box(small)[2] - alpha_box(small)[0]), (alpha_box(big)[2] - alpha_box(big)[0])
        self.assertAlmostEqual(wb / ws, 3.0, delta=0.35)

    def test_title_keeps_the_exact_brand_yellow(self):
        size = (1080, 1920)
        spec = dict(SAMPLES["title"], style="bold", accent="", glow=False, shadow=0)
        plan = graphics.build_plan({"elements": [spec]}, make_ctx(size))
        im = graphics.render_frame(plan, 2.5, size).img
        colors = im.getcolors(maxcolors=1 << 20) or []
        opaque = [(n, c) for n, c in colors if c[3] == 255]
        top = max(opaque)[1][:3]
        self.assertEqual(top, YELLOW)

    def test_badge_circle_uses_the_dark_violet(self):
        size = (1080, 1920)
        plan = graphics.build_plan({"elements": [SAMPLES["badge"]]}, make_ctx(size))
        im = graphics.render_frame(plan, 2.5, size).img
        n = sum(c for c, px in (im.getcolors(maxcolors=1 << 20) or []) if px[:3] == VIOLET_DARK and px[3] == 255)
        self.assertGreater(n, 1500)

    def test_stat_counts_up_to_its_value(self):
        size = (540, 960)
        spec = dict(SAMPLES["stat"], at=0, dur=5, **{"from": 0})
        plan = graphics.build_plan({"elements": [spec]}, make_ctx(size))
        early = graphics.render_frame(plan, 0.45, size)
        late_a = graphics.render_frame(plan, 3.0, size)
        late_b = graphics.render_frame(plan, 3.5, size)
        self.assertNotEqual(early.tobytes(), late_a.tobytes())
        self.assertEqual(late_a.tobytes(), late_b.tobytes())  # liczba doszła do wartości i stoi

    def test_card_text_does_not_run_into_the_next_card(self):
        size = (1080, 1920)
        spec = {"type": "cards", "at": 0, "dur": 5, "zone": "full", "items": [
            {"label": "Pierwsza", "kind": "play", "bullets": ["Bardzo długi punkt pod kartą, który musi się zawinąć"]},
            {"label": "Druga", "kind": "play", "bullets": ["Drugi długi punkt pod drugą kartą, też do zawinięcia"]}]}
        card = graphics.build_plan({"elements": [spec]}, make_ctx(size)).elements[0]
        self.assertEqual(card.notes, [])
        for item in card.items:
            img, (x0, _) = core.compose(card._bullets(item["bullets"]))
            box = img.getchannel("A").getbbox()
            self.assertGreaterEqual(x0 + box[0], -card.gap / 2, "tekst wystaje na lewo poza kartę i połowę odstępu")
            self.assertLessEqual(x0 + box[2], card.cw + card.gap / 2, "tekst wchodzi pod sąsiednią kartę")
            self.assertGreater(box[3] - box[1], 60, "punkt powinien zawinąć się na kilka wierszy")

    def test_card_labels_can_be_serif_italic(self):
        size = (1080, 1920)
        base = {"type": "cards", "at": 0, "dur": 5, "zone": "full", "items": [{"label": "Demonstracja", "kind": "play"}, {"label": "Dowód", "kind": "play"}]}
        bold = graphics.build_plan({"elements": [base]}, make_ctx(size)).elements[0]
        serif = graphics.build_plan({"elements": [dict(base, label_style="serif")]}, make_ctx(size)).elements[0]
        self.assertNotEqual(bold.sprites[0][0].tobytes(), serif.sprites[0][0].tobytes())
        self.assertGreater(serif.label_font.size, bold.label_font.size)
        with self.assertRaises(core.PlanError):
            graphics.build_plan({"elements": [dict(base, label_style="comic")]}, make_ctx(size))
        from reelcut.graphics import script

        spec = script.parse("{karty: A; B | etykiety: serif} x").cues[0].spec
        self.assertEqual(spec["label_style"], "serif")

    def test_cards_that_do_not_fit_scale_their_text_and_warn(self):
        size = (1080, 1920)
        spec = {"type": "cards", "at": 0, "dur": 5, "items": [
            {"label": "Pierwsza", "kind": "play", "bullets": ["Bardzo długi punkt pod kartą, który musi się zawinąć"]},
            {"label": "Druga", "kind": "play", "bullets": ["Drugi długi punkt pod drugą kartą, też do zawinięcia"]}]}
        plan = graphics.build_plan({"elements": [spec]}, make_ctx(size))  # strefa top jest za niska na karty z punktami
        card = plan.elements[0]
        self.assertTrue(card.notes and any("zone: full" in w for w in plan.warnings))
        for item in card.items:
            img, (x0, _) = core.compose(card._bullets(item["bullets"]))
            box = img.getchannel("A").getbbox()
            self.assertLessEqual(x0 + box[2], card.cw + card.gap, "mimo skali tekst wchodzi pod sąsiednią kartę")

    def test_captions_follow_the_words(self):
        size = (540, 960)
        words = [captions.Word("Test", 1.0, 1.4), captions.Word("napisów", 1.5, 2.0), captions.Word("marki", 2.2, 2.6)]
        plan = graphics.build_plan({"elements": [{"type": "captions", "max_words": 1}]}, make_ctx(size, words))
        self.assertIsNone(alpha_box(graphics.render_frame(plan, 0.2, size)))  # przed mową nic
        a = graphics.render_frame(plan, 1.2, size)
        b = graphics.render_frame(plan, 1.8, size)
        self.assertIsNotNone(alpha_box(a))
        self.assertNotEqual(a.tobytes(), b.tobytes())
        top = alpha_box(a)[1]
        self.assertAlmostEqual(top / size[1], 0.548, delta=0.02)  # górna krawędź napisów jak we wzorcu
        self.assertIsNone(alpha_box(graphics.render_frame(plan, 5.0, size)))  # po mowie nic

    def test_captions_without_words_draw_nothing(self):
        plan = graphics.build_plan({"elements": [{"type": "captions"}]}, make_ctx())
        self.assertIsNone(alpha_box(graphics.render_frame(plan, 1.0, (540, 960))))

    def test_frame_stream_has_exact_byte_length_and_shares_blank_frames(self):
        size = (270, 480)
        plan = graphics.build_plan({"elements": [dict(SAMPLES["badge"], at=0.5, dur=0.6)]}, make_ctx(size))
        frames = list(iter_frames(plan, size, 10, 20))
        self.assertEqual(len(frames), 20)
        self.assertTrue(all(len(f) == size[0] * size[1] * 4 for f in frames))
        self.assertEqual(frames[0], frames[19])  # przed i po elemencie: przezroczysto
        self.assertNotEqual(frames[0], frames[8])


@unittest.skipUnless(HAVE_FFMPEG, "brak ffmpeg")
class StdinFeedTests(unittest.TestCase):
    def test_run_ffmpeg_accepts_frames_on_stdin(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "o.mp4"
            w, h, n = 64, 64, 12
            frames = (bytes([i * 20 % 256, 0, 0, 255]) * (w * h) for i in range(n))
            media.run_ffmpeg(["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-framerate", "12", "-i", "pipe:0",
                              "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], stdin_frames=frames)
            res = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                  "stream=nb_read_frames", "-of", "csv=p=0", str(out)], capture_output=True, text=True)
            self.assertEqual(res.stdout.strip(), str(n))

    def test_ffmpeg_error_while_feeding_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            frames = (bytes(64 * 64 * 4) for _ in range(5))
            with self.assertRaises(media.MediaError):
                media.run_ffmpeg(["-f", "rawvideo", "-pix_fmt", "rgba", "-s", "64x64", "-i", "pipe:0", "-c:v", "nie_ma_takiego_kodeka",
                                  str(pathlib.Path(d) / "o.mp4")], stdin_frames=frames)


class TemplateTests(unittest.TestCase):
    def test_builtin_single_take_template(self):
        tpl = load_template(TEMPLATE)
        self.assertEqual(tpl.mode, "single")
        self.assertEqual([s.role for s in tpl.segments], ["A"])
        self.assertEqual(tpl.graphics["captions"]["max_words"], 3)
        self.assertAlmostEqual(tpl.duration_s, 61.1, delta=0.05)
        reels = tpl.dynamics["reels"]
        self.assertEqual([r["id"] for r in reels], ["Dez4fPJCR74", "DeGQ3NAC2f9", "Dd2i55aj43S", "DdxAwodlOGG"])
        face = tpl.segments[0].face  # cel kadru to mediana twarzy z czterech rolek
        hs = sorted(r["face"]["h"] for r in reels)
        self.assertAlmostEqual(face.h, (hs[1] + hs[2]) / 2, delta=0.003)

    def test_single_mode_rules(self):
        raw = json.loads((HERE.parent / "src" / "reelcut" / "data" / f"{TEMPLATE}.json").read_text(encoding="utf-8"))
        two = dict(raw, segments=raw["segments"] * 2)
        with self.assertRaises(TemplateError):
            parse_template(two)
        with self.assertRaises(TemplateError):
            parse_template(dict(raw, mode="inny"))
        b = dict(raw["segments"][0], role="B")
        with self.assertRaises(TemplateError):
            parse_template(dict(raw, segments=[b]))

    def test_cuts_templates_are_unchanged(self):
        tpl = load_template()
        self.assertEqual(tpl.mode, "cuts")
        self.assertEqual(tpl.graphics, {})
        self.assertGreater(len(tpl.segments), 10)

    def test_planner_makes_one_slot_for_any_length(self):
        tpl = load_template(TEMPLATE)
        for frames in (150, 900, 4000):
            plan = plan_cuts(tpl, frames, 30)
            self.assertEqual((len(plan.slots), plan.total_frames, plan.mode), (1, frames, "jedno ujęcie"))
            s = plan.slots[0]
            self.assertEqual((s.start, s.end, s.role, s.source), (0, frames, "A", "A"))


class StyleCardTests(unittest.TestCase):
    def test_single_take_card_describes_graphics_not_cuts(self):
        text = style.describe(load_template(TEMPLATE))
        self.assertIn("Jedno ujęcie bez cięć", text)
        self.assertNotIn("cięć na minutę", text)
        self.assertIn("#795DFF", text)
        self.assertIn("#FFD346", text)
        self.assertIn("Kadr stały", text)

    def test_grafiki_md_embeds_the_current_card(self):
        text = (HERE.parent / "GRAFIKI.md").read_text(encoding="utf-8")
        start, end = "<!-- karta:start -->", "<!-- karta:end -->"
        self.assertIn(start, text)
        embedded = text.split(start, 1)[1].split(end, 1)[0].strip("\n")
        self.assertEqual(embedded, style.describe(load_template(TEMPLATE)).strip("\n"),
                         "karta w GRAFIKI.md jest nieaktualna: python rolka.py style format2 i wklej między znaczniki")

    def test_card_lists_exactly_the_registered_elements(self):
        self.assertEqual(set(style.GRAPHICS_ELEMENTS), set(graphics.REGISTRY) - {"captions"})
        text = style.describe(load_template(TEMPLATE))
        for kind in style.GRAPHICS_ELEMENTS:
            self.assertIn(f"`{kind}`", text)


@unittest.skipUnless(HAVE_PIL and HAVE_FFMPEG, "brak Pillow albo ffmpeg")
class PipelineTests(unittest.TestCase):
    """Montaż z warstwą grafik na syntetycznym nagraniu: bez rozpoznawania mowy, z gotową transkrypcją."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_gfx_"))
        cls.video = cls.tmp / "wejscie.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=25", "-f", "lavfi", "-i",
                        "sine=f=220:d=8", "-t", "8", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(cls.video)], check=True)
        cls.dark = cls.tmp / "ciemne.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x16181A:s=1080x1920:r=25", "-f", "lavfi", "-i",
                        "sine=f=220:d=8", "-t", "8", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(cls.dark)], check=True)
        cls.words = cls.tmp / "slowa.json"
        cls.words.write_text(json.dumps([{"w": "Test", "start": 1.0, "end": 1.5}, {"w": "napisów", "start": 1.6, "end": 2.3},
                                         {"w": "marki", "start": 2.4, "end": 3.0}]), encoding="utf-8")
        cls.plan = cls.tmp / "plan.json"
        cls.plan.write_text(json.dumps({"schema": 1, "elements": [
            {"type": "badge", "at": 0.5, "dur": 5, "number": 1, "text": "Scenariusz", "zone": "top"},
            {"type": "title", "at": 0.5, "dur": 5, "text": "Content Strategy", "style": "bold", "zone": "bottom"},
        ], "effects": [{"type": "blur", "at": 5.5, "dur": 2, "sigma": 14, "dim": 0.3}]}), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def render(self, src, out_name, **kw):
        opts = Options(template=TEMPLATE, framing="off", preset="ultrafast", crf=22, **kw)
        return run(src, self.tmp / out_name, opts, log=lambda m: None)

    def frame(self, video, t):
        from PIL import Image

        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        return Image.frombytes("RGB", (1080, 1920), raw)

    @staticmethod
    def near(im, rgb, tol=8, box=None):
        if box:
            im = im.crop(box)
        return sum(n for n, px in (im.getcolors(maxcolors=1 << 22) or []) if all(abs(a - b) <= tol for a, b in zip(px, rgb)))

    def test_single_take_with_graphics_keeps_length_and_brand_colors(self):
        res = self.render(self.dark, "a.mp4", graphics=self.plan, words_file=self.words, captions="on")
        self.assertEqual(res.plan.mode, "jedno ujęcie")
        self.assertEqual(len(res.plan.slots), 1)
        self.assertEqual(res.graphics["elements"], 2)
        self.assertTrue(res.graphics["captions"])
        info = media.probe(res.output)
        self.assertAlmostEqual(info.duration, 8.0, delta=0.15)
        self.assertEqual((info.width, info.height), (1080, 1920))
        tags = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_space,color_primaries,color_transfer",
                               "-of", "default=nw=1", str(res.output)], capture_output=True, text=True).stdout
        self.assertIn("color_space=bt709", tags)
        im = self.frame(res.output, 2.0)
        self.assertGreater(self.near(im, VIOLET_DARK, 10), 1500, "plakietka nie ma koloru marki po kompresji")
        self.assertGreater(self.near(im, YELLOW, 10), 1500, "tytuł nie ma koloru marki po kompresji")

    def test_running_captions_are_drawn_by_the_graphics_layer(self):
        with_words = self.render(self.dark, "b.mp4", words_file=self.words, captions="on")
        self.assertTrue(with_words.captions_used)
        self.assertFalse(with_words.graphics["elements"])
        band = (200, int(0.54 * 1920), 880, int(0.60 * 1920))
        shown = self.near(self.frame(with_words.output, 1.2), (255, 255, 255), 20, band)
        hidden = self.near(self.frame(with_words.output, 5.0), (255, 255, 255), 20, band)
        self.assertGreater(shown, 300)
        self.assertLess(hidden, 20)

    def test_without_graphics_and_captions_the_picture_is_untouched(self):
        res = self.render(self.video, "c.mp4", captions="off")
        self.assertEqual(res.graphics, {})
        info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_space", "-of", "csv=p=0",
                               str(res.output)], capture_output=True, text=True).stdout.strip()
        self.assertNotEqual(info, "bt709")  # bez grafik nie dopisujemy znaczników koloru

    def test_blur_effect_softens_the_picture_only_inside_its_window(self):
        from PIL import ImageFilter, ImageStat

        res = self.render(self.video, "d.mp4", graphics=self.plan, captions="off")

        def sharpness(t):
            crop = self.frame(res.output, t).crop((100, 700, 980, 1500)).convert("L")
            return ImageStat.Stat(crop.filter(ImageFilter.FIND_EDGES)).mean[0]

        before, inside = sharpness(4.5), sharpness(6.6)
        self.assertLess(inside, before * 0.5, f"rozmycie nie działa: {before:.1f} -> {inside:.1f}")

    def test_plan_errors_stop_the_run_with_a_readable_message(self):
        bad = self.tmp / "zly.json"
        bad.write_text(json.dumps({"elements": [{"type": "title", "at": 1}]}), encoding="utf-8")
        with self.assertRaises(media.MediaError) as cm:
            self.render(self.video, "e.mp4", graphics=bad, captions="off")
        self.assertIn("Plan grafik", str(cm.exception))
        self.assertFalse((self.tmp / "e.mp4").exists())
        notjson = self.tmp / "nie.json"
        notjson.write_text("{to nie jest json", encoding="utf-8")
        with self.assertRaises(media.MediaError):
            self.render(self.video, "f.mp4", graphics=notjson, captions="off")

    def test_dry_run_prints_the_graphics_schedule(self):
        opts = Options(template=TEMPLATE, framing="off", graphics=self.plan, dry_run=True, captions="off")
        res = run(self.video, None, opts, log=lambda m: None)
        self.assertIsNone(res.output)
        self.assertIn("Grafiki", res.plan_text)
        self.assertIn("badge", res.plan_text)

    def test_phrases_place_graphics_on_the_spoken_words_even_without_captions(self):
        plan = self.tmp / "frazy.json"
        plan.write_text(json.dumps({"elements": [{"type": "badge", "text": "Na słowo", "zone": "top", "at": "napisów", "until": "marki"}]}),
                        encoding="utf-8")
        res = self.render(self.dark, "h.mp4", graphics=plan, words_file=self.words, captions="off")
        self.assertFalse(res.captions_used)  # napisów nie chciałeś, transkrypcja posłużyła tylko do czasów
        self.assertEqual(res.graphics["elements"], 1)
        self.assertTrue(res.words_file and res.words_file.exists())
        violet = lambda t: self.near(self.frame(res.output, t), VIOLET_DARK, 10)  # noqa: E731
        self.assertLess(violet(1.3), 100)  # przed słowem „napisów” nic nie ma
        self.assertGreater(violet(2.6), 1500)  # w trakcie frazy plakietka stoi
        self.assertLess(violet(3.8), 100)  # po słowie „marki” znika

    def test_script_with_markers_places_graphics_by_the_words(self):
        sc = self.tmp / "scenariusz.txt"
        sc.write_text("# uwaga: to nie jest mowa\nTest {plakietka: Na słowo | strefa: góra} napisów marki {/plakietka} dzięki.\n", encoding="utf-8")
        res = self.render(self.dark, "l.mp4", graphics=sc, words_file=self.words, captions="off")
        self.assertEqual(res.graphics["elements"], 1)
        violet = lambda t: self.near(self.frame(res.output, t), VIOLET_DARK, 10)  # noqa: E731
        self.assertLess(violet(1.3), 100)
        self.assertGreater(violet(2.6), 1500)
        self.assertLess(violet(3.8), 100)

    def test_script_that_is_not_the_recorded_text_is_refused(self):
        sc = self.tmp / "inny.txt"
        sc.write_text("{tytuł: X} zupełnie inny tekst niż w nagraniu", encoding="utf-8")
        with self.assertRaises(media.MediaError) as cm:
            self.render(self.dark, "m.mp4", graphics=sc, words_file=self.words, captions="off")
        self.assertIn("nie pasuje do nagrania", str(cm.exception))

    def test_phrase_plan_without_a_transcript_is_refused_with_a_hint(self):
        plan = self.tmp / "frazy2.json"
        plan.write_text(json.dumps({"elements": [{"type": "badge", "text": "x", "at": "coś"}]}), encoding="utf-8")
        empty = self.tmp / "pusta.json"
        empty.write_text("[]", encoding="utf-8")
        with self.assertRaises(media.MediaError) as cm:
            self.render(self.dark, "i.mp4", graphics=plan, words_file=empty, captions="off")
        self.assertIn("transkrypcji", str(cm.exception))
        with self.assertRaises(media.MediaError) as cm:
            self.render(self.dark, "j.mp4", graphics=plan, words_file=self.tmp / "nie_ma.json", captions="off")
        self.assertIn("Nie da się wczytać transkrypcji", str(cm.exception))

    def test_phrase_plan_that_names_words_nobody_said_shows_the_closest_fragment(self):
        plan = self.tmp / "frazy3.json"
        plan.write_text(json.dumps({"elements": [{"type": "badge", "text": "x", "at": "napisow marka"}]}), encoding="utf-8")
        with self.assertRaises(media.MediaError) as cm:
            self.render(self.dark, "k.mp4", graphics=plan, words_file=self.words, captions="off")
        self.assertIn("Najbliższy fragment", str(cm.exception))

    def test_dry_run_with_phrases_resolves_them_only_with_a_transcript(self):
        plan = self.tmp / "frazy4.json"
        plan.write_text(json.dumps({"elements": [{"type": "badge", "text": "x", "at": "marki"}]}), encoding="utf-8")
        text = run(self.dark, None, Options(template=TEMPLATE, framing="off", graphics=plan, dry_run=True, captions="off"),
                   log=lambda m: None).plan_text
        self.assertIn("fraz z mowy", text)
        text = run(self.dark, None, Options(template=TEMPLATE, framing="off", graphics=plan, words_file=self.words, dry_run=True,
                                            captions="off"), log=lambda m: None).plan_text
        self.assertIn("2.40", text)
        self.assertIn("po słowach „marki”", text)

    def test_layout_warnings_and_the_schedule_reach_the_result(self):
        plan = self.tmp / "kolizja.json"
        plan.write_text(json.dumps({"elements": [
            {"type": "badge", "at": 0.5, "dur": 4, "text": "Pierwsza", "zone": "top"},
            {"type": "stat", "at": 1.0, "dur": 4, "value": 5, "zone": "top"},
            {"type": "steps", "at": 1.0, "dur": 3, "zone": "right", "items": [{"title": "Za szeroka lista"}]}]}), encoding="utf-8")
        res = self.render(self.dark, "n.mp4", graphics=plan, captions="off")
        joined = "\n".join(res.warnings)
        self.assertIn("zajmują strefę „top”", joined)
        self.assertIn("nie mieści się w kadrze", joined)
        self.assertIn("Grafiki (czasy na osi gotowego filmu)", res.plan_text)
        self.assertIn("badge", res.plan_text)
        self.assertNotIn("captions", res.plan_text.split("Grafiki (czasy", 1)[1])  # napisy biegnące nie zaśmiecają harmonogramu

    def test_plan_starting_after_the_end_is_reported(self):
        late = self.tmp / "pozno.json"
        late.write_text(json.dumps({"elements": [{"type": "badge", "at": 30, "dur": 3, "text": "Za późno"}]}), encoding="utf-8")
        logs: list[str] = []
        opts = Options(template=TEMPLATE, framing="off", preset="ultrafast", crf=30, graphics=late, captions="off")
        run(self.video, self.tmp / "g.mp4", opts, log=logs.append)
        self.assertTrue(any("po końcu filmu" in m for m in logs), logs)

    @unittest.skipUnless(HAVE_ORT, "brak numpy/onnxruntime")
    def test_avatar_is_cut_from_the_users_own_face(self):
        from reelcut import faces
        from reelcut.graphics import glue

        clip = self.tmp / "twarz.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "10", "-i", str(PHOTO), "-t", "3", "-vf",
                        "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(clip)], check=True)
        track = faces.FaceTrack(faces.sample_faces(clip, every_s=0.4))
        self.assertGreater(track.coverage(), 0.5)
        out = glue.extract_avatar(clip, track, self.tmp / "avatar.png")
        self.assertIsNotNone(out)
        from PIL import Image

        with Image.open(out) as im:
            self.assertEqual(im.size, (512, 512))
        self.assertIsNone(glue.extract_avatar(clip, None, self.tmp / "brak.png"))


def quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return cli.main(argv)


@unittest.skipUnless(HAVE_PIL and HAVE_FFMPEG, "brak Pillow albo ffmpeg")
class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_cli_"))
        cls.plan = cls.tmp / "plan.json"
        cls.plan.write_text(json.dumps({"elements": [dict(SAMPLES["badge"], at=0.2, dur=1.5)]}), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_grafiki_writes_a_single_frame_on_a_photo(self):
        from PIL import Image

        out = self.tmp / "k.png"
        code = quiet_main(["grafiki", str(self.plan), "--klatka", "1.0", "--tlo", str(PHOTO), "-o", str(out)])
        self.assertEqual(code, 0)
        with Image.open(out) as im:
            self.assertEqual(im.size, (1080, 1920))

    def test_grafiki_writes_a_preview_video(self):
        out = self.tmp / "p.mp4"
        self.assertEqual(quiet_main(["grafiki", str(self.plan), "--czas", "1", "--fps", "10", "-o", str(out)]), 0)
        self.assertAlmostEqual(media.probe(out).duration, 1.0, delta=0.15)

    def test_preview_from_an_offset_shows_the_graphics_of_that_moment(self):
        plan = self.tmp / "pozniej.json"
        plan.write_text(json.dumps({"elements": [dict(SAMPLES["badge"], at=4.0, dur=3.0)]}), encoding="utf-8")
        out = self.tmp / "od.mp4"
        self.assertEqual(quiet_main(["grafiki", str(plan), "--od", "3", "--czas", "3", "--fps", "10", "-o", str(out)]), 0)
        from PIL import Image

        def violet(t):
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True, check=True).stdout
            im = Image.frombytes("RGB", (1080, 1920), raw)
            return sum(n for n, px in (im.getcolors(maxcolors=1 << 22) or []) if all(abs(a - b) <= 10 for a, b in zip(px, VIOLET_DARK)))

        self.assertLess(violet(0.3), 100)  # w 3,3 s filmu plakietki jeszcze nie ma
        self.assertGreater(violet(1.6), 1500)  # w 4,6 s jest

    def test_grafiki_reports_missing_plan_and_unreachable_background_time(self):
        self.assertEqual(quiet_main(["grafiki", str(self.tmp / "brak.json")]), 2)
        clip = self.tmp / "krotki.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=270x480:d=1", "-pix_fmt", "yuv420p", str(clip)],
                       check=True)
        self.assertEqual(quiet_main(["grafiki", str(self.plan), "--klatka", "50", "--tlo", str(clip), "-o", str(self.tmp / "x.png")]), 1)

    def test_cut_accepts_graphics_and_brand_flags(self):
        parser = cli.build_parser()
        args = parser.parse_args(["cut", "a.mp4", "--graphics", "p.json", "--brand", "kalewski"])
        self.assertEqual((str(args.graphics), args.brand), ("p.json", "kalewski"))


if __name__ == "__main__":
    unittest.main()
