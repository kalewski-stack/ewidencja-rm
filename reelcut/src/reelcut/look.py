"""Dopasowanie koloru do wzorca (look): statystyki obrazu, dopasowanie rozkładów w Lab, LUT 3D (.cube) i winieta.

Zasada: z rolki wzorcowej mierzymy rozkład jasności (percentyle L*), barwę i nasycenie w funkcji jasności oraz
spadek jasności ku rogom. Z Twojego nagrania mierzymy to samo i budujemy transformację, która przesuwa Twoje
statystyki ku wzorcowym. Siła (0-1) pozwala ją dozować. Efekt to tablica LUT 3D, którą ffmpeg nakłada na cały film.
"""
from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import media

PCTS = (0.5, 1, 5, 10, 25, 50, 75, 90, 95, 99, 99.5)
BIN = 10  # szerokość przedziału jasności w tabelach barwy
RINGS = ((0.0, 0.35), (0.35, 0.7), (0.7, 1.0), (1.0, 1.6))  # pierścienie od środka (elipsa po kadrze)
_M = ((0.4124564, 0.3575761, 0.1804375), (0.2126729, 0.7151522, 0.0721750), (0.0193339, 0.1191920, 0.9503041))
_WHITE = (0.95047, 1.0, 1.08883)


class LookUnavailable(RuntimeError):
    """Brak numpy (potrzebny do liczenia koloru)."""


def _np():
    try:
        import numpy as np
    except ImportError as exc:
        raise LookUnavailable("Do dopasowania kolorów potrzebny jest numpy: pip install numpy") from exc
    return np


# ---------------------------------------------------------------------------------------------
# Przestrzenie barw (sRGB <-> CIE Lab, D65)
# ---------------------------------------------------------------------------------------------

def srgb_to_lab(rgb):
    """rgb: tablica (...,3) w [0,1]."""
    np = _np()
    rgb = np.asarray(rgb, np.float64)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = (lin @ np.array(_M).T) / np.array(_WHITE)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lab_to_srgb(lab):
    """Zwraca sRGB w [0,1] (przycięte do gamutu)."""
    np = _np()
    lab = np.asarray(lab, np.float64)
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], -1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * np.array(_WHITE)
    lin = np.clip(xyz @ np.linalg.inv(np.array(_M)).T, 0, 1)
    return np.clip(np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055), 0, 1)


# ---------------------------------------------------------------------------------------------
# Statystyki
# ---------------------------------------------------------------------------------------------

@dataclass
class LookStats:
    luma: list[float]  # L* w punktach PCTS
    bins: list[dict]  # {"L": środek przedziału, "share": udział pikseli, "a", "b": średnia barwa, "C": średnie nasycenie}
    chroma: float  # średnie C* w całym obrazie
    vignette: list[float]  # jasność pierścieni 1-3 względem środka (1.0 = brak spadku)
    frames: int = 0

    def to_dict(self) -> dict:
        return {"luma": [round(v, 2) for v in self.luma],
                "bins": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in b.items()} for b in self.bins],
                "chroma": round(self.chroma, 2), "vignette": [round(v, 3) for v in self.vignette], "frames": self.frames}

    @staticmethod
    def from_dict(d: dict) -> "LookStats":
        return LookStats([float(v) for v in d["luma"]], [dict(b) for b in d["bins"]], float(d["chroma"]),
                         [float(v) for v in d["vignette"]], int(d.get("frames", 0)))


def read_frames(video: str | Path, *, fps: float = 2.0, size: tuple[int, int] = (180, 320), start: float = 0.0,
                duration: float | None = None, max_frames: int = 200, post_filter: str | None = None):
    """Dekoduje klatki (N,H,W,3 uint8) co 1/fps sekundy w zmniejszeniu `size` (szer., wys.).
    post_filter: dodatkowy filtr ffmpeg nakładany po zmniejszeniu (np. winieta)."""
    np = _np()
    w, h = size
    cmd = [media.find_binary("ffmpeg"), "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(video)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    vf = f"fps={fps},scale={w}:{h}:flags=area" + (f",{post_filter}" if post_filter else "")
    cmd += ["-an", "-vf", vf, "-frames:v", str(max_frames), "-f", "rawvideo",
            "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def caption_mask(frames):
    """Maska pikseli bez napisów wypalonych w materiale wzorcowym (czysta biel w pasach napisów i akcent limonkowy)."""
    np = _np()
    n, h, w, _ = frames.shape
    white = frames.min(axis=-1) >= 244
    ys, xs = np.arange(h)[:, None] / h, np.arange(w)[None, :] / w
    band = ((ys > 0.55) & (ys < 0.80)) | ((ys > 0.18) & (ys < 0.36) & (xs > 0.62)) | ((ys > 0.30) & (ys < 0.62))
    lime = (frames[..., 1] > 200) & (frames[..., 2] < 150) & (frames[..., 0] > 150)
    return ~((white & band[None]) | lime)


def _ring_ratios(L_mean_map):
    np = _np()
    h, w = L_mean_map.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((yy - (h - 1) / 2) / (h / 2), (xx - (w - 1) / 2) / (w / 2))
    ring = [L_mean_map[(r >= lo) & (r < hi)].mean() for lo, hi in RINGS]
    return [ring[i] / ring[0] for i in (1, 2, 3)]


def measure(frames, mask=None, max_pixels: int = 1_200_000, seed: int = 0) -> LookStats:
    """Statystyki look dla klatek (N,H,W,3 uint8); mask (N,H,W bool) wyklucza piksele (np. napisy)."""
    np = _np()
    n = frames.shape[0]
    L_map = srgb_to_lab(frames.astype(np.float64) / 255.0)[..., 0].mean(axis=0)
    vignette = _ring_ratios(L_map)
    px = frames[mask] if mask is not None else frames.reshape(-1, 3)
    if len(px) > max_pixels:
        px = px[np.random.default_rng(seed).choice(len(px), max_pixels, replace=False)]
    lab = srgb_to_lab(px.astype(np.float64) / 255.0)
    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]
    C = np.hypot(a, b)
    bins = []
    for lo in range(0, 100, BIN):
        m = (L >= lo) & (L < lo + BIN + (1 if lo == 100 - BIN else 0))
        if m.sum() < 50:
            continue
        bins.append({"L": lo + BIN / 2, "share": float(m.mean()), "a": float(a[m].mean()), "b": float(b[m].mean()),
                     "C": float(C[m].mean())})
    return LookStats([float(np.percentile(L, p)) for p in PCTS], bins, float(C.mean()), [float(v) for v in vignette], n)


def to_hex(lab) -> str:
    """Kolor z Lab jako #RRGGBB."""
    rgb = lab_to_srgb(_np().asarray(lab, float)[None])[0]
    return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in rgb)


def palette(frames, mask=None, k: int = 8, max_pixels: int = 60000, seed: int = 1) -> list[dict]:
    """Dominujące kolory (k-średnich w Lab) od najczęstszego: [{"hex", "share", "L", "C", "hue"}]."""
    np = _np()
    px = frames[mask] if mask is not None else frames.reshape(-1, 3)
    rng = np.random.default_rng(seed)
    if len(px) > max_pixels:
        px = px[rng.choice(len(px), max_pixels, replace=False)]
    if len(px) < k * 20:
        return []
    X = srgb_to_lab(px.astype(np.float64) / 255.0)
    centers = X[[int(rng.integers(len(X)))]]
    for _ in range(k - 1):  # k-means++: kolejne środki daleko od dotychczasowych
        d2 = ((X[:, None, :] - centers[None]) ** 2).sum(-1).min(1)
        total = float(d2.sum())
        centers = np.vstack([centers, X[rng.choice(len(X), p=d2 / total) if total > 1e-9 else int(rng.integers(len(X)))]])
    for _ in range(25):
        lab = ((X[:, None, :] - centers[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            if (lab == j).any():
                centers[j] = X[lab == j].mean(0)
    share = np.bincount(lab, minlength=k) / len(X)
    out = []
    for j in np.argsort(-share):
        if share[j] <= 0:  # puste skupienie (obraz ma mniej barw niż k)
            continue
        L, a, b = (float(v) for v in centers[j])
        out.append({"hex": to_hex(centers[j]), "share": round(float(share[j]), 3), "L": round(L, 1),
                    "C": round(math.hypot(a, b), 1), "hue": round(math.degrees(math.atan2(b, a)) % 360)})
    return out


def skin_lab(rgb, face) -> tuple[float, float, float] | None:
    """Mediana koloru (L*, a*, b*) w środku twarzy (policzki i nos); face ma x, y, w, h jako ułamki kadru."""
    np = _np()
    h, w = rgb.shape[:2]
    x0, x1 = int((face.x + 0.30 * face.w) * w), int((face.x + 0.70 * face.w) * w)
    y0, y1 = int((face.y + 0.45 * face.h) * h), int((face.y + 0.75 * face.h) * h)
    patch = rgb[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
    if patch.shape[0] < 3 or patch.shape[1] < 3:
        return None
    lab = srgb_to_lab(patch.reshape(-1, 3).astype(np.float64) / 255.0)
    return tuple(float(v) for v in np.median(lab, axis=0))


# ---------------------------------------------------------------------------------------------
# Transformacja
# ---------------------------------------------------------------------------------------------

def _smooth(y, k: int = 9):
    np = _np()
    pad = k // 2
    return np.convolve(np.pad(y, pad, mode="edge"), np.ones(k) / k, mode="valid")


def _smoothstep(x, lo, hi):
    np = _np()
    t = np.clip((np.asarray(x, float) - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def tone_curve(user: LookStats, ref: LookStats, strength: float):
    """Monotoniczna krzywa tonalna L -> L' z dopasowania percentyli (siatka L co 0.25)."""
    np = _np()
    ux, rx = np.array(user.luma, float), np.array(ref.luma, float)
    x = np.concatenate([[0.0], ux, [100.0]])
    y = np.concatenate([[strength * 0.8 * rx[0]], ux + strength * (rx - ux), [100.0 - strength * (100.0 - (rx[-1] + 5.0))]])
    order = np.argsort(x, kind="stable")
    x, y = x[order], y[order]
    keep = np.concatenate([[True], np.diff(x) > 1e-3])
    x, y = x[keep], np.maximum.accumulate(y[keep])
    grid = np.linspace(0, 100, 401)
    f = np.maximum.accumulate(_smooth(np.interp(grid, x, y), 9))
    return grid, f


def _bin_curve(stats: LookStats, key: str, Lq):
    np = _np()
    rows = [b for b in stats.bins if b["share"] >= 0.004] or stats.bins
    return np.interp(Lq, [b["L"] for b in rows], [b[key] for b in rows])


def color_curves(user: LookStats, ref: LookStats, grid, f, strength: float, max_shift: float = 10.0):
    """Zysk nasycenia i przesunięcie barwy (a*, b*) w funkcji jasności źródłowej L (101 punktów)."""
    np = _np()
    Lq = np.linspace(0, 100, 101)
    Lp = np.interp(Lq, grid, f)
    Cu, au, bu = (_bin_curve(user, k, Lq) for k in ("C", "a", "b"))
    Cr, ar, br = (_bin_curve(ref, k, Lp) for k in ("C", "a", "b"))
    gain = _smooth(np.clip(Cr / np.maximum(Cu, 1.0), 0.35, 1.8), 11) ** strength
    at, bt = au + strength * (ar - au), bu + strength * (br - bu)  # docelowa barwa: mieszanka Twojej i wzorca
    da, db = _smooth(at - gain * au, 11), _smooth(bt - gain * bu, 11)
    norm = np.hypot(da, db)
    scale = np.where(norm > max_shift, max_shift / np.maximum(norm, 1e-9), 1.0)
    w = _smoothstep(Lp, 6, 18) * (1 - _smoothstep(Lp, 62, 78))  # cienie neutralne, najjaśniejsze światła bez zmian
    return Lq, gain, da * scale * w, db * scale * w


def build_lut(user: LookStats, ref: LookStats, strength: float = 1.0, size: int = 33):
    """Tablica LUT 3D (size,size,size,3) w kolejności [b][g][r], wartości [0,1]."""
    np = _np()
    grid, f = tone_curve(user, ref, strength)
    Lq, gain, da, db = color_curves(user, ref, grid, f, strength)
    ax = np.linspace(0, 1, size)
    B, G, R = np.meshgrid(ax, ax, ax, indexing="ij")
    lab = srgb_to_lab(np.stack([R, G, B], -1).reshape(-1, 3))
    L = lab[:, 0]
    # przesunięcie barwy dotyczy tylko pikseli mało nasyconych (ściany, ubrania, cienie): skóra i inne kolory
    # zachowują swój odcień, zmienia się im tylko jasność i nasycenie
    wc = 1.0 - _smoothstep(np.hypot(lab[:, 1], lab[:, 2]), 8, 22)
    out = np.stack([np.interp(L, grid, f),
                    lab[:, 1] * np.interp(L, Lq, gain) + wc * np.interp(L, Lq, da),
                    lab[:, 2] * np.interp(L, Lq, gain) + wc * np.interp(L, Lq, db)], -1)
    return lab_to_srgb(out).reshape(size, size, size, 3)


def identity_lut(size: int = 33):
    np = _np()
    ax = np.linspace(0, 1, size)
    B, G, R = np.meshgrid(ax, ax, ax, indexing="ij")
    return np.stack([R, G, B], -1)


def write_cube(lut, path: str | Path, title: str = "reelcut look") -> None:
    size = lut.shape[0]
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in lut.reshape(-1, 3)]
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")


def apply_lut(rgb8, lut):
    """Trójliniowe nałożenie LUT na obraz uint8 (do testów i podglądu; ffmpeg używa interpolacji czworościennej)."""
    np = _np()
    n = lut.shape[0] - 1
    x = np.asarray(rgb8, np.float64) / 255.0 * n
    i0 = np.clip(np.floor(x).astype(int), 0, n - 1)
    t = x - i0
    out = 0.0
    for dr in (0, 1):
        for dg in (0, 1):
            for db_ in (0, 1):
                wgt = ((t[..., 0] if dr else 1 - t[..., 0]) * (t[..., 1] if dg else 1 - t[..., 1])
                       * (t[..., 2] if db_ else 1 - t[..., 2]))
                out = out + wgt[..., None] * lut[i0[..., 2] + db_, i0[..., 1] + dg, i0[..., 0] + dr]
    return np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)


def distance(a: LookStats, b: LookStats) -> dict:
    """Odległość między dwoma opisami look: średni błąd percentyli L*, nasycenia i barwy (do raportów i testów)."""
    np = _np()
    luma = float(np.mean(np.abs(np.array(a.luma) - np.array(b.luma))))
    Lq = np.arange(5, 100, 10.0)
    cast = float(np.mean(np.hypot(_bin_curve(a, "a", Lq) - _bin_curve(b, "a", Lq), _bin_curve(a, "b", Lq) - _bin_curve(b, "b", Lq))))
    return {"luma": luma, "chroma": abs(a.chroma - b.chroma), "cast": cast}


# ---------------------------------------------------------------------------------------------
# Winieta
# ---------------------------------------------------------------------------------------------

_VIG_ANGLES = tuple(0.20 + 0.075 * i for i in range(15))  # radiany
_vig_cache: dict[float, list[tuple[float, list[float]]]] = {}


def vignette_table(base_L: float = 28.0, size: tuple[int, int] = (180, 320)) -> list[tuple[float, list[float]]]:
    """Dla kolejnych kątów filtra vignette: jasność pierścieni 1-3 względem środka na jednolitym polu o jasności base_L."""
    key = round(base_L, 1)
    if key in _vig_cache:
        return _vig_cache[key]
    np = _np()
    w, h = size
    gray = int(round(float(lab_to_srgb(np.array([base_L, 0.0, 0.0]))[0]) * 255))
    n = len(_VIG_ANGLES)
    parts = [f"color=c=0x{gray:02x}{gray:02x}{gray:02x}:s={w}x{h}:d=0.04:r=25,format=gbrp,split={n}" + "".join(f"[s{i}]" for i in range(n))]
    parts += [f"[s{i}]vignette=angle={a:.4f}:mode=forward:eval=init[v{i}]" for i, a in enumerate(_VIG_ANGLES)]
    parts.append("".join(f"[v{i}]" for i in range(n)) + f"hstack=inputs={n},format=rgb24")
    raw = subprocess.run([media.find_binary("ffmpeg"), "-v", "error", "-filter_complex", ";".join(parts), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    img = np.frombuffer(raw, np.uint8).reshape(h, n * w, 3).astype(np.float64) / 255.0
    table = []
    for i, a in enumerate(_VIG_ANGLES):
        L = srgb_to_lab(img[:, i * w:(i + 1) * w])[..., 0]
        table.append((a, _ring_ratios(L)))
    _vig_cache[key] = table
    return table


def vignette_filter(angle: float) -> str:
    return f"vignette=angle={angle}:mode=forward:eval=init"


def vignette_angle(user: LookStats, ref: LookStats, strength: float, base_L: float | None = None) -> float | None:
    """Kąt filtra vignette, który dokłada brakujący spadek jasności ku brzegom (tylko przyciemnianie).

    Decydują zewnętrzne pierścienie 2-3: pierścień 1 zależy od kompozycji kadru, nie od światła.
    Poniżej 7% brakującego spadku nic nie dokładamy. None = winieta niepotrzebna."""
    target = [1.0 - strength * (1.0 - min(1.0, r / max(u, 1e-3))) for u, r in zip(user.vignette[1:], ref.vignette[1:])]
    if min(target) > 0.93:
        return None
    table = vignette_table(base_L if base_L is not None else 28.0)
    best = min(table, key=lambda t: sum((x - y) ** 2 for x, y in zip(t[1][1:], target)))
    return round(best[0], 3)


def filter_chain(cube_name: str | None, angle: float | None) -> str:
    """Łańcuch filtrów ffmpeg w RGB: najpierw winieta, potem LUT (statystyki liczymy już z winietą), powrót do
    yuv420p z macierzą BT.709."""
    chain = ["format=gbrp"]
    if angle:
        chain.append(vignette_filter(angle))
    if cube_name:
        chain.append(f"lut3d=file={cube_name}:interp=tetrahedral")
    chain += ["scale=out_color_matrix=bt709:out_range=tv", "format=yuv420p"]
    return ",".join(chain)
