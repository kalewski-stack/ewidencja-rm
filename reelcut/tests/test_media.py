import math
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from array import array

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from reelcut import media  # noqa: E402

SR = 16000


def tone(seconds: float, amp: float) -> array:
    n = int(SR * seconds)
    return array("h", (int(amp * 32767 * math.sin(2 * math.pi * 220 * i / SR)) for i in range(n)))


def silence(seconds: float) -> array:
    return array("h", [0] * int(SR * seconds))


def speechlike() -> array:
    """2 s "mowy", 1,2 s ciszy, 2 s "mowy", 0,3 s ciszy, 1 s "mowy"."""
    out = array("h")
    for part in (tone(2, 0.2), silence(1.2), tone(2, 0.2), silence(0.3), tone(1, 0.2)):
        out.extend(part)
    return out


class PauseTests(unittest.TestCase):
    def test_envelope_level_of_sine(self):
        env = media.level_envelope(tone(1.0, 0.1), SR)
        self.assertAlmostEqual(sum(env) / len(env), 20 * math.log10(0.1 / math.sqrt(2)), delta=0.3)

    def test_detects_only_long_pause(self):
        env = media.level_envelope(speechlike(), SR)
        pauses = media.detect_pauses(env, min_pause=0.5)
        self.assertEqual(len(pauses), 1)
        self.assertAlmostEqual(pauses[0][0], 2.0, delta=0.05)
        self.assertAlmostEqual(pauses[0][1], 3.2, delta=0.05)

    def test_flat_audio_has_no_pauses(self):
        self.assertEqual(media.detect_pauses(media.level_envelope(tone(5, 0.2), SR)), [])

    def test_keep_ranges_shortens_pause_to_keep_value(self):
        fps = 25
        ranges = media.keep_ranges(5.3, [(2.0, 3.2)], max_pause=0.5, keep_pause=0.35, fps=fps)
        kept = sum(b - a for a, b in ranges)
        self.assertEqual(len(ranges), 2)
        self.assertAlmostEqual(kept / fps, 5.3 - (1.2 - 0.35), delta=0.1)

    def test_pause_not_longer_than_max_is_kept(self):
        ranges = media.keep_ranges(6.0, [(2.0, 2.4)], max_pause=0.5, keep_pause=0.35, fps=25)
        self.assertEqual(ranges, [(0, 150)])

    def test_leading_and_trailing_silence_is_trimmed(self):
        ranges = media.keep_ranges(10.0, [(0.0, 1.5), (9.0, 10.0)], max_pause=0.5, keep_pause=0.35, fps=25)
        self.assertEqual(len(ranges), 1)
        a, b = ranges[0]
        self.assertAlmostEqual(a / 25, 1.5 - 0.12, delta=0.05)
        self.assertAlmostEqual(b / 25, 9.2, delta=0.05)

    def test_map_to_master_and_joins(self):
        ranges = [(0, 100), (200, 300)]
        self.assertEqual(media.map_to_master(50, ranges), 50)
        self.assertEqual(media.map_to_master(150, ranges), None)
        self.assertEqual(media.map_to_master(250, ranges), 150)
        self.assertEqual(media.join_frames(ranges), [100])

    def test_speech_breaks_include_joins_with_top_strength(self):
        env = media.level_envelope(speechlike(), SR)
        breaks = dict(media.speech_breaks(env, 25, joins=[50]))
        self.assertEqual(breaks[50], 3.0)
        self.assertTrue(any(s >= 2.0 for f, s in breaks.items() if abs(f - 25 * 2.1) < 10))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "brak ffmpeg")
class ProbeTests(unittest.TestCase):
    def test_probe_reads_basic_properties(self):
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "t.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x568:r=30:d=2",
                            "-f", "lavfi", "-i", "sine=f=440:d=2", "-shortest", "-pix_fmt", "yuv420p", str(f)], check=True)
            info = media.probe(f)
            self.assertEqual((info.width, info.height), (320, 568))
            self.assertAlmostEqual(info.fps, 30, delta=0.01)
            self.assertAlmostEqual(info.duration, 2.0, delta=0.1)
            self.assertTrue(info.has_audio and info.has_video)

    def test_read_pcm_returns_expected_length(self):
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "t.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=1.5", str(f)], check=True)
            self.assertAlmostEqual(len(media.read_pcm(f, SR)) / SR, 1.5, delta=0.05)

    def test_probe_rejects_garbage(self):
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "x.mp4"
            f.write_bytes(b"to nie jest wideo")
            with self.assertRaises(media.MediaError):
                media.probe(f)


if __name__ == "__main__":
    unittest.main()
