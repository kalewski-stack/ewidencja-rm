"""Renderowanie warstwy grafik: klatki RGBA w czasie i podgląd na tle (jednolitym albo na Twoim nagraniu)."""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Callable, Iterator

from .. import media
from .core import Layer, PlanError, cover, need_pil
from .plan import GraphicsPlan
from .transitions import BACKGROUND_KINDS

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def is_image(path: str | Path | None) -> bool:
    return bool(path) and Path(path).suffix.lower() in IMAGE_SUFFIXES


def background_frame(background: str | Path, t: float, size: tuple[int, int]):
    """Klatka tła w rozmiarze kadru (obraz RGB): ze zdjęcia albo z wideo w sekundzie t."""
    need_pil()
    from PIL import Image

    if is_image(background):
        try:
            return cover(Image.open(background), size[0], size[1]).convert("RGB")
        except OSError as exc:
            raise PlanError(f"Nie da się wczytać tła {background}: {exc}") from exc
    res = subprocess.run([media.find_binary("ffmpeg"), "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(background), "-frames:v", "1",
                          "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=increase,crop={size[0]}:{size[1]}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    if len(res.stdout) != size[0] * size[1] * 3:
        raise PlanError(f"Nie udało się odczytać klatki tła w {t:.1f} s z {background} (czy nagranie jest tak długie?).")
    return Image.frombytes("RGB", size, res.stdout)


def _draw(active, layer: Layer, t: float, matte) -> Layer:
    """Rysuje elementy w kolejności z; te z `behind` najpierw i ukryte tam, gdzie jest postać (matte.at(t)), a dopiero na nich reszta,
    więc postać zasłania tylko to, co ma być za nią."""
    behind = [e for e in active if e.behind]
    if behind:
        for e in behind:
            e.draw(layer, t)
        m = matte.at(t) if matte is not None else None
        if m is not None:
            from PIL import ImageChops

            layer.img.putalpha(ImageChops.multiply(layer.img.getchannel("A"), ImageChops.invert(m)))
    for e in active:
        if not e.behind:
            e.draw(layer, t)
    return layer


def _scene(plan: GraphicsPlan, t: float, size: tuple[int, int], matte, background: bool, cut: float | None = None) -> Layer:
    """Samo tło (background=True, np. papier z kropkami) albo cała reszta sceny w chwili t. Po cięciu `cut` stare elementy (te, które
    kończą się dokładnie w chwili cięcia) już nie są rysowane, żeby nowa scena nie nakładała się na starą."""
    def keep(e) -> bool:
        if (e.kind in BACKGROUND_KINDS) != background:
            return False
        return not (cut is not None and e.end <= cut + 1e-6 and e.start < cut - 1e-6)

    return _draw([e for e in plan.active(t) if keep(e)], Layer(size), t, matte)


def render_frame(plan: GraphicsPlan, t: float, size: tuple[int, int], matte=None) -> Layer:
    """Klatka warstwy grafik. Bez przejść: wszystkie aktywne elementy w kolejności z. W oknie przejścia scena (wszystko poza tłem)
    jest obrabiana osobno (rozmycie, najazd, przesunięcie, kurtyna) i dopiero potem kładziona na tle; błysk leży na całości."""
    trs = plan.transitions_at(t)
    if not trs:
        return _draw(plan.active(t), Layer(size), t, matte)
    stage = [tr for tr in trs if not tr.global_overlay]
    if stage:
        cut = max((tr.at for tr in stage if t >= tr.at - 1e-9), default=None)
        layer = _scene(plan, t, size, matte, True)
        fg = _scene(plan, t, size, matte, False, cut).img
        for tr in stage:
            fg = tr.apply(fg, t, lambda tt: _scene(plan, tt, size, matte, False).img)
        layer.img.alpha_composite(fg)
    else:
        layer = _draw(plan.active(t), Layer(size), t, matte)
    for tr in trs:
        if tr.global_overlay:
            layer.img = tr.overlay(layer.img, t)
    return layer


def iter_frames(plan: GraphicsPlan, size: tuple[int, int], fps: int, n_frames: int,
                progress: Callable[[float], None] | None = None, t0: float = 0.0, matte=None) -> Iterator[bytes]:
    """Kolejne klatki RGBA (surowe bajty) od czasu t0. Puste klatki to jeden współdzielony bufor, więc nic nie kosztują."""
    blank = bytes(size[0] * size[1] * 4)
    for i in range(n_frames):
        t = t0 + i / fps
        if plan.active(t) or plan.transitions_at(t):
            yield render_frame(plan, t, size, matte).tobytes()
        else:
            yield blank
        if progress and i % 5 == 0:
            progress(i / max(1, n_frames))


def render_png(plan: GraphicsPlan, t: float, size: tuple[int, int], bg=None, matte=None):
    """Pojedyncza klatka jako obraz Pillow (na tle bg, jeśli podano): do podglądu i testów."""
    from PIL import Image

    layer = render_frame(plan, t, size, matte)
    if bg is None:
        bg = Image.new("RGBA", size, (22, 24, 26, 255))
    out = bg.convert("RGBA").resize(size)
    out.alpha_composite(layer.img)
    return out


def preview(plan: GraphicsPlan, out: str | Path, *, size: tuple[int, int] = (1080, 1920), fps: int = 30,
            duration: float | None = None, background: str | Path | None = None, start: float = 0.0,
            progress: Callable[[float], None] | None = None, matte=None) -> Path:
    """Film z samymi grafikami na tle (jednolitym albo wideo z `background`). Służy do szybkiego sprawdzenia planu."""
    need_pil()
    out = Path(out)
    dur = duration or max(1.0, plan.duration + 0.5 - start)
    n = int(round(dur * fps))
    W, H = size
    if is_image(background):
        base = ["-loop", "1", "-framerate", str(fps), "-i", str(background)]
        bg = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},format=yuv420p[bg]"
    elif background:
        base = ["-ss", f"{start:.3f}", "-i", str(background)]
        bg = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},format=yuv420p[bg]"
    else:
        base = ["-f", "lavfi", "-i", f"color=c=0x16181A:s={W}x{H}:r={fps}"]
        bg = "[0:v]format=yuv420p[bg]"
    graph = f"{bg};[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
    cmd = [media.find_binary("ffmpeg"), "-v", "error", "-y", *base, "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-framerate", str(fps), "-i", "pipe:0", "-filter_complex", graph, "-map", "[v]", "-t", f"{dur:.3f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps), str(out)]
    with subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        assert proc.stdin is not None and proc.stderr is not None
        err: list[bytes] = []
        t = threading.Thread(target=lambda: err.append(proc.stderr.read()), daemon=True)  # type: ignore[union-attr]
        t.start()
        try:
            for frame in iter_frames(plan, size, fps, n, progress, t0=start, matte=matte):
                proc.stdin.write(frame)
        except BrokenPipeError:
            pass
        finally:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                pass
        code = proc.wait()
        t.join(timeout=5)
    if code != 0:
        raise PlanError("ffmpeg nie złożył podglądu: " + (err[0].decode("utf-8", "replace")[-400:] if err else ""))
    return out
