"""Elementy grafik: baza (czas życia, miejsce w kadrze), rejestr typów oraz tytuł i plakietka z numerem.

Każdy element ma czas startu (`at`, sekundy na osi gotowego filmu), czas trwania (`dur`) i rysuje się na warstwie RGBA.
Miejsce wskazujesz strefą (`zone`: top, left, right, bottom, head, full) albo ułamkami kadru (`x`, `y`, środek elementu).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .core import (Brand, Layer, Layout, Life, PlanError, blur, compose, disc, ease_out, ease_out_back, glow_of, lerp, life,
                   rgba_image, rounded_rect, scale_rotate, shadowed, text_size, text_sprite, wrap_text)

REGISTRY: dict[str, type["Element"]] = {}


def register(kind: str):
    def deco(cls):
        cls.kind = kind
        REGISTRY[kind] = cls
        return cls

    return deco


@dataclass
class Context:
    """Wspólne dane dla wszystkich elementów planu."""
    brand: Brand
    layout: Layout
    fps: int
    base_dir: Path = field(default_factory=Path)  # względem tego katalogu liczymy ścieżki do obrazów z planu
    avatar: Path | None = None  # automatyczny awatar: kółko z Twoją twarzą (pipeline wycina je z nagrania)
    words: list = field(default_factory=list)  # słowa mowy (captions.Word) na osi gotowego filmu: dla napisów biegnących
    duration: float = 0.0  # długość gotowego filmu w sekundach

    @property
    def W(self) -> int:
        return self.layout.W

    @property
    def H(self) -> int:
        return self.layout.H

    def resolve(self, ref: str) -> Path:
        p = Path(ref)
        return p if p.is_absolute() else (self.base_dir / p)


class Element:
    kind = "?"
    default_dur = 3.0
    d_in = 0.4
    d_out = 0.3
    default_zone = "top"
    default_z = 5

    def __init__(self, spec: dict, ctx: Context):
        self.spec, self.ctx = spec, ctx
        if "at" not in spec:
            raise PlanError(f"Element „{self.kind}” nie ma czasu startu (pole at).")
        self.start = float(spec["at"])
        self.dur = float(spec.get("dur", self.default_dur))
        if self.dur <= 0:
            raise PlanError(f"Element „{self.kind}”: dur musi być dodatnie.")
        self.z = int(spec.get("z", self.default_z))
        self.d_in = float(spec.get("in", self.d_in))
        self.d_out = float(spec.get("out", self.d_out))
        self.brand = ctx.brand
        self.notes: list[str] = []  # uwagi dla autora planu (np. „nie mieści się”): trafiają do ostrzeżeń planu
        self.build()

    # --- do nadpisania ---
    def build(self) -> None:
        """Przygotowanie obrazów, które się nie zmieniają w czasie."""

    def draw(self, layer: Layer, t: float) -> None:
        raise NotImplementedError

    # --- wspólne ---
    @property
    def end(self) -> float:
        return self.start + self.dur

    def active(self, t: float) -> bool:
        return self.start - 1e-6 <= t <= self.end + 1e-6

    def life(self, t: float) -> Life:
        return life(t, self.start, self.dur, self.d_in, self.d_out)

    def color(self, key: str):
        return self.brand.rgb(self.spec.get(f"{key}_color", key))

    def zone_width(self) -> float | None:
        """Szerokość strefy, w której element ma stać (None, gdy podano x/y: wtedy liczy się cały kadr)."""
        if "x" in self.spec or "y" in self.spec:
            return None
        x0, _, x1, _ = self.zone()
        return x1 - x0

    def fit_size(self, size: float, avail: float, widest) -> float:
        """Zmniejsza rozmiar kroju, aż najszersza linia (widest(size) -> piksele) zmieści się w avail. Nie mniej niż 45%."""
        floor = size * 0.45
        for _ in range(5):
            w = widest(size)
            if w <= avail or w <= 0:
                break
            size = max(floor, size * avail / w * 0.98)
        return size

    def zone(self, default: str | None = None) -> tuple[float, float, float, float]:
        return self.ctx.layout.zone(self.spec.get("zone", default or self.default_zone))

    def place(self, w: float, h: float, default_zone: str | None = None, align: str | None = None,
              valign: str | None = None) -> tuple[float, float]:
        """Lewy górny róg obrazu w x h: wg `x`, `y` (środek, ułamki kadru) albo w strefie z wyrównaniem."""
        W, H = self.ctx.W, self.ctx.H
        s = self.spec
        if "x" in s or "y" in s:
            cx, cy = float(s.get("x", 0.5)) * W, float(s.get("y", 0.2)) * H
            return cx - w / 2 + float(s.get("dx", 0)) * W, cy - h / 2 + float(s.get("dy", 0)) * H
        x0, y0, x1, y1 = self.zone(default_zone)
        a = s.get("align", align or "center")
        v = s.get("valign", valign or "center")
        x = x0 if a == "left" else x1 - w if a == "right" else (x0 + x1 - w) / 2
        y = y0 if v == "top" else y1 - h if v == "bottom" else (y0 + y1 - h) / 2
        return x + float(s.get("dx", 0)) * W, y + float(s.get("dy", 0)) * H

    def appear(self, sprite, lf: Life, rise: float = 40.0, blur_px: float = 10.0, overshoot: bool = False,
               scale_from: float = 0.94):
        """Standardowe wejście i wyjście: wzrost z lekkiego powiększenia, wjazd od dołu, rozmycie i zanik.
        Zwraca (obraz, przesunięcie y, krycie)."""
        k = ease_out_back(lf.k_in) if overshoot else ease_out(lf.k_in)
        sc = lerp(scale_from, 1.0, k) * lerp(1.0, 0.97, 1 - lf.k_out)
        dy = (1 - ease_out(lf.k_in)) * rise + (1 - lf.k_out) * -rise * 0.25
        bl = (1 - lf.k_in) * blur_px + (1 - lf.k_out) * blur_px * 0.6
        im = scale_rotate(sprite, sc) if abs(sc - 1) > 1e-3 else sprite
        if bl > 0.4:
            pad = int(bl * 2.5)
            canvas = rgba_image(im.size[0] + 2 * pad, im.size[1] + 2 * pad)
            canvas.paste(im, (pad, pad))
            im = blur(canvas, bl)
        return im, dy, lf.alpha


# ---------------------------------------------------------------------------------------------
# Tytuł: duży napis z małym słowem-akcentem
# ---------------------------------------------------------------------------------------------

@register("title")
class Title(Element):
    """Duży tytuł (domyślnie żółty) z opcjonalnym małym słowem obróconym nad prawym końcem, jak „worst” we wzorcu.

    Pola: text, accent (małe słowo), style: bold (krój marki, domyślnie) albo serif (kursywa szeryfowa jak we wzorcu),
    size (wysokość liter jako ułamek szerokości kadru), marker (żółta kreska pod tytułem), glow."""
    default_dur = 3.0
    default_zone = "bottom"

    def build(self) -> None:
        s, b = self.spec, self.brand
        text = str(s.get("text", "")).strip()
        if not text:
            raise PlanError("Tytuł (title) wymaga pola text.")
        style = s.get("style", "bold")
        role = "serif_italic" if style == "serif" else "display"
        size = float(s.get("size", 0.105 if style != "serif" else 0.15)) * self.ctx.W
        col = self.color("title") if "title_color" in s else b.rgb("title")
        zw = self.zone_width()
        max_w = min(0.92 * self.ctx.W, zw * 0.96) if zw else 0.92 * self.ctx.W

        def widest(sz: float) -> float:  # najszersza linia po zawinięciu
            f = b.font(role, sz)
            return max(text_size(ln, f, -0.01 * sz)[0] + 12 for ln in wrap_text(text, f, max_w, tracking=-0.01 * sz))

        size = self.fit_size(size, max_w, widest)
        font = b.font(role, size)
        lines = wrap_text(text, font, max_w, tracking=-0.01 * size)
        asc, desc = font.getmetrics()
        lh = (asc + desc) * (0.86 if style == "serif" else 0.92)
        parts = []
        wmax = 0.0
        for ln in lines:
            im, _ = text_sprite(ln, font, col + (255,), tracking=-0.01 * size, pad=6)
            parts.append(im)
            wmax = max(wmax, im.size[0])
        h = int(lh * (len(parts) - 1) + parts[-1].size[1]) + 12
        base = rgba_image(wmax, h)
        for i, im in enumerate(parts):
            base.alpha_composite(im, dest=(int((wmax - im.size[0]) // 2), int(i * lh)))
        # słowo-akcent: mniejsze, lekko obrócone, nad prawym końcem
        self.accent = None
        if s.get("accent"):
            f2 = b.font(role, size * 0.46)
            acol = b.rgb(s.get("accent_color", "accent"))
            im2, _ = text_sprite(str(s["accent"]), f2, acol + (255,), pad=6)
            self.accent, _ = shadowed(scale_rotate(im2, 1.0, 6.0), size * 0.035, float(s.get("shadow", 0.6)), dy=size * 0.012)
        # marker pod tytułem (podpis marki: żółta pociągnięta kreska)
        if s.get("marker"):
            mh = max(6, int(size * 0.09))
            mk = rounded_rect(wmax * 0.9, mh, mh / 2, fill=b.rgba("highlight", 0.9))
            base.alpha_composite(mk, dest=(int(wmax * 0.05), h - mh - 2))
        parts = [(base, 0, 0)]
        if s.get("glow", True):
            g, pad = glow_of(base, col, size * 0.12, 0.4)
            parts.insert(0, (g, -pad, -pad))
        if s.get("shadow", 0.6):  # ciemny cień pod napisem, żeby żółty tytuł dało się przeczytać także na jasnym tle
            sh, spad = glow_of(base, (0, 0, 0), size * 0.07, float(s.get("shadow", 0.6)))
            parts.insert(0, (sh, -spad, -spad + size * 0.03))
        if self.accent:
            parts.append((self.accent, wmax - self.accent.size[0] * 0.85, -self.accent.size[1] * 0.62))
        self.sprite, self.origin = compose(parts, pad=2)

    def draw(self, layer: Layer, t: float) -> None:
        lf = self.life(t)
        w, h = self.sprite.size
        x, y = self.place(w, h)
        im, dy, alpha = self.appear(self.sprite, lf, rise=28, blur_px=9, scale_from=0.93)
        layer.paste_center(im, x + w / 2, y + h / 2 + dy, alpha)


# ---------------------------------------------------------------------------------------------
# Plakietka z numerem: „#1 Tytuł”
# ---------------------------------------------------------------------------------------------

@register("badge")
class Badge(Element):
    """Numer w kole (znak marki) i tytuł obok, np. „1  Scenariusz wideo”. Pola: number, text, align, size."""
    default_dur = 4.0
    default_zone = "bottom"

    def build(self) -> None:
        s, b = self.spec, self.brand
        text = str(s.get("text", "")).strip()
        if not text:
            raise PlanError("Plakietka (badge) wymaga pola text.")
        size = float(s.get("size", 0.058)) * self.ctx.W  # wysokość kroju
        zw = self.zone_width()
        total_w = min(0.86 * self.ctx.W, zw * 0.96) if zw else 0.86 * self.ctx.W  # koło + odstęp + tekst
        text_w = lambda sz: total_w - sz * 1.93  # noqa: E731

        def widest(sz: float) -> float:
            f = b.font("display", sz)
            return max(text_size(ln, f)[0] for ln in wrap_text(text, f, text_w(sz))) + sz * 1.93

        size = self.fit_size(size, total_w, widest)
        font = b.font("display", size)
        lines = wrap_text(text, font, text_w(size))
        asc, desc = font.getmetrics()
        lh = (asc + desc) * 0.9
        parts = [text_sprite(ln, font, b.rgba("text"), tracking=-0.01 * size, pad=4)[0] for ln in lines]
        tw = max(p.size[0] for p in parts)
        th = int(lh * (len(parts) - 1) + parts[-1].size[1])
        d = int(size * 1.55)
        num = str(s.get("number", "1"))
        circle = disc(d, fill=b.rgba("badge"))
        nf = b.font("display", d * 0.55)
        nim, nbase = text_sprite(num, nf, b.rgba("text"), pad=2)
        circle.alpha_composite(nim, dest=((d - nim.size[0]) // 2, int((d - nim.size[1]) / 2)))
        gap = int(size * 0.38)
        H = max(d, th)
        base = rgba_image(d + gap + tw, H)
        base.alpha_composite(circle, dest=(0, (H - d) // 2))
        for i, p in enumerate(parts):
            base.alpha_composite(p, dest=(d + gap, int((H - th) / 2 + i * lh)))
        sh, pad = glow_of(base, (0, 0, 0), size * 0.25, 0.55)
        self.sprite, self.origin = compose([(sh, -pad, -pad), (base, 0, 0)], pad=2)

    def draw(self, layer: Layer, t: float) -> None:
        lf = self.life(t)
        w, h = self.sprite.size
        x, y = self.place(w, h)
        im, dy, alpha = self.appear(self.sprite, lf, rise=34, blur_px=8, overshoot=True, scale_from=0.9)
        layer.paste_center(im, x + w / 2, y + h / 2 + dy, alpha)
