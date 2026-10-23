"""Przejścia między scenami: obróbka całej klatki grafik w oknie wokół cięcia.

Przejście nie jest elementem, tylko efektem na obrazie w chwili cięcia `at` (pierwsza klatka nowej sceny): przed cięciem stara scena wychodzi,
po cięciu nowa wchodzi. Scena to cokolwiek, co zmienia się w tej chwili (plansza, tarcza, tytuł, lista); tło (`backdrop`) stoi w miejscu,
a efekt dotyczy tego, co na nim leży. Efekt `blysk` biały błysk obejmuje cały obraz, także wideo pod grafikami.

Liczby pochodzą z klatek rolek wzorcowych (30 kl./s; rozmycie w pikselach przy szerokości 1080, skala i przesunięcia jako ułamek kadru):
rozmycie, zoom, przesunięcie i kurtyna z rolki DekGW1-tCoi, błysk z rolki DcS25CKkmFM. Opis i zmierzone krzywe: PRZEJSCIA.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .anchors import norm
from .core import PlanError, clamp01, lerp

try:
    from PIL import Image, ImageFilter
except ImportError:  # pragma: no cover
    pass

FRAME = 1 / 30  # wszystkie krzywe są policzone na klatkach 30 kl./s

KINDS = {"blur": "blur", "rozmycie": "blur", "defocus": "blur", "zoom": "zoom", "najazd": "zoom", "whip": "whip", "przesuniecie": "whip",
         "wipe": "wipe", "kurtyna": "wipe", "flash": "flash", "blysk": "flash"}
DIRS = {"left": (-1, 0), "lewo": (-1, 0), "right": (1, 0), "prawo": (1, 0), "up": (0, -1), "gora": (0, -1), "down": (0, 1), "dol": (0, 1)}
DEFAULT_DIR = {"whip": "right", "wipe": "up"}
BACKGROUND_KINDS = ("backdrop",)  # elementy, które przy przejściu stoją w miejscu (rysowane pod sceną)

# --- rozmycie przez papier (T1, T2): wyjście = rozmycie rośnie, scena blednie do tła; wejście = ostrzenie ---
BLUR_OUT_FRAMES = 5.5  # tyle klatek przed cięciem scena zaczyna się rozmywać
BLUR_OUT_SIGMA = 80.0  # px (przy W = 1080) w ostatniej klatce przed cięciem; maleje o e^-0,45 na klatkę wstecz (zmierzone: 48-102)
BLUR_OUT_DECAY = 0.45
BLUR_OUT_WHITE = 0.48  # ile sceny zanika w ostatniej klatce (0,40-0,55), kolejne klatki wstecz × 0,55
BLUR_IN_SIGMA = 40.0  # px w pierwszej klatce nowej sceny; maleje e-krotnie na 2,6 klatki
BLUR_IN_TAU = 2.6
BLUR_IN_WHITE = 0.25
BLUR_IN_TAU_WHITE = 2.0

# --- zoom na wylot (T5): stara scena najeżdża i się rozmywa, nowa startuje mała i rośnie wykładniczo ---
ZOOM_OUT_FRAMES = 6.0
ZOOM_OUT_SCALE = 0.30  # o tyle (ułamek) stara scena urośnie tuż przed cięciem
ZOOM_OUT_BLUR = 0.04  # ułamek W, rozmycie w ostatniej klatce
ZOOM_OUT_WHITE = 0.30
ZOOM_IN_START = 0.28  # skala nowej sceny w pierwszej klatce (zmierzone: książka 0,28 końcowej)
ZOOM_IN_RHO = 0.80  # co klatkę zostaje 80% dystansu do skali 1 (stała czasowa ok. 4,5 klatki)
ZOOM_IN_FRAMES = 18.0
ZOOM_IN_BLUR = 0.03

# --- przesunięcie z rozmyciem ruchu (T4) ---
WHIP_OUT_FRAMES = 4.5
WHIP_OUT_SHIFT = 0.55  # ułamek W, o który stara scena ucieknie tuż przed cięciem
WHIP_IN_SHIFT = 0.42  # ułamek W, od którego nowa scena zaczyna (zmierzone: 0,28 W w pierwszej widocznej klatce, bo wcześniej jest rozmyta)
WHIP_IN_RHO = 0.85  # zmierzone: 0,82-0,87 na klatkę, stała czasowa ok. 6 klatek
WHIP_IN_FRAMES = 22.0
WHIP_BLUR = 0.35  # długość smugi jako ułamek aktualnego przesunięcia

# --- kurtyna (T3): półprzezroczysty pas przesuwa się po kadrze, za nim stoi nowa scena ---
WIPE_S = 0.17
WIPE_BAND = 0.45  # wysokość pasa (ułamek kadru w kierunku ruchu)
WIPE_SOFT = 0.10  # miękka krawędź (ułamek kadru)
WIPE_GREY = (150, 150, 150)
WIPE_ALPHA = 0.32

# --- błysk (DcS25CKkmFM): biała nakładka na całym obrazie, krycie w kolejnych klatkach wokół cięcia (środek = pierwsza klatka nowego ujęcia) ---
FLASH = (0.25, 0.58, 0.82, 0.86, 0.82, 0.58, 0.25)
FLASH_CENTER = 3


def window(kind: str) -> tuple[float, float]:
    """(sekundy przed cięciem, sekundy po cięciu), w których przejście coś robi."""
    if kind == "blur":
        return BLUR_OUT_FRAMES * FRAME, 9 * FRAME
    if kind == "zoom":
        return ZOOM_OUT_FRAMES * FRAME, ZOOM_IN_FRAMES * FRAME
    if kind == "whip":
        return WHIP_OUT_FRAMES * FRAME, WHIP_IN_FRAMES * FRAME
    if kind == "wipe":
        return 0.0, WIPE_S
    return (FLASH_CENTER + 1) * FRAME, (len(FLASH) - FLASH_CENTER) * FRAME  # krycie schodzi do zera w klatce za ostatnim wpisem tabeli


@dataclass
class Transition:
    kind: str
    at: float
    dir: str = ""
    strength: float = 1.0
    said: str | None = None

    def __post_init__(self) -> None:
        k = KINDS.get(norm(str(self.kind)))
        if k is None:
            raise PlanError(f"Przejście: nieznany rodzaj „{self.kind}”. Dostępne: rozmycie, zoom, przesunięcie, kurtyna, błysk.")
        self.kind = k
        if self.at < 0:
            raise PlanError("Przejście: czas cięcia (at) nie może być ujemny.")
        d = norm(self.dir) if self.dir else DEFAULT_DIR.get(k, "")
        if d and d not in DIRS:
            raise PlanError(f"Przejście: nieznany kierunek „{self.dir}” (lewo, prawo, góra, dół).")
        self.dir = d
        if not 0.0 < self.strength <= 3.0:
            raise PlanError("Przejście: moc (strength) musi być z przedziału (0, 3].")
        self.before, self.after = window(self.kind)

    @classmethod
    def from_spec(cls, spec: dict) -> "Transition":
        if not isinstance(spec, dict) or "at" not in spec:
            raise PlanError("Przejście: wymagane pola kind i at (czas cięcia w sekundach).")
        try:
            at = float(spec["at"])
            strength = float(spec.get("strength", 1.0))
        except (TypeError, ValueError) as exc:
            raise PlanError("Przejście: at i strength muszą być liczbami.") from exc
        return cls(str(spec.get("kind", spec.get("type", ""))), at, str(spec.get("dir", "")), strength, spec.get("said"))

    @property
    def start(self) -> float:
        return self.at - self.before

    @property
    def end(self) -> float:
        return self.at + self.after

    def active(self, t: float) -> bool:
        return self.start - 1e-6 <= t <= self.end + 1e-6

    @property
    def global_overlay(self) -> bool:
        """Błysk obejmuje cały obraz (też wideo pod grafikami), reszta przejść obrabia samą scenę."""
        return self.kind == "flash"

    # --- obróbka sceny (fg: RGBA całego kadru bez tła) ---
    def apply(self, fg, t: float, fg_at: Callable[[float], "Image.Image"]):
        """Zwraca obrobioną scenę dla chwili t (fg to scena w tej chwili, fg_at(tt) rysuje scenę w innej chwili)."""
        if self.kind == "flash":
            return fg
        if self.kind == "wipe":
            return _wipe(self, fg, t, fg_at)
        f = (self.at - t) / FRAME  # klatki do cięcia (>0 przed nim, <=0 po nim)
        return {"blur": _blur, "zoom": _zoom, "whip": _whip}[self.kind](self, fg, f)

    def overlay(self, img, t: float):
        """Biała nakładka błysku na gotowym obrazie."""
        if self.kind != "flash":
            return img
        a = flash_alpha((t - self.at) / FRAME) * min(1.0, self.strength)
        if a <= 0.004:
            return img
        white = Image.new("RGBA", img.size, (255, 255, 255, int(round(255 * a))))
        out = img.copy()
        out.alpha_composite(white)
        return out


def flash_alpha(k: float) -> float:
    """Krycie bieli w klatce o numerze k względem cięcia (0 = pierwsza klatka nowego ujęcia), interpolowane liniowo między klatkami;
    poza tabelą krycie schodzi do zera w ciągu jednej klatki."""
    pts = [0.0] + list(FLASH) + [0.0]  # indeks 0 to klatka tuż przed tabelą
    x = k + FLASH_CENTER + 1
    if x <= 0 or x >= len(pts) - 1:
        return 0.0
    lo = int(math.floor(x))
    return lerp(pts[lo], pts[lo + 1], x - lo)


# ---------------------------------------------------------------------------------------------
# Elementy składowe: rozmycie, zmiana skali, przesunięcie, rozmycie ruchu, wygaszenie
# ---------------------------------------------------------------------------------------------

def _premul(im):
    return im.convert("RGBa")


def _gauss(im, sigma: float):
    if sigma <= 0.4:
        return im
    return _premul(im).filter(ImageFilter.GaussianBlur(sigma)).convert("RGBA")


def _fade(im, k: float):
    """Wygasza scenę do tła pod nią (k = 0 nic, k = 1 nic nie zostaje)."""
    k = clamp01(k)
    if k <= 0.003:
        return im
    out = im.copy()
    out.putalpha(im.getchannel("A").point([int(round(v * (1 - k))) for v in range(256)]))
    return out


def _affine(im, scale: float, dx: float, dy: float, pivot: tuple[float, float]):
    """Skala wokół punktu pivot i przesunięcie o (dx, dy) pikseli; poza obrazem zostaje przezroczystość."""
    w, h = im.size
    cx, cy = pivot
    inv = 1.0 / max(scale, 1e-3)
    a = (inv, 0, cx - inv * (cx + dx), 0, inv, cy - inv * (cy + dy))
    return _premul(im).transform((w, h), Image.AFFINE, a, resample=Image.BILINEAR).convert("RGBA")


def _smear(im, samples: list[tuple[float, float, float]], pivot: tuple[float, float]):
    """Rozmycie ruchu: średnia z kopii obrazu dla kolejnych (skala, dx, dy) z krótszego zakresu migawki. Liczone w połowie rozdzielczości."""
    w, h = im.size
    half = im.resize((max(1, w // 2), max(1, h // 2)), Image.BILINEAR)
    pv = (pivot[0] / 2, pivot[1] / 2)
    acc = None
    for i, (s, dx, dy) in enumerate(samples):
        cur = _premul(_affine(half, s, dx / 2, dy / 2, pv))
        acc = cur if acc is None else Image.blend(acc, cur, 1.0 / (i + 1))
    return acc.convert("RGBA").resize((w, h), Image.BILINEAR)


# ---------------------------------------------------------------------------------------------
# Rodzaje przejść
# ---------------------------------------------------------------------------------------------

def _blur(tr: Transition, fg, f: float):
    W = fg.size[0]
    k = tr.strength
    px = W / 1080.0
    if f > 0:  # wyjście: f = ile klatek przed cięciem
        if f > BLUR_OUT_FRAMES:
            return fg
        sigma = BLUR_OUT_SIGMA * math.exp(-BLUR_OUT_DECAY * (f - 1)) * px * k
        white = BLUR_OUT_WHITE * 0.55 ** max(0.0, f - 1) * k
        return _fade(_gauss(fg, sigma), white)
    s = -f  # wejście: s = klatki po cięciu
    sigma = BLUR_IN_SIGMA * math.exp(-s / BLUR_IN_TAU) * px * k
    white = BLUR_IN_WHITE * math.exp(-s / BLUR_IN_TAU_WHITE) * k
    return _fade(_gauss(fg, sigma), white)


def _zoom(tr: Transition, fg, f: float):
    W, H = fg.size
    k = tr.strength
    pivot = (W / 2, H / 2)
    if f > 0:  # stara scena najeżdża
        if f >= ZOOM_OUT_FRAMES:
            return fg
        u = (1 - f / ZOOM_OUT_FRAMES) ** 2  # 0 -> 1 rosnąco do cięcia
        scale = 1 + ZOOM_OUT_SCALE * u * k
        spread = 0.10 * u * k  # smuga zoomu: kopie od skali s do s(1+spread)
        if spread > 0.01:
            im = _smear(fg, [(scale * (1 + spread * j / 4), 0, 0) for j in range(5)], pivot)
        else:
            im = _affine(fg, scale, 0, 0, pivot)
        return _fade(_gauss(im, ZOOM_OUT_BLUR * W * u * k), ZOOM_OUT_WHITE * u * k)
    s = -f  # nowa scena rośnie od małej
    tail = ZOOM_IN_RHO ** ZOOM_IN_FRAMES
    scale = 1 - (1 - ZOOM_IN_START) * (ZOOM_IN_RHO ** s - tail) / (1 - tail)
    scale = lerp(1.0, scale, min(1.0, k))
    im = _affine(fg, scale, 0, 0, pivot) if abs(scale - 1) > 0.002 else fg
    return _gauss(im, ZOOM_IN_BLUR * W * 0.7 ** s * k)


def _whip(tr: Transition, fg, f: float):
    W, H = fg.size
    k = tr.strength
    dx, dy = DIRS[tr.dir]
    unit = W if dx else H
    pivot = (W / 2, H / 2)
    if f > 0:  # stara scena ucieka w kierunku dir
        if f >= WHIP_OUT_FRAMES:
            return fg
        shift = WHIP_OUT_SHIFT * unit * (1 - f / WHIP_OUT_FRAMES) ** 2 * k
        sign = 1
    else:
        s = -f
        tail = WHIP_IN_RHO ** WHIP_IN_FRAMES
        shift = WHIP_IN_SHIFT * unit * (WHIP_IN_RHO ** s - tail) / (1 - tail) * k
        sign = -1  # nowa scena wjeżdża z przeciwnej strony
    if shift < 0.004 * unit:
        return fg
    sx, sy = sign * dx * shift, sign * dy * shift
    smear = WHIP_BLUR * shift
    if smear > 0.012 * unit:
        n = max(9, min(41, int(smear / 8)))  # kopie co kilka pikseli, żeby smuga była gładka, a nie "grzebieniem"
        samples = [(1.0, sx + dx * smear * (j / (n - 1) - 0.5), sy + dy * smear * (j / (n - 1) - 0.5)) for j in range(n)]
        im = _gauss(_smear(fg, samples, pivot), 0.004 * W)
    else:
        im = _affine(fg, 1.0, sx, sy, pivot)
    return _fade(im, 0.25 * clamp01(shift / (WHIP_OUT_SHIFT * unit)) * k) if f > 0 else im


def _wipe(tr: Transition, fg, t: float, fg_at):
    """Pas przesuwa się w kierunku dir; za nim (od strony, z której wszedł) stoi nowa scena, przed nim jeszcze stara (zamrożona z chwili cięcia)."""
    W, H = fg.size
    dx, dy = DIRS[tr.dir]
    vertical = bool(dy)
    n = H if vertical else W
    flip = dy < 0 or dx < 0  # ruch w górę albo w lewo: współrzędna ruchu liczona od końca osi
    soft, band = WIPE_SOFT * n, WIPE_BAND * n
    p = clamp01((t - tr.at) / WIPE_S)
    center = lerp(-0.5 * band - soft, n + 0.5 * band + soft, p)
    old = fg_at(tr.at - FRAME / 2)
    if p <= 0.0:
        return old
    behind = _axis_mask((W, H), vertical, flip, lambda s_: clamp01(0.5 + (center - s_) / max(soft, 1.0)))
    ahead = behind.point(lambda v: 255 - v)
    new_part = fg.copy()
    new_part.putalpha(_mul_alpha(new_part.getchannel("A"), behind))
    old_part = _fade(old, 0.35 * p)
    old_part.putalpha(_mul_alpha(old_part.getchannel("A"), ahead))
    out = old_part.copy()
    out.alpha_composite(new_part)
    shade_a = _axis_mask((W, H), vertical, flip, lambda s_: WIPE_ALPHA * max(0.0, 1 - ((s_ - center) / max(1.0, 0.5 * band)) ** 2) ** 1.5)
    if vertical:
        shade_a = shade_a.filter(ImageFilter.GaussianBlur(2))
    shade = Image.new("RGBA", (W, H), WIPE_GREY + (0,))
    shade.putalpha(shade_a)
    out.alpha_composite(shade)
    return out


def _axis_mask(size: tuple[int, int], vertical: bool, flip: bool, fn: Callable[[float], float]):
    """Maska L zależna tylko od współrzędnej s wzdłuż ruchu pasa (s = indeks piksela albo liczony od końca osi, gdy flip)."""
    W, H = size
    n = H if vertical else W
    lut = [int(round(255 * clamp01(fn((n - 1 - i) if flip else i)))) for i in range(n)]
    strip = Image.new("L", (1, n) if vertical else (n, 1))
    strip.putdata(lut)
    return strip.resize((W, H), Image.NEAREST)


def _mul_alpha(a, b):
    from PIL import ImageChops

    return ImageChops.multiply(a, b)
