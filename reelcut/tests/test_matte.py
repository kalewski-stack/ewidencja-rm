"""Grafiki „za postacią”: okna czasu, sylwetki, kompozycja pod postacią i model MODNet (prawdziwy model tylko, gdy jest na dysku)."""
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import graphics, media  # noqa: E402
from reelcut.graphics import core, glue, matte as mt  # noqa: E402
from reelcut.pipeline import Options, run  # noqa: E402
from reelcut.planner import build_plan as plan_cuts  # noqa: E402
from reelcut.template import load_template  # noqa: E402

HAVE_NP = importlib.util.find_spec("numpy") is not None
HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_ORT = HAVE_NP and importlib.util.find_spec("onnxruntime") is not None
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
HAVE_MODEL = HAVE_ORT and ((mt.MODEL_DIR / mt.MODEL_NAME).exists() or bool(os.environ.get(mt.ENV_MODEL)))
PHOTO = HERE / "assets" / "face_nasa_astronaut.jpg"


class WindowTests(unittest.TestCase):
    def test_spans_get_padding_and_merge(self):
        out = mt.windows_from([(5.0, 6.0), (6.2, 7.0), (20.0, 21.0)], 30.0)
        self.assertEqual(len(out), 2)
        self.assertAlmostEqual(out[0][0], 5.0 - mt.PAD_S)
        self.assertAlmostEqual(out[0][1], 7.0 + mt.PAD_S)
        self.assertAlmostEqual(out[1][1], 21.0 + mt.PAD_S)

    def test_windows_stay_inside_the_film(self):
        (a, b), = mt.windows_from([(0.0, 3.0)], 3.0)
        self.assertEqual((a, b), (0.0, 3.0))

    def test_matte_size_is_a_multiple_of_32_and_keeps_the_aspect(self):
        self.assertEqual(mt.matte_size((1080, 1920)), (384, 672))
        w, h = mt.matte_size((1080, 1350), 300)
        self.assertEqual((w % 32, h % 32), (0, 0))
        self.assertAlmostEqual(h / w, 1350 / 1080, delta=0.06)


@unittest.skipUnless(HAVE_NP and HAVE_PIL, "brak numpy albo Pillow")
class TrackTests(unittest.TestCase):
    def track(self, frames=None, windows=((1.0, 2.0),), fps=10):
        import numpy as np

        frames = frames if frames is not None else {i: np.full((8, 4), 40 * (i - 9), np.uint8) for i in (10, 11, 12, 13, 14, 15)}
        return mt.MatteTrack((40, 80), fps, (4, 8), frames, windows)

    def test_refine_clears_haze_and_keeps_the_core(self):
        import numpy as np

        a = np.array([0, 20, 30, 128, 225, 255], np.uint8)
        r = mt.refine(a)
        self.assertEqual((r[0], r[1], r[2]), (0, 0, 0))
        self.assertEqual((r[4], r[5]), (255, 255))
        self.assertTrue(all(r[i] <= r[i + 1] for i in range(len(r) - 1)))

    def test_only_inside_windows_and_in_canvas_size(self):
        tr = self.track()
        self.assertIsNone(tr.at(0.2))
        self.assertIsNone(tr.at(3.0))
        im = tr.at(1.5)
        self.assertEqual((im.size, im.mode), ((40, 80), "L"))

    def test_frames_are_interpolated_linearly(self):
        tr = self.track()
        v = lambda t: tr.at(t).getpixel((20, 40))  # noqa: E731
        self.assertAlmostEqual(v(1.0), 40, delta=2)  # klatka 10
        self.assertAlmostEqual(v(1.05), 60, delta=3)  # w połowie między klatkami 10 i 11
        self.assertAlmostEqual(v(1.1), 80, delta=2)

    def test_missing_frames_fall_back_to_the_nearest(self):
        import numpy as np

        tr = self.track({10: np.full((8, 4), 100, np.uint8)}, windows=((1.0, 1.4),))
        self.assertAlmostEqual(tr.at(1.3).getpixel((20, 40)), 100, delta=2)


@unittest.skipUnless(HAVE_NP and HAVE_PIL, "brak numpy albo Pillow")
class CompositingTests(unittest.TestCase):
    """Element z behind znika tam, gdzie jest postać; elementy przed postacią i reszta kadru zostają."""

    class FakeTrack:
        def __init__(self, size, box):
            from PIL import Image, ImageDraw

            self.im = Image.new("L", size, 0)
            ImageDraw.Draw(self.im).rectangle(box, fill=255)

        def at(self, t):
            return self.im

    def setUp(self):
        self.size = (540, 960)
        ctx = graphics.Context(graphics.load_brand(), core.Layout(*self.size), 30, HERE / "assets", None, [], 20.0)
        self.ctx = ctx
        self.person = (150, 250, 400, 700)  # prostokąt „postaci”
        self.matte = self.FakeTrack(self.size, self.person)

    def build(self, *elements):
        return graphics.build_plan({"elements": list(elements)}, self.ctx)

    def solid(self, **kw):
        # duży obraz (zdjęcie testowe) pokrywający środek kadru, rysowany za postacią
        return dict({"type": "illustration", "at": 0, "dur": 5, "image": "face_nasa_astronaut.jpg", "x": 0.5, "y": 0.5, "width": 0.9,
                     "float": False, "glow": None, "behind": True}, **kw)

    def alpha(self, layer, xy):
        return layer.img.getpixel(xy)[3]

    def test_behind_element_is_hidden_under_the_person_only(self):
        plan = self.build(self.solid())
        with_matte = graphics.render_frame(plan, 2.5, self.size, self.matte)
        without = graphics.render_frame(plan, 2.5, self.size)
        inside, outside = (270, 480), (60, 480)
        self.assertGreater(self.alpha(without, inside), 200)
        self.assertEqual(self.alpha(with_matte, inside), 0)  # tu stoi postać
        self.assertEqual(self.alpha(with_matte, outside), self.alpha(without, outside))  # poza postacią bez zmian
        self.assertGreater(self.alpha(with_matte, outside), 200)

    def test_front_elements_stay_visible_over_the_person(self):
        badge = {"type": "badge", "at": 0, "dur": 5, "number": 1, "text": "Przed", "x": 0.5, "y": 0.5}
        plan = self.build(self.solid(), badge)
        layer = graphics.render_frame(plan, 2.5, self.size, self.matte)
        front_only = graphics.render_frame(self.build(badge), 2.5, self.size)
        self.assertEqual(layer.img.getpixel((270, 480)), front_only.img.getpixel((270, 480)))  # plakietka nad sylwetką nietknięta
        self.assertGreater(self.alpha(layer, (270, 480)), 200)

    def test_without_a_matte_behind_elements_are_drawn_normally(self):
        plan = self.build(self.solid())
        layer = graphics.render_frame(plan, 2.5, self.size)
        self.assertGreater(self.alpha(layer, (270, 480)), 200)

    def test_order_of_drawing_does_not_depend_on_z(self):
        a = self.solid(z=9)  # wyższe z nie wynosi elementu przed postać
        layer = graphics.render_frame(self.build(a), 2.5, self.size, self.matte)
        self.assertEqual(self.alpha(layer, (270, 480)), 0)

    def test_behind_does_not_trigger_the_face_warning(self):
        plan = self.build(self.solid(width=0.4, y=0.45))
        self.assertFalse([w for w in plan.warnings if "zasłania twarz" in w])


class ModelFileTests(unittest.TestCase):
    def test_env_variable_points_to_a_model(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "m.onnx"
            p.write_bytes(b"x")
            with mock.patch.dict(os.environ, {mt.ENV_MODEL: str(p)}):
                self.assertEqual(mt.model_path(), p)
            with mock.patch.dict(os.environ, {mt.ENV_MODEL: str(p) + ".nie"}):
                with self.assertRaises(mt.MatteUnavailable):
                    mt.model_path()

    def test_download_checks_the_checksum_and_leaves_nothing_behind(self):
        payload = b"to nie jest model" * 100000

        class Resp:
            def __init__(self, data):
                self.data, self.pos = data, 0

            def read(self, n):
                chunk, self.pos = self.data[self.pos:self.pos + n], self.pos + n
                return chunk

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(mt, "MODEL_DIR", pathlib.Path(d)), mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop(mt.ENV_MODEL, None)
                with mock.patch("urllib.request.urlopen", return_value=Resp(payload)):
                    with self.assertRaises(mt.MatteUnavailable) as cm:
                        mt.model_path(lambda m: None)
                self.assertIn("sumę kontrolną", str(cm.exception))
                self.assertEqual(list(pathlib.Path(d).iterdir()), [])  # ani modelu, ani pliku tymczasowego
                with mock.patch.object(mt, "MODEL_SHA256", hashlib.sha256(payload).hexdigest()), \
                        mock.patch("urllib.request.urlopen", return_value=Resp(payload)):
                    p = mt.model_path(lambda m: None)
                self.assertEqual(p.read_bytes(), payload)
                self.assertEqual(mt.model_path(lambda m: None), p)  # drugi raz bez pobierania

    def test_network_failure_gives_a_manual_instruction(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(mt, "MODEL_DIR", pathlib.Path(d)), mock.patch("urllib.request.urlopen", side_effect=OSError("brak sieci")):
                os.environ.pop(mt.ENV_MODEL, None)
                with self.assertRaises(mt.MatteUnavailable) as cm:
                    mt.model_path(lambda m: None)
        self.assertIn("Pobierz go ręcznie", str(cm.exception))
        self.assertIn(mt.ENV_MODEL, str(cm.exception))

    def test_offline_without_download_option(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mt, "MODEL_DIR", pathlib.Path(d)):
            os.environ.pop(mt.ENV_MODEL, None)
            with self.assertRaises(mt.MatteUnavailable):
                mt.model_path(download=False)


@unittest.skipUnless(HAVE_PIL and HAVE_FFMPEG, "brak Pillow albo ffmpeg")
class FallbackTests(unittest.TestCase):
    def test_missing_model_falls_back_to_drawing_in_front_with_a_warning(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            master = d / "m.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=270x480:r=10:d=1", "-pix_fmt", "yuv420p",
                            str(master)], check=True)
            plan = graphics.build_plan({"elements": [{"type": "badge", "at": 0, "dur": 1, "text": "x", "behind": True}]},
                                       graphics.Context(graphics.load_brand(), core.Layout(540, 960), 30, d, None, [], 1.0))
            vplan = plan_cuts(load_template("format2"), 30, 30)
            with mock.patch.dict(os.environ, {mt.ENV_MODEL: str(d / "nie_ma.onnx")}):
                self.assertIsNone(glue.make_matte(plan, vplan, master, (540, 960), 1.0, lambda m: None))
            self.assertTrue(any("rysuję przed nią" in w for w in plan.warnings), plan.warnings)

    def test_cuts_templates_cannot_hide_graphics_behind_the_person(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            master = d / "m.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=270x480:r=30:d=1", "-pix_fmt", "yuv420p",
                            str(master)], check=True)
            plan = graphics.build_plan({"elements": [{"type": "badge", "at": 0, "dur": 1, "text": "x", "behind": True}]},
                                       graphics.Context(graphics.load_brand(), core.Layout(540, 960), 30, d, None, [], 1.0))
            vplan = plan_cuts(load_template("format1"), 900, 30)
            self.assertIsNone(glue.make_matte(plan, vplan, master, (540, 960), 1.0, lambda m: None))
            self.assertTrue(any("formacie 2" in w for w in plan.warnings), plan.warnings)

    def test_dry_run_does_not_try_to_cut_the_person(self):
        plan = graphics.build_plan({"elements": [{"type": "badge", "at": 0, "dur": 1, "text": "x", "behind": True}]},
                                   graphics.Context(graphics.load_brand(), core.Layout(540, 960), 30, pathlib.Path("."), None, [], 1.0))
        self.assertIsNone(glue.make_matte(plan, plan_cuts(load_template("format2"), 30, 30), pathlib.Path("nie_ma.mp4"), (540, 960), 1.0))
        self.assertEqual(plan.warnings, [])


@unittest.skipUnless(HAVE_MODEL and HAVE_PIL, "brak modelu MODNet na dysku (pobierze się przy pierwszym użyciu) albo Pillow")
class RealModelTests(unittest.TestCase):
    def test_the_model_finds_the_person_in_a_portrait(self):
        import numpy as np
        from PIL import Image

        matter = mt.Matter(mt.model_path(lambda m: None, download=False))
        w, h = 384, 512
        rgb = np.asarray(Image.open(PHOTO).convert("RGB").resize((w, h), Image.BILINEAR))
        a = matter.alpha(rgb)
        self.assertEqual(a.shape, (h, w))
        self.assertGreater(int(a[int(h * 0.30), int(w * 0.42)]), 200)  # twarz
        self.assertLess(int(a[int(h * 0.05), int(w * 0.95)]), 60)  # tło w rogu

    @unittest.skipUnless(HAVE_FFMPEG, "brak ffmpeg")
    def test_pipeline_hides_a_graphic_behind_the_person(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            clip = d / "twarz.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-i", str(PHOTO), "-f", "lavfi", "-i", "sine=f=200:d=4",
                            "-t", "4", "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", str(clip)], check=True)
            from PIL import Image

            Image.new("RGB", (600, 600), (255, 0, 255)).save(d / "magenta.png")
            plan = d / "plan.json"
            plan.write_text(json.dumps({"elements": [{"type": "illustration", "at": 0.2, "dur": 3.5, "image": "magenta.png", "x": 0.5, "y": 0.5,
                                                      "width": 1.0, "float": False, "glow": None, "behind": True, "in": 0.1, "out": 0.1}]}), encoding="utf-8")
            res = run(clip, d / "o.mp4", Options(template="format2", framing="off", graphics=plan, captions="off", preset="ultrafast", crf=18),
                      log=lambda m: None)
            self.assertEqual(res.graphics["elements"], 1)
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1.5", "-i", str(d / "o.mp4"), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True, check=True).stdout
            im = Image.frombytes("RGB", (1080, 1920), raw)

            def magenta(xy):
                r, g, b = im.getpixel(xy)
                return r > 200 and b > 200 and g < 90

            self.assertTrue(magenta((1040, 150)) or magenta((1040, 960)) or magenta((40, 960)), "grafika w ogóle nie widać poza postacią")
            face_xy = (int(1080 * 0.42), int(1920 * 0.30))  # twarz z portretu (kadr „cover”)
            self.assertFalse(magenta(face_xy), "postać nie zasłania grafiki za nią")


class RelativePathTests(unittest.TestCase):
    @unittest.skipUnless(HAVE_FFMPEG, "brak ffmpeg")
    def test_a_relative_input_and_output_path_work(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x202020:s=540x960:r=25", "-f", "lavfi", "-i", "sine=f=220:d=4",
                            "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(d / "nagranie.mp4")], check=True)
            old = os.getcwd()
            os.chdir(d)
            try:
                res = run("nagranie.mp4", "wynik.mp4", Options(template="format2", framing="off", captions="off", preset="ultrafast", crf=30),
                          log=lambda m: None)
            finally:
                os.chdir(old)
            self.assertEqual(res.output, (d / "wynik.mp4").resolve())
            self.assertAlmostEqual(media.probe(d / "wynik.mp4").duration, 4.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
