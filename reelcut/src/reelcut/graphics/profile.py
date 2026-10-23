"""Elementy z osobą: plakietka profilu (awatar, licznik, pasek, kursor), pigułki z napisem i chipy z wartością."""
from __future__ import annotations

import math
from pathlib import Path

from .core import (SS, Brand, Layer, PlanError, blur, circle_crop, compose, ease_in_out, ease_out, ease_out_back,
                   glow_of, lerp, load_image, prog, rgba_image, rounded_rect, scale_rotate, text_size, text_sprite)
from .elements import Context, Element, register

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------------------------
# Małe rysunki: kursor, korona, zegar, ikony
# ---------------------------------------------------------------------------------------------

def cursor_sprite(size: float, color):
    """Strzałka-kursor skierowana w prawo (kąt 0), wyśrodkowana w obrazie, z zaokrąglonymi rogami."""
    s = size
    pts = [(1.0, 0.0), (-0.72, -0.78), (-0.28, 0.0), (-0.72, 0.78)]
    big = int(s * 2.4)
    im = Image.new("RGBA", (big * SS, big * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = big * SS / 2
    P = [(c + x * s * SS * 0.95, c + y * s * SS * 0.95) for x, y in pts]
    d.polygon(P, fill=color)
    d.line(P + [P[0]], fill=color, width=int(s * SS * 0.24), joint="curve")
    for x, y in P:  # zaokrąglenie narożników
        r = s * SS * 0.12
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    return im.resize((big, big), Image.LANCZOS)


def crown_sprite(w: float, color):
    h = w * 0.78
    pts = [(0.04, 0.9), (0.0, 0.18), (0.26, 0.5), (0.5, 0.0), (0.74, 0.5), (1.0, 0.18), (0.96, 0.9)]
    big = Image.new("RGBA", (int(w) * SS, int(h) * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    P = [(x * w * SS, y * h * SS) for x, y in pts]
    d.polygon(P, fill=color)
    d.line(P + [P[0]], fill=color, width=int(w * SS * 0.07), joint="curve")
    d.rounded_rectangle([w * SS * 0.04, h * SS * 0.8, w * SS * 0.96, h * SS * 0.99], radius=h * SS * 0.06, fill=color)
    return big.resize((int(w), int(h)), Image.LANCZOS)


def clock_sprite(d: float, brand: Brand, angle: float):
    """Zegar: biała tarcza, obwódka w kolorze akcentu, dwie wskazówki (minutowa obraca się z czasem)."""
    d = int(d)
    big = Image.new("RGBA", (d * SS, d * SS), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    c = d * SS / 2
    ring = brand.rgb("accent")
    g.ellipse([0, 0, d * SS - 1, d * SS - 1], fill=ring + (255,))
    inset = d * SS * 0.1
    g.ellipse([inset, inset, d * SS - inset, d * SS - inset], fill=(255, 255, 255, 255))
    ink = brand.rgb("panel") + (255,)
    for k in range(12):  # kreski godzin
        a = math.radians(k * 30)
        r1, r2 = c * (0.70 if k % 3 else 0.62), c * 0.80
        g.line([(c + math.sin(a) * r1, c - math.cos(a) * r1), (c + math.sin(a) * r2, c - math.cos(a) * r2)], fill=(150, 150, 160, 255), width=max(1, int(d * SS * 0.02)))
    for ang, ln, wd in ((math.radians(300), 0.42, 0.075), (math.radians(angle), 0.62, 0.05)):
        g.line([(c, c), (c + math.sin(ang) * c * ln, c - math.cos(ang) * c * ln)], fill=ink, width=int(d * SS * wd))
    g.ellipse([c - d * SS * 0.05, c - d * SS * 0.05, c + d * SS * 0.05, c + d * SS * 0.05], fill=ink)
    return big.resize((d, d), Image.LANCZOS)


def trend_icon(h: float, color):
    """Strzałka trendu rosnącego."""
    w = int(h * 1.2)
    big = Image.new("RGBA", (w * SS, int(h) * SS), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    P = [(0.04 * w * SS, 0.84 * h * SS), (0.36 * w * SS, 0.50 * h * SS), (0.56 * w * SS, 0.68 * h * SS), (0.94 * w * SS, 0.16 * h * SS)]
    g.line(P, fill=color, width=int(h * SS * 0.13), joint="curve")
    ah = h * SS * 0.30
    g.line([(0.94 * w * SS - ah, 0.14 * h * SS), (0.94 * w * SS, 0.16 * h * SS), (0.94 * w * SS - 0.02 * ah, 0.16 * h * SS + ah)],
           fill=color, width=int(h * SS * 0.13), joint="curve")
    return big.resize((w, int(h)), Image.LANCZOS)


def placeholder_avatar(d: int, brand: Brand):
    """Awatar zastępczy (gdy nie ma Twojej twarzy): sylwetka w kolorach marki."""
    big = Image.new("RGBA", (d * SS, d * SS), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    g.ellipse([0, 0, d * SS - 1, d * SS - 1], fill=brand.rgb("panel") + (255,))
    v = brand.rgb("accent")
    cx, cy = d * SS / 2, d * SS / 2
    g.ellipse([cx - d * SS * 0.17, cy - d * SS * 0.30, cx + d * SS * 0.17, cy + d * SS * 0.04], fill=v + (255,))
    g.ellipse([cx - d * SS * 0.34, cy + d * SS * 0.12, cx + d * SS * 0.34, cy + d * SS * 0.78], fill=v + (255,))
    mask = Image.new("L", big.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d * SS - 1, d * SS - 1], fill=255)
    big.putalpha(Image.composite(big.getchannel("A"), Image.new("L", big.size, 0), mask))
    return big.resize((d, d), Image.LANCZOS)


def avatar_image(ctx: Context, ref, d: int):
    """Awatar jako kółko o średnicy d: auto = Twoja twarz z nagrania, ścieżka = plik, brak = sylwetka."""
    if ref in (None, "auto"):
        if ctx.avatar and Path(ctx.avatar).exists():
            return circle_crop(load_image(str(ctx.avatar)), d)
        return placeholder_avatar(d, ctx.brand)
    return circle_crop(load_image(str(ctx.resolve(str(ref)))), d)


# ---------------------------------------------------------------------------------------------
# Ścieżka ruchu plakietki
# ---------------------------------------------------------------------------------------------

class Path2D:
    """Punkty (czas względny, x, y) w ułamkach kadru; między nimi płynny ruch. Kierunek ruchu daje kierunek kursora."""

    def __init__(self, pts: list[tuple[float, float, float]]):
        self.pts = sorted(pts)

    def pos(self, lt: float) -> tuple[float, float]:
        p = self.pts
        if lt <= p[0][0]:
            return p[0][1], p[0][2]
        for a, b in zip(p[:-1], p[1:]):
            if lt <= b[0]:
                k = ease_in_out(prog(lt, a[0], b[0] - a[0]))
                return lerp(a[1], b[1], k), lerp(a[2], b[2], k)
        return p[-1][1], p[-1][2]

    def moving(self, lt: float) -> bool:
        """Czy w chwili lt plakietka jest w ruchu (między punktami o różnych położeniach)."""
        for a, b in zip(self.pts[:-1], self.pts[1:]):
            if a[0] <= lt <= b[0] and abs(b[1] - a[1]) + abs(b[2] - a[2]) > 1e-4:
                return True
        return False

    def heading(self, lt: float, default: float = -40.0) -> float:
        """Kierunek ruchu w stopniach (0 = w prawo, 90 = w dół); po zatrzymaniu zostaje ostatni kierunek."""
        last = default
        angles = []
        for a, b in zip(self.pts[:-1], self.pts[1:]):
            dx, dy = b[1] - a[1], b[2] - a[2]
            if abs(dx) + abs(dy) > 1e-4:
                angles.append((a[0], math.degrees(math.atan2(dy * 1.78, dx))))
        for t0, ang in angles:
            if lt >= t0:
                if abs(((ang - last + 180) % 360) - 180) > 1:
                    k = ease_in_out(prog(lt, t0, 0.35))
                    last = last + (((ang - last + 180) % 360) - 180) * k
                else:
                    last = ang
        return last


# ---------------------------------------------------------------------------------------------
# Plakietka profilu
# ---------------------------------------------------------------------------------------------

@register("profile")
class Profile(Element):
    """Awatar w kółku (Twoja twarz) z kursorem, licznikiem, paskiem postępu i opcjonalnym zegarem albo koroną.
    Pola: avatar (auto|plik), mode full|mini, label, unit, count [od, do], bar [od, do], tag, badge: clock,
    crown (true/false), cursor (true/false), size, path [[czas, x, y], ...] (ułamki kadru, środek awatara)."""
    default_dur = 6.0
    default_zone = "left"
    d_in = 0.45
    d_out = 0.35

    def build(self) -> None:
        s, b = self.spec, self.brand
        W = self.ctx.W
        self.mini = s.get("mode", "full") == "mini"
        d = int(float(s.get("size", 0.052 if self.mini else 0.105)) * W)
        self.d = d
        self.ring_w = max(3, int(d * (0.045 if self.mini else 0.07)))
        face = avatar_image(self.ctx, s.get("avatar", "auto"), d - 2 * self.ring_w)
        D = d
        ring = Image.new("RGBA", (D * SS, D * SS), (0, 0, 0, 0))
        g = ImageDraw.Draw(ring)
        g.ellipse([0, 0, D * SS - 1, D * SS - 1], fill=b.rgb("panel") + (255,), outline=b.rgb("accent") + (255,), width=self.ring_w * SS)
        self.base = ring.resize((D, D), Image.LANCZOS)
        self.base.alpha_composite(face, dest=(self.ring_w, self.ring_w))
        self.cursor_on = bool(s.get("cursor", True))
        self.cur = cursor_sprite(d * 0.26, b.rgba("highlight")) if self.cursor_on else None
        self.cur_glow = glow_of(self.cur, b.rgb("highlight"), d * 0.1, 0.8) if self.cur else None
        self.label_font = b.font("semibold", d * (0.2 if self.mini else 0.215))
        self.tag_font = b.font("display", d * 0.19)
        raw = s.get("path")
        self.path = None
        if raw:
            try:
                self.path = Path2D([(float(t), float(x), float(y)) for t, x, y in raw])
            except (TypeError, ValueError) as exc:
                raise PlanError("Plakietka: path to lista [czas, x, y].") from exc
        self.count = s.get("count")
        self.bar = s.get("bar")
        self.crown = crown_sprite(d * 0.42, b.rgba("highlight")) if s.get("crown") else None

    def _center(self, lt: float, w: float, h: float) -> tuple[float, float]:
        W, H = self.ctx.W, self.ctx.H
        if self.path:
            x, y = self.path.pos(lt)
            return x * W, y * H
        x, y = self.place(w, h)
        return x + w / 2, y + h / 2

    def draw(self, layer: Layer, t: float) -> None:
        s, b = self.spec, self.brand
        lf = self.life(t)
        lt = lf.lt
        d = self.d
        mini = self.mini
        # --- część statyczna + dynamiczna w jednym obrazie ---
        parts = [(self.base, 0, 0)]
        extra_h = 0
        if s.get("badge") == "clock" and not mini:
            cd = d * 0.44
            parts.append((clock_sprite(cd, b, (lt * 36) % 360), d * 0.64, -d * 0.12))
        y_below = d + d * 0.06
        label = s.get("label")
        if self.count and not mini:
            a, z = float(self.count[0]), float(self.count[1])
            k = ease_out(prog(lt, float(s.get("count_at", 0.5)), float(s.get("count_dur", 1.4))))
            label = f"{int(round(lerp(a, z, k)))} {s.get('unit', '')}".strip()
        if label:
            im, _ = text_sprite(str(label), self.label_font, b.rgba("text"), tracking=-0.3, pad=2)
            parts.append((im, (d - im.size[0]) / 2, y_below))
            y_below += im.size[1] + d * 0.02
        if self.bar and not mini:
            bw = d * 1.65
            bh = max(5, d * 0.075)
            k = ease_out(prog(lt, float(s.get("count_at", 0.5)), float(s.get("count_dur", 1.4))))
            frac = lerp(float(self.bar[0]), float(self.bar[1]), k)
            track = rounded_rect(bw, bh, bh / 2, fill=(255, 255, 255, 56))
            fill = rounded_rect(max(bh, bw * frac), bh, bh / 2, fill=b.rgba("accent"))
            track.alpha_composite(fill)
            tag = s.get("tag")
            x_bar = d / 2 - bw / 2
            if tag:
                tim, _ = text_sprite(str(tag), self.tag_font, b.rgba("accent"), pad=1)
                parts.append((tim, x_bar - tim.size[0] - 4, y_below - bh * 0.9))
                x_bar += 0
            parts.append((track, x_bar, y_below))
        if self.crown is not None:
            kc = ease_out_back(prog(lt, float(s.get("crown_at", 0.6)), 0.45), 2.0)
            cr = scale_rotate(self.crown, max(0.01, kc))
            parts.append((cr, d / 2 - cr.size[0] / 2, -cr.size[1] * 0.78))
        spr, (ox, oy) = compose(parts, pad=4)
        # --- ruch i kursor ---
        w0, h0 = d, d
        cx, cy = self._center(lt, w0, h0)
        cx += 0
        cy += 3.5 * math.sin(2 * math.pi * lt / 3.2)  # delikatne unoszenie
        im, dy, alpha = self.appear(spr, lf, rise=26, blur_px=8, overshoot=True, scale_from=0.85)
        # środek awatara w obrazie: (d/2 - ox, d/2 - oy)
        ax, ay = d / 2 - ox, d / 2 - oy
        layer.paste(im, cx - ax * (im.size[0] / spr.size[0]), cy + dy - ay * (im.size[1] / spr.size[1]), alpha)
        if self.cur is not None:
            # w ruchu strzałka leci przed awatarem i wskazuje kierunek ruchu; w spoczynku stoi z prawej i celuje w górę
            ang = self.path.heading(lt) if self.path else -40.0
            pos_ang = ang if self.path and self.path.moving(lt) else 14.0
            r = d * (0.70 if not mini else 0.84)
            px = cx + math.cos(math.radians(pos_ang)) * r
            py = cy + dy + math.sin(math.radians(pos_ang)) * r
            cur = scale_rotate(self.cur, 1.0, -ang)
            if self.cur_glow:
                g, pad = self.cur_glow
                gg = scale_rotate(g, 1.0, -ang)
                layer.paste_center(gg, px, py, alpha * 0.8)
            layer.paste_center(cur, px, py, alpha)


# ---------------------------------------------------------------------------------------------
# Pigułki z napisem
# ---------------------------------------------------------------------------------------------

@register("pills")
class Pills(Element):
    """Zaokrąglone etykiety („pigułki”) rozrzucone w kadrze. items: [{text, tag, style: white|glass|accent|yellow,
    icon: trend, x, y}]. Bez x, y układamy je na przemian po lewej i po prawej w strefie."""
    default_dur = 4.0
    default_zone = "bottom"
    d_in = 0.4
    d_out = 0.3

    def build(self) -> None:
        s, b = self.spec, self.brand
        items = s.get("items")
        if not items:
            raise PlanError("Pigułki (pills) wymagają listy items.")
        W, H = self.ctx.W, self.ctx.H
        self.items = [dict(i) if isinstance(i, dict) else {"text": str(i)} for i in items]
        fs = float(s.get("size", 0.03)) * W
        self.sprites = []
        for i, it in enumerate(self.items):
            self.sprites.append(self._pill(it, fs, i))
        x0, y0, x1, y1 = self.zone()
        n = len(self.items)
        self.pos = []
        for i, it in enumerate(self.items):
            if "x" in it and "y" in it:
                self.pos.append((float(it["x"]) * W, float(it["y"]) * H))
            else:
                w, h = self.sprites[i].size
                left = i % 2 == 0
                cx = x0 + w / 2 + 0.02 * W if left else x1 - w / 2 - 0.02 * W
                cy = y0 + (y1 - y0) * (0.2 + 0.6 * (i / max(1, n - 1)))
                self.pos.append((cx, cy))
        self.stagger = float(s.get("stagger", 0.16))

    def _pill(self, it: dict, fs: float, i: int):
        b = self.brand
        style = it.get("style", "white" if i % 2 == 0 else "glass")
        font = b.font("bold", fs)
        text = str(it.get("text", ""))
        tim, _ = text_sprite(text, font, (0, 0, 0, 0), pad=0)
        asc, desc = font.getmetrics()
        h = int(fs * 1.9)
        pad = int(h * 0.42)
        icon = trend_icon(fs * 1.0, b.rgba("accent")) if it.get("icon") == "trend" else None
        tag = it.get("tag")
        tag_im = None
        if tag:
            tf = b.font("display", fs * 0.62)
            ts, _ = text_sprite(str(tag).upper(), tf, b.rgba("text"), tracking=0.3, pad=0)
            th = int(fs * 1.12)
            tag_im = rounded_rect(ts.size[0] + th * 0.9, th, th / 2, fill=b.rgba("accent"))
            tag_im.alpha_composite(ts, dest=(int(th * 0.45), int((th - ts.size[1]) / 2)))
        w = pad * 2 + text_size(text, font)[0] + (icon.size[0] + pad * 0.45 if icon else 0) + (tag_im.size[0] + pad * 0.5 if tag_im else 0)
        if style == "white":
            fill, tcol = (255, 255, 255, 245), b.rgb("panel") + (255,)
        elif style == "yellow":
            fill, tcol = b.rgba("highlight"), b.rgb("panel") + (255,)
        elif style == "accent":
            fill, tcol = b.rgba("accent"), b.rgba("text")
        else:  # glass
            fill, tcol = b.rgb("accent") + (110,), b.rgba("text")
        body = rounded_rect(w, h, h / 2, fill=fill, outline=(255, 255, 255, 70), outline_w=1.5)
        x = pad
        if icon:
            body.alpha_composite(icon, dest=(int(x), int((h - icon.size[1]) / 2)))
            x += icon.size[0] + pad * 0.45
        txt, _ = text_sprite(text, font, tcol, pad=0)
        body.alpha_composite(txt, dest=(int(x), int((h - txt.size[1]) / 2)))
        x += txt.size[0] + pad * 0.5
        if tag_im:
            body.alpha_composite(tag_im, dest=(int(x), int((h - tag_im.size[1]) / 2)))
        sh, p = glow_of(body, (0, 0, 0), h * 0.22, 0.6)
        out, _ = compose([(sh, -p, -p + h * 0.12), (body, 0, 0)], pad=2)
        return out

    def draw(self, layer: Layer, t: float) -> None:
        lf = self.life(t)
        for i, spr in enumerate(self.sprites):
            k = prog(lf.lt, i * self.stagger, 0.45)
            if k <= 0:
                continue
            sc = lerp(0.8, 1.0, ease_out_back(k, 1.6))
            im = scale_rotate(spr, sc)
            bl = (1 - k) * 9 + (1 - lf.k_out) * 6
            if bl > 0.5:
                pad = int(bl * 2.5)
                tmp = rgba_image(im.size[0] + 2 * pad, im.size[1] + 2 * pad)
                tmp.alpha_composite(im, dest=(pad, pad))
                im = blur(tmp, bl)
            cx, cy = self.pos[i]
            dy = (1 - ease_out(k)) * 36 + 3 * math.sin(2 * math.pi * lf.lt / 3.0 + i)
            layer.paste_center(im, cx, cy + dy, ease_out(k) * lf.k_out)


# ---------------------------------------------------------------------------------------------
# Chipy z wartością (np. klienci z kwotą)
# ---------------------------------------------------------------------------------------------

@register("chips")
class Chips(Element):
    """Rząd chipów: awatar, podpis i wartość z odliczaniem. items: [{label, value, prefix, suffix, avatar}]."""
    default_dur = 4.0
    default_zone = "bottom"

    def build(self) -> None:
        s, b = self.spec, self.brand
        items = s.get("items")
        if not items:
            raise PlanError("Chipy (chips) wymagają listy items.")
        self.items = [dict(i) for i in items]
        W = self.ctx.W
        n = len(self.items)
        cw = float(s.get("chip_w", 0.42)) * W
        zw = self.zone_width()
        if zw and n > 1:  # kilka kafelków w rzędzie: zwężamy je, żeby zmieściły się w strefie
            cw = min(cw, (zw - (n - 1) * 0.02 * W) / n)
        self.cw = int(cw)
        self.ch = int(self.cw * 0.28)
        self.f_label = b.font("semibold", self.ch * 0.2)
        self.f_value = b.font("display", self.ch * 0.34)
        self.avatars = [avatar_image(self.ctx, it.get("avatar", "auto"), int(self.ch * 0.62)) for it in self.items]
        self.stagger = float(s.get("stagger", 0.2))

    def draw(self, layer: Layer, t: float) -> None:
        s, b = self.spec, self.brand
        lf = self.life(t)
        W = self.ctx.W
        x0, y0, x1, y1 = self.zone()
        n = len(self.items)
        gap = 0.02 * W
        total = n * self.cw + (n - 1) * gap
        for i, it in enumerate(self.items):
            k = prog(lf.lt, i * self.stagger, 0.5)
            if k <= 0:
                continue
            body = rounded_rect(self.cw, self.ch, self.ch * 0.3, fill=b.rgb("panel") + (225,), outline=b.rgb("accent") + (150,), outline_w=2)
            ah = self.avatars[i]
            body.alpha_composite(ah, dest=(int(self.ch * 0.18), int((self.ch - ah.size[1]) / 2)))
            tx = self.ch * 0.18 + ah.size[1] + self.ch * 0.16
            lab, _ = text_sprite(str(it.get("label", "")), self.f_label, b.rgba("text_dim", 0.85), pad=0)
            val = float(it.get("value", 0))
            kv = ease_out(prog(lf.lt, i * self.stagger + 0.3, 1.2))
            txt = f"{it.get('prefix', '')}{int(round(val * kv)):,}{it.get('suffix', '')}".replace(",", " ")
            vim, _ = text_sprite(txt, self.f_value, b.rgba("highlight"), pad=0)
            gap_t = self.ch * 0.06
            th = lab.size[1] + gap_t + vim.size[1]
            body.alpha_composite(lab, dest=(int(tx), int((self.ch - th) / 2)))
            body.alpha_composite(vim, dest=(int(tx), int((self.ch - th) / 2 + lab.size[1] + gap_t)))
            sh, p = glow_of(body, (0, 0, 0), 12, 0.6)
            spr, _ = compose([(sh, -p, -p + 8), (body, 0, 0)], pad=2)
            cx = (x0 + x1) / 2 - total / 2 + i * (self.cw + gap) + self.cw / 2
            cy = (y0 + y1) / 2 + self.spec.get("dy", 0) * self.ctx.H
            dy = (1 - ease_out(k)) * 80
            layer.paste_center(spr, cx, cy + dy, ease_out(k) * lf.k_out)
