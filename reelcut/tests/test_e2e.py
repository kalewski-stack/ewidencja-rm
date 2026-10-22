"""Testy end-to-end na syntetycznych nagraniach (ffmpeg/lavfi). Napisy wyłączone, żeby nie wymagać modelu mowy."""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from reelcut import media  # noqa: E402
from reelcut.pipeline import Options, run  # noqa: E402
from reelcut.template import load_template  # noqa: E402

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
TPL = load_template()


def ff(*args, cwd=None):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, cwd=cwd)


def make_input(path: pathlib.Path, seconds: float, *, frames: int | None = None, gap: tuple[float, float] | None = None,
               size: str = "1080x1920") -> None:
    """Obraz testsrc2 (dużo detali: każde przybliżenie kadru jest mierzalne) + stały ton, opcjonalnie z ciszą."""
    amp = "0.2*sin(2*PI*220*t)"
    if gap:
        amp += f"*(lt(t,{gap[0]})+gt(t,{gap[1]}))"
    vopts = ["-frames:v", str(frames)] if frames else ["-t", str(seconds)]
    ff("-f", "lavfi", "-i", f"testsrc2=s={size}:r=25", "-f", "lavfi", "-i", f"aevalsrc='{amp}':s=48000:d={seconds}",
       *vopts, "-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p",
       "-c:a", "aac", str(path))


def scene_scores(video: pathlib.Path) -> list[float]:
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "s.txt"
        ff("-i", str(video), "-an", "-vf", f"select='gte(scene,0)',metadata=print:key=lavfi.scene_score:file={out.name}",
           "-f", "null", "-", cwd=d)
        return [float(m.group(1)) for m in re.finditer(r"scene_score=([\d.]+)", out.read_text())]


def detected_cuts(video: pathlib.Path, threshold: float = 0.04) -> list[int]:
    sc = scene_scores(video)
    cuts: list[int] = []
    for i in range(1, len(sc)):
        if sc[i] >= threshold and (not cuts or i - cuts[-1] > 3):
            cuts.append(i)
    return cuts


def mean_rgb(video: pathlib.Path, t: float) -> tuple[float, float, float]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf",
                          "scale=8:8", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    px = [raw[i:i + 3] for i in range(0, len(raw), 3)]
    return tuple(sum(p[c] for p in px) / len(px) for c in range(3))


def integrated_lufs(video: pathlib.Path) -> float:
    res = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn", "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True)
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", res.stderr)[-1])


@unittest.skipUnless(HAVE_FFMPEG, "brak ffmpeg/ffprobe")
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_test_"))
        cls.src34 = cls.tmp / "in34.mp4"
        make_input(cls.src34, 34.0, frames=850)
        cls.opts = dict(captions="off", preset="ultrafast", crf=30)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_cuts_land_on_exactly_the_template_frames(self):
        out = self.tmp / "exact.mp4"
        res = run(self.src34, out, Options(snap=False, **self.opts), log=lambda m: None)
        self.assertEqual(res.plan.mode, "identyczny")
        info = media.probe(out)
        self.assertEqual((info.width, info.height), (1080, 1920))
        self.assertAlmostEqual(info.fps, 25, delta=0.01)
        self.assertAlmostEqual(info.duration, 34.0, delta=0.1)
        expected = [64, 131, 171, 200, 269, 314, 357, 434, 476, 502, 565, 612, 634, 775]
        self.assertEqual(detected_cuts(out), expected)

    def test_audio_is_normalised_to_target_loudness(self):
        out = self.tmp / "loud.mp4"
        run(self.src34, out, Options(snap=False, **self.opts), log=lambda m: None)
        self.assertAlmostEqual(integrated_lufs(out), TPL.lufs, delta=1.0)

    def test_dry_run_plans_without_rendering(self):
        out = self.tmp / "dry.mp4"
        res = run(self.src34, out, Options(dry_run=True, **self.opts), log=lambda m: None)
        self.assertIsNone(res.output)
        self.assertFalse(out.exists())
        self.assertEqual(len(res.plan.slots), 15)

    def test_long_pause_is_tightened(self):
        src = self.tmp / "gap.mp4"
        make_input(src, 20.0, gap=(8.0, 11.5))  # 3,5 s ciszy
        # dwa tony różnej głośności, żeby estymator szumu/mowy miał z czego liczyć próg
        res = run(src, self.tmp / "gap_out.mp4", Options(dry_run=True, **self.opts), log=lambda m: None)
        self.assertLess(res.master_seconds, 20.0 - 2.5)
        self.assertGreater(res.master_seconds, 20.0 - 3.5)

    def test_b_roll_replaces_b_slots_with_other_footage(self):
        red, blue = self.tmp / "red.mp4", self.tmp / "blue_wide.mp4"
        ff("-f", "lavfi", "-i", "color=c=red:s=1080x1920:r=25:d=8", "-c:v", "libx264", "-preset", "ultrafast", str(red))
        ff("-f", "lavfi", "-i", "color=c=blue:s=1920x1080:r=25:d=1", "-c:v", "libx264", "-preset", "ultrafast", str(blue))
        out = self.tmp / "broll.mp4"
        res = run(self.src34, out, Options(snap=False, broll=(red, blue), **self.opts), log=lambda m: None)
        b_slots = [s for s in res.plan.slots if s.source == "B"]
        self.assertEqual(len(b_slots), 6)
        seen = set()
        for s in b_slots:
            r, g, b = mean_rgb(out, (s.start + s.frames / 2) / 25)
            if r > 180 and g < 70 and b < 70:
                seen.add("red")
            elif b > 150 and r < 70 and g < 70:
                seen.add("blue")
            else:
                self.fail(f"ujęcie {s.index + 1} nie jest B-rollem: rgb=({r:.0f},{g:.0f},{b:.0f})")
        self.assertEqual(seen, {"red", "blue"})
        a_slots = [s for s in res.plan.slots if s.source == "A"]
        r, g, b = mean_rgb(out, (a_slots[0].start + a_slots[0].frames / 2) / 25)
        self.assertFalse(r > 180 and g < 70 and b < 70)

    def test_snapping_keeps_total_length_and_changes_only_a_little(self):
        res = run(self.src34, self.tmp / "snap.mp4", Options(snap=True, **self.opts), log=lambda m: None)
        self.assertEqual(sum(s.frames for s in res.plan.slots), 850)
        self.assertTrue(all(abs(s.shifted) <= 13 for s in res.plan.slots))

    def test_landscape_input_is_cropped_to_vertical_with_warning(self):
        src = self.tmp / "wide.mp4"
        make_input(src, 14.0, size="1920x1080")
        res = run(src, self.tmp / "wide_out.mp4", Options(**self.opts), log=lambda m: None)
        info = media.probe(res.output)
        self.assertEqual((info.width, info.height), (1080, 1920))
        self.assertTrue(any("poziome" in w for w in res.warnings))

    def test_short_input_still_renders(self):
        src = self.tmp / "short.mp4"
        make_input(src, 7.0)
        res = run(src, self.tmp / "short_out.mp4", Options(**self.opts), log=lambda m: None)
        self.assertTrue(res.output.exists())
        self.assertTrue(res.warnings)

    def test_missing_audio_is_handled(self):
        src = self.tmp / "silent.mp4"
        ff("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=25:d=15", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(src))
        res = run(src, self.tmp / "silent_out.mp4", Options(**self.opts), log=lambda m: None)
        self.assertFalse(media.probe(res.output).has_audio)
        self.assertTrue(any("dźwięk" in w for w in res.warnings))

    def test_rejects_non_video(self):
        bad = self.tmp / "bad.mp4"
        bad.write_bytes(b"nie wideo")
        with self.assertRaises(media.MediaError):
            run(bad, None, Options(**self.opts), log=lambda m: None)


if __name__ == "__main__":
    unittest.main()
