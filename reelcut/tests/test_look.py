import dataclasses
import importlib.util
import json
import math
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import look  # noqa: E402
from reelcut.template import load_template  # noqa: E402

HAVE_NP = importlib.util.find_spec("numpy") is not None
HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
ASSET = HERE / "assets" / "face_nasa_astronaut.jpg"
TPL = load_template()
REF = look.LookStats.from_dict(TPL.look["A"]) if HAVE_NP and TPL.look.get("A") else None


def synth(seed, n=6, h=64, w=36, light=1.0, sat=1.0, tint=(0.0, 0.0, 0.0)):
    """Klatki testowe: rozkład jasności jak u zdjęcia (od cieni do świateł) i losowa barwa o danej sile."""
    import numpy as np

    rng = np.random.default_rng(seed)
    base = np.clip(rng.beta(2.0, 2.6, (n, h, w)) * light, 0, 1)
    color = rng.normal(0.0, 0.10 * sat, (n, h, w, 3))
    rgb = base[..., None] + color + np.array(tint)
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)


def hue(rgb) -> float:
    lab = look.srgb_to_lab([c / 255.0 for c in rgb])
    return math.degrees(math.atan2(lab[2], lab[1]))


@unittest.skipUnless(HAVE_NP, "brak numpy")
class ColorSpaceTests(unittest.TestCase):
    def test_known_values(self):
        import numpy as np

        lab = look.srgb_to_lab(np.array([[1.0, 1.0, 1.0], [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]))
        self.assertAlmostEqual(lab[0][0], 100.0, delta=0.05)
        self.assertAlmostEqual(abs(lab[0][1]) + abs(lab[0][2]), 0.0, delta=0.05)
        self.assertAlmostEqual(lab[1][0], 0.0, delta=0.05)
        self.assertAlmostEqual(lab[2][0], 53.24, delta=0.1)  # czerwień sRGB
        self.assertAlmostEqual(lab[2][1], 80.09, delta=0.2)
        self.assertAlmostEqual(lab[2][2], 67.20, delta=0.2)

    def test_round_trip(self):
        import numpy as np

        rgb = np.random.default_rng(1).random((500, 3))
        self.assertLess(float(np.abs(look.lab_to_srgb(look.srgb_to_lab(rgb)) - rgb).max()), 2e-3)


@unittest.skipUnless(HAVE_NP, "brak numpy")
class StatsTests(unittest.TestCase):
    def test_measure_orders_percentiles_and_serializes(self):
        s = look.measure(synth(1))
        self.assertEqual(len(s.luma), len(look.PCTS))
        self.assertEqual(s.luma, sorted(s.luma))
        self.assertAlmostEqual(sum(b["share"] for b in s.bins), 1.0, delta=0.02)
        back = look.LookStats.from_dict(json.loads(json.dumps(s.to_dict())))
        self.assertEqual(back.frames, s.frames)
        self.assertLess(look.distance(s, back)["luma"], 0.01)

    def test_distance_is_zero_for_equal_and_positive_for_different(self):
        a, b = look.measure(synth(1)), look.measure(synth(2, light=0.5, sat=0.2))
        self.assertAlmostEqual(look.distance(a, a)["luma"], 0.0)
        d = look.distance(a, b)
        self.assertGreater(d["luma"], 5)
        self.assertGreater(d["chroma"], 3)

    def test_caption_mask_hides_white_text_and_lime_accent_only(self):
        import numpy as np

        frames = np.full((1, 100, 100, 3), 60, np.uint8)
        frames[0, 60:70, 20:80] = 255  # biały napis w pasie napisów
        frames[0, 5:15, 5:15] = 255  # biel poza pasem (np. okno) zostaje w pomiarze
        frames[0, 90:95, 10:30] = (226, 251, 119)  # akcent limonkowy
        m = look.caption_mask(frames)[0]
        self.assertFalse(m[65, 50])
        self.assertTrue(m[10, 10])
        self.assertFalse(m[92, 20])
        self.assertTrue(m[40, 50])


@unittest.skipUnless(HAVE_NP, "brak numpy")
class TransformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bright = synth(10, light=1.0, sat=1.4)  # jasne, nasycone nagranie
        cls.dark = synth(11, light=0.55, sat=0.35)  # ciemny, zgaszony wzorzec
        cls.user, cls.ref = look.measure(cls.bright), look.measure(cls.dark)

    def test_tone_curve_is_monotone_and_spans_the_full_range(self):
        import numpy as np

        for strength in (0.0, 0.5, 1.0):
            grid, f = look.tone_curve(self.user, self.ref, strength)
            self.assertTrue(bool((np.diff(f) >= -1e-9).all()), strength)
            self.assertGreaterEqual(float(f[0]), 0.0)
            self.assertLessEqual(float(f[-1]), 100.0 + 1e-9)

    def test_strength_zero_is_identity(self):
        lut = look.build_lut(self.user, self.ref, 0.0, size=17)
        import numpy as np

        self.assertLess(float(np.abs(lut - look.identity_lut(17)).max()), 0.02)

    def test_equal_stats_change_almost_nothing(self):
        import numpy as np

        lut = look.build_lut(self.user, self.user, 1.0, size=17)
        self.assertLess(float(np.abs(lut - look.identity_lut(17)).mean()), 0.015)

    def test_full_strength_lands_on_the_reference_distribution(self):
        out = look.apply_lut(self.bright, look.build_lut(self.user, self.ref, 1.0))
        got = look.measure(out)
        for i in range(2, 9):  # bez skrajnych percentyli (0.5, 99.5)
            self.assertAlmostEqual(got.luma[i], self.ref.luma[i], delta=2.0, msg=f"percentyl {look.PCTS[i]}")
        before, after = look.distance(self.user, self.ref), look.distance(got, self.ref)
        self.assertLess(after["luma"], 0.2 * before["luma"])
        self.assertLess(after["chroma"], 0.4 * before["chroma"])

    def test_half_strength_lands_between(self):
        half = look.measure(look.apply_lut(self.bright, look.build_lut(self.user, self.ref, 0.5)))
        mid = (self.user.luma[5] + self.ref.luma[5]) / 2
        self.assertAlmostEqual(half.luma[5], mid, delta=3.0)
        self.assertTrue(self.ref.chroma < half.chroma < self.user.chroma)

    def test_skin_hue_is_kept_while_neutral_tones_take_the_cast(self):
        import numpy as np

        teal = synth(12, light=0.55, sat=0.3, tint=(-0.07, 0.03, 0.05))
        ref = look.measure(teal)
        lut = look.build_lut(self.user, ref, 1.0)
        pix = np.array([[[196, 146, 118], [128, 128, 128]]], np.uint8)  # skóra, neutralny szary
        out = look.apply_lut(pix, lut)[0]
        skin_in, skin_out = hue(pix[0, 0]), hue(out[0])
        self.assertLess(abs(skin_out - skin_in), 10.0)
        lab = look.srgb_to_lab(out[1] / 255.0)
        want = look._bin_curve(ref, "a", np.array([lab[0]]))[0], look._bin_curve(ref, "b", np.array([lab[0]]))[0]
        self.assertGreater(lab[1] * want[0] + lab[2] * want[1], 0.0)  # szarość przesunięta w stronę barwy wzorca

    def test_lut_shape_and_range(self):
        lut = look.build_lut(self.user, self.ref, 1.0, size=9)
        self.assertEqual(lut.shape, (9, 9, 9, 3))
        self.assertGreaterEqual(float(lut.min()), 0.0)
        self.assertLessEqual(float(lut.max()), 1.0)

    def test_cube_file_format_has_red_as_fastest_axis(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "x.cube"
            look.write_cube(look.identity_lut(5), path)
            lines = path.read_text().splitlines()
        self.assertIn("LUT_3D_SIZE 5", lines)
        data = [ln for ln in lines if ln and ln[0] in "0123456789"]
        self.assertEqual(len(data), 125)
        self.assertEqual(data[1].split(), ["0.250000", "0.000000", "0.000000"])
        self.assertEqual(data[5].split(), ["0.000000", "0.250000", "0.000000"])
        self.assertEqual(data[25].split(), ["0.000000", "0.000000", "0.250000"])

    def test_template_look_block_is_usable(self):
        self.assertIsNotNone(REF, "szablon wzorcowy ma mieć blok look.A")
        self.assertEqual(len(REF.luma), len(look.PCTS))
        out = look.apply_lut(self.bright, look.build_lut(self.user, REF, 1.0))
        self.assertLess(look.distance(look.measure(out), REF)["luma"], 2.5)


@unittest.skipUnless(HAVE_NP and HAVE_FFMPEG, "brak numpy albo ffmpeg")
class FfmpegTests(unittest.TestCase):
    def test_ffmpeg_lut3d_matches_the_numpy_model(self):
        import numpy as np

        frames = synth(20, n=1, h=96, w=54)
        lut = look.build_lut(look.measure(synth(10, light=1.0, sat=1.4)), look.measure(synth(11, light=0.55, sat=0.35)), 1.0)
        with tempfile.TemporaryDirectory() as d:
            cube = pathlib.Path(d) / "look.cube"
            look.write_cube(lut, cube)
            raw = subprocess.run(
                ["ffmpeg", "-v", "error", "-nostdin", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "54x96", "-i", "-",
                 "-vf", "lut3d=file=look.cube:interp=tetrahedral", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                input=frames.tobytes(), capture_output=True, check=True, cwd=d).stdout
        got = np.frombuffer(raw, np.uint8).reshape(frames.shape).astype(float)
        want = look.apply_lut(frames, lut).astype(float)
        self.assertLess(float(np.abs(got - want).mean()), 1.5)
        self.assertLess(float(np.percentile(np.abs(got - want), 99)), 6.0)

    def test_filter_chain_order_and_tags(self):
        chain = look.filter_chain("look.cube", 0.35)
        parts = chain.split(",")
        self.assertEqual(parts[0], "format=gbrp")
        self.assertLess(chain.index("vignette="), chain.index("lut3d="))  # statystyki liczymy już z winietą
        self.assertIn("lut3d=file=look.cube:interp=tetrahedral", chain)
        self.assertEqual(parts[-1], "format=yuv420p")
        self.assertIn("out_color_matrix=bt709", chain)
        self.assertNotIn("vignette", look.filter_chain("look.cube", None))
        self.assertNotIn("lut3d", look.filter_chain(None, 0.3))

    def test_vignette_is_added_only_when_the_reference_is_darker_at_the_edges(self):
        s = look.measure(synth(1))
        flat = dataclasses.replace(s, vignette=[1.0, 1.0, 1.0])
        ref = dataclasses.replace(s, vignette=[0.9, 0.72, 0.66])
        self.assertIsNone(look.vignette_angle(flat, flat, 1.0))
        self.assertIsNone(look.vignette_angle(flat, ref, 0.0))
        dark_edges = dataclasses.replace(s, vignette=[0.8, 0.5, 0.4])
        self.assertIsNone(look.vignette_angle(dark_edges, ref, 1.0))  # Twoje brzegi są już ciemniejsze: nie dokładamy
        angle = look.vignette_angle(flat, ref, 1.0, base_L=21.0)
        self.assertIsNotNone(angle)
        table = dict(look.vignette_table(21.0))
        for got, want in zip(table[angle][1:], ref.vignette[1:]):
            self.assertAlmostEqual(got, want, delta=0.08)

    def test_read_frames_post_filter_darkens_corners(self):
        import numpy as np

        with tempfile.TemporaryDirectory() as d:
            src = pathlib.Path(d) / "gray.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x808080:s=180x320:r=10:d=1.0",
                            "-pix_fmt", "yuv420p", str(src)], check=True)
            plain = look.read_frames(src, fps=2, max_frames=1)[0].astype(float)
            vig = look.read_frames(src, fps=2, max_frames=1,
                                   post_filter="format=gbrp,vignette=angle=0.8:mode=forward:eval=init,format=rgb24")[0].astype(float)
        self.assertLess(float(vig[:20, :20].mean()), 0.7 * float(plain[:20, :20].mean()))
        self.assertAlmostEqual(float(vig[150:170, 80:100].mean()), float(plain[150:170, 80:100].mean()), delta=6.0)


@unittest.skipUnless(HAVE_NP and HAVE_PIL and HAVE_FFMPEG and ASSET.exists(), "brak numpy/Pillow/ffmpeg albo obrazu testowego")
class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image

        from reelcut.pipeline import Options, run

        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="look_"))
        img = Image.open(ASSET).convert("RGB")
        canvas = Image.new("RGB", (1080, 1920), (60, 70, 90))
        k = 1080 / img.width
        canvas.paste(img.resize((1080, round(img.height * k)), Image.LANCZOS), (0, 500))
        canvas.save(cls.tmp / "p.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "25", "-i", str(cls.tmp / "p.png"), "-f", "lavfi",
                        "-i", "sine=f=220:d=24", "-t", "24", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.tmp / "in.mp4")], check=True)
        common = dict(captions="off", snap=False, framing="off", max_zoom=1.0, preset="ultrafast", crf=22)
        cls.on = run(cls.tmp / "in.mp4", cls.tmp / "on.mp4", Options(look=1.0, **common), log=lambda m: None)
        cls.off = run(cls.tmp / "in.mp4", cls.tmp / "off.mp4", Options(look=0.0, **common), log=lambda m: None)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def tags(path):
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=color_range,color_space,color_transfer,color_primaries", "-of", "json", str(path)],
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)["streams"][0]

    def test_look_moves_the_output_toward_the_reference(self):
        inp = look.measure(look.read_frames(self.tmp / "in.mp4", fps=1))
        out = look.measure(look.read_frames(self.tmp / "on.mp4", fps=1))
        before, after = look.distance(inp, REF), look.distance(out, REF)
        self.assertLess(after["luma"], 0.5 * before["luma"])
        self.assertLess(after["chroma"], 0.7 * before["chroma"])
        self.assertTrue(self.on.look)
        self.assertEqual(self.on.look["strength"], 1.0)

    def test_look_output_is_tagged_bt709_limited_range(self):
        t = self.tags(self.tmp / "on.mp4")
        self.assertEqual((t["color_space"], t["color_transfer"], t["color_primaries"], t["color_range"]),
                         ("bt709", "bt709", "bt709", "tv"))

    def test_look_zero_leaves_colors_alone(self):
        import numpy as np

        self.assertEqual(self.off.look, {})
        inp = look.read_frames(self.tmp / "in.mp4", fps=1).astype(float)
        out = look.read_frames(self.tmp / "off.mp4", fps=1).astype(float)
        self.assertLess(float(np.abs(inp.mean(axis=(0, 1, 2)) - out.mean(axis=(0, 1, 2))).max()), 2.5)


@unittest.skipUnless(HAVE_FFMPEG, "brak ffmpeg")
class WithoutNumpyTests(unittest.TestCase):
    def test_pipeline_still_cuts_and_explains_what_was_skipped(self):
        code = textwrap.dedent("""
            import json, sys
            sys.modules["numpy"] = None  # symulacja: numpy i onnxruntime niedostępne
            sys.modules["onnxruntime"] = None
            sys.path.insert(0, sys.argv[1])
            from reelcut.pipeline import Options, run
            res = run(sys.argv[2], sys.argv[3], Options(captions="off", snap=False, preset="ultrafast", crf=32), log=lambda m: None)
            print(json.dumps({"warnings": res.warnings, "face": res.face, "look": res.look}))
        """)
        with tempfile.TemporaryDirectory() as d:
            src, dst = pathlib.Path(d) / "in.mp4", pathlib.Path(d) / "out.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=270x480:r=25:d=24", "-f", "lavfi", "-i",
                            "sine=f=220:d=24", "-t", "24", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a",
                            "aac", "-shortest", str(src)], check=True)
            out = subprocess.run([sys.executable, "-I", "-c", code, str(HERE.parent / "src"), str(src), str(dst)],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr[-800:])
            info = json.loads(out.stdout.strip().splitlines()[-1])
            self.assertTrue(dst.exists() and dst.stat().st_size > 10_000)
        self.assertEqual((info["face"], info["look"]), ({}, {}))
        text = " ".join(info["warnings"])
        self.assertIn("numpy", text)
        self.assertIn("Kadruję wg stałych zoomów", text)
        self.assertIn("Kolory zostają bez zmian", text)


if __name__ == "__main__":
    unittest.main()
