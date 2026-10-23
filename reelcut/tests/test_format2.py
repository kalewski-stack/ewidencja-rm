"""Elementy Formatu 2 (gadająca głowa): strzałka, opisy, tekst, lista, pierścień, karty w dowolnym miejscu, ruchoma ilustracja
i ich składnia w scenariuszu ze znacznikami."""
import importlib.util
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import graphics  # noqa: E402
from reelcut.graphics import core, script  # noqa: E402
from reelcut.graphics.core import PlanError  # noqa: E402
from reelcut.graphics.extras import Keys  # noqa: E402

HAVE_PIL = importlib.util.find_spec("PIL") is not None
ASSETS = HERE / "assets"
YELLOW = (255, 211, 70)
VIOLET_DARK = (99, 67, 255)
SIZE = (540, 960)


def ctx(size=SIZE):
    return graphics.Context(graphics.load_brand(), core.Layout(*size), 30, ASSETS, None, [], 20.0)


def plan_of(*elements, size=SIZE):
    return graphics.build_plan({"schema": 1, "elements": list(elements)}, ctx(size))


def frame(plan, t, size=SIZE):
    return graphics.render_frame(plan, t, size)


def solid(layer):
    """Obwiednia wyraźnie widocznych pikseli."""
    return layer.img.getchannel("A").point(lambda v: 255 if v >= 24 else 0).getbbox()


def body(layer):
    """Obwiednia samego korpusu (bez cienia i poświaty): tylko prawie nieprzezroczyste piksele."""
    return layer.img.getchannel("A").point(lambda v: 255 if v >= 200 else 0).getbbox()


def count_color(layer, rgb, tol=14):
    """Ile pikseli ma kolor rgb (z tolerancją) i jest prawie nieprzezroczystych."""
    n = 0
    for r, g, b, a in layer.img.getdata():
        if a >= 200 and abs(r - rgb[0]) <= tol and abs(g - rgb[1]) <= tol and abs(b - rgb[2]) <= tol:
            n += 1
    return n


def center(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class ArrowTests(unittest.TestCase):
    SPEC = {"type": "arrow", "at": 0, "dur": 3, "from": [0.2, 0.5], "to": [0.8, 0.5], "bend": 0.0, "draw": 1.0, "head": "filled"}

    def test_line_is_drawn_progressively_from_start_to_end(self):
        plan = plan_of(self.SPEC)
        early, mid, late = (solid(frame(plan, t)) for t in (0.3, 0.6, 1.6))
        self.assertIsNotNone(early)
        self.assertLess(early[2], mid[2])
        self.assertLess(mid[2], late[2])
        self.assertAlmostEqual(late[2], 0.8 * SIZE[0], delta=0.04 * SIZE[0])  # grot kończy się w punkcie docelowym
        self.assertAlmostEqual(early[0], 0.2 * SIZE[0], delta=0.04 * SIZE[0])  # a zaczyna w początkowym

    def test_bend_curves_the_line_away_from_the_straight_path(self):
        straight = solid(frame(plan_of(self.SPEC), 1.8))
        curved = solid(frame(plan_of(dict(self.SPEC, bend=0.3)), 1.8))
        self.assertGreater(curved[3] - curved[1], straight[3] - straight[1] + 20)

    def test_styles_and_heads_differ_and_unknown_ones_are_refused(self):
        solid_im = frame(plan_of(self.SPEC), 1.8).tobytes()
        for style in ("dashed", "dotted"):
            self.assertNotEqual(solid_im, frame(plan_of(dict(self.SPEC, style=style)), 1.8).tobytes(), style)
        self.assertNotEqual(solid_im, frame(plan_of(dict(self.SPEC, head="none")), 1.8).tobytes())
        for bad in ({"style": "wavy"}, {"head": "round"}):
            with self.assertRaises(PlanError):
                plan_of(dict(self.SPEC, **bad))

    def test_endpoints_are_required(self):
        with self.assertRaises(PlanError):
            plan_of({"type": "arrow", "at": 0, "from": [0.2, 0.5]})
        with self.assertRaises(PlanError):
            plan_of({"type": "arrow", "at": 0, "from": [0.2], "to": [0.5, 0.5]})

    def test_arrow_may_point_at_the_face_without_a_warning(self):
        plan = plan_of(dict(self.SPEC, **{"from": [0.1, 0.45], "to": [0.45, 0.45]}))
        self.assertFalse(any("zasłania" in w for w in plan.warnings), plan.warnings)


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class LabelsTests(unittest.TestCase):
    SPEC = {"type": "labels", "at": 0, "dur": 5, "stagger": 1.0,
            "items": [{"text": "Cel", "x": 0.25, "y": 0.12, "tx": 0.45, "ty": 0.16},
                      {"text": "Odbiorca", "x": 0.75, "y": 0.2, "tx": 0.55, "ty": 0.18}]}

    def test_labels_appear_one_after_another(self):
        plan = plan_of(self.SPEC)
        first, both = solid(frame(plan, 0.7)), solid(frame(plan, 3.0))
        self.assertLess(first[2], 0.55 * SIZE[0])  # po pół sekundy tylko lewy opis
        self.assertGreater(both[2], 0.7 * SIZE[0])  # potem dochodzi prawy

    def test_item_needs_text_and_position(self):
        for bad in ({"text": "x"}, {"x": 0.2, "y": 0.2}, {"text": "x", "x": 0.2}):
            with self.assertRaises(PlanError):
                plan_of(dict(self.SPEC, items=[bad]))
        with self.assertRaises(PlanError):
            plan_of(dict(self.SPEC, items=[]))

    def test_a_label_without_a_target_has_no_line(self):
        plain = plan_of(dict(self.SPEC, items=[{"text": "Sam napis", "x": 0.5, "y": 0.1}]))
        pointing = plan_of(dict(self.SPEC, items=[{"text": "Sam napis", "x": 0.5, "y": 0.1, "tx": 0.5, "ty": 0.3}]))
        self.assertGreater(solid(frame(pointing, 3.0))[3], solid(frame(plain, 3.0))[3] + 40)


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class RichTextTests(unittest.TestCase):
    SPEC = {"type": "text", "at": 0, "dur": 4, "text": "Idealna *strategia*", "x": 0.5, "y": 0.2, "size": 0.08}

    def test_highlight_uses_the_brand_yellow(self):
        with_mark = count_color(frame(plan_of(self.SPEC), 2.0), YELLOW)
        without = count_color(frame(plan_of(dict(self.SPEC, text="Idealna strategia")), 2.0), YELLOW)
        self.assertGreater(with_mark, 300)
        self.assertEqual(without, 0)

    def test_typing_reveals_the_text_over_time(self):
        plan = plan_of(dict(self.SPEC, reveal="type", cps=10))
        a, b = solid(frame(plan, 0.8)), solid(frame(plan, 3.0))
        self.assertLess(a[2] - a[0], b[2] - b[0])

    def test_lines_break_on_backslash_n_and_on_new_lines(self):
        one = solid(frame(plan_of(dict(self.SPEC, text="Raz dwa")), 2.0))
        for text in ("Raz\\ndwa", "Raz\ndwa"):
            two = solid(frame(plan_of(dict(self.SPEC, text=text)), 2.0))
            self.assertGreater(two[3] - two[1], (one[3] - one[1]) * 1.6, repr(text))

    def test_markers_add_a_drawing_and_unknown_values_are_refused(self):
        plain = frame(plan_of(self.SPEC), 3.0).tobytes()
        for marker in ("underline", "brush", "bracket"):
            self.assertNotEqual(plain, frame(plan_of(dict(self.SPEC, marker=marker)), 3.0).tobytes(), marker)
        for bad in ({"marker": "wavy"}, {"reveal": "zoom"}, {"font": "comic"}, {"text": "  "}):
            with self.assertRaises(PlanError):
                plan_of(dict(self.SPEC, **bad))

    def test_serif_runs_use_a_different_face(self):
        a = frame(plan_of(dict(self.SPEC, text="treści")), 2.0).tobytes()
        b = frame(plan_of(dict(self.SPEC, text="_treści_")), 2.0).tobytes()
        self.assertNotEqual(a, b)

    def test_runs_parse_marks_into_styles(self):
        from reelcut.graphics.format2 import parse_runs

        self.assertEqual(parse_runs("a *b* _c_"), [[("a ", ""), ("b", "hi"), (" ", ""), ("c", "serif")]])
        self.assertEqual(len(parse_runs("x\\ny\nz")), 3)


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class ListTests(unittest.TestCase):
    ROWS = {"type": "list", "at": 0, "dur": 8, "x": 0.08, "y": 0.1, "width": 0.84, "stagger": 1.0, "marker": "dot",
            "rows": [{"label": "Cel", "text": "jasny"}, {"label": "Odbiorca", "text": "konkretny"}, {"text": "bez etykiety"}]}

    def test_rows_arrive_one_by_one(self):
        plan = plan_of(self.ROWS)
        heights = [solid(frame(plan, t))[3] for t in (0.9, 2.2, 3.6)]
        self.assertLess(heights[0], heights[1])
        self.assertLess(heights[1], heights[2])

    def test_plain_string_rows_are_accepted(self):
        plan = plan_of(dict(self.ROWS, rows=["pierwszy", "drugi"]))
        self.assertIsNotNone(solid(frame(plan, 4.0)))

    def test_columns_make_a_comparison_with_a_rule_between_them(self):
        spec = {"type": "list", "at": 0, "dur": 8, "x": 0.06, "y": 0.1, "width": 0.88, "rule": True, "rule_to": 0.6,
                "columns": [{"title": "Stare", "rows": [{"text": "raz"}, {"text": "dwa"}]}, {"title": "Nowe", "rows": [{"text": "trzy"}]}]}
        with_rule = frame(plan_of(spec), 4.0)
        no_rule = frame(plan_of(dict(spec, rule=False)), 4.0)
        self.assertGreater(solid(with_rule)[3], solid(no_rule)[3] + 40)  # kreska schodzi niżej niż tekst
        self.assertGreater(solid(with_rule)[2], 0.7 * SIZE[0])  # druga kolumna stoi po prawej

    def test_a_done_row_gets_its_check_mark_after_it_is_written(self):
        spec = dict(self.ROWS, marker="box", rows=[{"label": "Cel", "text": "jasny", "state": "done"}])
        plan = plan_of(spec)
        before, after = frame(plan, 0.9), frame(plan, 3.0)
        self.assertEqual(count_color(before, VIOLET_DARK), 0)  # puste pole nie ma wypełnienia
        self.assertGreater(count_color(after, VIOLET_DARK), 100)  # odhaczone to fioletowe koło z ptaszkiem
        open_row = plan_of(dict(spec, rows=[{"label": "Cel", "text": "jasny"}]))
        self.assertEqual(count_color(frame(open_row, 3.0), VIOLET_DARK), 0)

    def test_invalid_input_is_refused(self):
        for bad in ({"rows": []}, {"rows": None}, {"marker": "star"}, {"text_font": "comic"},
                    {"rows": None, "columns": [{"title": "A"}]}):
            with self.assertRaises(PlanError, msg=str(bad)):
                plan_of(dict(self.ROWS, **bad))


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class RingTests(unittest.TestCase):
    SPEC = {"type": "ring", "at": 0, "dur": 4, "x": 0.5, "y": 0.5, "rx": 0.3, "dots": 24}

    def test_dots_appear_gradually_around_the_center(self):
        plan = plan_of(self.SPEC)
        early, late = solid(frame(plan, 0.2)), solid(frame(plan, 2.5))
        self.assertLess((early[2] - early[0]) * (early[3] - early[1]), (late[2] - late[0]) * (late[3] - late[1]))
        cx, cy = center(late)
        self.assertAlmostEqual(cx, 0.5 * SIZE[0], delta=0.03 * SIZE[0])
        self.assertAlmostEqual(cy, 0.5 * SIZE[1], delta=0.03 * SIZE[1])
        self.assertAlmostEqual(late[2] - late[0], 0.6 * SIZE[0], delta=0.05 * SIZE[0])

    def test_arcs_leave_part_of_the_circle_empty(self):
        full = solid(frame(plan_of(self.SPEC), 2.5))
        right = solid(frame(plan_of(dict(self.SPEC, arcs=[[40, 140]])), 2.5))  # kąty: 0 to góra, rosną zgodnie ze wskazówkami zegara
        self.assertGreater(center(right)[0], center(full)[0] + 0.05 * SIZE[0])
        top = solid(frame(plan_of(dict(self.SPEC, arcs=[[-60, 60]])), 2.5))
        self.assertLess(center(top)[1], center(full)[1] - 0.05 * SIZE[1])

    def test_center_is_required(self):
        with self.assertRaises(PlanError):
            plan_of({"type": "ring", "at": 0, "rx": 0.2})


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class FreeCardsTests(unittest.TestCase):
    def card(self, **item):
        item = dict({"kind": "play", "x": 0.3, "y": 0.4, "w": 0.2}, **item)
        return plan_of({"type": "cards", "at": 0, "dur": 6, "float": False, "items": [item]}, size=(1080, 1920))

    def test_a_card_with_x_and_y_stands_where_it_is_told(self):
        plan = self.card()
        box = body(frame(plan, 3.0, (1080, 1920)))
        cx, cy = center(box)
        self.assertAlmostEqual(cx, 0.3 * 1080, delta=8)
        self.assertAlmostEqual(cy, 0.4 * 1920, delta=8)
        self.assertAlmostEqual(box[2] - box[0], 0.2 * 1080, delta=10)  # w to szerokość karty

    def test_rotation_turns_the_card_around_its_own_center(self):
        flat = body(frame(self.card(), 3.0, (1080, 1920)))
        tilted = body(frame(self.card(rot=10), 3.0, (1080, 1920)))
        self.assertGreater(tilted[2] - tilted[0], flat[2] - flat[0] + 20)
        self.assertAlmostEqual(center(tilted)[0], center(flat)[0], delta=10)
        self.assertAlmostEqual(center(tilted)[1], center(flat)[1], delta=10)

    def test_view_count_sits_under_the_card_with_an_eye(self):
        with_views = body(frame(self.card(views="153K"), 3.0, (1080, 1920)))
        without = body(frame(self.card(), 3.0, (1080, 1920)))
        self.assertGreater(with_views[3], without[3] + 20)  # licznik z okiem stoi pod kartą
        self.assertEqual(with_views[1], without[1])  # a sama karta się nie rusza

    def test_label_styles_per_card(self):
        size = (1080, 1920)
        base = self.card(label="Nowy temat")
        yellow = self.card(label="Nowy temat", label_style="yellow")
        self.assertEqual(count_color(frame(base, 3.0, size), YELLOW), 0)
        self.assertGreater(count_color(frame(yellow, 3.0, size), YELLOW), 100)
        serif = self.card(label="Nowy temat", label_style="serif")
        self.assertNotEqual(frame(base, 3.0, size).tobytes(), frame(serif, 3.0, size).tobytes())
        with self.assertRaises(PlanError):
            self.card(label_style="comic")

    def test_free_and_flowing_cards_mix(self):
        plan = plan_of({"type": "cards", "at": 0, "dur": 6, "float": False, "zone": "bottom", "card_w": 0.2,
                        "items": [{"kind": "play", "label": "A"}, {"kind": "play", "label": "B"},
                                  {"kind": "blank", "x": 0.8, "y": 0.2, "w": 0.18}]}, size=(1080, 1920))
        layer = frame(plan, 4.0, (1080, 1920))
        top_right = layer.img.crop((int(0.7 * 1080), int(0.1 * 1920), 1080, int(0.3 * 1920))).getchannel("A").getbbox()
        bottom = layer.img.crop((0, int(0.6 * 1920), 1080, 1920)).getchannel("A").getbbox()
        self.assertIsNotNone(top_right, "wolna karta nie stoi w wybranym miejscu")
        self.assertIsNotNone(bottom, "karty w strefie bottom zniknęły")

    def test_cards_that_all_stand_where_told_do_not_collide_with_the_zone(self):
        title = {"type": "title", "at": 0, "dur": 5, "text": "Tytuł", "zone": "top"}
        free = {"type": "cards", "at": 0, "dur": 5, "items": [{"kind": "play", "x": 0.3, "y": 0.2, "w": 0.2}]}
        flowing = {"type": "cards", "at": 0, "dur": 5, "items": [{"kind": "play"}, {"kind": "play"}]}
        self.assertFalse(any("strefę" in w for w in plan_of(title, free, size=(1080, 1920)).warnings))
        self.assertTrue(any("strefę" in w for w in plan_of(title, flowing, size=(1080, 1920)).warnings))

    def test_a_card_can_appear_at_its_own_time(self):
        spec = {"type": "cards", "at": 0, "dur": 6, "float": False,
                "items": [{"kind": "play", "x": 0.25, "y": 0.4, "w": 0.2, "at": 0.0}, {"kind": "play", "x": 0.75, "y": 0.4, "w": 0.2, "at": 2.5}]}
        plan = plan_of(spec, size=(1080, 1920))
        early, late = solid(frame(plan, 1.5, (1080, 1920))), solid(frame(plan, 4.0, (1080, 1920)))
        self.assertLess(early[2], 0.5 * 1080)
        self.assertGreater(late[2], 0.8 * 1080)


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class IllustrationPathTests(unittest.TestCase):
    PATH = [[0, 0.25, 0.2], [2, 0.75, 0.2, 1.0, 0], [4, 0.75, 0.6, 1.5, 12]]
    SPEC = {"type": "illustration", "at": 0, "dur": 6, "image": "face_nasa_astronaut.jpg", "width": 0.2, "glow": False,
            "float": False, "in": 0.01, "out": 0.01}

    def test_keys_interpolate_position_scale_and_rotation(self):
        k = Keys(self.PATH)
        self.assertEqual(k.at(-1.0), (0.25, 0.2, 1.0, 0.0))  # przed pierwszym kluczem stoi na nim
        self.assertEqual(k.at(9.0), (0.75, 0.6, 1.5, 12.0))  # po ostatnim zostaje
        x, y, sc, rot = k.at(1.0)  # w połowie pierwszego odcinka (łagodny start i hamowanie: dokładnie pośrodku)
        self.assertAlmostEqual(x, 0.5)
        self.assertAlmostEqual(y, 0.2)
        self.assertAlmostEqual(sc, 1.0)
        self.assertAlmostEqual(rot, 0.0)
        _, _, sc2, rot2 = k.at(3.0)
        self.assertAlmostEqual(sc2, 1.25)
        self.assertAlmostEqual(rot2, 6.0)

    def test_keys_are_validated(self):
        for bad in (None, [], [[0, 0.1, 0.1]], [[0, 0.1], [1, 0.2, 0.2]], [[0, 0.1, 0.1], [1, 0.2, 0.2, 0]], [[0, "a", 0.1], [1, 0.2, 0.2]],
                    [[0, 0, 0, 1, 0, 9], [1, 0.2, 0.2]], "abc"):
            with self.assertRaises(PlanError, msg=str(bad)):
                Keys(bad)

    def test_illustration_travels_along_the_path(self):
        size = (540, 960)
        plan = plan_of(dict(self.SPEC, path=self.PATH), size=size)
        start, mid, end = (center(solid(frame(plan, t, size))) for t in (0.05, 2.0, 5.0))
        self.assertAlmostEqual(start[0], 0.25 * 540, delta=25)
        self.assertAlmostEqual(mid[0], 0.75 * 540, delta=25)
        self.assertAlmostEqual(end[1], 0.6 * 960, delta=35)
        grown = solid(frame(plan, 5.0, size))
        small = solid(frame(plan, 2.0, size))
        self.assertGreater(grown[2] - grown[0], (small[2] - small[0]) * 1.3)

    def test_static_rotation_and_opacity(self):
        size = (540, 960)
        flat = plan_of(dict(self.SPEC, x=0.5, y=0.3), size=size)
        tilted = plan_of(dict(self.SPEC, x=0.5, y=0.3, rot=20), size=size)
        faint = plan_of(dict(self.SPEC, x=0.5, y=0.3, opacity=0.4), size=size)
        a, b = solid(frame(flat, 3.0, size)), solid(frame(tilted, 3.0, size))
        self.assertGreater(b[2] - b[0], a[2] - a[0])
        alpha_full = max(frame(flat, 3.0, size).img.getchannel("A").getdata())
        alpha_faint = max(frame(faint, 3.0, size).img.getchannel("A").getdata())
        self.assertEqual(alpha_full, 255)
        self.assertAlmostEqual(alpha_faint, 0.4 * 255, delta=3)

    def test_bleed_allows_an_image_to_leave_the_frame(self):
        spec = dict(self.SPEC, x=0.95, y=0.3, width=0.3)
        loud = plan_of(spec)
        quiet = plan_of(dict(spec, bleed=True))
        self.assertTrue(any("nie mieści się w kadrze" in w for w in loud.warnings), loud.warnings)
        self.assertFalse(any("nie mieści się w kadrze" in w for w in quiet.warnings), quiet.warnings)

    def test_moving_illustration_is_not_a_zone_collision(self):
        plan = plan_of(dict(self.SPEC, path=self.PATH), dict(self.SPEC, path=self.PATH, at=1))
        self.assertEqual(plan.warnings, [])


class ScenarioSyntaxTests(unittest.TestCase):
    def cue(self, text):
        return script.parse(text + " a").cues[0].spec

    def test_text_marker(self):
        spec = self.cue("{tekst: Idealna *strategia*\\ntreści | rozmiar: 7% | zaznaczenie: nawias | odsłanianie: pisanie | kolor: text | x: 50% | y: 86%}")
        self.assertEqual(spec["type"], "text")
        self.assertEqual(spec["text"], "Idealna *strategia*\\ntreści")
        self.assertEqual((spec["size"], spec["marker"], spec["reveal"], spec["x"], spec["y"]), (0.07, "bracket", "type", 0.5, 0.86))
        self.assertEqual(spec["color"], "text")
        self.assertEqual(self.cue("{tekst: x | krój: szeryf}")["font"], "serif_italic")
        self.assertEqual(self.cue("{text: x | marker: brush}")["marker"], "brush")

    def test_arrow_marker_takes_points_in_fractions_and_percent(self):
        spec = self.cue("{strzałka: | od: 0,3; 0,5 | cel: 60% 70% | łuk: -0,2 | styl: kropkowana | grot: pełny | grubość: 0,005}")
        self.assertEqual(spec["type"], "arrow")
        self.assertEqual(spec["from"], [0.3, 0.5])
        self.assertEqual(spec["to"], [0.6, 0.7])
        self.assertEqual((spec["bend"], spec["style"], spec["head"], spec["width"]), (-0.2, "dotted", "filled", 0.005))
        for bad in ("{strzałka: | od: 0,3 | cel: 0,6; 0,7}", "{strzałka: | od: a; b | cel: 0,6; 0,7}", "{strzałka: | od: 1;2;3 | cel: 0,6; 0,7}"):
            with self.assertRaises(PlanError, msg=bad):
                script.parse(bad + " a")

    def test_labels_marker(self):
        spec = self.cue("{opisy: Cel @ 20% 12% > 42% 15%; Odbiorca @ 0,22 0,22 | kolor: highlight | linia: brak}")
        self.assertEqual(spec["items"][0], {"text": "Cel", "x": 0.2, "y": 0.12, "tx": 0.42, "ty": 0.15})
        self.assertEqual(spec["items"][1], {"text": "Odbiorca", "x": 0.22, "y": 0.22})
        self.assertEqual((spec["color"], spec["line"]), ("highlight", "none"))
        for bad in ("{opisy: Cel}", "{opisy: Cel @ 20%}", "{opisy: @ 1 2}"):
            with self.assertRaises(PlanError, msg=bad):
                script.parse(bad + " a")

    def test_list_marker_rows_and_checks(self):
        spec = self.cue("{lista: + Cel = jasny / z liczbą; Odbiorca = konkretny; sam tekst | zaznaczenie: ramka | pismo: zwykły | x: 8% | y: 10%}")
        self.assertEqual(spec["rows"][0], {"text": "jasny", "label": "Cel", "detail": "z liczbą", "state": "done"})
        self.assertEqual(spec["rows"][1], {"text": "konkretny", "label": "Odbiorca"})
        self.assertEqual(spec["rows"][2], {"text": "sam tekst"})
        self.assertEqual((spec["marker"], spec["text_font"], spec["x"], spec["y"]), ("box", "plain", 0.08, 0.1))

    def test_comparison_marker_makes_columns(self):
        spec = self.cue("{porównanie: Stare: raz; dwa // Nowe: + trzy | rule: tak}")
        self.assertEqual([c["title"] for c in spec["columns"]], ["Stare", "Nowe"])
        self.assertEqual([r["text"] for r in spec["columns"][0]["rows"]], ["raz", "dwa"])
        self.assertEqual(spec["columns"][1]["rows"][0]["state"], "done")
        self.assertNotIn("rows", spec)
        with self.assertRaises(PlanError):
            script.parse("{porównanie: bez dwukropka} a")

    def test_ring_marker_with_arcs(self):
        spec = self.cue("{pierścień: | x: 50% | y: 50% | rx: 22% | ry: 11,5% | kropki: 30 | luki: 100..260; -80..80}")
        self.assertEqual(spec["type"], "ring")
        self.assertEqual((spec["x"], spec["y"], spec["rx"], spec["ry"], spec["dots"]), (0.5, 0.5, 0.22, 0.115, 30))
        self.assertEqual(spec["arcs"], [[100.0, 260.0], [-80.0, 80.0]])
        with self.assertRaises(PlanError):
            script.parse("{pierścień: | luki: dużo} a")

    def test_cards_views_and_label_style(self):
        spec = self.cue("{karty: A; B; C | wyświetlenia: 153K; ; 12,4K | etykiety: żółte}")
        self.assertEqual([i.get("views") for i in spec["items"]], ["153K", None, "12,4K"])
        self.assertEqual(spec["label_style"], "yellow")
        self.assertEqual(self.cue("{karty: A | etykiety: szeryf}")["label_style"], "serif")

    def test_illustration_flags(self):
        spec = self.cue("{ilustracja: foto.png | obrót: -6 | przezroczystość: 80% | za: tak | wystaje: tak | x: 80% | y: 20%}")
        self.assertEqual((spec["rot"], spec["opacity"], spec["behind"], spec["bleed"]), (-6, 0.8, True, True))
        self.assertEqual((spec["x"], spec["y"]), (0.8, 0.2))

    def test_percent_stays_text_where_it_is_not_a_position(self):
        spec = self.cue("{tytuł: Zysk 100% | akcent: 100%}")
        self.assertEqual(spec["accent"], "100%")
        self.assertEqual(spec["text"], "Zysk 100%")

    def test_every_new_marker_becomes_a_working_element(self):
        text = ("Pierwsza myśl {tekst: Hak *dnia* | y: 20%} druga myśl {strzałka: | od: 20% 40% | cel: 60% 50%} trzecia "
                "{opisy: Cel @ 25% 12% > 45% 16%} czwarta {lista: Cel = jasny; Plan = prosty} piąta {pierścień: | x: 50% | y: 50% | rx: 25%} koniec.")
        words = script.parse(text).words
        spoken = [type("W", (), {"text": w, "start": i * 0.5, "end": i * 0.5 + 0.4})() for i, w in enumerate(words)]
        raw = script.to_plan(text, spoken)
        self.assertEqual([e["type"] for e in raw["elements"]], ["text", "arrow", "labels", "list", "ring"])
        starts = [e["at"] for e in raw["elements"]]
        self.assertEqual(starts, sorted(starts))
        if HAVE_PIL:
            for spec in raw["elements"]:
                plan = graphics.build_plan({"schema": 1, "elements": [spec]}, ctx())
                e = plan.elements[0]
                self.assertIsNotNone(solid(frame(plan, e.start + min(2.0, e.dur * 0.7))), spec["type"])



class FakeWord:
    def __init__(self, text, start, end):
        self.text, self.start, self.end = text, start, end


def spoken_at(words, per_s=4.2):
    step = 1 / per_s
    return [FakeWord(w, i * step, i * step + step * 0.8) for i, w in enumerate(words)]


def fenced(path, marker):
    """Zawartość bloku kodu między znacznikami <!-- marker:start --> i <!-- marker:end --> w pliku dokumentacji."""
    text = (HERE.parent / path).read_text(encoding="utf-8")
    block = text.split(f"<!-- {marker}:start -->", 1)[1].split(f"<!-- {marker}:end -->", 1)[0]
    return block.split("```", 2)[1].split("\n", 1)[1]


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class DocsTests(unittest.TestCase):
    def test_example_scenario_in_format2_md_builds_without_warnings(self):
        text = fenced("FORMAT2.md", "scenariusz")
        words = script.parse(text).words
        raw = script.to_plan(text, spoken_at(words))
        plan = graphics.build_plan(raw, ctx((1080, 1920)))
        self.assertEqual([e.kind for e in plan.elements], ["title", "list", "text", "stat", "arrow", "list", "text"])
        self.assertEqual(plan.warnings, [])
        columns = plan.elements[1].spec["columns"]
        self.assertEqual([c["title"] for c in columns], ["Marketing", "HR"])
        self.assertIn("done", [r.get("state") for r in plan.elements[5].spec["rows"]])

    def test_json_plan_in_grafiki_md_builds(self):
        import json
        import tempfile

        from PIL import Image

        raw = json.loads(fenced("GRAFIKI.md", "plan-f2"))
        with tempfile.TemporaryDirectory() as tmp:
            for name, mode in (("schemat.png", "RGBA"), ("a.jpg", "RGB")):
                Image.new(mode, (300, 200), (121, 93, 255) + ((255,) if mode == "RGBA" else ())).save(pathlib.Path(tmp) / name)
            c = graphics.Context(graphics.load_brand(), core.Layout(1080, 1920), 30, pathlib.Path(tmp), None, [], 30.0)
            plan = graphics.build_plan(raw, c)
            self.assertEqual([e.kind for e in plan.elements], ["illustration", "cards", "arrow", "ring"])
            self.assertTrue(plan.elements[0].behind)
            self.assertEqual(plan.warnings, [])
            for e in plan.elements:
                self.assertIsNotNone(solid(graphics.render_frame(plan, e.start + min(3.0, e.dur * 0.6), (1080, 1920))), e.kind)

    def test_numbers_in_format2_md_match_the_template(self):
        from reelcut import style
        from reelcut.template import load_template

        tpl = load_template("format2")
        text = (HERE.parent / "FORMAT2.md").read_text(encoding="utf-8").replace("\u2212", "-")
        d, face = tpl.dynamics, tpl.dynamics["face"]
        want = [f"{style._n(face['h'] * 100)}%", f"{style._n(face['cx'] * 100)}%", f"{style._n(face['cy'] * 100)}%",
                f"{style._n(tpl.segments[0].face.eye_y * 100)}%",
                f"{style._n(tpl.graphics['captions']['y'] * 100)}%", f"{style._n(d['loudness']['lufs'])} LUFS",
                f"{style._n(d['loudness']['lra'])} LU", f"{style._n(d['loudness']['true_peak'])} dBTP", f"{round(d['duration_s'])} s",
                style._n(d["words_per_s"])]
        missing = [w for w in want if w.replace("\u2212", "-") not in text]
        self.assertEqual(missing, [], "liczby w FORMAT2.md rozjechały się z szablonem format2")

    def test_every_new_marker_is_documented(self):
        doc = (HERE.parent / "GRAFIKI.md").read_text(encoding="utf-8")
        for name in ("tekst", "strzałka", "opisy", "lista", "porównanie", "pierścień"):
            self.assertIn(f"| `{name}` |", doc, name)
            self.assertIn(script.TYPES[script._fold(name)], graphics.REGISTRY)

    def test_the_format_name_is_the_same_everywhere(self):
        ui = (HERE.parent / "src" / "reelcut" / "data" / "ui.html").read_text(encoding="utf-8")
        self.assertIn("Format 2: gadająca głowa", ui)
        self.assertNotIn("Rolka Dez4fPJCR74", ui)
        for name in ("README.md", "WORKFLOW.md", "GRAFIKI.md", "FORMAT2.md", "CLAUDE.md"):
            self.assertIn("Format 2", (HERE.parent / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
