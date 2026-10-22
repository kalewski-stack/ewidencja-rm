import importlib.util
import math
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import faces, framing, media  # noqa: E402
from reelcut.faces import Face, FaceEstimate, FaceTrack  # noqa: E402
from reelcut.planner import build_plan  # noqa: E402
from reelcut.template import load_template  # noqa: E402

TPL = load_template()
HAVE_ORT = all(importlib.util.find_spec(m) for m in ("numpy", "onnxruntime"))
HAVE_PIL = importlib.util.find_spec("PIL") is not None
ASSET = HERE / "assets" / "face_nasa_astronaut.jpg"


def est(h=0.12, cx=0.5, cy=0.4, w=0.07) -> FaceEstimate:
    return FaceEstimate(h=h, cx=cx, cy=cy, eye_y=cy - 0.02, n=10, w=w)


def constant_track(h=0.12, cx=0.5, cy=0.4, seconds=60.0) -> FaceTrack:
    f = Face(cx - 0.035, cy - h / 2, 0.07, h, 0.9, cy - 0.02)
    return FaceTrack([(t * 0.4, f) for t in range(int(seconds / 0.4))])


class PlanZoomTests(unittest.TestCase):
    def test_exact_sizes_when_users_face_is_smaller_than_the_widest_shot(self):
        z = framing.plan_zooms([0.12, 0.20, 0.36], h_user=0.10, max_zoom=5.0)
        self.assertEqual([round(v, 3) for v in z], [1.2, 2.0, 3.6])

    def test_relative_ladder_when_users_face_is_bigger(self):
        z = framing.plan_zooms([0.12, 0.20, 0.36], h_user=0.20, max_zoom=9.0, face_limit=9.0)
        self.assertEqual([round(v, 3) for v in z], [1.0, 1.667, 3.0])

    def test_face_limit_compresses_the_whole_ladder_keeping_order_and_ratios_in_log_space(self):
        z = framing.plan_zooms([0.12, 0.20, 0.36], h_user=0.20, max_zoom=9.0)  # limit 0.42/0.20 = 2.1
        self.assertAlmostEqual(max(z), 2.1, places=6)
        self.assertEqual(z, sorted(z))
        raw = [1.0, 0.20 / 0.12, 3.0]
        p = math.log(2.1) / math.log(3.0)
        for a, b in zip(z, raw):
            self.assertAlmostEqual(a, b ** p, places=6)

    def test_resolution_cap_and_no_zoom(self):
        self.assertAlmostEqual(max(framing.plan_zooms([0.12, 0.36], 0.12, max_zoom=1.6)), 1.6)
        self.assertEqual(framing.plan_zooms([0.12, 0.36], 0.12, max_zoom=1.0), [1.0, 1.0])
        self.assertEqual(framing.plan_zooms([], 0.12, 2.0), [])

    def test_never_zooms_out(self):
        self.assertTrue(all(v >= 1.0 for v in framing.plan_zooms([0.05, 0.3], h_user=0.4, max_zoom=3.0)))


class WindowTests(unittest.TestCase):
    def test_face_lands_on_target_when_window_has_room(self):
        e = est(h=0.12, cx=0.5, cy=0.4)
        for z, (tx, ty) in ((1.5, (0.45, 0.35)), (2.0, (0.58, 0.30)), (2.5, (0.60, 0.38))):
            fx, fy = framing.window_center(e, z, tx, ty)
            ox, oy, oh = framing.face_in_output(e, z, fx, fy)
            self.assertAlmostEqual(ox, tx, places=6)
            self.assertAlmostEqual(oy, ty, places=6)
            self.assertAlmostEqual(oh, 0.12 * z, places=6)

    def test_no_room_at_zoom_one_keeps_face_where_it_is(self):
        e = est(cx=0.5, cy=0.4)
        fx, fy = framing.window_center(e, 1.0, 0.5, 0.48)
        ox, oy, _ = framing.face_in_output(e, 1.0, fx, fy)
        self.assertAlmostEqual(oy, 0.4, places=6)  # okno nie może wyjść poza kadr

    def test_fit_target_keeps_face_inside_frame(self):
        self.assertAlmostEqual(framing._fit_target(0.02, 0.2), framing.MARGIN + 0.1)
        self.assertAlmostEqual(framing._fit_target(0.99, 0.2), 1 - framing.MARGIN - 0.1)
        self.assertEqual(framing._fit_target(0.4, 0.2), 0.4)
        self.assertEqual(framing._fit_target(0.9, 1.5), 0.5)  # twarz większa niż kadr: środek


class ApplyFramingTests(unittest.TestCase):
    def plan(self, track, max_zoom=3.2, **kw):
        return build_plan(TPL, 850, snap=False, max_zoom=max_zoom, track=track, **kw)

    def test_zoom_follows_the_reference_ladder(self):
        plan = self.plan(constant_track(h=0.118))
        a = [s for s in plan.slots if s.role == "A"]
        for s in a:
            tgt = TPL.segments[s.tpl_index].face
            self.assertAlmostEqual(s.zoom, tgt.h / 0.118, delta=0.01)
            self.assertAlmostEqual(s.face_h, tgt.h, delta=0.005)

    def test_without_track_uses_the_fixed_ladder_as_fallback(self):
        plan = self.plan(None, max_zoom=1.6)
        zooms = {s.tpl_index: s.zoom for s in plan.slots if s.role == "A"}
        self.assertEqual(max(zooms.values()) <= 1.6 + 1e-9, True)
        self.assertGreater(zooms[11], zooms[1])  # zbliżenie > średni
        self.assertTrue(all(s.face_h is None for s in plan.slots))

    def test_big_faces_get_compressed_ladder(self):
        plan = self.plan(constant_track(h=0.25), max_zoom=3.2)
        zs = [s.zoom for s in plan.slots if s.role == "A"]
        self.assertLessEqual(max(zs), framing.FACE_LIMIT / 0.25 + 0.01)

    def test_detail_slots_zoom_into_face_or_below_it(self):
        plan = self.plan(constant_track(h=0.12, cy=0.35), max_zoom=3.0)
        details = [s for s in plan.slots if s.role == "B" and s.source == "A"]
        self.assertTrue(details)
        for s in details:
            alt = TPL.alts[TPL.segments[s.tpl_index].alt]
            if alt["anchor"] == "face":
                self.assertGreaterEqual(s.zoom, 1.2)
                self.assertAlmostEqual(s.fy, 0.36, places=2)
            else:
                self.assertGreater(s.fy, 0.35 + 0.12)  # pod twarzą

    def test_no_zoom_means_no_framing_changes(self):
        plan = self.plan(constant_track(), max_zoom=1.0)
        self.assertTrue(all(abs(s.zoom - 1.0) < 1e-9 for s in plan.slots if s.source == "A"))

    def test_consecutive_framed_slots_still_differ_visibly(self):
        plan = self.plan(constant_track(h=0.118), max_zoom=3.2)
        for a, b in zip(plan.slots, plan.slots[1:]):
            if a.source == "A" and b.source == "A":
                ratio = max(a.zoom, b.zoom) / min(a.zoom, b.zoom) - 1
                shift = max(abs(a.fx - b.fx), abs(a.fy - b.fy)) * max(a.zoom, b.zoom)
                self.assertTrue(ratio >= 0.10 - 1e-9 or shift >= 0.12, (a.index, a.zoom, b.zoom, shift))


class FaceTrackTests(unittest.TestCase):
    def test_estimate_uses_local_detections_when_enough(self):
        near = Face(0.4, 0.2, 0.2, 0.3, 0.9, 0.25)
        far = Face(0.45, 0.4, 0.1, 0.12, 0.9, 0.42)
        tr = FaceTrack([(0.0, far), (0.4, far), (0.8, far), (1.0, near), (1.2, near), (1.4, near), (1.6, near)])
        self.assertAlmostEqual(tr.estimate(1.0, 2.0).h, 0.3)
        self.assertAlmostEqual(tr.estimate(0.0, 0.9).h, 0.12)

    def test_estimate_falls_back_to_global(self):
        f = Face(0.4, 0.2, 0.2, 0.3, 0.9, 0.25)
        tr = FaceTrack([(0.0, f), (0.4, None), (0.8, f)])
        self.assertAlmostEqual(tr.estimate(0.4, 0.5).h, 0.3)
        self.assertAlmostEqual(tr.coverage(), 2 / 3)

    def test_empty_track(self):
        tr = FaceTrack([(0.0, None), (0.4, None)])
        self.assertIsNone(tr.global_estimate())
        self.assertIsNone(tr.estimate(0, 1))


@unittest.skipUnless(HAVE_ORT, "brak numpy/onnxruntime")
class DecoderTests(unittest.TestCase):
    def test_decode_synthetic_output(self):
        import numpy as np

        det = faces.FaceDetector()
        outs = {}
        for stride in faces.STRIDES:
            n = (faces.SIZE // stride) ** 2
            outs[f"cls_{stride}"] = np.zeros((1, n, 1), np.float32)
            outs[f"obj_{stride}"] = np.zeros((1, n, 1), np.float32)
            outs[f"bbox_{stride}"] = np.zeros((1, n, 4), np.float32)
            outs[f"kps_{stride}"] = np.zeros((1, n, 10), np.float32)
        cols, r, c = 40, 10, 20  # krok 16: siatka 40x40
        i = r * cols + c
        outs["cls_16"][0, i, 0] = outs["obj_16"][0, i, 0] = 0.9
        outs["bbox_16"][0, i] = [0.5, 0.5, math.log(40 / 16), math.log(60 / 16)]
        outs["kps_16"][0, i] = [0, -1.0, 0, -1.0, 0, 0, 0, 1, 0, 1]  # oczy 1 komórkę nad środkiem
        found = det._decode(outs, 360, 640)
        self.assertEqual(len(found), 1)
        f = found[0]
        self.assertAlmostEqual(f.x * 360, 308, delta=0.01)
        self.assertAlmostEqual(f.y * 640, 138, delta=0.01)
        self.assertAlmostEqual(f.w * 360, 40, delta=0.01)
        self.assertAlmostEqual(f.h * 640, 60, delta=0.01)
        self.assertAlmostEqual(f.score, 0.9, places=4)
        self.assertAlmostEqual(f.eye_y * 640, (10 - 1.0) * 16, delta=0.01)

    def test_nms_merges_overlapping_boxes_and_keeps_separate_faces(self):
        import numpy as np

        det = faces.FaceDetector()
        boxes = np.array([[100, 100, 50, 60], [104, 102, 50, 60], [300, 300, 50, 60]], np.float32)
        scores = np.array([0.9, 0.8, 0.7], np.float32)
        self.assertEqual(det._nms_keep(boxes, scores), [0, 2])

    def test_rejects_oversized_frames(self):
        import numpy as np

        with self.assertRaises(ValueError):
            faces.FaceDetector().detect(np.zeros((700, 300, 3), np.uint8))

    def test_blank_frame_has_no_face(self):
        import numpy as np

        self.assertEqual(faces.FaceDetector().detect(np.full((640, 360, 3), 40, np.uint8)), [])


@unittest.skipUnless(HAVE_ORT and HAVE_PIL and ASSET.exists(), "brak numpy/onnxruntime/Pillow albo obrazu testowego")
class RealFaceTests(unittest.TestCase):
    def test_detects_the_face_in_the_test_photo(self):
        import numpy as np
        from PIL import Image

        f = faces.FaceDetector().detect(np.asarray(Image.open(ASSET).convert("RGB")))
        self.assertEqual(len(f), 1)
        self.assertAlmostEqual(f[0].h, 0.22, delta=0.04)
        self.assertAlmostEqual(f[0].cx, 0.44, delta=0.05)
        self.assertGreater(f[0].score, 0.8)

    @unittest.skipUnless(shutil.which("ffmpeg"), "brak ffmpeg")
    def test_output_faces_match_planned_sizes_and_positions(self):
        import numpy as np
        from PIL import Image

        from reelcut.pipeline import Options, run

        det = faces.FaceDetector(score=0.5)
        img = Image.open(ASSET).convert("RGB")
        f = det.detect(np.asarray(img))[0]
        H, W = 1920, 1080
        k = 0.12 * H / (f.h * img.height)  # twarz ma mieć 12% wysokości, jak najszerszy kadr wzorca
        big = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
        canvas = Image.new("RGB", (W, H), (20, 20, 24))
        canvas.paste(big, (round(0.5 * W - (f.x + f.w / 2) * big.width), round(0.40 * H - (f.y + f.h / 2) * big.height)))
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            canvas.save(d / "p.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "25", "-i", str(d / "p.png"), "-f", "lavfi",
                            "-i", "sine=f=220:d=24", "-t", "24", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "in.mp4")], check=True)
            res = run(d / "in.mp4", d / "out.mp4", Options(captions="off", snap=False, max_zoom=3.2, framing="on",
                                                          preset="ultrafast", crf=24), log=lambda m: None)
            self.assertAlmostEqual(res.face["h"], 0.12, delta=0.01)
            track = FaceTrack(faces.sample_faces(d / "out.mp4", every_s=0.1, detector=det))
            checked = 0
            for s in res.plan.slots:
                seg = TPL.segments[s.tpl_index]
                if seg.face is None or s.source != "A" or s.zoom < 1.05:
                    continue
                e = track.estimate(s.start / 25 + 0.1, s.end / 25 - 0.05, min_count=3)
                if e is None or e.n < 3:
                    continue
                self.assertAlmostEqual(e.h, s.face_h, delta=0.10 * s.face_h, msg=f"ujęcie {s.index + 1}")
                self.assertAlmostEqual(e.cx, seg.face.cx, delta=0.04, msg=f"ujęcie {s.index + 1}")
                self.assertAlmostEqual(e.cy, seg.face.cy, delta=0.04, msg=f"ujęcie {s.index + 1}")
                checked += 1
            self.assertGreaterEqual(checked, 4)


if __name__ == "__main__":
    unittest.main()
