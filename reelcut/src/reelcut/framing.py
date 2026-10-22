"""Kadrowanie po twarzy: zoom i położenie okna tak, żeby trafić w proporcje kadrów wzorca.

Dla każdego ujęcia z mową szablon zna docelowy rozmiar i położenie twarzy (ułamki kadru). Z nagrania mierzymy,
jak duża i gdzie jest Twoja twarz, a stąd wynika, jak przybliżyć i przesunąć okno, żeby ją tak ustawić.
"""
from __future__ import annotations

import math
from typing import Sequence

from .faces import FaceEstimate, FaceTrack
from .template import Template

FACE_LIMIT = 0.42  # najwyższa twarz w kadrze (zbliżenie): powyżej głowa przestaje się mieścić
MARGIN = 0.02  # tyle kadru zostawiamy wokół twarzy


def plan_zooms(targets: Sequence[float], h_user: float, max_zoom: float, face_limit: float = FACE_LIMIT) -> list[float]:
    """Zoom dla kolejnych ujęć o docelowych wysokościach twarzy `targets` (ułamek kadru).

    Jeśli Twoja twarz jest mniejsza niż najszersze ujęcie wzorca, trafiamy w rozmiary dokładnie (zoom = cel / Twoja).
    Jeśli większa, najszersze ujęcie dostaje zoom 1, a reszta zachowuje proporcje drabinki wzorca.
    Gdy zoom przekracza limit (rozdzielczość źródła albo „twarz nie mieści się w kadrze”), całą drabinkę
    ściskamy potęgowo: kolejność i stosunki rozmiarów zostają, zmniejsza się tylko rozpiętość.
    """
    if not targets:
        return []
    h_ref = min(h_user, min(targets))
    z = [max(1.0, t / h_ref) for t in targets]
    cap = max(1.0, min(max_zoom, face_limit / max(h_user, 1e-6)))
    zmax = max(z)
    if zmax > cap + 1e-9:
        p = math.log(cap) / math.log(zmax) if cap > 1.0 else 0.0
        z = [zi ** p for zi in z]
    return z


def window_center(user: FaceEstimate, zoom: float, cx_target: float, cy_target: float) -> tuple[float, float]:
    """Środek okna kadrowania (ułamki mastera), przy którym twarz po przybliżeniu leży w (cx_target, cy_target)."""
    return user.cx + (0.5 - cx_target) / zoom, user.cy + (0.5 - cy_target) / zoom


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _fit_target(c: float, extent: float) -> float:
    """Przesuwa docelowy środek twarzy tak, żeby jej brzegi (o rozciągłości `extent`) mieściły się w kadrze."""
    lo, hi = MARGIN + extent / 2, 1 - MARGIN - extent / 2
    return _clamp(c, lo, hi) if lo <= hi else 0.5


def face_in_output(user: FaceEstimate, zoom: float, fx: float, fy: float) -> tuple[float, float, float]:
    """(środek x, środek y, wysokość) twarzy w kadrze wynikowym dla okna o środku (fx, fy) i danym zoomie."""
    half = 0.5 / zoom
    fx, fy = _clamp(fx, half, 1 - half), _clamp(fy, half, 1 - half)
    return (user.cx - (fx - half)) * zoom, (user.cy - (fy - half)) * zoom, user.h * zoom


def apply_framing(slots, tpl: Template, track: FaceTrack | None, fps: int, max_zoom: float) -> int:
    """Ustawia zoom i środek okna w ujęciach z mową oraz w ujęciach-detalach. Zwraca liczbę ujęć skadrowanych po twarzy."""
    glob = track.global_estimate() if track else None
    if glob is None:
        return 0
    cap = max(1.0, min(max_zoom, FACE_LIMIT / glob.h))
    a_slots = [s for s in slots if s.source == "A" and tpl.segments[s.tpl_index].face is not None]
    zooms = plan_zooms([tpl.segments[s.tpl_index].face.h for s in a_slots], glob.h, max_zoom)
    done = 0
    for s, z in zip(a_slots, zooms):
        tgt = tpl.segments[s.tpl_index].face
        est = track.estimate(s.start / fps, s.end / fps) or glob
        cx_t = _fit_target(tgt.cx, est.w * z) if est.w else tgt.cx
        cy_t = _fit_target(tgt.cy, est.h * z)
        s.zoom = round(z, 3)
        s.fx, s.fy = window_center(est, z, cx_t, cy_t)
        s.face_h = round(est.h * z, 3)
        done += 1
    # ujęcia-detale (B bez B-rolla): twarz z bliska albo to, co pod twarzą
    for s in slots:
        seg = tpl.segments[s.tpl_index]
        if not (s.role == "B" and s.source == "A"):
            continue
        alt = tpl.alts.get(seg.alt, {})
        est = track.estimate(s.start / fps, s.end / fps) or glob
        anchor = alt.get("anchor") or ("face" if float(alt.get("fy", 0.5)) < 0.5 else "below_face")
        if anchor == "face":
            z = min(cap, max(1.2, 0.48 / est.h))
            s.fx, s.fy = est.cx, est.cy + 0.01
        else:
            z = min(cap, max(1.0, float(alt.get("zoom", 1.45))))
            s.fx, s.fy = est.cx, min(0.92, est.cy + 1.5 * est.h)
        s.zoom, s.face_h = round(z, 3), None
        done += 1
    return done
