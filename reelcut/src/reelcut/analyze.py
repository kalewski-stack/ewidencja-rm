"""Szablon z dowolnej rolki wzorcowej: wykrywa cięcia, role ujęć (A/B) i skalę kadru, zapisuje JSON dla polecenia cut."""
from __future__ import annotations

import copy
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Sequence

from . import captions, media
from .template import TemplateError, parse_template


def scene_scores(video: Path) -> list[float]:
    """Wskaźnik zmiany sceny (0-1) dla każdej klatki, wg ffmpeg."""
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([media.find_binary("ffmpeg"), "-v", "error", "-y", "-i", str(Path(video).resolve()), "-an", "-vf",
                        "select='gte(scene,0)',metadata=print:key=lavfi.scene_score:file=s.txt", "-f", "null", "-"],
                       cwd=d, check=True, capture_output=True)
        text = (Path(d) / "s.txt").read_text()
    return [float(m.group(1)) for m in re.finditer(r"scene_score=([\d.]+)", text)]


def pick_cuts(scores: Sequence[float], threshold: float, min_len: int) -> list[int]:
    """Numery klatek, na których zaczyna się nowe ujęcie. Piki bliżej niż min_len łączymy (wygrywa wyższy)."""
    cuts: list[int] = []
    for i in range(min_len, len(scores) - min_len):
        if scores[i] < threshold:
            continue
        if cuts and i - cuts[-1] < min_len:
            if scores[i] > scores[cuts[-1]]:
                cuts[-1] = i
        else:
            cuts.append(i)
    return cuts


def _faces(video: Path, bounds: Sequence[int]):
    """(czy jest twarz, wysokość twarzy / wysokość kadru) dla każdego ujęcia; None, gdy brak OpenCV 4.x."""
    try:
        import cv2
        import numpy as np

        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    except (ImportError, AttributeError):
        return None
    cap = cv2.VideoCapture(str(video))
    out = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        heights = []
        for frac in (0.2, 0.4, 0.6, 0.8):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(a + (b - a) * frac))
            ok, frame = cap.read()
            if not ok:
                continue
            h = frame.shape[0]
            gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            faces = casc.detectMultiScale(gray, 1.1, 4, minSize=(h // 16, h // 16))
            if len(faces):
                heights.append(max(f[3] for f in faces) / h)
        out.append((bool(heights), float(np.median(heights)) if heights else 0.0))
    cap.release()
    return out


def dump_template(raw: dict, width: int = 175) -> str:
    """JSON czytelny dla człowieka: małe obiekty (np. pojedyncze ujęcie) w jednym wierszu."""
    def fmt(v, indent: int) -> str:
        flat = json.dumps(v, ensure_ascii=False)
        if len(flat) + indent * 2 <= width or not isinstance(v, (dict, list)):
            return flat
        pad, pad2 = "  " * indent, "  " * (indent + 1)
        if isinstance(v, dict):
            items = [f"{pad2}{json.dumps(k, ensure_ascii=False)}: {fmt(x, indent + 1)}" for k, x in v.items()]
            return "{\n" + ",\n".join(items) + f"\n{pad}}}"
        return "[\n" + ",\n".join(f"{pad2}{fmt(x, indent + 1)}" for x in v) + f"\n{pad}]"

    return fmt(raw, 0) + "\n"


def analyze_reference(video: str | Path, out: str | Path, *, threshold: float = 0.18, roles: str | None = None,
                      name: str | None = None, log: Callable[[str], None] = print) -> Path:
    video, out = Path(video), Path(out)
    info = media.probe(video)
    if not info.has_video:
        raise media.MediaError("W pliku nie ma obrazu.")
    fps = int(round(info.fps)) or 25
    log(f"Analizuję {video.name}: {info.duration:.1f} s, {info.width}x{info.height}, {fps} kl./s...")
    scores = scene_scores(video)
    total = len(scores)
    cuts = pick_cuts(scores, threshold, max(2, int(0.4 * fps)))
    if len(cuts) < 3:
        raise media.MediaError(f"Wykryłem tylko {len(cuts)} cięć (próg {threshold}). Spróbuj niższego progu: --threshold 0.12")
    bounds = [0] + cuts + [total]
    frames = [b - a for a, b in zip(bounds[:-1], bounds[1:])]
    n = len(frames)
    log(f"Wykryto {n} ujęć, średnio {total / fps / n:.2f} s.")

    # role i skala kadru
    faces = _faces(video, bounds)
    if roles:
        roles = roles.strip().upper()
        if len(roles) != n or set(roles) - {"A", "B"}:
            raise media.MediaError(f"--roles musi mieć dokładnie {n} liter A/B (jedna na ujęcie), a ma {len(roles)}. "
                                   f"Długości ujęć (s): {[round(f / fps, 2) for f in frames]}")
        role_list = list(roles)
    elif faces:
        role_list = ["A" if has else "B" for has, _ in faces]
        log("Role (A = mówiąca głowa, B = wstawka) rozpoznane po twarzy. Sprawdź je: " + "".join(role_list))
    else:
        role_list = ["A"] * n
        log("Nie rozpoznaję ról automatycznie (brak OpenCV 4.x). Wszystkie ujęcia mają rolę A. "
            "Podaj role sam: --roles " + "A" * min(n, 8) + "...  (A = mówiąca głowa, B = wstawka)")

    face_h = [f for (has, f), r in zip(faces or [(0, 0)] * n, role_list) if r == "A" and has and f > 0]
    base = min(face_h) if face_h else None
    cycle = [1.0, 1.15, 1.3]
    segs, a_idx, b_idx = [], 0, 0
    for i, (fr, r) in enumerate(zip(frames, role_list)):
        if r == "A":
            if base and faces and faces[i][0]:
                zoom = round(min(1.75, max(1.0, 1.0 + 0.45 * (faces[i][1] / base - 1.0))), 2)
            else:
                zoom = cycle[a_idx % len(cycle)]
            a_idx += 1
            segs.append({"frames": fr, "role": "A", "zoom": zoom})
        else:
            b_idx += 1
            segs.append({"frames": fr, "role": "B", "alt": 1 + (b_idx % 2)})

    # struktura: hak = pierwsze ~18% czasu, zakończenie = ostatnie ~28%, elastyczne = najdłuższe A w zakończeniu
    starts = bounds[:-1]
    hook = max(1, sum(1 for s, f in zip(starts, frames) if s + f <= 0.18 * total))
    outro = max(1, min(4, sum(1 for s in starts if s >= 0.72 * total)))
    outro = min(outro, n - hook - 1)
    cand = [i for i in range(n - outro, n) if role_list[i] == "A"]
    if not cand:
        raise media.MediaError("W końcówce rolki nie ma ujęcia z mówiącą głową (A). Popraw role: --roles")
    elastic = max(cand, key=lambda i: frames[i])
    segs[elastic]["note"] = "Elastyczne ujęcie: przejmuje różnicę długości całości."

    raw = {
        "schema": 1,
        "name": name or f"Szablon z {video.stem}",
        "source": video.name,
        "notes": "Wygenerowane przez rolka.py analyze. Sprawdź role (A/B), zoomy i strukturę, jeśli coś wygląda nie tak.",
        "fps": fps,
        "canvas": [1080, 1920],
        "structure": {"hook": hook, "outro": outro, "elastic": elastic, "elastic_min_s": 2.0, "elastic_max_s": 12.0,
                      "min_cut_s": 0.6, "snap_tol_s": 0.5},
        "alts": {"1": {"zoom": 1.6, "fy": 0.32, "note": "detal: twarz / oczy"},
                 "2": {"zoom": 1.45, "fy": 0.68, "note": "detal: dłonie / klatka piersiowa"}},
        "segments": segs,
        "pauses": {"max_pause_s": 0.5, "keep_pause_s": 0.35},
        "audio": {"lufs": -14.0, "true_peak": -1.0, "lra": 11.0},
        "captions": copy.deepcopy(captions.DEFAULTS),
    }
    try:
        parse_template(raw)  # to, co zapisujemy, musi dać się wczytać
    except TemplateError as exc:
        raise media.MediaError(f"Z wykrytych danych nie wyszedł poprawny szablon: {exc}") from exc
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump_template(raw), encoding="utf-8")
    log("Ujęcia (s): " + ", ".join(f"{fr / fps:.2f}{r}" for fr, r in zip(frames, role_list)))
    return out
