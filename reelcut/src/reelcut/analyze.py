"""Szablon z dowolnej rolki wzorcowej: cięcia, role ujęć (A/B), kadry twarzy, kolory i dynamika. Zapisuje JSON dla `cut`.

Szablon to „pakiet stylu”: rytm cięć i kadrowanie steruje montażem, blok look dopasowuje kolory, blok dynamics opisuje
tempo (komenda `style` zamienia go na kartę stylu do czytania). Z rolki nie trafia do szablonu obraz ani mowa, tylko liczby.
"""
from __future__ import annotations

import copy
import json
import math
import re
import statistics
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Sequence

from . import captions, media
from .template import TemplateError, parse_template

SCAN_STEP_S = 0.12  # co tyle sekund szukamy twarzy
MIN_FACE_H = 0.04  # mniejsze twarze (tło, plakaty) pomijamy


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


def _scan_faces(video: Path, total_s: float):
    """[(czas, Face | None, kolor skóry Lab | None)] co ~0.12 s albo None, gdy brak numpy/onnxruntime."""
    try:
        from . import faces, look

        det = faces.FaceDetector()
    except Exception as exc:  # FacesUnavailable, brak numpy
        if exc.__class__.__name__ not in ("FacesUnavailable", "ImportError", "LookUnavailable"):
            raise
        return None
    out = []
    for t, frame in faces.iter_rgb(video, every_s=max(SCAN_STEP_S, total_s / 600)):
        found = det.detect(frame)
        f = found[0] if found else None
        skin = look.skin_lab(frame, f) if f is not None and f.h >= MIN_FACE_H else None
        out.append((t, f, skin))
    return out


def _samples_in(scan, t0: float, t1: float):
    """Próbki z wnętrza ujęcia (bez ułamka sekundy przy cięciu); gdy ujęcie jest krótsze od kroku, najbliższa próbka."""
    inner = [x for x in scan if t0 + 0.05 <= x[0] < t1 - 0.05]
    if inner:
        return inner
    mid = (t0 + t1) / 2
    return [min(scan, key=lambda x: abs(x[0] - mid))]


def _segment_face(scan, t0: float, t1: float):
    """(udział próbek z twarzą, mediana twarzy w ujęciu albo None)."""
    from . import faces

    items = _samples_in(scan, t0, t1)
    found = [f for _, f, _ in items if f is not None and f.h >= MIN_FACE_H]
    return len(found) / len(items), faces.estimate(found)


def _size_for(info: media.MediaInfo, long_side: int) -> tuple[int, int]:
    """Rozmiar (szer., wys.) z zachowaniem proporcji, dłuższy bok = long_side."""
    if info.width >= info.height:
        return long_side, max(2, int(round(info.height * long_side / info.width / 2)) * 2)
    return max(2, int(round(info.width * long_side / info.height / 2)) * 2), long_side


def _motion_energy(video: Path, info: media.MediaInfo, fps: int, bounds: Sequence[int]) -> list[float]:
    """Średnia różnica kolejnych klatek (skala 0-255, szarość 108x192) w każdym ujęciu, bez klatki tuż po cięciu."""
    import numpy as np

    w, h = _size_for(info, 192)
    cmd = [media.find_binary("ffmpeg"), "-v", "error", "-nostdin", "-i", str(video), "-an", "-vf",
           f"fps={fps},scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    sums = [0.0] * (len(bounds) - 1)
    counts = [0] * (len(bounds) - 1)
    seg, prev, i = 0, None, 0
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        assert proc.stdout is not None
        while True:
            buf = proc.stdout.read(w * h)
            if len(buf) < w * h:
                break
            cur = np.frombuffer(buf, np.uint8).astype(np.int16)
            while seg < len(sums) - 1 and i >= bounds[seg + 1]:
                seg += 1
            if prev is not None and i > bounds[seg]:  # pierwsza klatka ujęcia różni się od poprzedniego ujęcia
                sums[seg] += float(np.abs(cur - prev).mean())
                counts[seg] += 1
            prev, i = cur, i + 1
    return [s / c if c else 0.0 for s, c in zip(sums, counts)]


def _look_block(video: Path, info: media.MediaInfo, fps: int, bounds: Sequence[int], roles: Sequence[str], scan) -> dict:
    """Blok look: rozkład jasności i barwy (osobno A i B, bez napisów wypalonych w materiale), paleta, kolor skóry."""
    import numpy as np

    from . import look

    size = _size_for(info, 320)
    rate = min(5.0, 240 / max(info.duration, 1.0))  # klatek na sekundę próbkowania (najwyżej 240 klatek)
    frames = look.read_frames(video, fps=rate, size=size, max_frames=240)
    t = np.arange(len(frames)) / rate
    seg = np.minimum(np.searchsorted(np.array(bounds[1:]) / fps, t, side="right"), len(roles) - 1)
    role = np.array(roles)[seg]
    mask = look.caption_mask(frames)
    block: dict = {"note": "Zmierzone z ujęć z mową (A) i wstawek (B), bez napisów wypalonych w materiale. "
                           "L* i barwa wg CIE Lab (D65). Winieta = jasność pierścieni 1-3 względem środka."}
    accents = {}
    for r in ("A", "B"):
        sel = role == r
        if int(sel.sum()) < 8:
            continue
        block[r] = look.measure(frames[sel], mask[sel]).to_dict()
        pal = look.palette(frames[sel], mask[sel])
        block[f"palette_{r}"] = pal
        vivid = [p for p in pal if p["C"] >= 45 and p["share"] >= 0.02]  # barwa wyraźnie żywsza niż skóra
        if vivid:
            accents[r] = max(vivid, key=lambda p: p["C"])["hex"]
    if accents:
        block["accents"] = accents
    if scan:
        skin = []
        for ts, f, lab in scan:
            if lab is not None:
                k = min(int(ts * fps), bounds[-1] - 1)
                j = min(max(i for i in range(len(roles)) if bounds[i] <= k), len(roles) - 1)
                if roles[j] == "A":
                    skin.append(lab)
        if len(skin) >= 5:
            L, a, b = (statistics.median(v[i] for v in skin) for i in range(3))
            block["skin"] = {"L": round(L, 1), "C": round(math.hypot(a, b), 1), "hue": round(math.degrees(math.atan2(b, a)) % 360)}
    return block


def _shot_stats(frames: Sequence[int], fps: int) -> dict:
    sec = sorted(f / fps for f in frames)
    return {"mean": round(statistics.fmean(sec), 2), "median": round(statistics.median(sec), 2),
            "min": round(sec[0], 2), "max": round(sec[-1], 2)}


def _speech_block(video: Path, bounds: Sequence[int], fps: int, model: str, language: str,
                  log: Callable[[str], None]) -> dict:
    """Tempo mowy w rolce wzorcowej: słowa na sekundę, pauzy, słowa w każdym ujęciu (bez treści)."""
    words = captions.transcribe(media.read_pcm(video), model=model, language=language, log=log)
    if len(words) < 5:
        return {}
    span = words[-1].end - words[0].start
    gaps = sorted(b.start - a.end for a, b in zip(words[:-1], words[1:]) if b.start - a.end >= 0.15)
    per_shot = [sum(1 for w in words if a / fps <= w.start < b / fps) for a, b in zip(bounds[:-1], bounds[1:])]
    out = {"words": len(words), "words_per_s": round(len(words) / span, 2), "words_per_shot": per_shot}
    if gaps:
        out["pauses_s"] = {"count": len(gaps), "median": round(statistics.median(gaps), 2), "max": round(gaps[-1], 2)}
    return out


def _dynamics_block(video: Path, info: media.MediaInfo, fps: int, bounds: Sequence[int], frames: Sequence[int],
                    roles: Sequence[str], hook: int, outro: int, speech: dict | None,
                    log: Callable[[str], None]) -> dict:
    total_s = bounds[-1] / fps
    dyn: dict = {"note": "Zmierzone z cięć, różnicy klatek i głośności rolki wzorcowej. Opisuje tempo (komenda style); "
                         "montażem steruje reszta szablonu.",
                 "duration_s": round(total_s, 2), "cuts": len(frames) - 1,
                 "cuts_per_min": round((len(frames) - 1) / total_s * 60, 1), "shot_s": _shot_stats(frames, fps),
                 "sections_s": {"hook": round(sum(frames[:hook]) / fps, 2),
                                "body": round(sum(frames[hook:len(frames) - outro]) / fps, 2),
                                "outro": round(sum(frames[len(frames) - outro:]) / fps, 2)},
                 "share": {r: round(sum(f for f, x in zip(frames, roles) if x == r) / sum(frames), 3) for r in ("A", "B")},
                 "pattern": "".join(roles)}
    try:
        energy = _motion_energy(video, info, fps, bounds)
        dyn["motion"] = {r: round(sum(e * f for e, f, x in zip(energy, frames, roles) if x == r)
                                  / max(1, sum(f for f, x in zip(frames, roles) if x == r)), 2) for r in ("A", "B")
                         if r in roles}
    except ImportError:
        log("Pomijam pomiar ruchu: potrzebny numpy.")
    if info.has_audio:
        from . import render

        m = render.measure_loudness(video, -14.0, -1.0, 11.0)
        if m:
            dyn["loudness"] = {"lufs": round(float(m["input_i"]), 1), "true_peak": round(float(m["input_tp"]), 1),
                               "lra": round(float(m["input_lra"]), 1)}
    if speech:
        dyn["speech"] = speech
    return dyn


def dump_template(raw: dict, width: int = 175) -> str:
    """JSON czytelny dla człowieka: małe obiekty i rekordy list (np. pojedyncze ujęcie) w jednym wierszu."""
    def fmt(v, indent: int) -> str:
        flat = json.dumps(v, ensure_ascii=False)
        if len(flat) + indent * 2 <= width or not isinstance(v, (dict, list)):
            return flat
        pad, pad2 = "  " * indent, "  " * (indent + 1)
        if isinstance(v, dict):
            items = [f"{pad2}{json.dumps(k, ensure_ascii=False)}: {fmt(x, indent + 1)}" for k, x in v.items()]
            return "{\n" + ",\n".join(items) + f"\n{pad}}}"
        if v and all(isinstance(x, dict) for x in v):  # lista rekordów (np. ujęć): jeden rekord = jeden wiersz
            return "[\n" + ",\n".join(f"{pad2}{json.dumps(x, ensure_ascii=False)}" for x in v) + f"\n{pad}]"
        return "[\n" + ",\n".join(f"{pad2}{fmt(x, indent + 1)}" for x in v) + f"\n{pad}]"

    return fmt(raw, 0) + "\n"


def analyze_reference(video: str | Path, out: str | Path, *, threshold: float = 0.18, roles: str | None = None,
                      name: str | None = None, speech: bool = False, model: str = "small", language: str = "pl",
                      log: Callable[[str], None] = print) -> Path:
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

    # twarze: role ujęć, rozmiar i położenie twarzy w każdym ujęciu z mową
    scan = _scan_faces(video, total / fps)
    has: list[bool] | None = None
    heights = [0.0] * n
    targets: list[dict | None] = [None] * n
    no_faces = False
    if scan:
        per_seg = [_segment_face(scan, a / fps, b / fps) for a, b in zip(bounds[:-1], bounds[1:])]
        has = [ratio >= 0.5 and est is not None for ratio, est in per_seg]
        for i, (_, est) in enumerate(per_seg):
            if has[i] and est is not None:
                heights[i] = est.h
                targets[i] = {"h": round(est.h, 4), "cx": round(est.cx, 4), "cy": round(est.cy, 4), "eye_y": round(est.eye_y, 4)}
        if not any(has):  # żadnej twarzy: to nie jest rolka z mówiącą głową albo detektor jej nie widzi
            has, no_faces = None, True
    else:
        legacy = _faces(video, bounds)  # stary tryb: OpenCV 4.x (bez położenia twarzy)
        if legacy:
            has, heights = [h for h, _ in legacy], [v for _, v in legacy]
    if roles:
        roles = roles.strip().upper()
        if len(roles) != n or set(roles) - {"A", "B"}:
            raise media.MediaError(f"--roles musi mieć dokładnie {n} liter A/B (jedna na ujęcie), a ma {len(roles)}. "
                                   f"Długości ujęć (s): {[round(f / fps, 2) for f in frames]}")
        role_list = list(roles)
    elif has is not None:
        role_list = ["A" if h else "B" for h in has]
        log("Role (A = mówiąca głowa, B = wstawka) rozpoznane po twarzy. Sprawdź je: " + "".join(role_list))
    else:
        role_list = ["A"] * n
        why = ("Nie wykryłem w rolce żadnej twarzy" if no_faces
               else "Nie rozpoznaję ról automatycznie (brak numpy/onnxruntime; zainstaluj je: pip install numpy onnxruntime)")
        log(f"{why}, więc wszystkie ujęcia mają rolę A. Podaj role sam: --roles " + "A" * min(n, 8)
            + "...  (A = mówiąca głowa, B = wstawka)")

    face_h = [heights[i] for i in range(n) if role_list[i] == "A" and has and has[i] and heights[i] > 0]
    base = min(face_h) if face_h else None
    cycle = [1.0, 1.15, 1.3]
    segs, a_idx, b_idx = [], 0, 0
    for i, (fr, r) in enumerate(zip(frames, role_list)):
        if r == "A":
            seg = {"frames": fr, "role": "A"}
            if base and has and has[i] and heights[i] > 0:
                seg["zoom"] = round(max(1.0, heights[i] / base), 2)  # drabinka kadrów: ile razy twarz większa niż w najszerszym
                if targets[i]:
                    seg["face"] = targets[i]
            else:
                seg["zoom"] = cycle[a_idx % len(cycle)]
            a_idx += 1
            segs.append(seg)
        else:
            b_idx += 1
            segs.append({"frames": fr, "role": "B", "alt": 1 + (b_idx % 2)})
    n_face = sum(1 for sg in segs if "face" in sg)
    if n_face:
        log(f"Kadry: zmierzyłem twarz w {n_face} ujęciach z mową (wysokość {min(sg['face']['h'] for sg in segs if 'face' in sg) * 100:.0f}% "
            f"– {max(sg['face']['h'] for sg in segs if 'face' in sg) * 100:.0f}% kadru).")

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
        "notes": "Wygenerowane przez rolka.py analyze. Zawiera wyłącznie parametry montażu i statystyki koloru, bez obrazu "
                 "i treści z oryginału. Sprawdź role (A/B), zoomy i strukturę, jeśli coś wygląda nie tak.",
        "fps": fps,
        "canvas": [1080, 1920],
        "structure": {"hook": hook, "outro": outro, "elastic": elastic, "elastic_min_s": 2.0, "elastic_max_s": 12.0,
                      "min_cut_s": 0.6, "snap_tol_s": 0.5},
        "alts": {"1": {"zoom": 1.6, "fy": 0.32, "anchor": "face", "note": "detal: twarz i oczy"},
                 "2": {"zoom": 1.45, "fy": 0.68, "anchor": "below_face", "note": "detal: klatka piersiowa i dłonie"}},
        "segments": segs,
        "pauses": {"max_pause_s": 0.5, "keep_pause_s": 0.35},
        "audio": {"lufs": -14.0, "true_peak": -1.0, "lra": 11.0},
        "captions": copy.deepcopy(captions.DEFAULTS),
    }

    # kolory i dynamika (każdy blok jest dodatkiem: bez numpy szablon i tak działa)
    try:
        raw["look"] = _look_block(video, info, fps, bounds, role_list, scan)
        a = raw["look"].get("A")
        if a:
            log(f"Kolory: ujęcia A mają medianę jasności L* {a['luma'][5]:.0f}, nasycenie C* {a['chroma']:.0f}, "
                f"winieta {a['vignette'][2]:.2f} w rogach.")
    except (ImportError, RuntimeError, subprocess.CalledProcessError) as exc:
        log(f"Pomijam blok kolorów: {exc}")
    speech_stats = None
    if speech:
        try:
            speech_stats = _speech_block(video, bounds, fps, model, language, log)
        except captions.CaptionsUnavailable as exc:
            log(f"Pomijam tempo mowy: {exc}")
    try:
        raw["dynamics"] = _dynamics_block(video, info, fps, bounds, frames, role_list, hook, outro, speech_stats, log)
        loud = raw["dynamics"].get("loudness")
        if loud:
            raw["audio"]["lufs"] = round(min(-11.0, max(-20.0, loud["lufs"])), 1)
            log(f"Dźwięk: rolka ma {loud['lufs']:.1f} LUFS, taki poziom ustawiam jako cel.")
        dyn = raw["dynamics"]
        log(f"Tempo: {dyn['cuts_per_min']:.1f} cięć na minutę, ujęcie średnio {dyn['shot_s']['mean']:.2f} s "
            f"(od {dyn['shot_s']['min']:.2f} do {dyn['shot_s']['max']:.2f} s).")
    except (ImportError, RuntimeError, subprocess.CalledProcessError) as exc:
        log(f"Pomijam blok dynamiki: {exc}")

    try:
        parse_template(raw)  # to, co zapisujemy, musi dać się wczytać
    except TemplateError as exc:
        raise media.MediaError(f"Z wykrytych danych nie wyszedł poprawny szablon: {exc}") from exc
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump_template(raw), encoding="utf-8")
    log("Ujęcia (s): " + ", ".join(f"{fr / fps:.2f}{r}" for fr, r in zip(frames, role_list)))
    return out
