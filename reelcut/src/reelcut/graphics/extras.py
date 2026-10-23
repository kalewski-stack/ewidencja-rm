"""Pozostałe elementy: wyróżnienie z pisaniem na żywo (callout), licznik (stat), ilustracja z poświatą oraz napisy biegnące."""
from __future__ import annotations

import math

from .core import (SS, Layer, PlanError, clamp01, compose, cover, ease_in_out, ease_out, glow_of, lerp, load_image, prog,
                   round_corners, rounded_rect, scale_rotate, shadowed, text_size, text_sprite, wrap_text)
from .elements import Element, register

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    pass


def icon_tile(kind: str, size: int, brand):
    """Kafelek z ikoną: żółty zaokrąglony kwadrat i prosty rysunek w kolorze tuszu (żarówka, ptaszek, gwiazdka)."""
    tile = rounded_rect(size, size, size * 0.22, fill=brand.rgba("highlight"))
    big = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    ink = brand.rgb("panel") + (255,)
    c = size * SS / 2
    w = max(2, int(size * SS * 0.055))
    if kind == "bulb":
        r = size * SS * 0.2
        g.ellipse([c - r, c - r * 1.35, c + r, c + r * 0.65], outline=ink, width=w)
        g.line([(c - r * 0.55, c + r * 0.95), (c + r * 0.55, c + r * 0.95)], fill=ink, width=w)
        g.line([(c - r * 0.35, c + r * 1.3), (c + r * 0.35, c + r * 1.3)], fill=ink, width=w)
        for ang in (-90, -45, 45, 90 + 45, 180, 0):
            a = math.radians(ang - 0)
            g.line([(c + math.cos(a) * r * 1.65, c - r * 0.35 + math.sin(a) * r * 1.65), (c + math.cos(a) * r * 2.0, c - r * 0.35 + math.sin(a) * r * 2.0)], fill=ink, width=w)
    elif kind == "check":
        g.line([(c - size * SS * 0.22, c + size * SS * 0.02), (c - size * SS * 0.05, c + size * SS * 0.2), (c + size * SS * 0.24, c - size * SS * 0.16)],
               fill=ink, width=int(w * 1.8), joint="curve")
    elif kind == "star":
        pts = []
        for k in range(10):
            a = math.radians(-90 + k * 36)
            rr = size * SS * (0.27 if k % 2 == 0 else 0.12)
            pts.append((c + math.cos(a) * rr, c + math.sin(a) * rr))
        g.polygon(pts, fill=ink)
    tile.alpha_composite(big.resize((size, size), Image.LANCZOS))
    return tile


def check_badge(d: int, brand):
    """Biały kafelek z ptaszkiem w kolorze akcentu (potwierdzenie przy karcie)."""
    t = rounded_rect(d, d, d * 0.26, fill=(255, 255, 255, 255))
    big = Image.new("RGBA", (d * SS, d * SS), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    c = d * SS / 2
    g.ellipse([c - d * SS * 0.34, c - d * SS * 0.34, c + d * SS * 0.34, c + d * SS * 0.34], fill=brand.rgb("accent_strong") + (255,))
    g.line([(c - d * SS * 0.16, c + d * SS * 0.0), (c - d * SS * 0.04, c + d * SS * 0.13), (c + d * SS * 0.18, c - d * SS * 0.12)],
           fill=(255, 255, 255, 255), width=int(d * SS * 0.07), joint="curve")
    t.alpha_composite(big.resize((d, d), Image.LANCZOS))
    return t


# ---------------------------------------------------------------------------------------------
# Wyróżnienie z pisaniem na żywo
# ---------------------------------------------------------------------------------------------

@register("callout")
class Callout(Element):
    """Kafelek z ikoną i tytułem, pod spodem tekst „pisany” znak po znaku (najnowsze znaki w kolorze wyróżnienia).
    Pola: icon (bulb|check|star|none), title, text, cps (znaków na sekundę), kicker (tytuł szeryfowy po prawej),
    image (karta po prawej), width."""
    default_dur = 5.0
    default_zone = "top"
    d_in = 0.4
    d_out = 0.35

    def build(self) -> None:
        s, b = self.spec, self.brand
        W = self.ctx.W
        if not (s.get("title") or s.get("text")):
            raise PlanError("Wyróżnienie (callout) wymaga title albo text.")
        self.f_title = b.font("display", W * 0.052)
        self.f_body = b.font("semibold", W * 0.034)
        self.body_w = float(s.get("width", 0.46)) * W
        self.text = str(s.get("text", ""))
        self.lines = wrap_text(self.text, self.f_body, self.body_w, tracking=-0.3)
        self.cps = float(s.get("cps", 30))
        self.tile = icon_tile(s.get("icon", "bulb"), int(W * 0.078), b) if s.get("icon", "bulb") != "none" else None
        self.kicker = None
        if s.get("kicker"):
            kf = b.font("serif_italic", W * 0.07)
            lines = str(s["kicker"]).split("\n")
            kcol = b.rgb("title")
            parts, y = [], 0.0
            for ln in lines:
                im, _ = text_sprite(ln, kf, kcol + (255,), tracking=-1.2, pad=2)
                parts.append((im, 0, y))
                y += (kf.getmetrics()[0] + kf.getmetrics()[1]) * 0.78
            w = max(p[0].size[0] for p in parts)
            self.kicker, _ = compose([(im, w - im.size[0], yy) for im, _, yy in parts])
        self.card = None
        if s.get("image"):
            cw = int(W * 0.2)
            self.card = round_corners(cover(load_image(str(self.ctx.resolve(str(s["image"])))), cw, int(cw * 16 / 9)), 8)
            badge = check_badge(int(W * 0.045), b)
            self.badge = badge

    def draw(self, layer: Layer, t: float) -> None:
        s, b = self.spec, self.brand
        lf = self.life(t)
        W = self.ctx.W
        lt = lf.lt
        parts = []
        x = 0.0
        title = s.get("title")
        th = 0
        if self.tile is not None:
            parts.append((self.tile, 0, 0))
            x = self.tile.size[0] + W * 0.02
            th = self.tile.size[1]
        if title:
            tim, _ = text_sprite(str(title), self.f_title, b.rgba("text"), tracking=-1.0, pad=2)
            parts.append((tim, x, (th - tim.size[1]) / 2 if th else 0))
            th = max(th, tim.size[1])
        # tekst pisany
        n = int(max(0.0, lt - 0.45) * self.cps)
        total = sum(len(l) for l in self.lines)
        shown = min(n, total)
        asc, desc = self.f_body.getmetrics()
        lh = (asc + desc) * 0.98
        y = th + W * 0.022
        left = 0
        for ln in self.lines:
            take = max(0, min(len(ln), shown - left))
            left += len(ln)
            if take <= 0:
                break
            hot = min(take, 3) if shown < total else 0
            head, tail = ln[: take - hot], ln[take - hot: take]
            xx = 0.0
            if head:
                im, _ = text_sprite(head, self.f_body, b.rgba("text"), tracking=-0.3, pad=0)
                parts.append((im, xx, y))
                xx += self.f_body.getlength(head) - 0.3 * len(head)
            if tail:
                im, _ = text_sprite(tail, self.f_body, b.rgba("highlight"), tracking=-0.3, pad=0)
                parts.append((im, xx, y))
            y += lh
        if not parts:
            return
        spr, (ox, oy) = compose(parts, pad=6)
        block_w = spr.size[0]
        spr, (sx, sy) = shadowed(spr, 9, float(s.get("shadow", 0.55)), dy=3)
        ox, oy = ox - sx, oy - sy
        zx0, zy0, zx1, zy1 = self.zone()
        margin = W * 0.03
        left_x = zx0 + margin if s.get("align", "left") == "left" else (zx0 + zx1 - spr.size[0]) / 2
        top_y = zy0 + (zy1 - zy0) * 0.18
        im, dy, alpha = self.appear(spr, lf, rise=24, blur_px=8, scale_from=0.96)
        layer.paste(im, left_x + ox, top_y + oy + dy, alpha)
        # prawa kolumna: tytuł szeryfowy nad kartą z „ptaszkiem”; zwężamy go, żeby nie wchodził na lewy blok
        if self.kicker is not None or self.card is not None:
            rx = zx1 - margin
            ry = zy0 + (zy1 - zy0) * 0.04
            avail = rx - (left_x + block_w - 12 + margin)
            k = ease_out(prog(lt, 0.25, 0.5))
            if self.kicker is not None:
                kim = self.kicker
                if kim.size[0] > avail > 0:
                    kim = scale_rotate(kim, max(0.55, avail / kim.size[0]))
                layer.paste(kim, rx - kim.size[0], ry + (1 - k) * 20, alpha * k)
                ry += kim.size[1] + 8
            if self.card is not None:
                layer.paste(self.card, rx - self.card.size[0], ry + (1 - k) * 30, alpha * k)
                layer.paste(self.badge, rx - self.card.size[0] - self.badge.size[0] * 0.5, ry + self.badge.size[1] * 0.4 + (1 - k) * 30, alpha * k)


# ---------------------------------------------------------------------------------------------
# Licznik
# ---------------------------------------------------------------------------------------------

@register("stat")
class Stat(Element):
    """Duża liczba odliczana od `from` do `value`, podpis pod spodem i opcjonalnie pasek postępu.
    Pola: value, from, prefix, suffix, label, decimals, size, bar (true/false), count_at, count_dur."""
    default_dur = 4.0
    default_zone = "top"
    d_in = 0.4
    d_out = 0.35

    def build(self) -> None:
        s, b = self.spec, self.brand
        if "value" not in s:
            raise PlanError("Licznik (stat) wymaga pola value.")
        W = self.ctx.W
        self.v0, self.v1 = float(s.get("from", 0)), float(s["value"])
        self.dec = int(s.get("decimals", 0))
        size = W * float(s.get("size", 0.17))
        zw = self.zone_width()
        if zw:  # liczba w wąskiej strefie (np. obok głowy) maleje tak, żeby w całości się zmieściła
            finals = [self._text(v) for v in (self.v0, self.v1)]
            size = self.fit_size(size, zw * 0.96, lambda sz: max(text_size(t, b.font("display", sz), -3)[0] + 8 for t in finals))
        self.f_num = b.font("display", size)
        self.f_label = b.font("semibold", min(W * 0.04, size * 0.24 + 6))

    def _text(self, v: float) -> str:
        s = self.spec
        return f"{s.get('prefix', '')}{v:,.{self.dec}f}".replace(",", " ") + str(s.get("suffix", ""))

    def draw(self, layer: Layer, t: float) -> None:
        s, b = self.spec, self.brand
        lf = self.life(t)
        W = self.ctx.W
        k = ease_out(prog(lf.lt, float(s.get("count_at", 0.35)), float(s.get("count_dur", 1.5))))
        v = lerp(self.v0, self.v1, k)
        nim, _ = text_sprite(self._text(v), self.f_num, b.rgba("highlight"), tracking=-3, pad=4)
        parts = [(nim, 0, 0)]
        wmax = nim.size[0]
        y = nim.size[1] * 0.92
        if s.get("label"):
            lim, _ = text_sprite(str(s["label"]), self.f_label, b.rgba("text"), pad=2)
            parts.append((lim, (wmax - lim.size[0]) / 2, y))
            y += lim.size[1] + W * 0.012
        if s.get("bar", True):
            bw, bh = wmax * 1.0, max(5, W * 0.0085)
            track = rounded_rect(bw, bh, bh / 2, fill=(255, 255, 255, 60))
            frac = clamp01((v - self.v0) / (self.v1 - self.v0)) if self.v1 != self.v0 else 1.0
            track.alpha_composite(rounded_rect(max(bh, bw * frac), bh, bh / 2, fill=b.rgba("accent")))
            parts.append((track, 0, y))
        spr, _ = compose(parts, pad=6)
        spr, _ = shadowed(spr, 10, float(s.get("shadow", 0.55)), dy=3)
        x, y0 = self.place(spr.size[0], spr.size[1])
        im, dy, alpha = self.appear(spr, lf, rise=22, blur_px=8, scale_from=0.95)
        layer.paste_center(im, x + spr.size[0] / 2, y0 + spr.size[1] / 2 + dy, alpha)


# ---------------------------------------------------------------------------------------------
# Ilustracja z poświatą
# ---------------------------------------------------------------------------------------------

class Keys:
    """Klatki kluczowe ruchu: [czas, x, y, skala, obrót]. Czas liczymy od startu elementu (sekundy), x i y to środek (ułamki kadru),
    skala (domyślnie 1) i obrót w stopniach (domyślnie z pola rot) są opcjonalne. Między kluczami ruch jest płynny: łagodny start i hamowanie."""

    def __init__(self, raw, rot0: float = 0.0):
        if not isinstance(raw, list) or len(raw) < 2:
            raise PlanError("path to lista co najmniej dwóch kluczy [czas, x, y] albo [czas, x, y, skala, obrót].")
        pts = []
        for k in raw:
            if not isinstance(k, (list, tuple)) or not 3 <= len(k) <= 5:
                raise PlanError("Każdy klucz ścieżki to [czas, x, y] albo [czas, x, y, skala, obrót].")
            try:
                t, x, y = float(k[0]), float(k[1]), float(k[2])
                sc = float(k[3]) if len(k) > 3 and k[3] is not None else 1.0
                rot = float(k[4]) if len(k) > 4 and k[4] is not None else rot0
            except (TypeError, ValueError) as exc:
                raise PlanError("Klucze ścieżki muszą być liczbami.") from exc
            if sc <= 0:
                raise PlanError("Skala w kluczu ścieżki musi być dodatnia.")
            pts.append((t, x, y, sc, rot))
        self.pts = sorted(pts)

    def at(self, lt: float) -> tuple[float, float, float, float]:
        """(x, y, skala, obrót) w chwili lt (sekundy od startu elementu)."""
        p = self.pts
        if lt <= p[0][0]:
            return p[0][1:]
        for a, b in zip(p[:-1], p[1:]):
            if lt <= b[0]:
                k = ease_in_out(prog(lt, a[0], max(1e-6, b[0] - a[0])))
                return tuple(lerp(u, v, k) for u, v in zip(a[1:], b[1:]))
        return p[-1][1:]


@register("illustration")
class Illustration(Element):
    """Dowolny obraz (PNG z przezroczystością albo zdjęcie) z miękką poświatą, np. nad głową. Pola: image, width
    (ułamek szerokości kadru), glow (kolor marki albo #hex; false: bez poświaty), anchor: head (nad głową) albo strefa albo x i y,
    rot (obrót w stopniach), opacity (0-1), float, round (zaokrąglenie rogów), bleed (true: może wychodzić poza kadr),
    path: klatki kluczowe [[czas, x, y, skala, obrót], ...] (czas od startu elementu): obraz przesuwa się, rośnie i obraca."""
    default_dur = 3.0
    default_zone = "top"
    d_in = 0.5
    d_out = 0.4

    def build(self) -> None:
        s, b = self.spec, self.brand
        if not s.get("image"):
            raise PlanError("Ilustracja (illustration) wymaga pola image.")
        W = self.ctx.W
        img = load_image(str(self.ctx.resolve(str(s["image"]))))
        w = int(float(s.get("width", 0.3)) * W)
        h = int(img.size[1] * w / img.size[0])
        im = img.resize((w, h), Image.LANCZOS)
        if s.get("round"):
            im = round_corners(im, float(s["round"]) * w)
        parts = [(im, 0, 0)]
        if s.get("glow", "accent"):
            gcol = b.rgb(s.get("glow", "accent"))
            g, pad = glow_of(im, gcol, w * 0.09, 0.9)
            parts.insert(0, (g, -pad, -pad))
        self.sprite, self.origin = compose(parts, pad=2)
        self.rot = float(s.get("rot", 0.0))
        self.opacity = max(0.0, min(1.0, float(s.get("opacity", 1.0))))
        self.keys = Keys(s["path"], self.rot) if s.get("path") else None
        self.free_placement = self.keys is not None
        self._static = scale_rotate(self.sprite, 1.0, self.rot) if abs(self.rot) > 1e-3 else self.sprite

    def draw(self, layer: Layer, t: float) -> None:
        s = self.spec
        lf = self.life(t)
        L = self.ctx.layout
        base, float_dy = self._static, 0.0
        if self.keys:
            kx, ky, sc, rot = self.keys.at(lf.lt)
            base = scale_rotate(self.sprite, sc, rot) if (abs(sc - 1) > 1e-3 or abs(rot) > 1e-3) else self.sprite
            cx, cy = kx * L.W, ky * L.H
        else:
            w, h = base.size
            if s.get("anchor") == "head":
                x = L.face_cx * L.W - w / 2
                y = (L.head_top * L.H) - h * 0.78
            else:
                x, y = self.place(w, h)
            cx, cy = x + w / 2, y + h / 2
            float_dy = 6 * math.sin(2 * math.pi * lf.lt / 3.0) if s.get("float", True) else 0
        im, dy2, alpha = self.appear(base, lf, rise=30, blur_px=14, scale_from=0.88)
        layer.paste_center(im, cx, cy + float_dy + dy2, alpha * self.opacity)


# ---------------------------------------------------------------------------------------------
# Napisy biegnące (warstwa grafik)
# ---------------------------------------------------------------------------------------------

@register("captions")
class CaptionTrack(Element):
    """Napisy słowo po słowie: 1-3 słowa naraz, biały krój marki, środek kadru nad klatką piersiową.
    Słowa podaje potok montażu (ctx.words, czasy na osi gotowego filmu). Pola: size (wysokość wersalików, ułamek
    wysokości kadru), y (górna krawędź, ułamek wysokości), max_words, shift [{at, dur, y}] przesuwa napisy, gdy dół
    kadru zajmuje inny element, skip [[od, do], ...] (sekundy) pomija słowa wypowiedziane w tych przedziałach, bo
    pokazuje je coś innego (hasło), hide [[od, do], ...] chowa napisy na ten czas (hasło stoi w tym miejscu)."""
    default_dur = 0.0
    default_z = 9
    d_in = 0.0
    d_out = 0.0

    def __init__(self, spec: dict, ctx):
        spec = dict(spec)
        spec.setdefault("at", 0.0)
        spec.setdefault("dur", getattr(ctx, "duration", 0.0) or 1.0)
        super().__init__(spec, ctx)

    def build(self) -> None:
        from .. import captions as cap

        s, b = self.spec, self.brand
        H = self.ctx.H
        words = list(getattr(self.ctx, "words", []) or [])
        skip = [(float(lo), float(hi)) for lo, hi in s.get("skip", [])]
        if skip:
            words = [w for w in words if not any(lo <= (float(w.start) + float(w.end)) / 2 <= hi for lo, hi in skip)]
        self.groups = cap.group_words(words, int(s.get("max_words", 3)), int(s.get("short_max", 3))) if words else []
        cap_px = float(s.get("size", 0.0188)) * H
        self.font = b.font(s.get("weight", "semibold"), cap_px / 0.66)
        self.top = float(s.get("y", 0.548)) * H
        self.shift = [(float(w["at"]), float(w["at"]) + float(w["dur"]), float(w["y"]) * H) for w in s.get("shift", [])]
        self.lead, self.hold = float(s.get("lead", 0.04)), float(s.get("hold", 0.25))
        self.hide = [(float(lo), float(hi)) for lo, hi in s.get("hide", [])]
        self.cache: dict[str, object] = {}
        self.starts = [g.start for g in self.groups]
        self.dur = max([self.dur] + [g.end for g in self.groups])

    def active(self, t: float) -> bool:
        return bool(self.groups)

    def _sprite(self, text: str):
        if text not in self.cache:
            if len(self.cache) > 400:
                self.cache.clear()
            im, base = text_sprite(text, self.font, self.brand.rgba("text"), tracking=-0.6, pad=3)
            im, (_, sy) = shadowed(im, self.font.size * 0.09, float(self.spec.get("shadow", 0.5)), dy=self.font.size * 0.025)
            self.cache[text] = (im, base + sy)
        return self.cache[text]

    def draw(self, layer: Layer, t: float) -> None:
        import bisect

        if any(lo <= t < hi for lo, hi in self.hide):
            return
        i = bisect.bisect_right(self.starts, t + self.lead) - 1
        if i < 0:
            return
        g = self.groups[i]
        nxt = self.groups[i + 1].start if i + 1 < len(self.groups) else 1e9
        if t > min(g.end + self.hold, nxt):
            return
        im, base = self._sprite(g.text.upper() if self.spec.get("upper") else g.text)
        y_top = self.top
        for a, bnd, yy in self.shift:
            if a <= g.start < bnd:
                y_top = yy
        cap_top_in_sprite = base - 0.66 * self.font.size  # górna krawędź wersalików w obrazie
        layer.paste(im, self.ctx.W / 2 - im.size[0] / 2, y_top - cap_top_in_sprite)
