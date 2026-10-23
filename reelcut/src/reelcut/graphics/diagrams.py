"""Diagramy: lista kroków z poświatą (steps), wykres schodkowy (axis) i paski struktury (bars)."""
from __future__ import annotations

import math

from .core import (SS, Layer, PlanError, blur, clamp01, compose, disc, ease_in_out, ease_out, ease_out_back, fit_font,
                   glow_of, lerp, prog, rgba_image, rounded_rect, scale_rotate, text_size, text_sprite)
from .elements import Element, register

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    pass


def _line(w: float, h: float, color, width: float, dashed: bool = False):
    """Pozioma linia z zaokrąglonymi końcami (obraz w x h)."""
    return rounded_rect(max(w, width), max(h, width), width / 2, fill=color)


# ---------------------------------------------------------------------------------------------
# Lista kroków (szklany panel z osią czasu i poświatą aktywnej pozycji)
# ---------------------------------------------------------------------------------------------

@register("steps")
class Steps(Element):
    """Panel z kolejnymi krokami: numer w kółku, podpis „KROK 03”, tytuł i opis. Aktywny krok ma poświatę i jest
    pośrodku, lista przewija się razem z mową. Pola: items [{title, sub}], active [czasy względne zmiany kroku]
    (domyślnie równo rozłożone), width, title_size."""
    default_dur = 6.0
    default_zone = "bottom"
    d_in = 0.5
    d_out = 0.4

    def build(self) -> None:
        s, b = self.spec, self.brand
        items = s.get("items")
        if not items:
            raise PlanError("Lista kroków (steps) wymaga items.")
        self.items = [dict(i) if isinstance(i, dict) else {"title": str(i)} for i in items]
        n = len(self.items)
        W = self.ctx.W
        self.pw = int(float(s.get("width", 0.62)) * W)
        self.row_h = int(self.pw * 0.215)
        self.rows_vis = 3
        self.ph = int(self.row_h * self.rows_vis + self.row_h * 0.25)
        self.f_title = b.font("semibold", self.pw * 0.066)
        self.f_sub = b.font("text", self.pw * 0.046)
        self.f_step = b.font("bold", self.pw * 0.033)
        self.f_num = b.font("bold", self.pw * 0.038)
        act = s.get("active")
        if act:
            self.active_at = [float(a) for a in act]
        else:
            first, last = 0.9, max(1.0, self.dur - 1.0)
            self.active_at = [lerp(first, last, i / max(1, n - 1)) for i in range(n)]
        if len(self.active_at) != n:
            raise PlanError(f"Lista kroków: active ma {len(self.active_at)} czasów, a kroków jest {n}.")
        self.rows = [self._row(i, it) for i, it in enumerate(self.items)]

    def _row(self, i: int, it: dict):
        b = self.brand
        pw, rh = self.pw, self.row_h
        parts = []
        left = rh * 0.62
        avail = pw - left - pw * 0.05
        step = text_sprite(f"KROK {i + 1:02d}", self.f_step, b.rgba("text_dim", 0.55), tracking=1.2, pad=1)[0]
        tf = fit_font(b, "semibold", str(it.get("title", "")), self.f_title.size, avail)
        title = text_sprite(str(it.get("title", "")), tf, b.rgba("text"), pad=1)[0]
        parts.append((step, left, rh * 0.12))
        parts.append((title, left, rh * 0.12 + step.size[1] + 2))
        if it.get("sub"):
            sf = fit_font(b, "text", str(it["sub"]), self.f_sub.size, avail)
            sub = text_sprite(str(it["sub"]), sf, b.rgba("text_dim", 0.6), pad=1)[0]
            parts.append((sub, left, rh * 0.12 + step.size[1] + title.size[1] + 4))
        parts.append((rgba_image(pw, rh), 0, 0))
        im, _ = compose(parts)
        return im

    def _marker(self, i: int, active: float):
        b = self.brand
        d = int(self.row_h * 0.3)
        ring = b.rgb("highlight") if active > 0.5 else b.rgb("accent")
        base = disc(d, fill=(255, 255, 255, 255), outline=ring + (255,), outline_w=d * 0.1)
        num, _ = text_sprite(f"{i + 1}", self.f_num, ring + (255,), pad=0)
        base.alpha_composite(num, dest=((d - num.size[0]) // 2, (d - num.size[1]) // 2 - 1))
        return base

    def _scroll(self, lt: float) -> float:
        """Przesunięcie listy (w wierszach): aktywny krok ma być w środkowym wierszu."""
        a = self.active_at
        pos = 0.0
        for i, t0 in enumerate(a):
            pos = lerp(pos, float(i), ease_in_out(prog(lt, t0 - 0.35, 0.55))) if i > 0 else 0.0
        return pos

    def draw(self, layer: Layer, t: float) -> None:
        s, b = self.spec, self.brand
        lf = self.life(t)
        pw, ph, rh = self.pw, self.ph, self.row_h
        panel = rounded_rect(pw, ph, pw * 0.05, fill=b.rgb("panel") + (232,), outline=b.rgb("accent") + (120,), outline_w=2)
        scroll = self._scroll(lf.lt)
        active_idx = max(i for i, t0 in enumerate(self.active_at) if lf.lt >= t0 - 0.2) if lf.lt >= self.active_at[0] - 0.2 else 0
        content = rgba_image(pw, ph)
        # poświata aktywnej pozycji (żółta, rozmyta)
        center_y = rh * 1.15
        row_y0 = lambda i: center_y - rh / 2 + (i - scroll) * rh  # noqa: E731
        gl = rgba_image(pw, ph)
        gx = int(pw * 0.34)
        glow_rect = rounded_rect(pw * 0.62, rh * 0.82, rh * 0.3, fill=b.rgb("highlight") + (255,))
        gl.alpha_composite(glow_rect, dest=(gx, int(center_y - rh * 0.41)))
        gl = blur(gl, rh * 0.35)
        k_pulse = 0.2 + 0.05 * math.sin(2 * math.pi * lf.lt / 1.8)
        content.alpha_composite(self._tint(gl, k_pulse))
        # oś czasu
        x_axis = int(rh * 0.3)
        first_y, last_y = row_y0(0) + rh * 0.27, row_y0(len(self.rows) - 1) + rh * 0.27
        line = rounded_rect(max(3, rh * 0.03), max(4, last_y - first_y), 2, fill=b.rgba("accent", 0.8))
        content.alpha_composite(line, dest=(int(x_axis - line.size[0] / 2), max(0, int(first_y))))
        for i, row in enumerate(self.rows):
            y = row_y0(i)
            dist = abs(i - scroll - 0.98)
            a = clamp01(1.15 - dist * 0.55)
            if y + rh < 0 or y > ph:
                continue
            r = row.copy()
            r.putalpha(r.getchannel("A").point([int(v * (0.35 + 0.65 * a)) for v in range(256)]))
            if y >= 0:
                content.alpha_composite(r, dest=(0, int(y)))
            else:  # wiersz wysunięty ponad panel: pokazujemy tylko jego dolną część
                content.alpha_composite(r, dest=(0, 0), source=(0, int(-y), r.size[0], r.size[1]))
            mk = self._marker(i, 1.0 if i == active_idx else 0.0)
            my = int(y + rh * 0.12)
            if 0 <= my < ph - mk.size[1]:
                content.alpha_composite(mk, dest=(int(x_axis - mk.size[0] / 2), my))
        # maska panelu: zawartość nie wychodzi poza zaokrąglone rogi
        from PIL import ImageChops
        mask = panel.getchannel("A").point(lambda v: 255 if v > 0 else 0)
        content.putalpha(ImageChops.multiply(content.getchannel("A"), mask))
        panel.alpha_composite(content)
        sh, p = glow_of(panel, (0, 0, 0), 20, 0.7)
        spr, _ = compose([(sh, -p, -p + 12), (panel, 0, 0)], pad=2)
        x, y = self.place(spr.size[0], spr.size[1])
        im, dy, alpha = self.appear(spr, lf, rise=70, blur_px=12, scale_from=0.97)
        layer.paste_center(im, x + spr.size[0] / 2, y + spr.size[1] / 2 + dy, alpha)

    @staticmethod
    def _tint(img, k: float):
        out = img.copy()
        out.putalpha(img.getchannel("A").point([int(v * k) for v in range(256)]))
        return out


# ---------------------------------------------------------------------------------------------
# Wykres schodkowy z podpisami (oś w kształcie litery L)
# ---------------------------------------------------------------------------------------------

@register("axis")
class Axis(Element):
    """Dwie osie (L) i rosnące kroki: biała kropka z dymkiem na każdy punkt, ostatni wyróżniony żółtym.
    Pola: items [podpisy od najniższego], zone (domyślnie top), step (odstęp między punktami, s)."""
    default_dur = 6.0
    default_zone = "top"
    d_in = 0.3
    d_out = 0.4

    def build(self) -> None:
        s, b = self.spec, self.brand
        items = s.get("items")
        if not items or len(items) < 2:
            raise PlanError("Wykres (axis) wymaga co najmniej dwóch pozycji w items.")
        self.items = [str(i.get("text", i) if isinstance(i, dict) else i) for i in items]
        x0, y0, x1, y1 = self.zone()
        self.box = (x0, y0, x1, y1)
        self.font = b.font("bold", self.ctx.W * 0.027)
        self.step = float(s.get("step", max(0.35, (self.dur - 1.6) / len(self.items))))

    def _bubble(self, text: str, hot: bool):
        b = self.brand
        pad = self.font.size * 0.55
        tw, th = text_size(text, self.font)
        h = int(th + pad * 0.9)
        w = int(tw + pad * 2)
        fill = b.rgba("highlight") if hot else (255, 255, 255, 250)
        col = b.rgb("panel") + (255,) if hot else b.rgb("accent_strong") + (255,)
        body = rounded_rect(w, h + 10, h * 0.28, fill=fill)
        tip, (ox, oy) = polygon_tip(w / 2, h, h * 0.36, fill)
        im = rgba_image(w, h + 12)
        im.alpha_composite(body.crop((0, 0, w, h)), dest=(0, 0))
        im.alpha_composite(tip, dest=(int(w / 2 - tip.size[0] / 2), h - 1))
        t, _ = text_sprite(text, self.font, col, pad=0)
        im.alpha_composite(t, dest=((w - t.size[0]) // 2, int((h - t.size[1]) / 2)))
        return im

    def draw(self, layer: Layer, t: float) -> None:
        b = self.brand
        lf = self.life(t)
        x0, y0, x1, y1 = self.box
        w, h = x1 - x0, y1 - y0
        ax_w = max(4, int(self.ctx.W * 0.0042))
        ox, oy = x0 + w * 0.08, y1 - h * 0.04
        kx = ease_out(prog(lf.lt, 0.0, 0.5))
        ky = ease_out(prog(lf.lt, 0.15, 0.5))
        color = b.rgba("accent", 1.0)
        lay = rgba_image(w + 40, h + 40)
        vh = (oy - (y0 + h * 0.02)) * ky
        hw = (x0 + w * 0.97 - ox) * kx
        if vh > 2:
            lay.alpha_composite(rounded_rect(ax_w, vh, ax_w / 2, fill=color), dest=(int(ox - x0 + 20), int(oy - y0 + 20 - vh)))
        if hw > 2:
            lay.alpha_composite(rounded_rect(hw, ax_w, ax_w / 2, fill=color), dest=(int(ox - x0 + 20), int(oy - y0 + 20 - ax_w)))
        n = len(self.items)
        pts = []
        for i in range(n):
            u = i / (n - 1)
            px = ox + (x0 + w * 0.86 - ox) * (0.12 + 0.88 * u)
            py = oy - (oy - (y0 + h * 0.2)) * (0.1 + 0.9 * (u ** 1.15))
            pts.append((px, py))
        # ślad szarych kropek między punktami
        for i in range(n - 1):
            for j in range(1, 4):
                u = j / 4
                gx, gy = lerp(pts[i][0], pts[i + 1][0], u) + w * 0.03, lerp(pts[i][1], pts[i + 1][1], u) + h * 0.035
                kk = ease_out(prog(lf.lt, 0.5 + i * self.step + 0.1 * j, 0.3))
                if kk > 0:
                    r = self.ctx.W * 0.0055
                    lay.alpha_composite(disc(r * 2, fill=(255, 255, 255, int(90 * kk))), dest=(int(gx - x0 + 20 - r), int(gy - y0 + 20 - r)))
        layer.paste(lay, x0 - 20, y0 - 20, lf.alpha if lf.k_in >= 1 else lf.alpha)
        for i, (px, py) in enumerate(pts):
            hot = i == n - 1
            k = prog(lf.lt, 0.6 + i * self.step, 0.45)
            if k <= 0:
                continue
            kk = ease_out_back(k, 1.5)
            r = self.ctx.W * (0.0105 if hot else 0.0085)
            dot = disc(r * 2, fill=(b.rgba("highlight") if hot else (255, 255, 255, 255)))
            fade_a = ease_out(k) * lf.k_out
            if hot:
                ring = disc(r * 3.6, outline=b.rgba("highlight", 0.9), outline_w=2.5)
                layer.paste_center(scale_rotate(ring, max(0.01, kk)), px, py, fade_a)
            layer.paste_center(scale_rotate(dot, max(0.01, kk)), px, py, fade_a)
            bub = self._bubble(self.items[i], hot)
            layer.paste_center(scale_rotate(bub, max(0.01, kk)), px, py - r - bub.size[1] / 2 - 4 + (1 - ease_out(k)) * 20, fade_a)


def polygon_tip(cx: float, y: float, size: float, fill):
    """Mały trójkąt-wskaźnik pod dymkiem (skierowany w dół)."""
    from .core import polygon
    im, off = polygon([(0, 0), (size * 2, 0), (size, size)], fill)
    return im, off


# ---------------------------------------------------------------------------------------------
# Paski struktury (wiersze: podpis + pasek w kolorze, albo kółko „otwartej pętli”)
# ---------------------------------------------------------------------------------------------

@register("bars")
class Bars(Element):
    """Wiersze: podpis po lewej i pasek (podwójny, pojedynczy) albo obracające się kółko (spinner).
    rows: [{label, kind: double|single|spinner, color}] lub same podpisy; kolory z serii marki."""
    default_dur = 5.0
    default_zone = "top"
    d_in = 0.3
    d_out = 0.4

    def build(self) -> None:
        s, b = self.spec, self.brand
        rows = s.get("rows")
        if not rows:
            raise PlanError("Paski (bars) wymagają listy rows.")
        self.rows = [dict(r) if isinstance(r, dict) else {"label": str(r)} for r in rows]
        W = self.ctx.W
        self.font = b.font("semibold", W * 0.034)
        self.bw = int(float(s.get("bar_w", 0.36)) * W)
        self.th = max(5, int(W * 0.0105))
        self.pitch = int(W * 0.055)
        self.label_w = int(max(text_size(str(r.get("label", "")), self.font)[0] for r in self.rows)) + 12
        self.stagger = float(s.get("stagger", 0.13))

    def draw(self, layer: Layer, t: float) -> None:
        b = self.brand
        lf = self.life(t)
        n = len(self.rows)
        gap = int(self.ctx.W * 0.022)
        w = self.label_w + gap + self.bw
        h = self.pitch * n
        x, y = self.place(w, h)
        lay = rgba_image(w + 20, h + 20)
        for i, r in enumerate(self.rows):
            kind = r.get("kind", "double")
            k = ease_out(prog(lf.lt, i * self.stagger, 0.5))
            k_out = clamp01((self.dur - lf.lt - (n - 1 - i) * 0.05) / self.d_out)
            alpha = min(1.0, k * 2) * k_out
            if alpha <= 0.01:
                continue
            col = b.rgb(r["color"]) if r.get("color") else b.series_rgb(i)
            lab, _ = text_sprite(str(r.get("label", "")), self.font, b.rgba("text", alpha), tracking=-0.5, pad=2)
            cy = i * self.pitch + self.pitch / 2
            lay.alpha_composite(lab, dest=(int(self.label_w - lab.size[0]), int(cy - lab.size[1] / 2)))
            bx = self.label_w + gap
            if kind == "spinner":
                d = int(self.pitch * 0.72)
                ring = Image.new("RGBA", (d * SS, d * SS), (0, 0, 0, 0))
                g = ImageDraw.Draw(ring)
                wd = int(d * SS * 0.11)
                g.ellipse([wd / 2, wd / 2, d * SS - wd / 2, d * SS - wd / 2], outline=(255, 255, 255, int(255 * alpha)), width=wd)
                a0 = (lf.lt * 300) % 360
                g.arc([wd / 2, wd / 2, d * SS - wd / 2, d * SS - wd / 2], a0, a0 + 80, fill=b.rgb("highlight") + (int(255 * alpha),), width=wd)
                ring = ring.resize((d, d), Image.LANCZOS)
                lay.alpha_composite(ring, dest=(int(bx + self.bw / 2 - d / 2), int(cy - d / 2)))
                continue
            lines = 2 if kind == "double" else 1
            L = max(self.th, int(self.bw * k))
            for j in range(lines):
                yy = cy - (self.th * (lines * 0.5 + (lines - 1) * 0.25)) + j * self.th * 1.5
                lay.alpha_composite(rounded_rect(L, self.th, self.th / 2, fill=col + (int(255 * alpha),)), dest=(int(bx), int(yy)))
        layer.paste(lay, x - 10, y - 10)
