"""Operacje na plikach multimedialnych: ffprobe, ffmpeg z postępem, analiza głośności i pauz."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
from array import array
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

HOP_S = 0.02  # krok obwiedni głośności


class MediaError(RuntimeError):
    """Błąd ffmpeg/ffprobe albo nieczytelny plik."""


INSTALL_HINT = (
    "Nie znaleziono programu {name}. Zainstaluj ffmpeg: macOS `brew install ffmpeg`, "
    "Windows `winget install Gyan.FFmpeg`, Linux `sudo apt install ffmpeg`. Potem uruchom ponownie."
)


def find_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise MediaError(INSTALL_HINT.format(name=name))
    return path


@dataclass(frozen=True)
class MediaInfo:
    path: str
    duration: float
    width: int  # wymiary po uwzględnieniu obrotu (tak jak widzi je odtwarzacz)
    height: int
    fps: float
    has_video: bool
    has_audio: bool


def probe(path: str | Path) -> MediaInfo:
    cmd = [find_binary("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise MediaError(f"Nie mogę odczytać pliku {Path(path).name}: {res.stderr.strip()[-300:]}")
    data = json.loads(res.stdout or "{}")
    video = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    duration = float(data.get("format", {}).get("duration") or (video or audio or {}).get("duration") or 0)
    w = h = 0
    fps = 0.0
    if video:
        w, h = int(video.get("width", 0)), int(video.get("height", 0))
        rot = 0
        for sd in video.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(round(float(sd["rotation"])))
        rot = int(video.get("tags", {}).get("rotate", rot) or rot)
        if abs(rot) % 180 == 90:
            w, h = h, w
        num, _, den = (video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1").partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    return MediaInfo(str(path), duration, w, h, fps, video is not None, audio is not None)


def ffmpeg_major() -> int | None:
    try:
        out = subprocess.run([find_binary("ffmpeg"), "-version"], capture_output=True, text=True).stdout
    except OSError:
        return None
    m = re.search(r"ffmpeg version n?(\d+)\.", out.splitlines()[0] if out else "")
    return int(m.group(1)) if m else None


def ffmpeg_summary() -> str:
    """Jeden wiersz do logu: wersja i ścieżka używanego ffmpeg. Przy błędach od razu widać, czy to starszy program."""
    try:
        path = find_binary("ffmpeg")
        out = subprocess.run([path, "-version"], capture_output=True, text=True).stdout
    except (OSError, MediaError):
        return "ffmpeg: nie znaleziono"
    m = re.search(r"ffmpeg version (\S+)", out)
    return f"ffmpeg {m.group(1) if m else '(nieznana wersja)'}: {path}"


def filter_script_args(graph: str, workdir: Path, name: str = "graph") -> list[str]:
    """Długi graf filtrów przekazujemy plikiem (limit długości linii poleceń, zwłaszcza w Windows)."""
    script = workdir / f"{name}.txt"
    script.write_text(graph, encoding="utf-8")
    major = ffmpeg_major()
    if major is not None and major < 7:
        return ["-filter_complex_script", script.name]
    return ["-/filter_complex", script.name]


ProgressCb = Callable[[float], None]


def run_ffmpeg(args: Sequence[str], *, total_s: float | None = None, on_progress: ProgressCb | None = None,
               cwd: str | Path | None = None, stdin_frames: Iterable[bytes] | None = None) -> None:
    """Uruchamia ffmpeg. Postęp 0-1 trafia do on_progress; przy błędzie rzuca MediaError z końcówką logu.
    stdin_frames: kolejne porcje bajtów podawane na wejście `pipe:0` (np. surowe klatki RGBA warstwy grafik)."""
    cmd = [find_binary("ffmpeg"), "-hide_banner", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats", *args]
    if stdin_frames is None:
        cmd.insert(2, "-nostdin")
    tail: deque[str] = deque(maxlen=30)
    feed_error: list[BaseException] = []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          stdin=subprocess.PIPE if stdin_frames is not None else None,
                          encoding="utf-8", errors="replace", cwd=str(cwd) if cwd else None) as proc:
        assert proc.stdout is not None
        feeder = None
        if stdin_frames is not None:
            assert proc.stdin is not None

            def feed() -> None:
                try:
                    for chunk in stdin_frames:
                        proc.stdin.buffer.write(chunk)  # type: ignore[union-attr]
                except BrokenPipeError:
                    pass  # ffmpeg skończył wcześniej (np. błąd): jego komunikat złapiemy poniżej
                except BaseException as exc:  # błąd w generatorze klatek: przerywamy i zgłaszamy
                    feed_error.append(exc)
                    proc.kill()
                finally:
                    try:
                        proc.stdin.close()  # type: ignore[union-attr]
                    except (BrokenPipeError, OSError, ValueError):
                        pass

            feeder = threading.Thread(target=feed, daemon=True)
            feeder.start()
        for line in proc.stdout:
            line = line.strip()
            m = re.match(r"out_time_(?:us|ms)=(-?\d+)", line)
            if m:
                if on_progress and total_s:
                    on_progress(max(0.0, min(1.0, int(m.group(1)) / 1e6 / total_s)))
            elif line and not re.match(r"^[a-z_0-9:]+=", line):
                tail.append(line)
        returncode = proc.wait()
        if feeder is not None:
            feeder.join(timeout=10)
    if feed_error:
        exc = feed_error[0]
        raise MediaError(f"Nie udało się narysować grafik: {exc}") from exc
    if returncode != 0:
        # wersja ffmpeg na końcu: po zrzucie ekranu od razu widać, czy pracuje starszy program
        raise MediaError("ffmpeg zakończył się błędem:\n" + "\n".join(tail) + f"\n({ffmpeg_summary()})")
    if on_progress:
        on_progress(1.0)


# ----------------------------------------------------------------------------------------------
# Dźwięk: obwiednia głośności, pauzy, granice mowy
# ----------------------------------------------------------------------------------------------

def read_pcm(path: str | Path, sr: int = 16000, start: float = 0.0, duration: float | None = None) -> array:
    cmd = [find_binary("ffmpeg"), "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        raise MediaError("Nie udało się odczytać ścieżki dźwiękowej: " + res.stderr.decode("utf-8", "replace")[-300:])
    samples = array("h")
    samples.frombytes(res.stdout[: len(res.stdout) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    return samples


def level_envelope(samples: array, sr: int = 16000, hop_s: float = HOP_S) -> list[float]:
    """Poziom RMS w dBFS co hop_s sekund."""
    hop = int(sr * hop_s)
    out: list[float] = []
    try:
        import numpy as np  # szybka ścieżka, gdy numpy jest zainstalowane (np. razem z faster-whisper)

        x = np.frombuffer(samples, dtype=np.int16).astype(np.float64)
        n = len(x) // hop
        if n == 0:
            return []
        r = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1)) / 32768.0
        return (20 * np.log10(np.maximum(r, 1e-6))).tolist()
    except ImportError:
        pass
    import math

    for i in range(0, len(samples) - hop + 1, hop):
        chunk = samples[i:i + hop]
        ms = sum(v * v for v in chunk) / hop
        out.append(20 * math.log10(max(math.sqrt(ms) / 32768.0, 1e-6)))
    return out


def speech_levels(env: Sequence[float]) -> tuple[float, float]:
    """Szacunek poziomu szumu tła (10. percentyl) i mowy (90. percentyl) w dB."""
    s = sorted(env)
    n = len(s)
    return s[int(n * 0.10)], s[min(n - 1, int(n * 0.90))]


def detect_pauses(env: Sequence[float], hop_s: float = HOP_S, min_pause: float = 0.5,
                  thr_db: float | None = None) -> list[tuple[float, float]]:
    """Przedziały ciszy (sekundy) dłuższe niż min_pause. Próg dobierany względem szumu i mowy w nagraniu."""
    if not env:
        return []
    noise, speech = speech_levels(env)
    if thr_db is None:
        if speech - noise < 12.0:
            return []  # zbyt płaska dynamika: nie ma czego skracać (muzyka, silny szum)
        thr_db = min(noise + 0.30 * (speech - noise), speech - 10.0)
    need = max(1, int(round(min_pause / hop_s)))
    pauses, run_start = [], None
    for i, v in enumerate(list(env) + [1e9]):
        if v < thr_db:
            run_start = i if run_start is None else run_start
        elif run_start is not None:
            if i - run_start >= need:
                pauses.append((run_start * hop_s, i * hop_s))
            run_start = None
    return pauses


def keep_ranges(duration_s: float, pauses: Sequence[tuple[float, float]], max_pause: float,
                keep_pause: float, fps: int, lead_keep: float = 0.12, tail_keep: float = 0.20) -> list[tuple[int, int]]:
    """Zakresy klatek [od, do) do zachowania po skróceniu długich pauz do keep_pause."""
    total_f = int(duration_s * fps)
    removed: list[tuple[float, float]] = []
    for s, e in pauses:
        if s <= 0.001:  # cisza na początku
            if e - lead_keep > 0.05:
                removed.append((0.0, e - lead_keep))
        elif e >= duration_s - 0.05:  # cisza na końcu
            if e - s > tail_keep + 0.05:
                removed.append((s + tail_keep, duration_s))
        elif e - s > max_pause:
            removed.append((s + keep_pause / 2, e - keep_pause / 2))
    keep, cursor = [], 0
    for a, b in sorted(removed):
        fa, fb = int(round(a * fps)), int(round(b * fps))
        if fb - fa < 2:
            continue
        if fa > cursor:
            keep.append((cursor, fa))
        cursor = max(cursor, fb)
    if cursor < total_f:
        keep.append((cursor, total_f))
    return keep or [(0, total_f)]


def map_to_master(t_frames: float, ranges: Sequence[tuple[int, int]]) -> float | None:
    """Klatka źródła -> klatka mastera (None, jeśli ten fragment został wycięty)."""
    off = 0
    for a, b in ranges:
        if a <= t_frames < b:
            return off + (t_frames - a)
        off += b - a
    return None


def join_frames(ranges: Sequence[tuple[int, int]]) -> list[int]:
    """Klatki mastera, w których zszyto fragmenty (miejsca po wyciętych pauzach)."""
    out, off = [], 0
    for a, b in ranges[:-1]:
        off += b - a
        out.append(off)
    return out


def speech_breaks(env: Sequence[float], fps: int, joins: Sequence[int] = (), hop_s: float = HOP_S) -> list[tuple[int, float]]:
    """Kandydaci na cięcie wyznaczeni z samej głośności (gdy nie ma transkrypcji):
    siła 3 = miejsce po wyciętej pauzie lub długa cisza, 2 = krótka cisza, 1 = lokalny dołek głośności."""
    if not env:
        return [(j, 3.0) for j in joins]
    noise, speech = speech_levels(env)
    out: dict[int, float] = {int(j): 3.0 for j in joins}
    if speech - noise >= 8.0:
        thr = noise + 0.45 * (speech - noise)
        i, n = 0, len(env)
        while i < n:
            if env[i] < thr:
                j = i
                while j < n and env[j] < thr:
                    j += 1
                length = (j - i) * hop_s
                if length >= 0.06:
                    f = int(round(((i + j) / 2) * hop_s * fps))
                    out[f] = max(out.get(f, 0.0), 3.0 if length >= 0.25 else 2.0)
                i = j
            else:
                i += 1
        w = int(0.15 / hop_s)
        for k in range(w, n - w):
            window = env[k - w:k + w + 1]
            if env[k] == min(window) and max(window) - env[k] >= 5.0:
                f = int(round(k * hop_s * fps))
                out.setdefault(f, 1.0)
    return sorted(out.items())
