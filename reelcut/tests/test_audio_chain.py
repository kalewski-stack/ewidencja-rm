"""Łańcuch audio końcowego montażu: ma przechodzić na każdej wersji ffmpeg, także starej.

W ffmpeg 4.4 do 6.0 „loudnorm” z gołym „aresample” po nim kończy się błędem
„Cannot select channel layout for the link between filters Parsed_aresample_1 and format_out_0_1”,
bo koder AAC nie podaje obsługiwanych układów kanałów. Pliki startowe nie wymuszają nowego ffmpeg,
więc program ma sam pinować częstotliwość i stereo na końcu łańcucha."""
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

from reelcut import media, render  # noqa: E402
from reelcut.planner import Plan, Slot  # noqa: E402

MEASURED = {"input_i": "-20.50", "input_tp": "-3.10", "input_lra": "5.00", "input_thresh": "-31.00", "target_offset": "0.30"}
OTHER_FFMPEGS = [p for p in os.environ.get("REELCUT_TEST_FFMPEGS", "").split(os.pathsep) if p]


class AudioChainTests(unittest.TestCase):
    def test_the_chain_ends_with_an_explicit_rate_and_layout_not_a_bare_aresample(self):
        with mock.patch.object(render, "measure_loudness", return_value=MEASURED):
            af = render.audio_filter(pathlib.Path("master.mkv"), -14.0, -1.0, 11.0)
        self.assertTrue(af.startswith("loudnorm=I=-14.0:TP=-1.0:LRA=11.0:measured_I=-20.50:measured_TP=-3.10"))
        self.assertTrue(af.endswith(":linear=true," + render.AUDIO_TAIL), af)
        self.assertNotIn("aresample", af)
        self.assertIn("sample_rates=48000", render.AUDIO_TAIL)
        self.assertIn("channel_layouts=stereo", render.AUDIO_TAIL)

    def test_without_a_measurement_only_the_pinned_tail_remains(self):
        with mock.patch.object(render, "measure_loudness", return_value=None):
            self.assertEqual(render.audio_filter(pathlib.Path("master.mkv"), -14.0, -1.0, 11.0), render.AUDIO_TAIL)

    def test_the_final_render_asks_the_aac_encoder_for_48k_stereo(self):
        plan = Plan(fps=25, total_frames=50, slots=[Slot(index=0, tpl_index=0, start=0, frames=50, role="A", source="A")], mode="identyczny")
        info = media.MediaInfo("master.mkv", 2.0, 1080, 1920, 25.0, True, True)
        for normalize, expected_tail in ((True, ":linear=true," + render.AUDIO_TAIL), (False, None)):
            seen: list[list[str]] = []
            with tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(render, "measure_loudness", return_value=MEASURED), \
                    mock.patch.object(render, "check_audio_chain", return_value=True), \
                    mock.patch.object(media, "ffmpeg_major", return_value=9), \
                    mock.patch.object(media, "run_ffmpeg", lambda args, **kw: seen.append(list(args))):
                render.render_final(pathlib.Path("master.mkv"), info, (1080, 1920), plan, {}, pathlib.Path(tmp) / "out.mp4",
                                    pathlib.Path(tmp), canvas=(1080, 1920), normalize=normalize)
            args = seen[0]
            af = args[args.index("-af") + 1]
            if expected_tail:
                self.assertTrue(af.endswith(expected_tail), af)
            else:
                self.assertEqual(af, render.AUDIO_TAIL)
            self.assertEqual(args[args.index("-ac") + 1], "2")
            self.assertEqual(args[args.index("-ar") + 1], "48000")
            self.assertEqual(args[args.index("-c:a") + 1], "aac")

    def test_a_chain_that_does_not_run_falls_back_to_the_plain_tail_with_a_warning(self):
        plan = Plan(fps=25, total_frames=50, slots=[Slot(index=0, tpl_index=0, start=0, frames=50, role="A", source="A")], mode="identyczny")
        info = media.MediaInfo("master.mkv", 2.0, 1080, 1920, 25.0, True, True)
        seen: list[list[str]] = []
        warned: list[str] = []
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(render, "measure_loudness", return_value=MEASURED), \
                mock.patch.object(render, "check_audio_chain", return_value=False), \
                mock.patch.object(media, "ffmpeg_major", return_value=9), \
                mock.patch.object(media, "run_ffmpeg", lambda args, **kw: seen.append(list(args))):
            render.render_final(pathlib.Path("master.mkv"), info, (1080, 1920), plan, {}, pathlib.Path(tmp) / "out.mp4",
                                pathlib.Path(tmp), canvas=(1080, 1920), warn=warned.append)
        args = seen[0]
        self.assertEqual(args[args.index("-af") + 1], render.AUDIO_TAIL)
        self.assertEqual(len(warned), 1)
        self.assertIn("ffmpeg", warned[0])
        self.assertIn("brew upgrade ffmpeg", warned[0])

    def test_a_working_chain_is_not_replaced_and_gives_no_warning(self):
        plan = Plan(fps=25, total_frames=50, slots=[Slot(index=0, tpl_index=0, start=0, frames=50, role="A", source="A")], mode="identyczny")
        info = media.MediaInfo("master.mkv", 2.0, 1080, 1920, 25.0, True, True)
        seen: list[list[str]] = []
        warned: list[str] = []
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(render, "measure_loudness", return_value=MEASURED), \
                mock.patch.object(render, "check_audio_chain", return_value=True), \
                mock.patch.object(media, "ffmpeg_major", return_value=9), \
                mock.patch.object(media, "run_ffmpeg", lambda args, **kw: seen.append(list(args))):
            render.render_final(pathlib.Path("master.mkv"), info, (1080, 1920), plan, {}, pathlib.Path(tmp) / "out.mp4",
                                pathlib.Path(tmp), canvas=(1080, 1920), warn=warned.append)
        self.assertIn("loudnorm", seen[0][seen[0].index("-af") + 1])
        self.assertEqual(warned, [])

    def test_the_pipeline_hands_its_warnings_to_the_final_render(self):
        src = (HERE.parent / "src" / "reelcut" / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("warn=warnings.append", src)

    @unittest.skipUnless(shutil.which("ffmpeg"), "brak ffmpeg")
    def test_the_probe_accepts_the_real_chain_and_rejects_nonsense(self):
        with tempfile.TemporaryDirectory() as tmp:
            master = pathlib.Path(tmp) / "master.mkv"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=4", "-af", "aformat=channel_layouts=stereo",
                            "-ar", "48000", "-c:a", "pcm_s16le", str(master)], check=True)
            self.assertTrue(render.check_audio_chain(master, render.AUDIO_TAIL))
            with mock.patch.object(render, "measure_loudness", return_value=MEASURED):
                self.assertTrue(render.check_audio_chain(master, render.audio_filter(master, -14.0, -1.0, 11.0)))
            self.assertFalse(render.check_audio_chain(master, "nie_ma_takiego_filtru=1"))

    def test_a_master_without_audio_gets_no_audio_options(self):
        plan = Plan(fps=25, total_frames=50, slots=[Slot(index=0, tpl_index=0, start=0, frames=50, role="A", source="A")], mode="identyczny")
        info = media.MediaInfo("master.mkv", 2.0, 1080, 1920, 25.0, True, False)
        seen: list[list[str]] = []
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(media, "ffmpeg_major", return_value=9), \
                mock.patch.object(media, "run_ffmpeg", lambda args, **kw: seen.append(list(args))):
            render.render_final(pathlib.Path("master.mkv"), info, (1080, 1920), plan, {}, pathlib.Path(tmp) / "out.mp4",
                                pathlib.Path(tmp), canvas=(1080, 1920))
        self.assertIn("-an", seen[0])
        self.assertNotIn("-af", seen[0])


class FfmpegSummaryTests(unittest.TestCase):
    """Wiersz z wersją ffmpeg trafia do logu montażu, żeby po zrzucie ekranu od razu było widać, jaki program pracuje."""

    def test_the_summary_names_version_and_path(self):
        out = subprocess.CompletedProcess([], 0, stdout="ffmpeg version 5.1.6 Copyright (c) 2000-2024 the FFmpeg developers\n")
        with mock.patch.object(media, "find_binary", return_value="/opt/ff/ffmpeg"), mock.patch.object(media.subprocess, "run", return_value=out):
            self.assertEqual(media.ffmpeg_summary(), "ffmpeg 5.1.6: /opt/ff/ffmpeg")

    def test_an_unreadable_version_is_still_reported(self):
        out = subprocess.CompletedProcess([], 0, stdout="coś innego\n")
        with mock.patch.object(media, "find_binary", return_value="/opt/ff/ffmpeg"), mock.patch.object(media.subprocess, "run", return_value=out):
            self.assertEqual(media.ffmpeg_summary(), "ffmpeg (nieznana wersja): /opt/ff/ffmpeg")

    def test_missing_ffmpeg_is_reported_not_raised(self):
        with mock.patch.object(media, "find_binary", side_effect=media.MediaError("brak")):
            self.assertEqual(media.ffmpeg_summary(), "ffmpeg: nie znaleziono")

    def test_the_pipeline_logs_it_right_after_the_input_line(self):
        src = (HERE.parent / "src" / "reelcut" / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("log(media.ffmpeg_summary())", src)

    def test_a_failed_ffmpeg_run_names_the_version_in_the_error(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("brak ffmpeg")
        with self.assertRaises(media.MediaError) as ctx:
            media.run_ffmpeg(["-i", "nie_ma_takiego_pliku.mp4", "-f", "null", "-"])
        text = str(ctx.exception)
        self.assertTrue(text.startswith("ffmpeg zakończył się błędem:"), text)
        self.assertRegex(text.splitlines()[-1], r"^\(ffmpeg \S+: .+\)$")


@unittest.skipUnless(OTHER_FFMPEGS, "ustaw REELCUT_TEST_FFMPEGS na ścieżki do ffmpeg rozdzielone dwukropkiem (w Windows średnikiem), "
                                    "żeby sprawdzić łańcuch na starszych wersjach")
class ChainOnOtherFfmpegVersions(unittest.TestCase):
    """Ten sam łańcuch co w końcowym montażu, na prawdziwych plikach i na każdej wskazanej wersji ffmpeg."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.master = pathlib.Path(self.tmp.name) / "master.mkv"
        # plik próbny robi zwykły ffmpeg z systemu (pełny), a sprawdzane są wskazane wersje, także okrojone
        gen = [shutil.which("ffmpeg") or OTHER_FFMPEGS[-1], "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=6",
               "-af", "aformat=channel_layouts=stereo", "-ar", "48000", "-c:a", "pcm_s16le", str(self.master)]
        subprocess.run(gen, check=True)

    def _chain(self, ffmpeg: str) -> str:
        probe = [ffmpeg, "-hide_banner", "-nostdin", "-i", str(self.master), "-vn", "-af", "loudnorm=I=-14.0:TP=-1.0:LRA=11.0:print_format=json", "-f", "null", "-"]
        res = subprocess.run(probe, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr[-400:])
        with mock.patch.object(render, "measure_loudness", return_value=MEASURED):
            return render.audio_filter(self.master, -14.0, -1.0, 11.0)

    def test_every_listed_ffmpeg_encodes_the_chain(self):
        for ffmpeg in OTHER_FFMPEGS:
            with self.subTest(ffmpeg=ffmpeg):
                af = self._chain(ffmpeg)
                cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(self.master), "-map", "0:a:0", "-af", af,
                       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-f", "null", "-"]
                res = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, res.stderr[-400:])
                with mock.patch.object(media, "find_binary", return_value=ffmpeg):  # a próba przed składaniem też to przepuszcza
                    self.assertTrue(render.check_audio_chain(self.master, af))

    def test_the_chain_alone_is_enough_without_ac_and_ar(self):
        """Dwa niezależne zabezpieczenia: sam łańcuch (bez -ac i -ar) też musi przechodzić, inaczej goły aresample wróciłby niezauważony."""
        for ffmpeg in OTHER_FFMPEGS:
            with self.subTest(ffmpeg=ffmpeg):
                af = self._chain(ffmpeg)
                cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(self.master), "-map", "0:a:0", "-af", af,
                       "-c:a", "aac", "-b:a", "192k", "-f", "null", "-"]
                res = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, res.stderr[-400:])

    def test_the_chain_without_normalisation_runs_too(self):
        for ffmpeg in OTHER_FFMPEGS:
            with self.subTest(ffmpeg=ffmpeg):
                cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(self.master), "-map", "0:a:0", "-af", render.AUDIO_TAIL,
                       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-f", "null", "-"]
                res = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, res.stderr[-400:])


if __name__ == "__main__":
    unittest.main()
