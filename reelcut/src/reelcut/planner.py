"""Planista cięć.

Zamienia szablon (rytm cięć z rolki wzorcowej) w konkretny plan dla materiału o danej długości:
  1. hak (początek) i zakończenie zostają dokładnie takie jak w rolce,
  2. środek jest powtarzany cyklicznie tyle razy, ile potrzeba,
  3. jedno ujęcie "elastyczne" (monolog) przejmuje resztę czasu,
  4. cięcia są dosuwane do najbliższej granicy zdania/pauzy w mowie (jak robi człowiek na montażu),
  5. sąsiednie ujęcia z tego samego materiału muszą różnić się kadrem, inaczej cięcie byłoby niewidoczne.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from . import framing
from .faces import FaceTrack
from .template import Fx, Template

Break = tuple[int, float]  # (klatka w osi mastera, siła granicy: 1 = słowo, 2 = przecinek/pauza, 3 = koniec zdania)


@dataclass
class Slot:
    index: int
    tpl_index: int
    start: int
    frames: int
    role: str  # rola w szablonie: A (mówiąca głowa) albo B (wstawka)
    source: str  # skąd bierzemy obraz: "A" = główne wideo, "B" = materiał B-roll, "S" = karta w jednolitym kolorze (bez nagrania)
    zoom: float = 1.0
    fx: float = 0.5  # środek kadrowania w poziomie (0-1)
    fy: float = 0.4  # środek kadrowania w pionie (0-1)
    effects: tuple[Fx, ...] = ()
    alt: int = 0
    elastic: bool = False
    shifted: int = 0  # o ile klatek przesunięto początek ujęcia względem czystego szablonu
    face_h: float | None = None  # spodziewana wysokość Twojej twarzy w kadrze wynikowym (gdy kadrujemy po twarzy)
    slide: str = ""  # klucz koloru karty z szablonu (source "S"); grafiki piszą na niej to, co słychać
    slide_rgb: str = "#F7F4EC"  # kolor tła karty w obrazie (grafiki kładą na nim ten sam kolor, więc to tylko podkład)

    @property
    def end(self) -> int:
        return self.start + self.frames


@dataclass
class Plan:
    fps: int
    total_frames: int
    slots: list[Slot]
    mode: str  # "identyczny" | "dopasowany" | "skrócony"
    warnings: list[str] = field(default_factory=list)

    def cuts(self) -> list[int]:
        return [s.start for s in self.slots[1:]]


def build_plan(
    tpl: Template,
    master_frames: int,
    fps: int | None = None,
    *,
    has_broll: bool = False,
    breaks: Sequence[Break] = (),
    snap: bool = True,
    max_zoom: float = 1.6,
    focus: tuple[float, float] = (0.5, 0.40),
    track: FaceTrack | None = None,
) -> Plan:
    fps = fps or tpl.fps
    segs = tpl.segments
    n = len(segs)
    warnings: list[str] = []

    def fr(i: int) -> int:
        return max(1, round(segs[i].frames / tpl.fps * fps))

    hook = list(range(tpl.hook))
    outro = list(range(n - tpl.outro, n))
    body = list(range(tpl.hook, n - tpl.outro))
    min_f = max(1, round(tpl.min_cut_s * fps))

    if tpl.single_take:  # jedno ujęcie bez cięć: dynamikę robią grafiki, kadr ustawia się po twarzy
        slot = _make_slot(0, 0, 0, master_frames, tpl, True, has_broll, 1.0, focus, max_zoom, fps)
        if track is not None:
            framing.apply_framing([slot], tpl, track, fps, max_zoom)
        return Plan(fps, master_frames, [slot], "motion" if tpl.motion else "jedno ujęcie", warnings)

    if master_frames < 2 * min_f:
        warnings.append("Materiał jest bardzo krótki: zostawiam jedno ujęcie bez cięć.")
        first_a = next((i for i, sg in enumerate(segs) if sg.role == "A"), 0)  # (hak niektórych szablonów to wstawka albo karta)
        slot = _make_slot(0, first_a, 0, master_frames, tpl, False, has_broll, 1.0, focus, 1.0, fps)
        return Plan(fps, master_frames, [slot], "skrócony", warnings)

    def body_seq(n: int) -> list[int]:
        """Kolejne ujęcia środka: cykl powtarza się, ale wstawka, która wypadłaby zaraz po innej wstawce, jest pomijana
        (dwie wstawki pod rząd zlałyby się w jedną długą, a we wzorcu są oddzielone mową)."""
        out: list[int] = []
        while body and len(out) < n:
            cyc = list(body)
            if out and segs[out[-1]].role == "B" and segs[cyc[0]].role == "B":
                j = next((k for k, i in enumerate(cyc) if segs[i].role == "A"), None)
                if j is not None:
                    cyc = cyc[j:]
            out += cyc
        return out[:n]

    seq = body_seq(5000)
    fixed = sum(fr(i) for i in hook) + sum(fr(i) for i in outro if i != tpl.elastic)
    e0 = fr(tpl.elastic)
    emin, emax = round(tpl.elastic_min_s * fps), round(tpl.elastic_max_s * fps)

    # ile ujęć "środka" wstawić, by ujęcie elastyczne zmieściło się w widełkach i było jak najbliżej wzorca
    best: tuple[int, int, int] | None = None
    acc = 0
    for n_body in range(0, 5000):
        if n_body:
            if n_body > len(seq):
                break
            acc += fr(seq[n_body - 1])
        e = master_frames - fixed - acc
        if e < emin:
            break
        if e <= emax:
            cand = (abs(e - e0), n_body, e)
            if best is None or cand < best:
                best = cand

    if best is not None:
        _, n_body, e = best
        items = [(i, fr(i), False) for i in hook]
        items += [(seq[k], fr(seq[k]), False) for k in range(n_body)]
        items += [(i, e if i == tpl.elastic else fr(i), i == tpl.elastic) for i in outro]
        mode = "identyczny" if (n_body == len(body) and e == e0) else "dopasowany"
    else:
        warnings.append(
            f"Materiał jest krótszy niż {(fixed + emin) / fps:.1f} s, więc skaluję rytm szablonu proporcjonalnie. "
            "Dla najwierniejszego efektu nagraj co najmniej tyle."
        )
        base = [(i, fr(i), i == tpl.elastic) for i in hook + outro]
        scale = master_frames / sum(f for _, f, _ in base)
        items = [(i, max(1, round(f * scale)), el) for i, f, el in base]
        k = next(j for j, it in enumerate(items) if it[2])
        items[k] = (items[k][0], items[k][1] + master_frames - sum(f for _, f, _ in items), True)
        mode = "skrócony"

    # drabinka kadrów szablonu jest ściskana potęgowo do dozwolonego zoomu: kolejność i stosunki rozmiarów zostają
    ladder = tpl.ladder_max
    zk = 1.0 if ladder <= max_zoom else (math.log(max_zoom) / math.log(ladder) if max_zoom > 1.0 else 0.0)

    slots: list[Slot] = []
    start = 0
    for idx, (ti, frames, elastic) in enumerate(items):
        slot = _make_slot(idx, ti, start, frames, tpl, elastic, has_broll, zk, focus, max_zoom, fps)
        slots.append(slot)
        start += frames
    assert start == master_frames, (start, master_frames)

    if snap and breaks:
        _snap_cuts(slots, breaks, fps, tpl.snap_tol_s, tpl.min_cut_s)
    cap = max_zoom
    if track is not None:
        framing.apply_framing(slots, tpl, track, fps, max_zoom)
        glob = track.global_estimate()
        if glob is not None:
            cap = max(1.0, min(max_zoom, framing.FACE_LIMIT / glob.h))
    _ensure_visible_cuts(slots, cap)
    return Plan(fps, master_frames, slots, mode, warnings)


def _make_slot(idx, ti, start, frames, tpl, elastic, has_broll, zk, focus, max_zoom, fps) -> Slot:
    seg = tpl.segments[ti]
    if seg.slide:  # karta: jednolity kolor, bez nagrania i bez B-rolla
        rgb = tpl.slide_colors.get(seg.slide, "#F7F4EC")
        return Slot(idx, ti, start, frames, "B", "S", 1.0, focus[0], focus[1], seg.fx, seg.alt, elastic,
                    slide=seg.slide, slide_rgb=rgb if rgb.startswith("#") else "#F7F4EC")
    zoom, fx, fy = seg.zoom ** zk, focus[0], focus[1]
    source = "A"
    if seg.role == "B":
        if has_broll:
            source = "B"
        else:  # detal z własnego nagrania: zoom bezwzględny, ograniczony tylko limitem
            alt = tpl.alts.get(seg.alt, {"zoom": 1.4, "fy": 0.5})
            zoom, fy = min(float(alt.get("zoom", 1.4)), max_zoom), float(alt.get("fy", 0.5))
    return Slot(idx, ti, start, frames, seg.role, source, round(min(zoom, max_zoom), 3), fx, fy,
                seg.fx, seg.alt, elastic)


STAY_SCORE = 0.9  # tyle "wart" jest brak ruchu, gdy cięcie i tak wypada przy jakiejś granicy mowy
MIDWORD_SCORE = -1.0  # a tyle, gdy cięcie wypadałoby w środku słowa (każda granica w zasięgu jest lepsza)
PULL = 3.5  # jak mocno odległość zmniejsza atrakcyjność granicy (1.0 = skraj okna)


def _snap_cuts(slots: list[Slot], breaks: Sequence[Break], fps: int, tol_s: float, min_cut_s: float) -> None:
    """Przesuwa wewnętrzne cięcia do najlepszej granicy mowy w oknie +-tol_s.

    Mocna granica (koniec zdania) wygrywa z bliższą słabą, ale cięcie trzyma się czasu z szablonu:
    daleka granica nie wygra, a ujęcie nie może skurczyć się poniżej 60% długości z szablonu.
    Jeśli cięcie wypadałoby w środku słowa, bierzemy najbliższą granicę choćby słabą."""
    import bisect

    tol, min_f = max(1, round(tol_s * fps)), max(1, round(min_cut_s * fps))
    planned = [s.start for s in slots[1:]]
    total = slots[-1].end
    ordered = sorted(breaks)
    frames = [b for b, _ in ordered]
    plan_len = [s.frames for s in slots]
    prev = 0
    for i, c in enumerate(planned):
        nxt = planned[i + 1] if i + 1 < len(planned) else total
        floor_left = max(min_f, int(0.6 * plan_len[i]))
        floor_right = max(min_f, int(0.6 * plan_len[i + 1]))
        lo, hi = max(prev + floor_left, c - tol), min(nxt - floor_right, c + tol)
        near = any(abs(frames[j] - c) <= 2 for j in range(max(0, bisect.bisect_left(frames, c - 2)),
                                                           min(len(frames), bisect.bisect_right(frames, c + 2))))
        best, best_score = c, (STAY_SCORE if near else MIDWORD_SCORE)
        if lo <= hi:
            for j in range(bisect.bisect_left(frames, lo), bisect.bisect_right(frames, hi)):
                bf, strength = ordered[j]
                score = strength - PULL * abs(bf - c) / tol
                if score > best_score:
                    best, best_score = bf, score
        best = max(prev + 1, min(best, nxt - 1)) if not (lo <= best <= hi) else best
        prev = best
        slots[i + 1].start = best
        slots[i + 1].shifted = best - c
    for i, s in enumerate(slots):
        s.frames = (slots[i + 1].start if i + 1 < len(slots) else total) - s.start


def _ensure_visible_cuts(slots: list[Slot], cap: float, min_ratio: float = 0.10, min_shift: float = 0.12) -> None:
    """Dwa kolejne ujęcia z tego samego materiału muszą różnić się widocznie, inaczej cięcia nie widać.

    Widoczna różnica to zmiana rozmiaru o >= 10% albo przesunięcie treści o >= 12% kadru wynikowego
    (przesunięcie okna mnożymy przez zoom, bo przy dużym zoomie małe okno to duża zmiana w kadrze)."""
    prev: Slot | None = None
    for s in slots:
        if s.source == "A" and prev is not None and prev.source == "A":
            ratio = max(s.zoom, prev.zoom) / min(s.zoom, prev.zoom) - 1.0
            shift = max(abs(s.fx - prev.fx), abs(s.fy - prev.fy)) * max(s.zoom, prev.zoom)
            if ratio < min_ratio and shift < min_shift:
                up = prev.zoom * (1 + 1.2 * min_ratio)
                down = max(1.0, prev.zoom / (1 + 1.2 * min_ratio))
                s.zoom = round(up if up <= cap else down, 3)
        prev = s


def describe_plan(plan: Plan) -> str:
    """Czytelna tabela planu (do trybu --dry-run i logów)."""
    fps = plan.fps
    lines = [f"Plan: {len(plan.slots)} ujęć, {plan.total_frames / fps:.2f} s ({plan.mode})",
             "  nr    od      do     dł.   obraz  zoom   uwagi"]
    for s in plan.slots:
        what = "A-roll" if s.source == "A" and s.role == "A" else ("kadr-detal" if s.source == "A" else "B-roll")
        if s.source == "S":
            what = "karta"
        if plan.mode == "motion":  # w trybie motion obraz powstaje z grafik, z nagrania liczy się tylko głos
            what = "grafiki"
        notes = []
        if s.face_h:
            notes.append(f"twarz {s.face_h * 100:.0f}% kadru")
        if s.slide:
            notes.append(f"kolor karty: {s.slide}")
        if s.effects:
            notes.append("+".join(f.type + (" na wyjściu" if f.edge == "end" else "") for f in s.effects))
        if s.elastic:
            notes.append("elastyczne")
        if s.shifted:
            notes.append(f"dosunięte {s.shifted / fps:+.2f}s")
        lines.append(
            f"  {s.index + 1:>2}  {s.start / fps:6.2f}  {s.end / fps:6.2f}  {s.frames / fps:5.2f}  "
            f"{what:<10} {s.zoom:4.2f}   {', '.join(notes)}"
        )
    lines += [f"  UWAGA: {w}" for w in plan.warnings]
    return "\n".join(lines)
