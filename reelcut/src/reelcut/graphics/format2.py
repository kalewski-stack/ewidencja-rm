"""Elementy formatu 2 „gadająca głowa”: tekst z odsłanianiem i zakreślaczem, strzałki, opisy z liniami łączącymi, listy
(z punktami, ptaszkami i w dwóch kolumnach) oraz pierścień z kropek.

Miejsce podajesz w ułamkach kadru (`x`, `y`: 0 = lewa/górna krawędź). Czasy jak w innych elementach (`at`, `dur`, `in`, `out`).
"""
from __future__ import annotations

import math
import random
import re

from .core import (SS, Layer, PlanError, clamp01, compose, disc, ease_in_out, ease_out, ease_out_back, lerp, prog, rgba_image,
                   rounded_rect, shadowed, text_size, text_sprite, wrap_text)
from .elements import Element, register

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------------------------
# Krzywe i kreski
# ---------------------------------------------------------------------------------------------

def curve(a: tuple[float, float], b: tuple[float, float], bend: float = 0.0, n: int = 72) -> list[tuple[float, float]]:
    """Punkty łuku od a do b; bend to wygięcie jako ułamek długości (dodatnie: w lewo patrząc od a do b)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    c = ((a[0] + b[0]) / 2 - dy / length * bend * length, (a[1] + b[1]) / 2 + dx / length * bend * length)
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append(((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0], (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]))
    return pts


def _cumulative(pts):
    out, acc = [0.0], 0.0
    for p, q in zip(pts[:-1], pts[1:]):
        acc += math.hypot(q[0] - p[0], q[1] - p[1])
        out.append(acc)
    return out


def _upto(pts, cum, length):
    """Początek łamanej o danej długości (ostatni punkt interpolowany)."""
    out = [pts[0]]
    for i in range(1, len(pts)):
        if cum[i] <= length:
            out.append(pts[i])
        else:
            seg = cum[i] - cum[i - 1]
            k = (length - cum[i - 1]) / seg if seg > 0 else 0.0
            out.append((lerp(pts[i - 1][0], pts[i][0], k), lerp(pts[i - 1][1], pts[i][1], k)))
            break
    return out


def _dashes(pts, on: float, off: float):
    """Odcinki łamanej: `on` widoczne, `off` przerwy (w pikselach)."""
    cum = _cumulative(pts)
    total = cum[-1]
    out, pos = [], 0.0
    while pos < total:
        seg = _upto(pts, cum, min(total, pos + on))
        start = _upto(pts, cum, pos)[-1]
        part = [start] + [p for p, c in zip(pts, cum) if pos < c < pos + on]
        part.append(seg[-1])
        out.append(part)
        pos += on + off
    return out


def stroke(pts, width: float, color, *, style: str = "solid", progress: float = 1.0, head: str = "none", head_len: float | None = None):
    """Kreska po łamanej (styl solid | dashed | dotted), narysowana do `progress` długości, z grotem na końcu.
    Zwraca (obraz RGBA, (x, y) lewego górnego rogu w układzie kadru) albo None, gdy nic jeszcze nie widać."""
    if progress <= 0.002 or len(pts) < 2:
        return None
    cum = _cumulative(pts)
    total = cum[-1]
    if total < 1:
        return None
    shown = _upto(pts, cum, total * min(1.0, progress))
    head_len = head_len or width * 4.2
    pad = width * 2 + head_len
    xs, ys = [p[0] for p in shown], [p[1] for p in shown]
    x0, y0 = math.floor(min(xs) - pad), math.floor(min(ys) - pad)
    w, h = int(math.ceil(max(xs) + pad)) - x0, int(math.ceil(max(ys) + pad)) - y0
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    col = tuple(color) + (255,) if len(color) == 3 else tuple(color)

    def line(seq):
        P = [((x - x0) * SS, (y - y0) * SS) for x, y in seq]
        if len(P) >= 2:
            g.line(P, fill=col, width=max(1, int(width * SS)), joint="curve")
        r = width * SS / 2
        for x, y in (P[0], P[-1]):  # zaokrąglone końce
            g.ellipse([x - r, y - r, x + r, y + r], fill=col)

    if style == "dashed":
        for part in _dashes(shown, width * 3.4, width * 2.6):
            line(part)
    elif style == "dotted":
        for part in _dashes(shown, 0.01, width * 2.4):
            line(part)
    else:
        line(shown)
    if head != "none" and progress >= 0.999 and len(shown) >= 2:
        tip = shown[-1]
        back = shown[max(0, len(shown) - 6)]
        ang = math.atan2(tip[1] - back[1], tip[0] - back[0])
        wing = []
        for s in (-1, 1):
            a = ang + math.pi + s * math.radians(27)
            wing.append((tip[0] + math.cos(a) * head_len, tip[1] + math.sin(a) * head_len))
        if head == "filled":
            g.polygon([((tip[0] - x0) * SS, (tip[1] - y0) * SS)] + [((x - x0) * SS, (y - y0) * SS) for x, y in wing], fill=col)
        else:
            for wpt in wing:
                line([tip, wpt])
    return big.resize((w, h), Image.LANCZOS), (x0, y0)


def _color(brand, spec, key: str, default: str):
    return brand.rgb(spec.get(key, default))


# ---------------------------------------------------------------------------------------------
# Strzałka
# ---------------------------------------------------------------------------------------------

@register("arrow")
class Arrow(Element):
    """Linia albo strzałka rysowana „na żywo” od początku do końca: łuk, kreska ciągła/przerywana/kropkowana, grot otwarty lub
    pełny. Pola: from [x, y], to [x, y] (ułamki kadru), bend (wygięcie: 0 = prosta, 0,25 = wyraźny łuk, minus = w drugą stronę),
    style (solid|dashed|dotted), head (open|filled|none), width (ułamek szerokości kadru), color (rola marki), draw (sekundy),
    delay (sekundy od startu), dot (kropka na początku)."""
    default_dur = 3.0
    default_zone = "top"
    d_in = 0.0
    d_out = 0.3
    free_placement = True
    thin = True

    def build(self) -> None:
        s = self.spec
        if "from" not in s or "to" not in s:
            raise PlanError("Strzałka (arrow) wymaga pól from i to: [x, y] w ułamkach kadru.")
        try:
            (x1, y1), (x2, y2) = s["from"], s["to"]
            W, H = self.ctx.W, self.ctx.H
            self.a, self.b = (float(x1) * W, float(y1) * H), (float(x2) * W, float(y2) * H)
        except (TypeError, ValueError) as exc:
            raise PlanError("Strzałka: from i to to dwie liczby [x, y].") from exc
        self.style = s.get("style", "solid")
        if self.style not in ("solid", "dashed", "dotted"):
            raise PlanError("Strzałka: style to solid, dashed albo dotted.")
        self.head = s.get("head", "open")
        if self.head not in ("open", "filled", "none"):
            raise PlanError("Strzałka: head to open, filled albo none.")
        self.pts = curve(self.a, self.b, float(s.get("bend", 0.2)))
        self.w = max(2.0, float(s.get("width", 0.0046)) * W)
        self.col = _color(self.brand, s, "color", "text")
        self.draw_s = float(s.get("draw", 0.7))
        self.delay = float(s.get("delay", 0.0))
        self.dot = bool(s.get("dot", False))

    def draw(self, layer: Layer, t: float) -> None:
        lf = self.life(t)
        k = ease_in_out(prog(lf.lt, self.delay, self.draw_s))
        res = stroke(self.pts, self.w, self.col, style=self.style, progress=k, head=self.head)
        if res is None:
            return
        spr, (x, y) = res
        if self.dot:
            r = self.w * 1.5
            spr2 = rgba_image(spr.size[0], spr.size[1])
            spr2.alpha_composite(spr)
            d = disc(r * 2, fill=tuple(self.col) + (255,))
            spr2.alpha_composite(d, dest=(int(self.a[0] - x - r), int(self.a[1] - y - r)))
            spr = spr2
        layer.paste(spr, x, y, lf.alpha if lf.k_out < 1 else 1.0)


# ---------------------------------------------------------------------------------------------
# Opisy z liniami łączącymi
# ---------------------------------------------------------------------------------------------

@register("labels")
class Labels(Element):
    """Opisy przy elementach ilustracji: napis i cienka linia (łuk) do wskazanego punktu, na końcu kropka. items: [{text, x, y,
    tx, ty}]: (x, y) to środek napisu, (tx, ty) punkt, na który wskazuje linia (ułamki kadru). Pola wspólne: font (bold|serif|display),
    color, size, stagger (sekundy między opisami), line (solid|dashed|dotted|none), bend, dot (true/false)."""
    default_dur = 5.0
    default_zone = "top"
    d_in = 0.2
    d_out = 0.35
    free_placement = True
    thin = True

    def build(self) -> None:
        s, b = self.spec, self.brand
        items = s.get("items")
        if not items or not isinstance(items, list):
            raise PlanError("Opisy (labels) wymagają listy items: [{text, x, y, tx, ty}].")
        W, H = self.ctx.W, self.ctx.H
        self.items = []
        font_kind = s.get("font", "bold")
        for i, it in enumerate(items):
            if not isinstance(it, dict) or "text" not in it or "x" not in it or "y" not in it:
                raise PlanError(f"Opis {i + 1}: wymagane pola text, x i y.")
            role = {"bold": "bold", "serif": "serif_italic", "display": "display"}.get(it.get("font", font_kind))
            if role is None:
                raise PlanError("Opisy: font to bold, serif albo display.")
            size = float(it.get("size", s.get("size", 0.026))) * W * (1.15 if role == "serif_italic" else 1.0)
            font = b.font(role, size)
            col = b.rgb(it.get("color", s.get("color", "text")))
            im, _ = text_sprite(str(it["text"]), font, col + (255,), pad=3)
            im, org = shadowed(im, size * 0.18, 0.55, dy=size * 0.05)
            c = (float(it["x"]) * W, float(it["y"]) * H)
            tgt = (float(it["tx"]) * W, float(it["ty"]) * H) if "tx" in it and "ty" in it else None
            line = None
            if tgt is not None and s.get("line", "dotted") != "none":
                hw, hh = (im.size[0] - 2 * org[0]) / 2, (im.size[1] - 2 * org[1]) / 2
                dx, dy = tgt[0] - c[0], tgt[1] - c[1]
                gap = 0.01 * W
                if abs(dx) * hh > abs(dy) * hw:  # linia wychodzi z boku napisu
                    start = (c[0] + math.copysign(hw + gap, dx), c[1])
                else:
                    start = (c[0], c[1] + math.copysign(hh + gap, dy))
                line = curve(start, tgt, float(it.get("bend", s.get("bend", 0.18))))
            self.items.append({"im": im, "center": c, "line": line, "target": tgt})
        self.stagger = float(s.get("stagger", 0.3))
        self.line_style = s.get("line", "dotted")
        self.line_w = max(2.0, float(s.get("width", 0.0036)) * W)
        self.line_col = b.rgb(s.get("line_color", "text"))
        self.dot = bool(s.get("dot", True))

    def draw(self, layer: Layer, t: float) -> None:
        lf = self.life(t)
        for i, it in enumerate(self.items):
            t0 = i * self.stagger
            k = ease_out(prog(lf.lt, t0, 0.4))
            if k <= 0:
                continue
            cx, cy = it["center"]
            a = lf.alpha * k
            im = it["im"]
            layer.paste_center(im, cx, cy + (1 - k) * 14, a)
            if it["line"] is not None:
                kl = ease_in_out(prog(lf.lt, t0 + 0.25, 0.6))
                res = stroke(it["line"], self.line_w, self.line_col, style=self.line_style, progress=kl)
                if res is not None:
                    spr, (x, y) = res
                    layer.paste(spr, x, y, lf.alpha)
                if self.dot and kl > 0.98:
                    kd = ease_out_back(prog(lf.lt, t0 + 0.85, 0.25), 1.8)
                    r = self.line_w * 1.9 * kd
                    if r > 0.5:
                        layer.paste_center(disc(max(2, r * 2), fill=tuple(self.line_col) + (255,)), it["target"][0], it["target"][1], lf.alpha)


# ---------------------------------------------------------------------------------------------
# Tekst z odsłanianiem, zakreślaczem i etykietą
# ---------------------------------------------------------------------------------------------

_MARK = re.compile(r"(\*|_)")


def parse_runs(text: str) -> list[list[tuple[str, str]]]:
    """„Co się *psuje* w _tym_ filmie” -> wiersze z fragmentami (tekst, styl): styl to "", "hi" (*...*) albo "serif" (_..._)."""
    lines = []
    for raw in text.replace("\\n", "\n").split("\n"):
        runs, mode = [], ""
        for part in _MARK.split(raw):
            if part == "*":
                mode = "" if mode == "hi" else "hi"
            elif part == "_":
                mode = "" if mode == "serif" else "serif"
            elif part:
                runs.append((part, mode))
        lines.append(runs or [("", "")])
    return lines


def _advance(text: str, font, tracking: float, k: int) -> float:
    if tracking == 0:
        return font.getlength(text[:k])
    return sum(font.getlength(c) + tracking for c in text[:k])


@register("text")
class RichText(Element):
    """Tekst z formatowaniem i odsłanianiem: nagłówek, podpis, cytat. W tekście `*wyróżnienie*` świeci kolorem akcentu,
    `_kursywa_` to krój szeryfowy, `\\n` (albo nowy wiersz) łamie wiersz. Pola: text, font (display|bold|semibold|text|serif_italic),
    size (ułamek szerokości kadru), color, highlight (rola koloru wyróżnień), align (center|left|right), reveal (fade|type|words),
    cps (znaków na sekundę przy type), marker (none|underline|brush|bracket), tag (mała żółta etykieta pod tekstem),
    x, y albo zone."""
    default_dur = 3.5
    default_zone = "top"
    d_in = 0.3
    d_out = 0.3

    def build(self) -> None:
        s, b = self.spec, self.brand
        text = str(s.get("text", ""))
        if not text.strip():
            raise PlanError("Tekst (text) wymaga pola text.")
        W = self.ctx.W
        role = s.get("font", "display")
        if role not in ("display", "bold", "semibold", "text", "serif_italic"):
            raise PlanError("Tekst: font to display, bold, semibold, text albo serif_italic.")
        self.marker = s.get("marker", "none")
        if self.marker not in ("none", "underline", "brush", "bracket"):
            raise PlanError("Tekst: marker to none, underline, brush albo bracket.")
        self.reveal = s.get("reveal", "fade")
        if self.reveal not in ("fade", "type", "words"):
            raise PlanError("Tekst: reveal to fade, type albo words.")
        size = float(s.get("size", 0.06)) * W
        zw = self.zone_width()
        max_w = min(0.92 * W, zw * 0.96) if zw else 0.92 * W
        lines = parse_runs(text)
        has_brush_target = any(st == "hi" for ln in lines for _, st in ln)
        base_col = b.rgb(s.get("color", "text"))
        hi_col = b.rgb(s.get("highlight", "highlight"))
        ink = b.rgb("panel")
        if self.marker == "brush":
            base_col = b.rgb(s["color"]) if "color" in s else (base_col if has_brush_target else ink)
            if has_brush_target and "highlight" not in s:
                hi_col = ink  # czarny napis na żółtym zakreślaczu
        self.tracking = -0.012 * size if role in ("display", "bold") else 0.0

        def font_for(style: str, sz: float):
            return b.font("serif_italic", sz * 1.14) if style == "serif" else b.font(role, sz)

        def widest(sz: float) -> float:
            best = 0.0
            for ln in lines:
                best = max(best, sum(text_size(t, font_for(st, sz), -0.012 * sz if role in ("display", "bold") and st != "serif" else 0.0)[0] for t, st in ln))
            return best

        size = self.fit_size(size, max_w, widest)
        self.size = size
        tr = -0.012 * size if role in ("display", "bold") else 0.0
        self.tr = tr
        # każdy wiersz: obrazy fragmentów w jednej linii bazowej
        rows = []
        asc_all = 0.0
        desc_all = 0.0
        for ln in lines:
            parts, x, asc_l, desc_l = [], 0.0, 0.0, 0.0
            for t, st in ln:
                f = font_for(st, size)
                a, d = f.getmetrics()
                asc_l, desc_l = max(asc_l, a), max(desc_l, d)
                col = hi_col if st == "hi" else base_col
                trk = 0.0 if st == "serif" else tr
                im, _ = text_sprite(t, f, col + (255,), tracking=trk, pad=0) if t else (rgba_image(1, 1), 0)
                parts.append({"im": im, "x": x, "asc": a, "text": t, "font": f, "trk": trk, "style": st})
                x += (text_size(t, f, trk)[0] if t else 0.0)
            rows.append({"parts": parts, "w": x, "asc": asc_l, "desc": desc_l})
            asc_all, desc_all = max(asc_all, asc_l), max(desc_all, desc_l)
        lh = (asc_all + desc_all) * float(s.get("line_height", 0.92))
        self.rows, self.lh = rows, lh
        self.text_w = max(r["w"] for r in rows)
        self.text_h = lh * (len(rows) - 1) + asc_all + desc_all
        self.align = s.get("align", "center")
        if self.align not in ("center", "left", "right"):
            raise PlanError("Tekst: align to center, left albo right.")
        self.line_sprites = []
        self.char_x = []  # po każdym znaku: x końca znaku w wierszu (do odsłaniania)
        self.n_chars = 0
        pad = int(size * 0.08) + 2
        for r in rows:
            base = rgba_image(r["w"] + 2 * pad, r["asc"] + r["desc"] + 2 * pad)
            marks = []
            for p in r["parts"]:
                if p["text"]:
                    base.alpha_composite(p["im"], dest=(int(pad + p["x"]), int(pad + r["asc"] - p["asc"])))
                    for k in range(1, len(p["text"]) + 1):
                        marks.append(p["x"] + _advance(p["text"], p["font"], p["trk"], k))
            self.line_sprites.append((base, pad, r["w"], r["asc"]))
            self.char_x.append(marks)
            self.n_chars += len(marks)
        self.hi_boxes = []  # prostokąty fragmentów *wyróżnionych* (do zakreślacza), w układzie bloku tekstu
        for i, r in enumerate(rows):
            for p in r["parts"]:
                if p["style"] == "hi" and p["text"]:
                    self.hi_boxes.append((p["x"], i * lh, p["x"] + text_size(p["text"], p["font"], p["trk"])[0], i * lh + r["asc"] + r["desc"]))
        self.cps = float(s.get("cps", 30))
        self.col_hi, self.col_base, self.ink = hi_col, base_col, ink
        self.tag_im = None
        if s.get("tag"):
            tf = b.font("display", size * 0.42)
            ts, _ = text_sprite(str(s["tag"]), tf, ink + (255,), pad=0)
            th = int(size * 0.62)
            self.tag_im = rounded_rect(ts.size[0] + th * 0.9, th, th / 2, fill=b.rgba("highlight"))
            self.tag_im.alpha_composite(ts, dest=(int(th * 0.45), int((th - ts.size[1]) / 2)))
        self.brush = None
        if self.marker == "brush":
            boxes = self.hi_boxes or [(0.0, 0.0, self.text_w, self.text_h)]
            self.brush = self._brush(boxes, size, hi_col if not self.hi_boxes else b.rgb("highlight"))
        self.cache: dict = {}

    def _brush(self, boxes, size, color):
        """Żółty zakreślacz „pędzlem” za wyróżnionym fragmentem: nierówny pas z lekkim skosem."""
        rnd = random.Random(sum(ord(c) for c in str(self.spec.get("text", ""))))
        x0 = min(b[0] for b in boxes) - size * 0.22
        x1 = max(b[2] for b in boxes) + size * 0.22
        y0 = min(b[1] for b in boxes) + size * 0.08
        y1 = max(b[3] for b in boxes) - size * 0.04
        w, h = int(x1 - x0) + 8, int(y1 - y0) + 8
        n = 14
        top = [(4 + (w - 8) * i / n, 4 + rnd.uniform(-0.07, 0.07) * h + (0.04 * h if i % 2 else 0)) for i in range(n + 1)]
        bot = [(4 + (w - 8) * i / n, h - 4 + rnd.uniform(-0.07, 0.07) * h) for i in range(n, -1, -1)]
        big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        ImageDraw.Draw(big).polygon([(x * SS, y * SS) for x, y in top + bot], fill=tuple(color) + (250,))
        return big.resize((w, h), Image.LANCZOS), (x0 - 4, y0 - 4)

    # --- rysowanie ---
    def _visible_chars(self, lt: float) -> int:
        if self.reveal == "fade":
            return self.n_chars
        run = max(0.0, lt - 0.25)
        if self.reveal == "type":
            return int(min(self.n_chars, run * self.cps))
        ends, pos = [], 0  # words: odsłaniamy po całych słowach, ok. 5,5 słowa na sekundę
        for r in self.rows:
            txt = "".join(p["text"] for p in r["parts"])
            ends += [pos + m.end() for m in re.finditer(r"\S+", txt)]
            pos += len(txt)
        if not ends:
            return self.n_chars
        return ends[min(int(run * 5.5) + 1, len(ends)) - 1]

    def _sprite(self, visible: int, mk: float):
        key = (visible, round(mk * 12))
        if key in self.cache:
            return self.cache[key]
        parts = []
        left = visible
        W = self.text_w
        for i, ((base, pad, w, asc), marks) in enumerate(zip(self.line_sprites, self.char_x)):
            take = max(0, min(len(marks), left))
            left -= len(marks)
            if take <= 0:
                continue
            line = base if take >= len(marks) else base.crop((0, 0, int(pad + marks[take - 1] + 2), base.size[1]))
            x = {"center": (W - w) / 2, "left": 0.0, "right": W - w}[self.align] - pad
            parts.append((line, x, i * self.lh - pad))
        if not parts:
            self.cache[key] = None
            return None
        if self.brush is not None and mk > 0:
            bim, (bx, by) = self.brush
            cut = max(1, int(bim.size[0] * mk))
            parts.insert(0, (bim.crop((0, 0, cut, bim.size[1])), bx, by))
        if self.marker == "underline" and mk > 0:
            lw = max(3, int(self.size * 0.07))
            bar = rounded_rect(max(lw, self.text_w * 0.94 * mk), lw, lw / 2, fill=self.brand.rgba("highlight"))
            parts.append((bar, self.text_w * 0.03 if self.align == "center" else 0.0, self.text_h + self.size * 0.04))
        if self.marker == "bracket" and mk > 0:
            bw = max(3, int(self.size * 0.075))
            hh = self.text_h * 1.12 * mk
            x = self.text_w + self.size * 0.3
            y0 = -self.text_h * 0.06
            vert = rounded_rect(bw, max(bw, hh), bw / 2, fill=self.brand.rgba("highlight"))
            parts.append((vert, x, y0))
            if mk > 0.3:
                tick = rounded_rect(self.size * 0.3, bw, bw / 2, fill=self.brand.rgba("highlight"))
                parts.append((tick, x - self.size * 0.3 + bw, y0))
                if mk > 0.95:
                    parts.append((tick, x - self.size * 0.3 + bw, y0 + hh - bw))
        if self.tag_im is not None:
            parts.append((self.tag_im, 0.0, self.text_h + self.size * (0.2 if self.marker == "underline" else 0.1)))
        spr, org = compose(parts, pad=2)
        sh, off = shadowed(spr, self.size * 0.07, float(self.spec.get("shadow", 0.5)), dy=self.size * 0.03)
        self.cache[key] = (sh, (org[0] - off[0], org[1] - off[1]))
        if len(self.cache) > 300:
            self.cache.pop(next(iter(self.cache)))
        return self.cache[key]

    def draw(self, layer: Layer, t: float) -> None:
        lf = self.life(t)
        mk = ease_out(prog(lf.lt, 0.35, 0.5)) if self.marker != "none" else 0.0
        res = self._sprite(self._visible_chars(lf.lt), mk)
        if res is None:
            return
        spr, org = res
        bw, bh = self.text_w, self.text_h
        x, y = self.place(bw, bh, valign="center")
        typed = self.reveal != "fade"
        im, dy, alpha = self.appear(spr, lf, rise=10 if typed else 26, blur_px=0 if typed else 8, scale_from=0.99 if typed else 0.96)
        # sprite ma własny początek: (org) to położenie jego lewego górnego rogu względem lewego górnego rogu bloku tekstu
        shift_x = (im.size[0] - spr.size[0]) / 2
        shift_y = (im.size[1] - spr.size[1]) / 2
        layer.paste(im, x + org[0] - shift_x, y + org[1] - shift_y + dy, alpha)


# ---------------------------------------------------------------------------------------------
# Lista: punkty, ptaszki, dwie kolumny
# ---------------------------------------------------------------------------------------------

def check_marker(d: int, brand, k: float):
    """Pole wyboru: pusty kwadrat (k=0) albo wypełnione koło z ptaszkiem (k=1, z odbiciem przy wejściu)."""
    big = Image.new("RGBA", (d * SS, d * SS), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    if k <= 0:
        g.rounded_rectangle([d * SS * 0.14, d * SS * 0.14, d * SS * 0.86, d * SS * 0.86], radius=d * SS * 0.18,
                            outline=(255, 255, 255, 220), width=max(2, int(d * SS * 0.09)))
        return big.resize((d, d), Image.LANCZOS)
    r = d * SS * 0.5 * min(1.0, 0.55 + 0.45 * ease_out_back(k, 2.0))
    c = d * SS / 2
    g.ellipse([c - r, c - r, c + r, c + r], fill=brand.rgb("accent_strong") + (255,))
    s = r / (d * SS * 0.5)
    g.line([(c - d * SS * 0.2 * s, c + d * SS * 0.0), (c - d * SS * 0.06 * s, c + d * SS * 0.14 * s), (c + d * SS * 0.22 * s, c - d * SS * 0.14 * s)],
           fill=(255, 255, 255, 255), width=max(2, int(d * SS * 0.1)), joint="curve")
    return big.resize((d, d), Image.LANCZOS)


@register("list")
class ListBlock(Element):
    """Wiersze, które pojawiają się kolejno, z „pisaniem” treści: etykieta (żółta, pogrubiona) i tekst (kursywa szeryfowa albo biały).
    Pola: rows [{label, text, detail, state: open|done, check_at, at}] albo columns [{title, rows}] (porównanie w kolumnach z kreską
    pośrodku: rule true, rule_to = dokąd schodzi kreska, ułamek wysokości kadru); marker (none|dot|box), text_font (serif|plain),
    size, width, stagger, cps, x, y (lewy górny róg bloku, ułamki kadru) albo zone."""
    default_dur = 8.0
    default_zone = "top"
    d_in = 0.3
    d_out = 0.4

    def build(self) -> None:
        s, b = self.spec, self.brand
        W = self.ctx.W
        cols = s.get("columns")
        if cols:
            if not isinstance(cols, list) or not all(isinstance(c, dict) and c.get("rows") for c in cols):
                raise PlanError("Lista: columns to lista obiektów {title, rows}.")
            self.cols = [{"title": c.get("title"), "rows": list(c["rows"])} for c in cols]
        else:
            rows = s.get("rows")
            if not rows or not isinstance(rows, list):
                raise PlanError("Lista (list) wymaga rows albo columns.")
            self.cols = [{"title": None, "rows": list(rows)}]
        self.marker = s.get("marker", "none")
        if self.marker not in ("none", "dot", "box"):
            raise PlanError("Lista: marker to none, dot albo box.")
        text_font = s.get("text_font", "serif")
        if text_font not in ("serif", "plain"):
            raise PlanError("Lista: text_font to serif albo plain.")
        size = float(s.get("size", 0.038)) * W
        total_w = float(s.get("width", 0.84)) * W
        zw = self.zone_width()
        if zw:
            total_w = min(total_w, zw)
        colw = total_w / len(self.cols)
        self.f_label = b.font("display", size)
        self.f_text = b.font("serif_italic", size * 1.16) if text_font == "serif" else b.font("text", size)
        self.f_detail = b.font("text", size * 0.62)
        f_title = b.font("serif_italic", size * 1.3)
        lab_col, txt_col, det_col = b.rgb("highlight"), b.rgb("text"), b.rgb("text_dim")
        self.mk_d = int(size * 0.95)
        marker_w = (self.mk_d + size * 0.35) if self.marker != "none" else 0.0
        title_h = (sum(f_title.getmetrics()) * 1.1) if any(c["title"] for c in self.cols) else 0.0
        lh = sum(self.f_label.getmetrics()) * 1.02
        tl = sum(self.f_text.getmetrics()) * 0.96
        dl = sum(self.f_detail.getmetrics()) * 0.98
        row_gap = float(s.get("row_gap", 0.35)) * lh
        self.layout, self.height = [], 0.0
        for ci, c in enumerate(self.cols):
            y, out = title_h, []
            for r in c["rows"]:
                if not isinstance(r, dict):
                    r = {"text": str(r)}
                label, text, detail = str(r.get("label", "")), str(r.get("text", "")), str(r.get("detail", ""))
                lab = text_sprite(label, self.f_label, lab_col + (255,), tracking=-0.4, pad=0)[0] if label else None
                lab_w = (lab.size[0] + size * 0.3) if lab is not None else 0.0
                avail = max(colw - marker_w - lab_w - size * 0.2, size * 3)
                t_lines = [(ln, text_sprite(ln, self.f_text, txt_col + (255,), pad=0)[0]) for ln in (wrap_text(text, self.f_text, avail) if text else [])]
                d_lines = [(ln, text_sprite(ln, self.f_detail, det_col + (255,), pad=0)[0]) for ln in (wrap_text(detail, self.f_detail, avail) if detail else [])]
                h = max(lh, tl * len(t_lines)) + dl * len(d_lines)
                out.append({"lab": lab, "lab_w": lab_w, "t_lines": t_lines, "d_lines": d_lines, "y": y, "h": h, "x": ci * colw,
                            "state": r.get("state", "open"), "check_at": r.get("check_at"), "at": r.get("at"), "marker_w": marker_w})
                y += h + row_gap
            self.layout.append(out)
            self.height = max(self.height, y - row_gap)
        self.colw, self.total_w = colw, total_w
        self.title_ims = [text_sprite(str(c["title"]), f_title, txt_col + (255,), pad=0)[0] if c["title"] else None for c in self.cols]
        self.stagger = float(s.get("stagger", 0.55))
        self.cps = float(s.get("cps", 30))
        self.rule = bool(s.get("rule", False)) and len(self.cols) >= 2
        self.rule_to = float(s.get("rule_to", 0.0))
        self.lh, self.tl, self.dl = lh, tl, dl

    def _row_start(self, i: int, row: dict) -> float:
        return float(row["at"]) if row.get("at") is not None else 0.35 + i * self.stagger

    def draw(self, layer: Layer, t: float) -> None:
        s, b = self.spec, self.brand
        lf = self.life(t)
        W, H = self.ctx.W, self.ctx.H
        if "x" in s and "y" in s:
            ox, oy = float(s["x"]) * W + float(s.get("dx", 0)) * W, float(s["y"]) * H + float(s.get("dy", 0)) * H
        else:
            ox, oy = self.place(self.total_w, self.height, align="left", valign="top")
        a_all = lf.alpha
        for ci, im in enumerate(self.title_ims):
            if im is not None:
                kt = ease_out(prog(lf.lt, 0.05 + ci * 0.15, 0.4))
                layer.paste(im, ox + ci * self.colw + (self.colw - im.size[0]) / 2, oy + (1 - kt) * 12, a_all * kt)
        if self.rule:
            y_end = (self.rule_to * H) if self.rule_to > 0 else oy + self.height
            res = stroke([(ox + self.colw, oy), (ox + self.colw, y_end)], max(2.0, W * 0.0035), b.rgb("highlight"),
                         progress=ease_in_out(prog(lf.lt, 0.15, 0.8)))
            if res is not None:
                layer.paste(res[0], res[1][0], res[1][1], a_all)
        for rows in self.layout:
            for i, r in enumerate(rows):
                t0 = self._row_start(i, r)
                k = ease_out(prog(lf.lt, t0, 0.35))
                if k <= 0:
                    continue
                x, y, al = ox + r["x"], oy + r["y"] + (1 - k) * 10, a_all * k
                if self.marker == "dot":
                    d = disc(self.mk_d * 0.45, fill=b.rgba("highlight"))
                    layer.paste(d, x + self.mk_d * 0.1, y + self.lh * 0.5 - d.size[1] / 2, al)
                elif self.marker == "box":
                    ca = r["check_at"]
                    kc = prog(lf.lt, float(ca) if ca is not None else t0 + 0.9, 0.35) if r["state"] == "done" else 0.0
                    layer.paste(check_marker(self.mk_d, b, kc), x, y + self.lh * 0.5 - self.mk_d / 2, al)
                tx = x + r["marker_w"]
                if r["lab"] is not None:
                    layer.paste(r["lab"], tx, y, al)
                tx += r["lab_w"]
                shown = int(max(0.0, lf.lt - t0 - 0.25) * self.cps)  # tyle znaków tekstu już „napisano”
                ty = y
                for text, im in r["t_lines"]:
                    if shown <= 0:
                        break
                    w = im.size[0] if shown >= len(text) else int(self.f_text.getlength(text[:shown])) + 1
                    layer.paste(im.crop((0, 0, max(1, min(w, im.size[0])), im.size[1])), tx, ty, al)
                    shown -= len(text)
                    ty += self.tl
                if r["d_lines"]:
                    kd = 1.0 if not r["t_lines"] else clamp01(shown / 6.0)  # szczegół wchodzi, gdy tekst jest napisany
                    dy = y + (self.tl * len(r["t_lines"]) if r["t_lines"] else self.lh * 0.85)
                    for _, im in r["d_lines"]:
                        if kd > 0:
                            layer.paste(im, tx, dy, al * kd)
                        dy += self.dl


# ---------------------------------------------------------------------------------------------
# Pierścień z kropek
# ---------------------------------------------------------------------------------------------

@register("ring")
class Ring(Element):
    """Pierścień (albo dwa łuki) z kropek wokół wskazanego miejsca, np. wokół karty; kropki pojawiają się kolejno. Pola: x, y (środek),
    rx, ry (promienie, ułamki szerokości i wysokości kadru), dots (liczba), size (kropka, ułamek szerokości), arcs [[od, do], ...]
    w stopniach (0 to góra, kąty rosną zgodnie ze wskazówkami zegara; domyślnie pełny okrąg), color."""
    default_dur = 3.5
    default_zone = "top"
    d_in = 0.0
    d_out = 0.35
    free_placement = True
    thin = True

    def build(self) -> None:
        s = self.spec
        if "x" not in s or "y" not in s:
            raise PlanError("Pierścień (ring) wymaga środka: x i y.")
        W, H = self.ctx.W, self.ctx.H
        self.cx, self.cy = float(s["x"]) * W, float(s["y"]) * H
        self.rx, self.ry = float(s.get("rx", 0.2)) * W, float(s.get("ry", s.get("rx", 0.2) * W / H)) * H
        n = int(s.get("dots", 26))
        arcs = s.get("arcs") or [[0, 360]]
        self.size = max(2.0, float(s.get("size", 0.0095)) * W)
        pts = []
        per = max(1, n // len(arcs))
        full = len(arcs) == 1 and arcs[0][1] - arcs[0][0] >= 359
        for a0, a1 in arcs:
            m = per if not full else n
            for i in range(m):
                k = i / (m if full else max(1, m - 1))
                ang = math.radians(lerp(float(a0), float(a1), k) - 90)
                pts.append((self.cx + math.cos(ang) * self.rx, self.cy + math.sin(ang) * self.ry))
        self.pts = pts
        self.col = self.brand.rgb(s.get("color", "highlight"))
        self.spread = float(s.get("spread", 0.9))

    def draw(self, layer: Layer, t: float) -> None:
        lf = self.life(t)
        n = len(self.pts)
        for i, (x, y) in enumerate(self.pts):
            k = ease_out_back(prog(lf.lt, self.spread * i / n, 0.25), 2.2)
            if k <= 0.02:
                continue
            r = self.size * k
            layer.paste_center(disc(max(2, r * 2), fill=tuple(self.col) + (255,)), x, y, lf.alpha)
