"""Wycinanie postaci z obrazu: grafiki „za postacią” (kręgosłup za głową, karty za ramieniem, poświata za głową).

Model MODNet (portrait matting, licencja Apache-2.0) liczy dla klatki przezroczystość sylwetki: 1 = osoba, 0 = tło. Grafika
oznaczona `behind: true` jest rysowana pod osobą: jej krycie mnożymy przez (1 - sylwetka). Model (26 MB) pobiera się raz, przy
pierwszym użyciu, do ~/ReelCut/modele i dalej działa bez internetu. Potrzebne są numpy i onnxruntime.

Sylwetkę liczymy tylko tam, gdzie jest grafika „za postacią”, w 15 klatkach na sekundę i w niewielkiej rozdzielczości;
między klatkami liniowo interpolujemy, a do rozmiaru filmu skalujemy dwuliniowo.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, Sequence

from .. import media

MODEL_NAME = "modnet_fp32.onnx"
MODEL_URL = "https://huggingface.co/Xenova/modnet/resolve/main/onnx/model.onnx"
MODEL_SHA256 = "07c308cf0fc7e6e8b2065a12ed7fc07e1de8febb7dc7839d7b7f15dd66584df9"
MODEL_DIR = Path.home() / "ReelCut" / "modele"
ENV_MODEL = "REELCUT_MODNET"  # ścieżka do własnego pliku modelu (praca bez internetu)
MATTE_FPS = 15
MATTE_W = 384  # szerokość obrazu podawanego modelowi (wysokość z proporcji kadru, wielokrotność 32)
PAD_S = 0.15  # zapas czasu wokół okna z grafiką za postacią


class MatteUnavailable(RuntimeError):
    """Nie da się wyciąć postaci: brak numpy/onnxruntime albo modelu (i internetu, żeby go pobrać)."""


def _np():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise MatteUnavailable("Do wycinania postaci potrzebny jest pakiet numpy: pip install numpy onnxruntime") from exc
    return np


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_path(log: Callable[[str], None] = print, *, download: bool = True) -> Path:
    """Plik modelu: z REELCUT_MODNET, z ~/ReelCut/modele albo pobrany z Hugging Face (z kontrolą sumy SHA-256)."""
    env = os.environ.get(ENV_MODEL)
    if env:
        p = Path(env)
        if not p.exists():
            raise MatteUnavailable(f"Zmienna {ENV_MODEL} wskazuje nieistniejący plik: {p}")
        return p
    p = MODEL_DIR / MODEL_NAME
    if p.exists() and p.stat().st_size > 1_000_000:
        return p
    if not download:
        raise MatteUnavailable(f"Brak modelu wycinania postaci ({p}).")
    log("Pobieram model wycinania postaci (26 MB, jednorazowo)...")
    try:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkstemp(prefix="modnet_", suffix=".part", dir=MODEL_DIR)[1])
        try:
            with urllib.request.urlopen(MODEL_URL, timeout=60) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            if sha256_of(tmp) != MODEL_SHA256:
                raise MatteUnavailable("Pobrany model ma złą sumę kontrolną (plik uszkodzony albo podmieniony), odrzucam go.")
            tmp.replace(p)
        finally:
            tmp.unlink(missing_ok=True)
    except MatteUnavailable:
        raise
    except (OSError, ValueError) as exc:
        raise MatteUnavailable(
            f"Nie udało się pobrać modelu wycinania postaci ({type(exc).__name__}: {exc}). Pobierz go ręcznie z {MODEL_URL} "
            f"i zapisz jako {p} (albo wskaż plik zmienną {ENV_MODEL}).") from exc
    return p


class Matter:
    """Sylwetka osoby z pojedynczych klatek (MODNet przez onnxruntime)."""

    def __init__(self, path: Path):
        np = _np()
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise MatteUnavailable("Do wycinania postaci potrzebny jest pakiet onnxruntime: pip install numpy onnxruntime") from exc
        self.np = np
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        try:
            self.session = ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])
        except Exception as exc:  # noqa: BLE001: uszkodzony plik modelu to jeden komunikat dla użytkownika
            raise MatteUnavailable(f"Nie da się wczytać modelu {path.name}: {exc}") from exc
        self.input_name = self.session.get_inputs()[0].name

    def alpha(self, rgb) -> "object":
        """rgb: tablica uint8 (h, w, 3), h i w podzielne przez 32. Zwraca tablicę uint8 (h, w): 255 = osoba."""
        np = self.np
        x = (rgb.astype(np.float32) / 255.0 - 0.5) / 0.5
        out = self.session.run(None, {self.input_name: x.transpose(2, 0, 1)[None]})[0][0, 0]
        return (np.clip(out, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def matte_size(canvas: tuple[int, int], width: int = MATTE_W) -> tuple[int, int]:
    """Rozmiar obrazu dla modelu: szerokość `width`, wysokość z proporcji kadru, obie podzielne przez 32."""
    w = max(32, int(round(width / 32)) * 32)
    h = max(32, int(round(w * canvas[1] / canvas[0] / 32)) * 32)
    return w, h


def refine(a):
    """Lekko wyostrza krawędź sylwetki (uint8 -> uint8): słabą mgiełkę przy tle zerujemy, środek zostawiamy pełny."""
    np = _np()
    x = (a.astype(np.float32) - 30.0) / (225.0 - 30.0)
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


class MatteTrack:
    """Sylwetki w oknach czasu: at(t) daje obraz „L” rozmiaru kadru (255 = osoba)."""

    def __init__(self, canvas: tuple[int, int], fps: int, size: tuple[int, int], frames: dict, windows: Sequence[tuple[float, float]]):
        self.canvas, self.fps, self.size, self.frames = canvas, fps, size, frames
        self.windows = list(windows)

    def covers(self, t: float) -> bool:
        return any(a - 1e-6 <= t <= b + 1e-6 for a, b in self.windows)

    def at(self, t: float):
        """Obraz „L” w rozmiarze kadru dla chwili t (interpolacja liniowa między klatkami sylwetki) albo None poza oknami."""
        if not self.frames or not self.covers(t):
            return None
        from PIL import Image

        np = _np()
        k = t * self.fps
        i0 = int(k // 1)
        f = k - i0
        a, b = self.frames.get(i0), self.frames.get(i0 + 1)
        if a is None and b is None:  # klatki brakuje (koniec nagrania): bierzemy najbliższą
            a = self.frames[min(self.frames, key=lambda j: abs(j - i0))]
        if a is None:
            a = b
        if b is None or f < 1e-3:
            m = a
        else:
            m = (a.astype(np.float32) * (1 - f) + b.astype(np.float32) * f + 0.5).astype(np.uint8)
        return Image.fromarray(m).resize(self.canvas, Image.BILINEAR)


def windows_from(spans: Sequence[tuple[float, float]], total: float) -> list[tuple[float, float]]:
    """Łączy przedziały czasu (z zapasem PAD_S) w rozłączne okna."""
    out: list[list[float]] = []
    for a, b in sorted(spans):
        a, b = max(0.0, a - PAD_S), min(total, b + PAD_S)
        if out and a <= out[-1][1] + 0.25:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def build_track(video: Path, vf: str, canvas: tuple[int, int], windows: Sequence[tuple[float, float]], *, fps: int = MATTE_FPS,
                width: int = MATTE_W, matter: Matter | None = None, log: Callable[[str], None] = print,
                progress: Callable[[float], None] | None = None, start: float = 0.0) -> MatteTrack:
    """Liczy sylwetki w oknach. `vf` to filtry kadrujące (jak w montażu) bez skalowania do rozmiaru modelu; `start` to
    przesunięcie w nagraniu (sekundy), od którego liczymy oś czasu filmu."""
    np = _np()
    mw, mh = matte_size(canvas, width)
    windows = list(windows)
    if not windows:
        return MatteTrack(canvas, fps, (mw, mh), {}, [])
    matter = matter or Matter(model_path(log))
    need = set()
    for a, b in windows:
        need.update(range(int(a * fps), int(b * fps) + 2))
    cmd = [media.find_binary("ffmpeg"), "-v", "error", "-nostdin", "-ss", f"{start:.3f}", "-i", str(video), "-an",
           "-vf", f"{vf},fps={fps},scale={mw}:{mh}:flags=bilinear,format=rgb24", "-f", "rawvideo", "-"]
    frames: dict[int, object] = {}
    size = mw * mh * 3
    last = max(need)
    log(f"Wycinam postać w {len(need)} klatkach...")
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        assert proc.stdout is not None
        i = 0
        while i <= last:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            if i in need:
                frames[i] = refine(matter.alpha(np.frombuffer(buf, np.uint8).reshape(mh, mw, 3)))
                if progress and len(frames) % 10 == 0:
                    progress(len(frames) / len(need))
            i += 1
        proc.kill()
    if not frames:
        raise MatteUnavailable("Nie udało się odczytać klatek, z których wycinam postać.")
    return MatteTrack(canvas, fps, (mw, mh), frames, windows)
