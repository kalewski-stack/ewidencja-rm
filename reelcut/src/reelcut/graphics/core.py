"""Fundament silnika grafik: marka (kolory i kroje), animacje (easing), rysowanie na warstwie RGBA i strefy kadru.

Grafiki powstają w Pillow jako klatki RGBA 1080x1920, które ffmpeg nakłada na wideo. Kształty rysujemy z nadpróbkowaniem,
a rozmycie i skalowanie liczymy na obrazie z alfą przemnożoną (bez ciemnych obwódek na brzegach).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Sequence

from ..template import DATA_DIR

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

    HAVE_PIL = True
except ImportError:  # Pillow jest opcjonalny: bez niego nie ma grafik, reszta narzędzia działa
    HAVE_PIL = False

FONTS_DIR = DATA_DIR / "fonts"
DEFAULT_BRAND = DATA_DIR / "brand_kalewski.json"
SS = 3  # nadpróbkowanie przy rysowaniu kształtów


class GraphicsUnavailable(RuntimeError):
    """Brak Pillow (pip install pillow) albo plików z krojami."""


class PlanError(ValueError):
    """Błąd w planie grafik (z komunikatem dla użytkownika)."""


def need_pil() -> None:
    if not HAVE_PIL:
        raise GraphicsUnavailable("Do grafik potrzebny jest pakiet Pillow: pip install pillow")


# ---------------------------------------------------------------------------------------------
# Kolory
# ---------------------------------------------------------------------------------------------

def hex_rgb(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise PlanError(f"Zły kolor „{value}”: podaj #RRGGBB.")
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except ValueError as exc:
        raise PlanError(f"Zły kolor „{value}”: podaj #RRGGBB.") from exc


def with_alpha(rgb: tuple[int, int, int], alpha: float) -> tuple[int, int, int, int]:
    return rgb[0], rgb[1], rgb[2], max(0, min(255, int(round(alpha * 255))))


def mix(a: tuple[int, int, int], b: tuple[int, int, int], k: float) -> tuple[int, int, int]:
    return tuple(int(round(x + (y - x) * k)) for x, y in zip(a, b))  # type: ignore[return-value]


# ---------------------------------------------------------------------------------------------
# Animacje
# ---------------------------------------------------------------------------------------------

def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * k


def prog(t: float, t0: float, dur: float) -> float:
    """Postęp 0-1 animacji, która zaczyna się w t0 i trwa dur sekund."""
    return 1.0 if dur <= 0 else clamp01((t - t0) / dur)


def ease_linear(x: float) -> float:
    return x


def ease_out(x: float) -> float:  # cubic
    return 1 - (1 - x) ** 3


def ease_in(x: float) -> float:
    return x ** 3


def ease_in_out(x: float) -> float:
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_expo(x: float) -> float:
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_out_back(x: float, s: float = 1.45) -> float:
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def ease_smooth(x: float) -> float:
    return x * x * (3 - 2 * x)


EASINGS: dict[str, Callable[[float], float]] = {
    "linear": ease_linear, "out": ease_out, "in": ease_in, "in_out": ease_in_out, "out_expo": ease_out_expo,
    "out_back": ease_out_back, "smooth": ease_smooth,
}


@dataclass(frozen=True)
class Life:
    """Stan elementu w chwili t: postęp wejścia i wyjścia (0-1) oraz czas lokalny."""
    lt: float  # sekundy od startu elementu
    k_in: float  # 0 → 1 w czasie wejścia
    k_out: float  # 1 → 0 w czasie wyjścia

    @property
    def alpha(self) -> float:
        return ease_smooth(self.k_in) * ease_smooth(self.k_out)


def life(t: float, start: float, dur: float, d_in: float = 0.4, d_out: float = 0.3) -> Life:
    lt = t - start
    k_in = clamp01(lt / d_in) if d_in > 0 else (1.0 if lt >= 0 else 0.0)
    k_out = clamp01((dur - lt) / d_out) if d_out > 0 else (1.0 if lt <= dur else 0.0)
    return Life(lt, k_in, k_out)


# ---------------------------------------------------------------------------------------------
# Marka
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Brand:
    name: str
    colors: dict[str, str]
    roles: dict[str, str]
    series: tuple[str, ...]
    fonts: dict[str, str]
    base: Path = FONTS_DIR

    def rgb(self, key: str) -> tuple[int, int, int]:
        """Kolor po roli (accent, highlight...), po nazwie (violet...) albo jako #RRGGBB."""
        seen = 0
        while key in self.roles and seen < 5:
            key, seen = self.roles[key], seen + 1
        if key in self.colors:
            return hex_rgb(self.colors[key])
        return hex_rgb(key)

    def rgba(self, key: str, alpha: float = 1.0) -> tuple[int, int, int, int]:
        return with_alpha(self.rgb(key), alpha)

    def series_rgb(self, i: int) -> tuple[int, int, int]:
        return self.rgb(self.series[i % len(self.series)])

    def font(self, role: str, size: float):
        need_pil()
        path = self.fonts.get(role)
        if not path:
            raise PlanError(f"Marka „{self.name}” nie ma kroju „{role}”.")
        p = Path(path)
        if not p.is_absolute():
            p = self.base / p
        if not p.exists():
            raise GraphicsUnavailable(f"Brak pliku kroju: {p}")
        return _load_font(str(p), max(4, int(round(size))))


@lru_cache(maxsize=128)
def _load_font(path: str, size: int):
    return ImageFont.truetype(path, size)


def parse_brand(raw: dict, base: Path = FONTS_DIR) -> Brand:
    if raw.get("schema") != 1:
        raise PlanError("Nieznana wersja marki (oczekiwano schema=1).")
    colors = {str(k): str(v) for k, v in raw.get("colors", {}).items()}
    for v in colors.values():
        hex_rgb(v)
    roles = {str(k): str(v) for k, v in raw.get("roles", {}).items()}
    brand = Brand(str(raw.get("name", "marka")), colors, roles, tuple(raw.get("series", [])) or tuple(colors)[:4],
                  {str(k): str(v) for k, v in raw.get("fonts", {}).items()}, base)
    for role in ("text", "accent", "highlight", "panel"):
        brand.rgb(role)  # musi dać się rozwiązać
    return brand


def load_brand(ref: str | Path | None = None) -> Brand:
    """Marka domyślna („Linia Kalewski”), plik JSON albo nazwa pliku z katalogu data (brand_<nazwa>.json)."""
    if ref is None:
        path = DEFAULT_BRAND
    else:
        path = Path(str(ref))
        if not path.exists():
            alt = DATA_DIR / f"brand_{ref}.json"
            if not alt.exists():
                raise PlanError(f"Nie znaleziono marki: {ref}")
            path = alt
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"Nie da się wczytać marki {path}: {exc}") from exc
    brand = parse_brand(raw, base=path.parent / "fonts" if path.parent != DATA_DIR else FONTS_DIR)
    return brand


# ---------------------------------------------------------------------------------------------
# Rysowanie
# ---------------------------------------------------------------------------------------------

def rgba_image(w: float, h: float):
    need_pil()
    return Image.new("RGBA", (max(1, int(math.ceil(w))), max(1, int(math.ceil(h)))), (0, 0, 0, 0))


def _premul(im, fn):
    """Wykonuje fn na obrazie z alfą przemnożoną (rozmycie, obrót), potem wraca do zwykłej alfy."""
    return fn(im.convert("RGBa")).convert("RGBA")


def blur(im, radius: float):
    if radius <= 0.3:
        return im
    return _premul(im, lambda x: x.filter(ImageFilter.GaussianBlur(radius)))


def scale_rotate(im, scale: float = 1.0, angle: float = 0.0):
    """Skaluje i obraca wokół środka (obraz rośnie, gdy trzeba)."""
    if abs(scale - 1.0) > 1e-3:
        w, h = im.size
        im = im.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))), Image.LANCZOS)
    if abs(angle) > 1e-3:
        im = _premul(im, lambda x: x.rotate(angle, resample=Image.BICUBIC, expand=True))
    return im


def fade(im, alpha: float):
    """Mnoży alfę obrazu."""
    if alpha >= 0.999:
        return im
    if alpha <= 0.001:
        return rgba_image(1, 1)
    lut = [int(round(v * alpha)) for v in range(256)]
    out = im.copy()
    out.putalpha(im.getchannel("A").point(lut))
    return out


def rounded_rect(w: float, h: float, radius: float, fill=None, outline=None, outline_w: float = 0.0):
    need_pil()
    w, h = max(2, int(round(w))), max(2, int(round(h)))
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], radius=radius * SS, fill=fill, outline=outline,
                        width=max(0, int(round(outline_w * SS))))
    return big.resize((w, h), Image.LANCZOS)


def disc(d: float, fill=None, outline=None, outline_w: float = 0.0):
    d = max(2, int(round(d)))
    big = Image.new("RGBA", (d * SS, d * SS), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse([0, 0, d * SS - 1, d * SS - 1], fill=fill, outline=outline,
                                width=max(0, int(round(outline_w * SS))))
    return big.resize((d, d), Image.LANCZOS)


def eye_icon(d: float, color: tuple[int, int, int]):
    """Ikona oka (liczba wyświetleń): kontur migdału z kropką pośrodku."""
    d = max(8, int(round(d)))
    big = Image.new("RGBA", (d * SS, d * SS), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    c, k = d * SS / 2, d * SS
    col = tuple(color) + (255,)
    g.ellipse([c - k * 0.46, c - k * 0.27, c + k * 0.46, c + k * 0.27], outline=col, width=max(2, int(k * 0.12)))
    r = k * 0.14
    g.ellipse([c - r, c - r, c + r, c + r], fill=col)
    return big.resize((d, d), Image.LANCZOS)


def polygon(points: Sequence[tuple[float, float]], fill, size: tuple[int, int] | None = None, pad: int = 2):
    """Wielokąt z wygładzonymi krawędziami; punkty w pikselach docelowych."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x0, y0 = min(xs) - pad, min(ys) - pad
    w = size[0] if size else int(math.ceil(max(xs) - x0 + pad))
    h = size[1] if size else int(math.ceil(max(ys) - y0 + pad))
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    ImageDraw.Draw(big).polygon([((x - x0) * SS, (y - y0) * SS) for x, y in points], fill=fill)
    return big.resize((w, h), Image.LANCZOS), (x0, y0)


def glow_of(im, color: tuple[int, int, int], radius: float, strength: float = 1.0):
    """Poświata w danym kolorze wokół kształtu z kanału alfa obrazu."""
    pad = int(radius * 3)
    w, h = im.size
    base = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    base.paste(im.getchannel("A"), (pad, pad))
    base = base.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        lut = [min(255, int(v * strength)) for v in range(256)]
        base = base.point(lut)
    out = Image.new("RGBA", base.size, color + (0,))
    out.putalpha(base)
    return out, pad


def vgradient(w: float, h: float, top, bottom):
    """Prostokąt RGBA z płynnym przejściem od koloru `top` (góra) do `bottom` (dół); kolory jako krotki RGBA."""
    need_pil()
    w, h = max(1, int(round(w))), max(1, int(round(h)))
    mask = Image.linear_gradient("L").resize((w, h), Image.BILINEAR)
    return Image.composite(Image.new("RGBA", (w, h), tuple(bottom)), Image.new("RGBA", (w, h), tuple(top)), mask)


def shadowed(im, radius: float, strength: float = 0.55, dy: float = 0.0, color: tuple[int, int, int] = (0, 0, 0)):
    """Obraz z miękkim cieniem pod spodem (czytelność tekstu na jasnym tle). Zwraca (obraz, (ox, oy)), gdzie (ox, oy)
    to położenie lewego górnego rogu oryginału w wyniku."""
    if strength <= 0 or radius <= 0:
        return im, (0, 0)
    sh, pad = glow_of(im, color, radius, strength)
    out, (x0, y0) = compose([(sh, -pad, -pad + dy), (im, 0, 0)])
    return out, (int(round(-x0)), int(round(-y0)))


def text_size(text: str, font, tracking: float = 0.0) -> tuple[float, float]:
    if not text:
        return 0.0, 0.0
    asc, desc = font.getmetrics()
    if tracking == 0:
        return font.getlength(text), asc + desc
    return sum(font.getlength(c) for c in text) + tracking * (len(text) - 1), asc + desc


def text_sprite(text: str, font, fill, tracking: float = 0.0, pad: int = 4):
    """Obraz z tekstem. Zwraca (obraz, wysokość linii bazowej od góry obrazu)."""
    need_pil()
    asc, desc = font.getmetrics()
    w, h = text_size(text, font, tracking)
    im = Image.new("RGBA", (int(math.ceil(w)) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if tracking == 0:
        d.text((pad, pad), text, font=font, fill=fill)
    else:
        x = float(pad)
        for c in text:
            d.text((x, pad), c, font=font, fill=fill)
            x += font.getlength(c) + tracking
    return im, pad + asc


def fit_font(brand, role: str, text: str, size: float, max_w: float, min_scale: float = 0.62):
    """Krój o rozmiarze size, a gdy tekst jest za szeroki, zmniejszony tak, by zmieścił się w max_w (nie mniej niż min_scale)."""
    font = brand.font(role, size)
    w = text_size(text, font)[0]
    if w <= max_w or w <= 0:
        return font
    return brand.font(role, size * max(min_scale, max_w / w))


def wrap_text(text: str, font, max_w: float, tracking: float = 0.0) -> list[str]:
    """Łamie tekst na wiersze o szerokości do max_w (po spacjach)."""
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            trial = f"{cur} {word}".strip()
            if cur and text_size(trial, font, tracking)[0] > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
    return lines


def compose(parts, pad: int = 0):
    """Skleja obrazy w jeden: parts = [(obraz, x, y)] we wspólnym układzie (x, y mogą być ujemne).
    Zwraca (obraz, (x0, y0)): położenie jego lewego górnego rogu w tym układzie."""
    need_pil()
    x0 = min(x for _, x, _ in parts) - pad
    y0 = min(y for _, _, y in parts) - pad
    x1 = max(x + im.size[0] for im, x, _ in parts) + pad
    y1 = max(y + im.size[1] for im, _, y in parts) + pad
    out = Image.new("RGBA", (int(math.ceil(x1 - x0)), int(math.ceil(y1 - y0))), (0, 0, 0, 0))
    for im, x, y in parts:
        out.alpha_composite(im, dest=(int(round(x - x0)), int(round(y - y0))))
    return out, (x0, y0)


def cover(img, w: int, h: int):
    """Skaluje i przycina obraz tak, by wypełnił w x h (jak object-fit: cover)."""
    need_pil()
    iw, ih = img.size
    k = max(w / iw, h / ih)
    nw, nh = max(1, int(round(iw * k))), max(1, int(round(ih * k)))
    im = img.convert("RGBA").resize((nw, nh), Image.LANCZOS)
    x, y = (nw - w) // 2, (nh - h) // 2
    return im.crop((x, y, x + w, y + h))


def round_corners(img, radius: float):
    """Zaokrągla rogi obrazu (maska z nadpróbkowaniem)."""
    need_pil()
    w, h = img.size
    mask = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], radius=radius * SS, fill=255)
    out = img.convert("RGBA")
    out.putalpha(ImageChops.multiply(out.getchannel("A"), mask.resize((w, h), Image.LANCZOS)))
    return out


@lru_cache(maxsize=32)
def load_image(path: str):
    need_pil()
    try:
        return Image.open(path).convert("RGBA")
    except OSError as exc:
        raise PlanError(f"Nie da się wczytać obrazu {path}: {exc}") from exc


def circle_crop(img, d: int):
    """Wycina z obrazu kółko o średnicy d (środek obrazu)."""
    need_pil()
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).convert("RGBA").resize((d, d), Image.LANCZOS)
    mask = Image.new("L", (d * SS, d * SS), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d * SS - 1, d * SS - 1], fill=255)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask.resize((d, d), Image.LANCZOS)))
    return img


class Layer:
    """Warstwa RGBA całego kadru; elementy dokładają na niej swoje obrazy."""

    def __init__(self, size: tuple[int, int]):
        need_pil()
        self.size = size
        self.img = Image.new("RGBA", size, (0, 0, 0, 0))

    def paste(self, sprite, x: float, y: float, alpha: float = 1.0) -> None:
        if alpha <= 0.002:
            return
        sprite = fade(sprite, alpha)
        x, y = int(round(x)), int(round(y))
        w, h = sprite.size
        x0, y0, x1, y1 = max(0, x), max(0, y), min(self.size[0], x + w), min(self.size[1], y + h)
        if x1 <= x0 or y1 <= y0:
            return
        self.img.alpha_composite(sprite, dest=(x0, y0), source=(x0 - x, y0 - y, x1 - x, y1 - y))

    def paste_center(self, sprite, cx: float, cy: float, alpha: float = 1.0) -> None:
        self.paste(sprite, cx - sprite.size[0] / 2, cy - sprite.size[1] / 2, alpha)

    def tobytes(self) -> bytes:
        return self.img.tobytes()


# ---------------------------------------------------------------------------------------------
# Strefy kadru
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Layout:
    """Układ kadru: gdzie jest twarz, a więc gdzie wolno stawiać grafiki, żeby jej nie zasłaniać."""
    W: int
    H: int
    face_cx: float = 0.4826  # środek twarzy (ułamki kadru); wartości domyślne: mediany czterech rolek formatu 2
    face_cy: float = 0.458
    face_h: float = 0.1536
    caption_top: float = 0.548  # górna krawędź napisów biegnących
    caption_bottom: float = 0.575

    @property
    def head_top(self) -> float:  # czubek głowy z włosami (ułamek wysokości)
        return self.face_cy - 0.78 * self.face_h

    @property
    def head_half_w(self) -> float:  # połowa szerokości głowy z uszami i włosami (ułamek szerokości)
        return 0.78 * self.face_h * (self.H / self.W) * 0.95

    def zone(self, name: str) -> tuple[float, float, float, float]:
        """(x0, y0, x1, y1) w pikselach."""
        W, H = self.W, self.H
        mx, my = 0.045 * W, 0.035 * H
        top_bottom = max(0.14, self.head_top - 0.012) * H
        left_r = max(0.15, self.face_cx - self.head_half_w - 0.015) * W
        right_l = min(0.85, self.face_cx + self.head_half_w + 0.015) * W
        zones = {
            "top": (mx, my, W - mx, top_bottom),
            "left": (mx, 0.20 * H, left_r, 0.60 * H),
            "right": (right_l, 0.20 * H, W - mx, 0.60 * H),
            "bottom": (mx, (self.caption_bottom + 0.035) * H, W - mx, H - 0.03 * H),
            "captions": (mx, self.caption_top * H, W - mx, self.caption_bottom * H),
            "head": (left_r, self.head_top * H, right_l, (self.face_cy + 0.6 * self.face_h) * H),
            "full": (mx, my, W - mx, H - my),
        }
        if name not in zones:
            raise PlanError(f"Nieznana strefa „{name}”. Dostępne: {', '.join(zones)}.")
        return zones[name]
