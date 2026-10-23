"""Przejścia między scenami: rozmycie, zoom, przesunięcie, kurtyna i błysk (rolki DekGW1-tCoi i DcS25CKkmFM), ich składnia w scenariuszu
i obróbka klatki w oknie wokół cięcia."""
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

from reelcut import captions, graphics  # noqa: E402
from reelcut.graphics import core, script, transitions  # noqa: E402
from reelcut.graphics.core import PlanError  # noqa: E402
from reelcut.graphics.transitions import FRAME, Transition  # noqa: E402

HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
SIZE = (360, 640)
AT = 2.0

# stara scena: żółte słowo w lewym górnym rogu, nowa: inne słowo w prawym dolnym; tło (papier z kropkami) stoi w miejscu
BACKDROP = {"type": "backdrop", "at": 0, "dur": 30}
OLD = {"type": "text", "at": 0.0, "dur": AT, "text": "*COŚ*", "x": 0.3, "y": 0.25, "size": 0.18, "in": 0, "out": 0}
NEW = {"type": "text", "at": AT, "dur": 4.0, "text": "*INNE*", "x": 0.7, "y": 0.75, "size": 0.18, "in": 0, "out": 0}


def plan_of(*transitions_, elements=(BACKDROP, OLD, NEW), size=SIZE):
    ctx = graphics.Context(graphics.load_brand(), core.Layout(*size), 30, None, None, [], 10.0)
    return graphics.build_plan({"schema": 1, "elements": list(elements), "transitions": list(transitions_)}, ctx)


def frame(plan, k, size=SIZE):
    """Klatka o numerze k względem cięcia (0 = pierwsza klatka nowej sceny)."""
    return graphics.render_frame(plan, AT + k * FRAME, size).img


class Mass:
    """Ślad sceny na tle: różnica jasności względem samego tła (papier z kropkami), jej środek ciężkości, rozrzut i największy gradient."""

    BG = None

    def __init__(self, img):
        from PIL import ImageChops, ImageFilter

        if Mass.BG is None:
            Mass.BG = graphics.render_frame(plan_of(elements=(BACKDROP,)), 0.5, SIZE).img.convert("L")
        d = ImageChops.difference(img.convert("L"), Mass.BG).point(lambda v: 0 if v < 12 else v)  # bez drobnych różnic (kropki, siatka)
        W, H = d.size
        px = d.tobytes()
        self.total = float(sum(px))
        if self.total <= 0:
            self.cx = self.cy = self.sx = self.sy = 0.0
        else:
            xs = [0.0] * W
            ys = [0.0] * H
            for i, v in enumerate(px):
                if v:
                    xs[i % W] += v
                    ys[i // W] += v
            self.cx = sum(x * v for x, v in enumerate(xs)) / self.total
            self.cy = sum(y * v for y, v in enumerate(ys)) / self.total
            self.sx = (sum((x - self.cx) ** 2 * v for x, v in enumerate(xs)) / self.total) ** 0.5
            self.sy = (sum((y - self.cy) ** 2 * v for y, v in enumerate(ys)) / self.total) ** 0.5
        self.grad = d.filter(ImageFilter.FIND_EDGES).getextrema()[1]


def region_energy(img, box):
    """Średnia siła krawędzi (filtr FIND_EDGES) śladu sceny w prostokącie: im ostrzejszy i wyraźniejszy napis, tym więcej. Liczone z różnicy
    względem samego tła, żeby stałe kropki papieru nie zagłuszały napisu."""
    from PIL import ImageChops, ImageFilter, ImageStat

    if Mass.BG is None:
        Mass(img)
    diff = ImageChops.difference(img.convert("L"), Mass.BG).crop(box)
    return ImageStat.Stat(diff.filter(ImageFilter.FIND_EDGES)).mean[0]


OLD_BOX = (24, 105, 193, 204)  # gdzie stoi stare słowo (z zapasem na rozmycie)
NEW_BOX = (154, 440, 349, 524)


def mean_luma(img):
    from PIL import ImageStat

    return ImageStat.Stat(img.convert("L")).mean[0]


class ParseTests(unittest.TestCase):
    def test_kinds_have_polish_and_english_names_and_directions(self):
        for name, kind in (("rozmycie", "blur"), ("Rozmycie", "blur"), ("blur", "blur"), ("zoom", "zoom"), ("najazd", "zoom"), ("przesunięcie", "whip"),
                           ("przesuniecie", "whip"), ("whip", "whip"), ("kurtyna", "wipe"), ("wipe", "wipe"), ("błysk", "flash"), ("blysk", "flash")):
            self.assertEqual(Transition(name, 1.0).kind, kind, name)
        self.assertEqual(Transition("przesunięcie", 1.0).dir, "right")  # domyślny kierunek jak we wzorcu: scena ucieka w prawo, nowa wchodzi z lewej
        self.assertEqual(Transition("kurtyna", 1.0).dir, "up")
        for name, d in (("lewo", "lewo"), ("prawo", "prawo"), ("góra", "gora"), ("dół", "dol"), ("left", "left")):
            self.assertEqual(Transition("przesunięcie", 1.0, name).dir, d, name)

    def test_errors_are_readable(self):
        for args, hint in ((("kometa", 1.0), "nieznany rodzaj"), (("zoom", -1.0), "ujemny"), (("zoom", 1.0, "ukośnie"), "kierunek"),
                           (("zoom", 1.0, "", 0.0), "moc")):
            with self.assertRaises(PlanError, msg=hint) as cm:
                Transition(*args)
            self.assertIn(hint, str(cm.exception))
        with self.assertRaises(PlanError):
            Transition.from_spec({"kind": "zoom"})  # brak czasu cięcia

    def test_windows_surround_the_cut(self):
        for kind in ("blur", "zoom", "whip", "wipe", "flash"):
            tr = Transition(kind, 5.0)
            self.assertLessEqual(tr.start, 5.0)
            self.assertGreater(tr.end, 5.0)
            self.assertTrue(tr.active(5.0))
            self.assertFalse(tr.active(tr.start - 0.05) or tr.active(tr.end + 0.05))
        self.assertEqual(Transition("kurtyna", 5.0).start, 5.0)  # kurtyna zaczyna się w chwili cięcia

    def test_flash_follows_the_measured_curve(self):
        table = [round(transitions.flash_alpha(k), 2) for k in range(-4, 5)]
        self.assertEqual(table, [0.0, 0.25, 0.58, 0.82, 0.86, 0.82, 0.58, 0.25, 0.0])
        self.assertEqual(max(transitions.FLASH), transitions.flash_alpha(0))  # szczyt jest w pierwszej klatce nowego ujęcia
        self.assertAlmostEqual(transitions.flash_alpha(-0.5), (0.82 + 0.86) / 2, places=6)  # między klatkami interpolacja liniowa
        self.assertEqual((transitions.flash_alpha(-9), transitions.flash_alpha(9)), (0.0, 0.0))

    def test_scenario_marker_builds_transitions_with_times_from_speech(self):
        text = "{przejście: rozmycie} Raz dwa trzy. {przejście: przesunięcie | kierunek: lewo | moc: 0,8} Cztery pięć sześć. {przejście: błysk} Siedem."
        words = script.parse(text).words
        spoken = [captions.Word(w, i * 0.5, i * 0.5 + 0.4) for i, w in enumerate(words)]
        raw = script.to_plan(text, spoken)
        self.assertEqual([(t["kind"], t["at"]) for t in raw["transitions"]], [("rozmycie", 0.0), ("przesunięcie", 1.5), ("błysk", 3.0)])
        self.assertEqual((raw["transitions"][1]["dir"], raw["transitions"][1]["strength"]), ("lewo", 0.8))
        self.assertEqual(raw["elements"], [])  # przejście nie jest elementem

    def spoken_plan(self, text, step=0.5, dur=0.4):
        words = script.parse(text).words
        return script.to_plan(text, [captions.Word(w, i * step, i * step + dur) for i, w in enumerate(words)])

    def test_a_transition_snaps_to_the_nearest_scene_boundary(self):
        # plansza: słowa 3-4 (1,5-2,4 s), koniec = ostatnie słowo + 0,3 s = 2,7 s; przejście stoi przed słowem „sześć” (2,5 s)
        raw = self.spoken_plan("Jeden dwa trzy {przejście: rozmycie} {plansza} cztery pięć {/plansza} {przejście: najazd} sześć siedem osiem.")
        card = raw["elements"][0]
        self.assertEqual((card["at"], round(card["at"] + card["dur"], 3)), (1.5, 2.7))
        self.assertEqual([(t["kind"], t["at"]) for t in raw["transitions"]], [("rozmycie", 1.5), ("najazd", 2.7)])

    def test_exact_transitions_and_far_ones_stay_where_the_words_put_them(self):
        raw = self.spoken_plan("Jeden dwa trzy {plansza} cztery pięć {/plansza} {przejście: najazd | dokładnie: tak} sześć siedem {przejście: błysk} osiem dziewięć dziesięć.")
        self.assertEqual([(t["kind"], t["at"]) for t in raw["transitions"]], [("najazd", 2.5), ("błysk", 3.5)])
        self.assertNotIn("exact", raw["transitions"][0])

    def test_scenario_without_scenes_leaves_the_transition_on_its_word(self):
        raw = self.spoken_plan("Raz dwa trzy. {przejście: zoom} Cztery pięć sześć.")
        self.assertEqual([t["at"] for t in raw["transitions"]], [1.5])

    def test_marker_without_kind_or_with_a_wrong_one_is_refused(self):
        words = "Raz dwa trzy cztery".split()
        spoken = [captions.Word(w, i * 0.5, i * 0.5 + 0.4) for i, w in enumerate(words)]
        with self.assertRaises(PlanError) as cm:
            script.to_plan("{przejście} Raz dwa trzy cztery", spoken)
        self.assertIn("rodzaju", str(cm.exception))
        if HAVE_PIL:
            raw = script.to_plan("{przejście: kometa} Raz dwa trzy cztery", spoken)
            with self.assertRaises(PlanError) as cm:
                plan_of(*raw["transitions"], elements=[BACKDROP])
            self.assertIn("kometa", str(cm.exception))

    def test_transition_time_can_be_a_phrase_from_speech(self):
        from reelcut.graphics import anchors

        raw = {"schema": 1, "elements": [], "transitions": [{"kind": "zoom", "at": "cztery pięć"}]}
        spoken = [captions.Word(w, i * 0.5, i * 0.5 + 0.4) for i, w in enumerate("raz dwa trzy cztery pięć sześć".split())]
        self.assertTrue(anchors.has_phrases(raw))
        self.assertEqual(anchors.resolve(raw, spoken)["transitions"][0]["at"], 1.5)


@unittest.skipUnless(HAVE_PIL, "brak Pillow")
class RenderTests(unittest.TestCase):
    def test_plan_lists_and_measures_the_transitions(self):
        plan = plan_of({"kind": "rozmycie", "at": AT}, {"kind": "błysk", "at": 4.0})
        self.assertEqual([tr.kind for tr in plan.transitions], ["blur", "flash"])
        self.assertGreater(plan.duration, 4.1)
        self.assertIn("przejście: blur", plan.describe())
        self.assertEqual(plan.transitions_at(AT)[0].kind, "blur")
        self.assertEqual(plan.transitions_at(3.0), [])

    def test_outside_the_window_the_frame_is_exactly_the_plain_scene(self):
        with_tr, plain = plan_of({"kind": "rozmycie", "at": AT}), plan_of()
        for t in (0.5, 1.5, AT + 0.5, 3.0):
            self.assertEqual(graphics.render_frame(with_tr, t, SIZE).tobytes(), graphics.render_frame(plain, t, SIZE).tobytes(), t)

    def test_rendering_is_deterministic(self):
        plan = plan_of({"kind": "zoom", "at": AT})
        for k in (-3, 0, 4):
            self.assertEqual(frame(plan, k).tobytes(), frame(plan, k).tobytes(), k)

    def test_blur_defocuses_the_old_scene_into_the_cut_and_refocuses_the_new_one(self):
        plan = plan_of({"kind": "rozmycie", "at": AT})
        before = [region_energy(frame(plan, -k), OLD_BOX) for k in (6, 4, 3, 2)]
        self.assertTrue(all(b < a for a, b in zip(before, before[1:])), before)  # im bliżej cięcia, tym mniej ostrych krawędzi
        after = [region_energy(frame(plan, k), NEW_BOX) for k in (0, 6, 8, 10)]
        self.assertTrue(all(b > a for a, b in zip(after, after[1:])), after)  # po cięciu obraz ostrzeje
        self.assertEqual(frame(plan, 12).tobytes(), frame(plan_of(), 12).tobytes())  # po oknie sceny są takie jak bez przejścia

    def test_blur_fades_the_old_scene_toward_the_paper_and_keeps_the_backdrop_still(self):
        plan = plan_of({"kind": "rozmycie", "at": AT})
        self.assertLess(Mass(frame(plan, -1)).total, 0.5 * Mass(frame(plan, -5)).total)  # scena blednie do papieru (i rozmywa się)
        corner = (300, 560, 356, 636)  # róg, w którym żadna scena niczego nie rysuje
        self.assertEqual(frame(plan, -2).crop(corner).tobytes(), frame(plan_of(), -2).crop(corner).tobytes())  # tło poza sceną bez zmian

    def test_zoom_pushes_the_old_scene_in_and_grows_the_new_one_from_small(self):
        plan = plan_of({"kind": "zoom", "at": AT})
        spread = [Mass(frame(plan, -k)).sx for k in (5, 3, 1)]
        self.assertTrue(spread[0] < spread[1] < spread[2], spread)  # stara scena najeżdża: rozrzut rośnie
        final = Mass(frame(plan_of(), 20)).sx
        grow = [Mass(frame(plan, k)).sx for k in (0, 2, 5, 10, 18)]
        self.assertLess(grow[0], 0.55 * final)  # nowa zaczyna mała
        self.assertTrue(all(b >= a * 0.98 for a, b in zip(grow, grow[1:])), grow)
        self.assertAlmostEqual(grow[-1], final, delta=0.2 * final)
        # najazd odbywa się wokół środka kadru: nowe słowo (prawy dół) startuje bliżej środka niż stoi na końcu
        c0, cf = Mass(frame(plan, 0)), Mass(frame(plan_of(), 20))
        self.assertLess(abs(c0.cx - SIZE[0] / 2), abs(cf.cx - SIZE[0] / 2))

    def test_whip_moves_the_old_scene_out_and_brings_the_new_one_in_from_the_other_side(self):
        for name, sign in (("prawo", 1), ("lewo", -1)):
            plan = plan_of({"kind": "przesunięcie", "at": AT, "dir": name})
            base_old = Mass(frame(plan_of(), -8)).cx
            out = [Mass(frame(plan, -k)).cx for k in (3, 2, 1)]
            self.assertTrue(all(sign * (b - a) > 0 for a, b in zip([base_old] + out, out)), (name, out))  # stara ucieka w kierunku dir
            base_new = Mass(frame(plan_of(), 25)).cx
            enter = [Mass(frame(plan, k)).cx for k in (1, 5, 12)]
            self.assertLess(sign * (enter[0] - base_new), -0.05 * SIZE[0], (name, enter))  # nowa wjeżdża z przeciwnej strony
            self.assertTrue(abs(enter[0] - base_new) > abs(enter[1] - base_new) > abs(enter[2] - base_new), (name, enter))  # i hamuje

    def test_whip_smears_along_the_direction_of_the_move(self):
        from PIL import Image

        W, H = SIZE
        scene = Image.new("RGBA", SIZE, (0, 0, 0, 0))
        scene.paste(Image.new("RGBA", (24, 24), (255, 0, 0, 255)), (W // 2 - 12, H // 2 - 12))
        for name, horizontal in (("prawo", True), ("góra", False)):
            tr = Transition("przesunięcie", AT, name)
            out = tr.apply(scene, AT - 1.5 * FRAME, lambda t: scene)
            box = out.getchannel("A").point(lambda v: 255 if v >= 20 else 0).getbbox()
            long, short = (box[2] - box[0], box[3] - box[1]) if horizontal else (box[3] - box[1], box[2] - box[0])
            self.assertGreater(long, 1.9 * 24, (name, box))  # smuga ciągnie się wzdłuż ruchu
            self.assertLess(short, 1.4 * 24, (name, box))  # a w poprzek prawie nie

    def test_wipe_replaces_the_old_scene_behind_a_moving_band(self):
        plan = plan_of({"kind": "kurtyna", "at": AT, "dir": "góra"})
        plain_old = Mass(frame(plan_of(), -3))
        start = Mass(frame(plan, 0))
        self.assertAlmostEqual(start.cy, plain_old.cy, delta=6)  # w chwili cięcia stoi jeszcze stara scena
        mid = frame(plan, 3)
        top, bottom = mid.crop((0, 0, SIZE[0], SIZE[1] // 2)), mid.crop((0, SIZE[1] // 2, SIZE[0], SIZE[1]))
        bg = Mass.BG
        from PIL import ImageChops

        def covered(part, y0):
            return sum(ImageChops.difference(part.convert("L"), bg.crop((0, y0, SIZE[0], y0 + part.size[1]))).tobytes())

        self.assertGreater(covered(top, 0), 0)  # stare słowo jeszcze widać u góry
        self.assertEqual(frame(plan, 9).tobytes(), frame(plan_of(), 9).tobytes())  # po kurtynie czysta nowa scena
        mass_mid = Mass(mid)
        self.assertTrue(mass_mid.total > 0)
        self.assertGreater(covered(bottom, SIZE[1] // 2), 0)  # a nowe słowo wchodzi od dołu (za pasem)

    def test_wipe_direction_decides_which_side_gives_way_first(self):
        from PIL import ImageChops

        up, down = plan_of({"kind": "kurtyna", "at": AT, "dir": "góra"}), plan_of({"kind": "kurtyna", "at": AT, "dir": "dół"})

        def ink(img, box):
            return sum(ImageChops.difference(img.convert("L").crop(box), Mass.BG.crop(box)).point(lambda v: 0 if v < 12 else v).tobytes())

        Mass(frame(up, 0))  # wypełnia Mass.BG
        self.assertGreater(ink(frame(up, 2), NEW_BOX), 0)  # pas idący w górę odsłania nowe słowo (dół kadru) najpierw
        self.assertEqual(ink(frame(down, 2), NEW_BOX), 0)  # a idący w dół zaczyna od góry, więc na dole jeszcze nic nie ma
        self.assertGreater(ink(frame(up, 2), OLD_BOX), 0)  # stare słowo (góra kadru) w pierwszym przypadku jeszcze stoi
        self.assertGreater(ink(frame(down, 4), NEW_BOX), 0)  # i w drugim w końcu też się pojawia

    def test_flash_whitens_everything_including_the_backdrop_and_peaks_at_the_cut(self):
        plan = plan_of({"kind": "błysk", "at": AT})
        luma = {k: mean_luma(frame(plan, k)) for k in range(-4, 5)}
        self.assertEqual(max(luma, key=luma.get), 0)
        self.assertGreater(luma[-1], luma[-3])
        self.assertGreater(luma[-3], luma[-4] - 1)
        self.assertAlmostEqual(luma[-1], luma[1], delta=8)  # krzywa jest prawie symetryczna wokół cięcia
        self.assertEqual(frame(plan, -5).tobytes(), frame(plan_of(), -5).tobytes())  # poza oknem bez zmian
        peak = frame(plan, 0).getpixel((4, 4))
        self.assertTrue(all(v > 235 for v in peak[:3]), peak)  # biel leży też na samym tle

    def test_flash_strength_dims_the_peak(self):
        full, soft = plan_of({"kind": "błysk", "at": AT}), plan_of({"kind": "błysk", "at": AT, "strength": 0.5})
        self.assertGreater(mean_luma(frame(full, 0)), mean_luma(frame(soft, 0)))

    def test_elements_that_end_exactly_at_the_cut_do_not_leak_into_the_new_scene(self):
        plan = plan_of({"kind": "rozmycie", "at": AT})  # OLD kończy się dokładnie w AT, NEW zaczyna się w AT
        first = Mass(frame(plan, 0))
        self.assertGreater(first.cx, SIZE[0] / 2)  # tylko nowe słowo (prawy dół), bez stejszego słowa z lewej
        self.assertGreater(first.cy, SIZE[1] / 2)

    def test_strength_scales_the_effect(self):
        weak, strong = plan_of({"kind": "rozmycie", "at": AT, "strength": 0.4}), plan_of({"kind": "rozmycie", "at": AT, "strength": 1.5})
        self.assertGreater(region_energy(frame(weak, -2), OLD_BOX), region_energy(frame(strong, -2), OLD_BOX))

    def test_transitions_alone_keep_the_plan_alive_in_the_frame_stream(self):
        plan = plan_of({"kind": "błysk", "at": AT}, elements=())
        frames = list(graphics.render.iter_frames(plan, SIZE, 30, 90))
        self.assertEqual(len(frames), 90)
        blank = bytes(SIZE[0] * SIZE[1] * 4)
        self.assertEqual(frames[0], blank)
        self.assertNotEqual(frames[60], blank)  # klatka w chwili cięcia: sam błysk


@unittest.skipUnless(HAVE_PIL and HAVE_FFMPEG, "brak Pillow albo ffmpeg")
class PipelineTests(unittest.TestCase):
    """Przejście wpisane w scenariuszu dociera do gotowego filmu: te same dwa filmy motion, z jednym znacznikiem i bez niego."""

    TEXT = ("{tarcza: brief | nad: Formuła} Skopiuj tę formułę. Pierwsza jest {krok: Cel} cel. Druga to {krok: Miara} miara. "
            "{przejście: rozmycie} {plansza} Ale *uwaga*. {/plansza} {finał: Gotowe} To cała formuła.")

    @classmethod
    def setUpClass(cls):
        from reelcut.pipeline import Options, run

        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_tr_"))
        voice = cls.tmp / "glos.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "aevalsrc='0.3*sin(2*PI*180*t)*(0.6+0.4*sin(2*PI*3*t))':s=44100:d=8",
                        str(voice)], check=True)
        words = script.parse(cls.TEXT).words
        cls.cut = 0.5 * words.index("Ale")
        (cls.tmp / "slowa.json").write_text(json.dumps([{"w": w.lower().strip(".,"), "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(words)]),
                                            encoding="utf-8")
        cls.res = {}
        for name, text in (("z", cls.TEXT), ("bez", cls.TEXT.replace("{przejście: rozmycie} ", ""))):
            sc = cls.tmp / f"{name}.txt"
            sc.write_text(text, encoding="utf-8")
            cls.res[name] = run(voice, cls.tmp / f"{name}.mp4", Options(template="motion", graphics=sc, words_file=cls.tmp / "slowa.json", captions="on",
                                                                        preset="ultrafast", crf=28), log=lambda m: None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def frame(self, name, t):
        from PIL import Image

        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", str(self.tmp / f"{name}.mp4"), "-frames:v", "1", "-vf", "scale=108:192",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        return Image.frombytes("RGB", (108, 192), raw)

    def diff(self, t):
        a, b = self.frame("z", t).tobytes(), self.frame("bez", t).tobytes()
        return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

    def test_the_transition_is_listed_in_the_plan_of_the_film(self):
        self.assertIn("przejście: blur", self.res["z"].plan_text)
        self.assertNotIn("przejście", self.res["bez"].plan_text)
        self.assertEqual(self.res["z"].warnings, [])

    def test_the_two_films_are_the_same_outside_the_transition_window(self):
        for t in (self.cut - 0.5, self.cut - 0.25, self.cut + 0.5, self.cut + 1.0):
            self.assertLess(self.diff(t), 1.0, t)

    def test_the_frames_next_to_the_cut_are_different(self):
        for dt in (-1 / 30, 0.0, 1 / 30):
            self.assertGreater(self.diff(self.cut + dt), 20, dt)

    def test_the_new_scene_starts_whitened_and_blurred_so_it_is_lighter_than_the_hard_cut(self):
        light = lambda im: sum(im.convert("L").tobytes()) / (108 * 192)  # noqa: E731
        t = self.cut + 1 / 30
        self.assertGreater(light(self.frame("z", t)), light(self.frame("bez", t)) + 15)

    def test_a_flash_over_a_picture_is_enough_to_keep_the_graphics_layer_running(self):
        from reelcut.pipeline import Options, run

        sc = self.tmp / "tylko_blysk.txt"
        sc.write_text("{przejście: błysk} Skopiuj tę formułę, jeśli chcesz wyniku.", encoding="utf-8")
        res = run(self.tmp / "glos.wav", None, Options(template="motion", graphics=sc, words_file=self.tmp / "slowa.json", captions="off", dry_run=True),
                  log=lambda m: None)
        self.assertIn("przejście: flash", res.plan_text)


if __name__ == "__main__":
    unittest.main()
