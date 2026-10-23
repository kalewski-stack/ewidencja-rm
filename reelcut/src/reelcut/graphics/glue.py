"""Wpięcie grafik w potok montażu: układ kadru z wykrytej twarzy, awatar z Twojego nagrania, kontekst i strumień klatek."""
from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from .. import framing, media, render as video_render
from ..faces import FaceTrack
from . import script
from .core import Layout, PlanError, load_brand, need_pil
from .elements import Context
from .plan import GraphicsPlan, build_plan, with_template
from .render import iter_frames


@dataclass
class GraphicsJob:
    plan: GraphicsPlan
    size: tuple[int, int]
    fps: int
    n_frames: int
    matte: object | None = None  # sylwetki do grafik „za postacią” (matte.MatteTrack)

    @property
    def effects(self) -> list[dict]:
        return self.plan.effects

    def frames(self, progress: Callable[[float], None] | None = None) -> Iterator[bytes]:
        return iter_frames(self.plan, self.size, self.fps, self.n_frames, progress, matte=self.matte)


def face_layout(video_plan, track: FaceTrack | None, tpl, size: tuple[int, int]) -> Layout:
    """Gdzie w kadrze wynikowym jest Twoja twarz (średnia z ujęć z mową), a stąd, gdzie wolno stawiać grafiki."""
    W, H = size
    fps = video_plan.fps
    if track is not None and track.global_estimate() is not None:
        acc = []
        for s in video_plan.slots:
            if s.source != "A" or s.role != "A":
                continue
            est = track.estimate(s.start / fps, s.end / fps) or track.global_estimate()
            cx, cy, h = framing.face_in_output(est, s.zoom, s.fx, s.fy)
            acc.append((cx, cy, h, s.frames))
        if acc:
            tot = sum(a[3] for a in acc)
            cx, cy, h = (sum(a[i] * a[3] for a in acc) / tot for i in range(3))
            return Layout(W, H, cx, cy, h)
    for seg in tpl.segments:  # bez wykrytej twarzy: kadr docelowy z szablonu
        if seg.role == "A" and seg.face is not None:
            return Layout(W, H, seg.face.cx, seg.face.cy, seg.face.h)
    return Layout(W, H)


def extract_avatar(master: Path, track: FaceTrack | None, out: Path) -> Path | None:
    """Wycina z nagrania kwadrat z Twoją twarzą (klatka z typowym rozmiarem twarzy i najlepszym wynikiem detekcji)."""
    need_pil()
    if track is None:
        return None
    dets = [(t, f) for t, f in track.samples if f is not None]
    if not dets:
        return None
    hs = sorted(f.h for _, f in dets)
    med = hs[len(hs) // 2]
    cand = [(t, f) for t, f in dets if abs(f.h - med) <= 0.12 * med] or dets
    t, f = max(cand, key=lambda x: x[1].score)
    from PIL import Image

    with tempfile.TemporaryDirectory() as d:
        png = Path(d) / "f.png"
        res = subprocess.run([media.find_binary("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(master), "-frames:v", "1", str(png)],
                             capture_output=True)
        if res.returncode != 0 or not png.exists():
            return None
        img = Image.open(png).convert("RGB")
    W, H = img.size
    side = max(f.w * W, f.h * H) * 1.95
    cx, cy = f.cx * W, (f.cy + 0.04 * f.h) * H
    x0, y0 = int(max(0, min(W - side, cx - side / 2))), int(max(0, min(H - side, cy - side / 2)))
    side_i = int(min(side, W - x0, H - y0))
    img.crop((x0, y0, x0 + side_i, y0 + side_i)).resize((512, 512), Image.LANCZOS).save(out)
    return out


def make_matte(plan: GraphicsPlan, video_plan, master: Path, canvas: tuple[int, int], duration_s: float,
               log: Callable[[str], None] = print):
    """Sylwetki dla elementów z `behind` (grafika za postacią). Gdy się nie da, dopisuje ostrzeżenie do planu i zwraca None:
    elementy rysują się wtedy przed postacią."""
    behind = [e for e in plan.elements if e.behind]
    if not behind or not master.is_file():  # master nie istnieje przy --dry-run
        return None
    from . import matte as mt

    if len(video_plan.slots) != 1 or video_plan.slots[0].source != "A":
        plan.warnings.append("Grafiki za postacią (behind) działają w formacie 2, czyli w jednym ujęciu; tu rysuję je przed postacią.")
        return None
    info = media.probe(master)
    vf = video_render.matte_chain(video_plan.slots[0], (info.width, info.height))
    try:
        return mt.build_track(master, vf, canvas, mt.windows_from([(e.start, e.end) for e in behind], duration_s), log=log)
    except mt.MatteUnavailable as exc:
        plan.warnings.append(f"{str(exc).rstrip('. ')}. Grafiki za postacią rysuję przed nią.")
        return None


class StaticMatte:
    """Jedna sylwetka dla wszystkich chwil (podgląd na zdjęciu albo pojedynczej klatce)."""

    def __init__(self, image):
        self.image = image

    def at(self, t: float):
        return self.image


def matte_for_background(plan: GraphicsPlan, background: Path | None, size: tuple[int, int], *, start: float = 0.0,
                         duration: float | None = None, frame: object | None = None, log: Callable[[str], None] = print):
    """Sylwetki dla podglądu na Twoim nagraniu albo zdjęciu (`grafiki --tlo ...`). `frame` (obraz Pillow) to już wczytana klatka tła
    dla podglądu jednej klatki. Bez elementów behind albo bez tła zwraca None; gdy się nie da, dopisuje ostrzeżenie do planu."""
    if not any(e.behind for e in plan.elements) or (background is None and frame is None):
        return None
    from . import matte as mt
    from .render import is_image

    try:
        if frame is not None or is_image(background):
            from PIL import Image
            import numpy as np

            img = frame if frame is not None else Image.open(background)
            w, h = mt.matte_size(size)
            a = mt.refine(mt.Matter(mt.model_path(log)).alpha(np.asarray(img.convert("RGB").resize((w, h), Image.BILINEAR))))
            return StaticMatte(Image.fromarray(a).resize(size, Image.BILINEAR))
        end = start + duration if duration else plan.duration + 0.5
        spans = [(max(e.start, start), min(e.end, end)) for e in plan.elements if e.behind and e.end > start and e.start < end]
        vf = f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=increase,crop={size[0]}:{size[1]}"
        return mt.build_track(Path(background), vf, size, mt.windows_from(spans, end), log=log)
    except mt.MatteUnavailable as exc:
        plan.warnings.append(f"{str(exc).rstrip('. ')}. Grafiki za postacią rysuję przed nią.")
        return None


FLASH_MATCH_S = 0.1  # przejście wpisane przez autora w tej odległości od cięcia zastępuje błysk ze wzoru ujęć


def flash_cuts(video_plan) -> list[float]:
    """Chwile cięć (sekundy na osi filmu), w których wzór ujęć każe dać błysk: fx flash na ujęciu działa na jego początku (edge: start)
    albo na końcu (edge: end), więc wstawka dostaje błysk na wejściu i na wyjściu, a nie ma go tam, gdzie jej nie ma. Koniec filmu nie jest cięciem."""
    cuts = set()
    for s in video_plan.slots:
        for f in s.effects:
            if f.type == "flash" and (f.edge == "start" or s.end < video_plan.total_frames):
                cuts.add(round((s.start if f.edge == "start" else s.end) / video_plan.fps, 3))
    return sorted(cuts)


def prepare(graphics_path: str | Path | None, brand_ref: str | Path | None, tpl, video_plan, track: FaceTrack | None,
            master: Path, workdir: Path, words: list, canvas: tuple[int, int], duration_s: float,
            layer_captions: bool, log: Callable[[str], None] = print, caption_words: list | None = None) -> GraphicsJob | None:
    """Buduje plan grafik: z pliku JSON (jeśli podano) i napisów biegnących (gdy szablon ich chce). None = nic do narysowania."""
    need_pil()
    raw: dict = {"schema": 1, "elements": [], "effects": []}
    base_dir = Path(".")
    if graphics_path:
        gp = Path(graphics_path)
        try:
            text = gp.read_text(encoding="utf-8-sig")
            raw = script.to_plan(text, words) if script.is_script(gp) else json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            raise PlanError(f"Nie da się wczytać planu grafik {gp}: {exc}") from exc
        base_dir = gp.parent
    # ustawienia napisów daje szablon; z planu (scenariusza) bierzemy tylko to, co do nich dopisał (np. wyróżnione frazy);
    # w trybie motion szablon dokłada też tło, bo cały obraz rysują grafiki
    raw = with_template(raw, tpl, caption_words if caption_words is not None else words, duration_s, layer_captions=layer_captions)
    own = [float(t["at"]) for t in raw.get("transitions", []) or [] if isinstance(t, dict) and "at" in t]
    flashes = [at for at in flash_cuts(video_plan) if all(abs(at - o) > FLASH_MATCH_S for o in own)]
    if flashes:  # błyski z wzoru ujęć (Format 3: przy wstawce) to zwykłe przejścia, więc idą tą samą drogą co te ze scenariusza
        raw["transitions"] = list(raw.get("transitions", []) or []) + [{"kind": "flash", "at": at} for at in flashes]
    if not raw["elements"] and not raw.get("effects") and not raw.get("transitions"):
        return None
    brand = load_brand(brand_ref if brand_ref is not None else raw.get("brand") or tpl.graphics.get("brand"))
    layout = face_layout(video_plan, track, tpl, canvas)
    avatar = extract_avatar(master, track, workdir / "avatar.png")
    ctx = Context(brand, layout, video_plan.fps, base_dir, avatar, list(caption_words if caption_words is not None else words), duration_s)
    plan = build_plan(raw, ctx)
    n = video_plan.total_frames
    over = [e for e in plan.elements if e.kind != "captions" and e.start > duration_s]
    if over:
        log(f"UWAGA: {len(over)} elementów grafik zaczyna się po końcu filmu ({duration_s:.1f} s) i nie będzie widocznych.")
    log(f"Grafiki: {len([e for e in plan.elements if e.kind != 'captions'])} elementów, marka „{brand.name}”"
        f"{', napisy biegnące' if layer_captions and words else ''}{f', przejścia: {len(plan.transitions)}' if plan.transitions else ''}; "
        f"twarz w kadrze: wysokość {layout.face_h * 100:.0f}%, środek ({layout.face_cx * 100:.0f}%, {layout.face_cy * 100:.0f}%).")
    return GraphicsJob(plan, canvas, video_plan.fps, n, make_matte(plan, video_plan, master, canvas, duration_s, log))
