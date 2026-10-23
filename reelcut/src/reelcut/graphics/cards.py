"""Karty: rząd albo siatka miniatur z etykietami, punktami pod spodem i wyróżnieniem jednej karty (jak we wzorcu)."""
from __future__ import annotations

import math
import re

from .core import (Layer, PlanError, blur, clamp01, compose, cover, disc, ease_in_out, ease_out, ease_out_back,
                   glow_of, lerp, load_image, polygon, prog, rgba_image, rounded_rect, round_corners, scale_rotate,
                   text_sprite, vgradient, wrap_text)
from .elements import Element, register


def _split_marked(text: str) -> list[tuple[str, bool]]:
    """„Dostajesz *wynik* za 60 s” -> [(„Dostajesz ”, False), („wynik”, True), („ za 60 s”, False)]."""
    out: list[tuple[str, bool]] = []
    for i, part in enumerate(re.split(r"\*", text)):
        if part:
            out.append((part, i % 2 == 1))
    return out


@register("cards")
class Cards(Element):
    """Karty (miniatury 9:16) z etykietami nad spodem. Pola:
    items: [{label, image, kind: image|play|blank, bullets: [tekst z *wyróżnieniem*]}], layout: row|grid, cols,
    label_style: bold (domyślnie) albo serif (kursywa szeryfowa), stagger (opóźnienie między kartami),
    focus (numer karty od 0) i focus_at (sekundy od startu), float."""
    default_dur = 4.0
    default_zone = "top"
    d_in = 0.5
    d_out = 0.35

    def build(self) -> None:
        s, b = self.spec, self.brand
        items = s.get("items")
        if not items or not isinstance(items, list):
            raise PlanError("Karty (cards) wymagają listy items.")
        self.items = [dict(i) if isinstance(i, dict) else {"label": str(i)} for i in items]
        n = len(self.items)
        W = self.ctx.W
        x0, y0, x1, y1 = self.zone()
        layout = s.get("layout", "row")
        cols = n if layout == "row" else int(s.get("cols", min(3, n)))
        rows = math.ceil(n / cols)
        gap = float(s.get("gap", 0.028)) * W
        label_size = float(s.get("label_size", 0.03)) * W
        style = s.get("label_style", "bold")
        if style not in ("bold", "serif"):
            raise PlanError("Karty: label_style to bold albo serif.")
        self.serif_labels = style == "serif"
        self.label_font = b.font("serif_italic", label_size * 1.55) if self.serif_labels else b.font("display", label_size)
        asc, desc = self.label_font.getmetrics()
        label_h = (asc + desc) * 2 * 0.88 + 6  # miejsce na dwa wiersze etykiety
        has_bullets = any(i.get("bullets") for i in self.items)
        bullets_h = float(s.get("bullets_h", 0.16)) * self.ctx.H if has_bullets else 0.0
        zw, zh = x1 - x0, y1 - y0
        cw = min(float(s.get("card_w", 0.21)) * W, (zw - (cols - 1) * gap) / cols)
        ch = cw * 16 / 9
        max_ch = (zh - rows * (label_h + bullets_h) - (rows - 1) * gap * 0.6) / rows
        if ch > max_ch:
            ch = max(60.0, max_ch)
            cw = ch * 9 / 16
        self.cw, self.ch = int(cw), int(ch)
        self.cw_wanted = float(s.get("card_w", 0.21)) * W
        if self.cw < 0.6 * self.cw_wanted:
            self.notes.append(f"karty zmieściły się tylko w szerokości {self.cw} px (chciane {self.cw_wanted:.0f} px), więc tekst jest drobny: "
                              "dodaj zone: full (i rozmycie obrazu), skróć punkty albo pokaż mniej kart naraz.")
        self.gap = gap
        self.label_h, self.bullets_h = label_h, bullets_h
        row_h = ch + label_h + bullets_h + gap * 0.6
        total_h = rows * row_h - gap * 0.6
        top = y0 + (zh - total_h) / 2 if s.get("valign", "top") != "top" else y0
        self.cells: list[tuple[float, float]] = []  # środek karty (x, y)
        for i in range(n):
            r, c = divmod(i, cols)
            in_row = min(cols, n - r * cols)
            row_w = in_row * cw + (in_row - 1) * gap
            rx = x0 + (zw - row_w) / 2 + c * (cw + gap)
            ry = top + r * row_h + label_h
            self.cells.append((rx + cw / 2, ry + ch / 2))
        self.zone_center = ((x0 + x1) / 2, y0 + label_h + ch / 2)
        self.stagger = float(s.get("stagger", 0.12))
        self.sprites = [self._make_card(i, it) for i, it in enumerate(self.items)]
        self.focus = s.get("focus")
        if self.focus is not None and not (0 <= int(self.focus) < n):
            raise PlanError(f"Karty: focus={self.focus} poza zakresem 0..{n - 1}.")
        self.focus_at = float(s.get("focus_at", self.dur * 0.45))
        self.focus_dur = float(s.get("focus_dur", 0.55))
        self.focus_scale = float(s.get("focus_scale", 1.3))

    # --- obrazy ---
    def _card_image(self, it: dict):
        b = self.brand
        cw, ch = self.cw, self.ch
        kind = it.get("kind") or ("image" if it.get("image") else "play")
        if kind not in ("image", "play", "blank"):
            raise PlanError(f"Karta: nieznany typ „{kind}”. Dostępne: image, play, blank.")
        radius = max(6, cw * 0.05)
        if kind == "image":
            if not it.get("image"):
                raise PlanError("Karta typu image wymaga pola image.")
            body = round_corners(cover(load_image(str(self.ctx.resolve(str(it["image"])))), cw, ch), radius)
        elif kind == "blank":  # pusta karta: ciemne szkło z kreskami zamiast treści
            body = round_corners(vgradient(cw, ch, b.rgb("panel") + (170,), b.rgb("accent_strong") + (150,)), radius)
            for wf, yf in ((0.62, 0.62), (0.78, 0.69), (0.5, 0.76)):
                bh = max(4, ch * 0.016)
                body.alpha_composite(rounded_rect(cw * wf, bh, bh / 2, fill=(255, 255, 255, 64)), dest=(int(cw * 0.12), int(ch * yf)))
        else:  # play: miniatura wideo w barwach marki z przyciskiem odtwarzania
            body = round_corners(vgradient(cw, ch, b.rgb("accent_strong") + (245,), b.rgb("panel") + (250,)), radius)
            d = int(cw * 0.46)
            body.alpha_composite(disc(d, fill=(255, 255, 255, 46), outline=(255, 255, 255, 120), outline_w=2),
                                 dest=(int((cw - d) / 2), int(ch / 2 - d / 2)))
            s = cw * 0.17
            tri, (ox, oy) = polygon([(0, 0), (0, s * 1.15), (s, s * 0.575)], b.rgba("text"))
            body.alpha_composite(tri, dest=(int(cw / 2 - s * 0.42 + ox), int(ch / 2 - s * 0.575 + oy)))
        border = rounded_rect(cw, ch, radius, outline=(255, 255, 255, 46), outline_w=2)
        body.alpha_composite(border)
        return body

    def _make_card(self, i: int, it: dict):
        """Etykieta, karta i punkty pod spodem w jednym obrazie; (obraz, y środka karty w obrazie)."""
        b = self.brand
        cw, ch = self.cw, self.ch
        parts = []
        card = self._card_image(it)
        sh, pad = glow_of(card, (0, 0, 0), 14, 0.8)
        parts.append((sh, -pad, -pad + 10))
        parts.append((card, 0, 0))
        label = str(it.get("label", "")).strip()
        if label:
            lcol = b.rgb("label")
            lines = wrap_text(label, self.label_font, cw + self.gap * 0.9, tracking=-0.4)
            asc, desc = self.label_font.getmetrics()
            lh = (asc + desc) * 0.88
            for k, ln in enumerate(lines[-2:] if len(lines) > 2 else lines):
                im, _ = text_sprite(ln, self.label_font, lcol + (255,), tracking=0.0 if self.serif_labels else -0.4, pad=3)
                yy = -(len(lines[-2:]) - k) * lh - 4
                parts.append((im, (cw - im.size[0]) / 2, yy))
        bl = it.get("bullets")
        if bl:
            parts.extend(self._bullets(bl))
        im, (ox, oy) = compose(parts, pad=2)
        return im, -oy, -ox  # (obraz, y górnej krawędzi karty w obrazie, x lewej krawędzi karty w obrazie)

    def _bullets(self, bullets):
        b = self.brand
        fs = float(self.spec.get("bullet_size", 0.026)) * self.ctx.W * min(1.0, self.cw / self.cw_wanted)  # tekst maleje razem z kartą
        font = b.font("semibold", fs)
        asc, desc = font.getmetrics()
        lh = (asc + desc) * 1.02
        width = self.cw + self.gap * 0.6
        parts = []
        y = self.ch + 18.0
        dot_d = fs * 0.36
        for text in bullets:
            segs = _split_marked(str(text))
            plain = "".join(t for t, _ in segs)
            lines = wrap_text(plain, font, width - dot_d * 2.4)
            # przypisanie wyróżnień do wierszy po znakach
            marks = []
            for t_, hi in segs:
                marks += [hi] * len(t_)
            pos = 0
            for li, ln in enumerate(lines):
                # wiersz po łamaniu zjada spacje na styku: dopasuj przesunięcie
                while pos < len(plain) and plain[pos] == " ":
                    pos += 1
                row = rgba_image(width + 20, lh + 6)
                x = float(dot_d * 2.4)
                run, run_hi = "", None
                chunks = []
                for ch_i, chr_ in enumerate(ln):
                    hi = marks[pos + ch_i] if pos + ch_i < len(marks) else False
                    if run_hi is None or hi == run_hi:
                        run += chr_
                        run_hi = hi
                    else:
                        chunks.append((run, run_hi))
                        run, run_hi = chr_, hi
                if run:
                    chunks.append((run, run_hi))
                for t_, hi in chunks:
                    col = b.rgba("highlight") if hi else b.rgba("text")
                    im, _ = text_sprite(t_, font, col, pad=0)
                    row.alpha_composite(im, dest=(int(x), 2))
                    x += font.getlength(t_)
                if li == 0:
                    dot = disc(dot_d, fill=b.rgba("accent"))
                    row.alpha_composite(dot, dest=(int(dot_d * 0.5), int(asc * 0.55 - dot_d / 2) + 2))
                parts.append((row, (self.cw - width) / 2 - 10, y))
                y += lh
                pos += len(ln)
            y += lh * 0.25
        return parts

    # --- czas ---
    def draw(self, layer: Layer, t: float) -> None:
        lf = self.life(t)
        n = len(self.items)
        lt = lf.lt
        fk = prog(lt, self.focus_at, self.focus_dur) if self.focus is not None else 0.0
        fk = ease_in_out(fk)
        for i, (im, top_y, left_x) in enumerate(self.sprites):
            cx, cy = self.cells[i]
            k = prog(lt, i * self.stagger, 0.5)
            k_out = lf.k_out
            alpha = ease_out(k) * k_out
            dy = (1 - ease_out(k)) * 70 + (1 - k_out) * -18
            sc = lerp(0.88, 1.0, ease_out_back(k, 1.2))
            bl = (1 - k) * 12 + (1 - k_out) * 8
            if self.focus is not None:
                if i == int(self.focus):
                    fx, fy = self.zone_center
                    cx, cy = lerp(cx, fx, fk), lerp(cy, fy, fk)
                    sc *= lerp(1.0, self.focus_scale, fk)
                else:
                    alpha *= 1 - fk
                    bl += fk * 14
                    sc *= lerp(1.0, 0.92, fk)
            if self.spec.get("float", True):
                dy += 4 * math.sin(2 * math.pi * lt / 3.4 + i * 1.3) * clamp01(k)
            spr = im
            if abs(sc - 1.0) > 1e-3:
                spr = scale_rotate(spr, sc)
            if bl > 0.5:
                pad = int(bl * 2.5)
                tmp = rgba_image(spr.size[0] + 2 * pad, spr.size[1] + 2 * pad)
                tmp.alpha_composite(spr, dest=(pad, pad))
                spr = blur(tmp, bl)
                pad_x = pad_y = pad
            else:
                pad_x = pad_y = 0
            # kotwica: środek karty w obrazie to (left_x + cw/2, top_y + ch/2), po skalowaniu przeliczamy
            anchor_x = (left_x + self.cw / 2) * sc + pad_x
            anchor_y = (top_y + self.ch / 2) * sc + pad_y
            layer.paste(spr, cx - anchor_x, cy + dy - anchor_y, alpha)
