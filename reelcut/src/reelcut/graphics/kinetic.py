"""Format 4 „kinetyczna typografia”: mowa jako napisy z małymi i dużymi słowami, karty w jednolitym kolorze i odręczna elipsa.

Wzorzec: jedna rolka poziomego eseju wideo (DdZBWMyq4Zx), liczby zmierzone klatka po klatce (25 kl./s, 1916x1078). Co z niej wzięto:

* **Fraza** (napisy bieżące): każde zdanie rozpada się na krótkie frazy, a w każdej jedno duże słowo (rzeczownik, czasownik, liczba) i małe słowa
  wokół niego: te przed nim stoją nad nim, przy lewej krawędzi bloku, te po nim pod nim, przy prawej. Słowa wskakują w chwili, gdy padają
  (jedna klatka, bez animacji). Na ujęciach z twarzą napis jest skromny (duże słowo 8,7% wysokości kadru, blok od 57% wysokości), na wstawkach
  czterokrotnie większy jak plansza (17% wysokości, blok od 38%). Duże słowa w grubej, ciasnej grotesce, małe w tym samym kroju.
* **Karta**: pełny kadr w jednolitym kolorze (białym albo żółto-pomarańczowym), na którym czarny tekst dochodzi słowo po słowie i za każdym
  razem się wyśrodkowuje (wiersz, 8,7% wysokości), albo duże słowo z małymi wokół (19% wysokości). Wyróżnione słowo dostaje odręczną elipsę.
* **Elipsa**: cienka kreska (0,4% wysokości), rysowana na żywo zgodnie z ruchem wskazówek zegara od lewej górnej strony, w ciągu ok. 0,4 s,
  z końcem zachodzącym do środka na początek. Obejmuje cały blok tekstu (szerokość 1,12 tekstu, wysokość 2,7 jego wysokości przy jednym wierszu).

Układ liter robi `lockup.py`; tu jest dobór dużych słów, podział na frazy, karty i wiersz pisany słowami. W planie to zwykłe elementy
(`lockup`, `slide`, `typeline`), więc wszystko da się też wpisać ręcznie.
"""
from __future__ import annotations

import math
import random
from typing import Sequence

from .anchors import norm
from .core import Layer, PlanError, ease_in_out, prog, shadowed, text_size, text_sprite
from .elements import Element, register
from .format2 import stroke
from .lockup import MAX_GAP_S, SENTENCE_END, _ends, from_emphasis

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    pass

LINE_EM = 0.087  # wiersz na karcie: wielkość kroju (ułamek H), jak w napisach na ujęciach z twarzą
LINE_MAX_W = 0.8  # najszerszy wiersz (ułamek W); dłuższy łamie się na kilka
LINE_SPACE = 0.27  # odstęp między słowami (ułamek wielkości kroju)
LINE_BREAK_WORDS = 6  # po tylu słowach wiersz na karcie się kończy i zaczyna nowy
ELLIPSE_W = 0.0038  # grubość kreski elipsy (ułamek H)
ELLIPSE_DUR = 0.4  # tyle trwa rysowanie elipsy
ELLIPSE_START = -0.82 * math.pi  # początek kreski: lewa górna strona
ELLIPSE_SWEEP = 2.1 * math.pi  # obieg z zakładką: koniec zachodzi na początek
PHRASE_Z = 12
SLIDE_Z = 4
LINE_Z = 14

# Słowa funkcyjne: nie bywają „dużym” słowem, chyba że w zdaniu nie ma nic innego. Polskie i angielskie, bez ogonków (porównujemy po `norm`).
STOP = frozenset("""
a aby ale albo ani bo by byc byl byla bylo byly bede bedzie bez bylem bylam cie co czy czyli dla do gdy gdyby gdzie go i ich ile im ja jak jaki jako
je jego jej jesli jest jestem jestes jeszcze juz ma mam masz mi mimo mnie mnostwo moj moja moje mu my na nad nam nas nasz nasza nasze nawet nic nie
niech nim no o od on ona one oni ono po pod ponad poniewaz potem przed przez przy sa sam sie swoj swoje ta tak takie tam te tego tej ten to tobie
toba tu ty tych tylko u w we wam was wiec wiem wy z za ze zeby zawsze ktory ktora ktore ktorego ktorej ktorym ktorych ktorzy tym taki taka jaka jakie
about after all also an and any are as at be been but by can could did do does for from get got had has have he her him his how i if in into is it
its just me more my no not of on one or our out over she so some than that the their them then there these they this to too up us was we were what
when which who will with would you your
""".split())

KEEP_SHORT = frozenset({"ai", "pr", "hr", "b2b", "it", "ux", "ui", "ok"})  # krótkie, ale sensowne jako duże słowo (skróty)


# ---------------------------------------------------------------------------------------------
# Elipsa odręczna
# ---------------------------------------------------------------------------------------------

def ellipse_points(cx: float, cy: float, a: float, b: float, seed: int = 0, n: int = 120) -> list[tuple[float, float]]:
    """Punkty odręcznej elipsy: obieg zgodny z ruchem wskazówek zegara od lewej górnej strony, lekkie drgania promienia, a koniec kreski
    zachodzi do środka na początek (jak przy rysowaniu ręką)."""
    rnd = random.Random(seed * 7919 + 13)
    ph = [rnd.uniform(0, 2 * math.pi) for _ in range(3)]
    pts = []
    for i in range(n + 1):
        s = i / n
        th = ELLIPSE_START + ELLIPSE_SWEEP * s
        wob = 1 + 0.012 * math.sin(2 * th + ph[0]) + 0.008 * math.sin(3 * th + ph[1]) + 0.006 * math.sin(5 * th + ph[2])
        r = wob * (1 - 0.08 * max(0.0, s - 0.82) / 0.18)
        pts.append((cx + a * r * math.cos(th), cy + b * r * math.sin(th)))
    return pts


def ellipse_axes(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """(środek x, środek y, półoś pozioma, półoś pionowa) elipsy obejmującej ramkę tekstu."""
    x0, y0, x1, y1 = box
    th = y1 - y0
    a = (x1 - x0) / 2 * 1.12 + 0.28 * th
    b = max(0.8 * th, 0.37 * a)
    return (x0 + x1) / 2, (y0 + y1) / 2, a, b


def draw_ellipse(layer: Layer, box: tuple[float, float, float, float], ctx, lt: float, dur: float, rgb, seed: int = 0) -> None:
    """Dorysowuje elipsę wokół ramki w chwili `lt` (sekundy od rozpoczęcia rysowania); przed rozpoczęciem nic nie rysuje."""
    k = ease_in_out(prog(lt, 0.0, max(1e-3, dur)))
    if k <= 0.002:
        return
    cx, cy, a, b = ellipse_axes(box)
    res = stroke(ellipse_points(cx, cy, a, b, seed), max(2.5, ELLIPSE_W * ctx.H), tuple(rgb), progress=k)
    if res is not None:
        spr, (x, y) = res
        layer.paste(spr, x, y)


# ---------------------------------------------------------------------------------------------
# Dobór dużych słów i frazy
# ---------------------------------------------------------------------------------------------

def _score(word) -> float:
    """Im wyższy wynik, tym lepszy kandydat na duże słowo: długie, treściwe, z cyfrą; słowa funkcyjne i króciutkie na końcu."""
    t = norm(str(word.text))
    if not t:
        return -9.0
    sc = float(len(t))
    if t in STOP:
        sc -= 7.0
    elif len(t) <= 2 and t not in KEEP_SHORT:
        sc -= 3.0
    if any(c.isdigit() for c in t):
        sc += 4.0
    return sc


BIG_COST = 3.0  # koszt każdego dużego słowa: im mniej fraz, tym spokojniejszy obraz
SCORE_CEIL = 9.0  # słowo o wyniku od tylu w górę nie dopłaca nic ponad koszt podstawowy


def _best_chain(words: Sequence, a: int, b: int, required: list[tuple[int, int]], pre: int, post: int) -> list[tuple[int, int]]:
    """Najtańszy zestaw dużych słów dla fragmentu zdania a..b (indeksy włącznie): każde słowo musi być w zasięgu jakiegoś dużego (pre słów
    przed nim i post po nim), a słowa z `required` (wyróżnione w scenariuszu) muszą być w zestawie. Koszt słowa to BIG_COST plus dopłata
    za to, że słowo jest słabe (funkcyjne, króciutkie), więc duże zostają rzeczowniki i czasowniki, a słowa łączące lądują w zasięgu sąsiadów."""
    nodes = [(i0, i1, 0.0, True) for i0, i1 in required]
    inside = lambda j: any(i0 <= j <= i1 for i0, i1 in required)  # noqa: E731
    nodes += [(j, j, BIG_COST + max(0.0, SCORE_CEIL - _score(words[j])), False) for j in range(a, b + 1) if not inside(j)]
    nodes.sort(key=lambda n: (n[0], n[1]))
    req_starts = [r[0] for r in required]
    inf = float("inf")
    cost = [inf] * len(nodes)
    back = [-1] * len(nodes)
    for i, (s0, e0, c0, _) in enumerate(nodes):
        if s0 - pre <= a and not any(rs < s0 for rs in req_starts):
            cost[i] = c0
        for k in range(i):
            s1, e1 = nodes[k][0], nodes[k][1]
            if cost[k] == inf or s0 <= e1 or s0 - pre > e1 + post + 1:
                continue  # węzły muszą iść po kolei i nie zostawiać dziury w pokryciu
            if any(e1 < rs < s0 for rs in req_starts):
                continue  # nie wolno pominąć słowa wyróżnionego
            if cost[k] + c0 < cost[i]:
                cost[i], back[i] = cost[k] + c0, k
    ends = [i for i, (s0, e0, _, _) in enumerate(nodes) if cost[i] < inf and e0 + post >= b and not any(rs > e0 for rs in req_starts)]
    if not ends:  # (nie powinno się zdarzyć) każde słowo osobno
        return [(j, j) for j in range(a, b + 1)] if not required else sorted(set(required) | {(j, j) for j in range(a, b + 1) if not inside(j)})
    i = min(ends, key=lambda x: cost[x])
    chain = []
    while i != -1:
        chain.append((nodes[i][0], nodes[i][1]))
        i = back[i]
    return chain[::-1]


def pick_bigs(words: Sequence, marks: Sequence[Sequence[float]], cfg: dict) -> list[tuple[int, int]]:
    """Zakresy indeksów [pierwsze, ostatnie] słów, które będą duże. Słowa wyróżnione w scenariuszu (`*tak*`, `marks`: przedziały czasu)
    są duże zawsze; w każdym zdaniu i fragmencie (przecinek, pauza) dobieramy resztę tak, żeby każde słowo było w zasięgu jakiegoś dużego
    (cfg.pre słów przed nim i cfg.post po nim), najtaniej: mało fraz i same słowa treściwe (`_best_chain`)."""
    pre, post = max(0, int(cfg.get("pre", 2))), max(0, int(cfg.get("post", 2)))
    big_max = max(1, int(cfg.get("big_max", 2)))
    gap = float(cfg.get("max_gap_s", MAX_GAP_S))
    n = len(words)
    mids = [(float(w.start) + float(w.end)) / 2 for w in words]
    marked = [any(float(m[0]) - 1e-3 <= mids[i] <= float(m[1]) + 1e-3 for m in marks) for i in range(n)]
    out: list[tuple[int, int]] = []
    start = 0
    for i in range(n):
        if not (i == n - 1 or _ends(words[i], SENTENCE_END + (",",)) or float(words[i + 1].start) - float(words[i].end) > gap):
            continue
        a, b = start, i
        start = i + 1
        required: list[tuple[int, int]] = []
        k = a
        while k <= b:
            if marked[k]:
                j = k
                while j + 1 <= b and marked[j + 1]:
                    j += 1
                required.append((k, min(j, k + big_max - 1)))
                k = j + 1
            else:
                k += 1
        out.extend(_best_chain(words, a, b, required, pre, post))
    return sorted(out)


def _mark_hit(spec: dict, marks: Sequence[Sequence[float]], lead: float) -> list[int]:
    """Numery wierszy dużych słów, w których jest słowo wyróżnione w scenariuszu."""
    at = float(spec["at"])
    hit = []
    for i, ln in enumerate(spec["lines"]):
        if ln.get("tier") != "big":
            continue
        for w in ln["words"]:
            t = at + float(w["t"]) + lead
            if any(float(m[0]) - 0.03 <= t <= float(m[1]) + 0.03 for m in marks):
                hit.append(i)
                break
    return hit


def phrase_specs(words: Sequence, marks: Sequence[Sequence[float]], cfg: dict) -> tuple[list[dict], list[list[float]], list[str]]:
    """Frazy (elementy `lockup`) dla słów jednego ujęcia. Zwraca (elementy, przedziały czasu słów objętych frazami, uwagi)."""
    if not words:
        return [], [], []
    spans = pick_bigs(words, marks, cfg)
    ranges = [[float(words[i0].start), float(words[i1].end)] for i0, i1 in spans]
    specs, skips, notes = from_emphasis(words, ranges, cfg)
    lead = float(cfg.get("lead", 0.04))
    for sp in specs:
        sp["z"] = int(cfg.get("z", PHRASE_Z))
        hit = _mark_hit(sp, marks, lead) if marks else []
        if hit and cfg.get("mark_color"):
            for i in hit:
                sp["lines"][i]["color"] = cfg["mark_color"]
        if hit and cfg.get("mark_circle"):  # elipsa zaczyna się rysować, gdy pada słowo wyróżnione
            sp["circle"] = True
            sp["circle_at"] = min(float(w["t"]) for i in hit for w in sp["lines"][i]["words"])
    return specs, skips, notes


def _clip(specs: list[dict], end: float) -> None:
    """Fraza nie wchodzi na następną ani na cięcie: kończy się, gdy zaczyna się kolejna, najpóźniej przy końcu ujęcia."""
    specs.sort(key=lambda s: float(s["at"]))
    for i, sp in enumerate(specs):
        limit = float(specs[i + 1]["at"]) if i + 1 < len(specs) else end
        limit = min(limit, end)
        if float(sp["at"]) + float(sp["dur"]) > limit:
            sp["dur"] = round(max(0.04, limit - float(sp["at"])), 3)


def _clamp_start(spec: dict, at: float) -> None:
    """Element nie zaczyna się przed ujęciem: słowo, które zaczęło się tuż przed cięciem, a jego środek wypadł już po nim, dostaje start na cięciu
    (czasy słów w elemencie przesuwają się o tyle samo, więc nic się nie rozjeżdża)."""
    d = at - float(spec["at"])
    if d <= 1e-6:
        return
    spec["at"] = round(at, 3)
    spec["dur"] = round(max(0.04, float(spec["dur"]) - d), 3)
    groups = [ln["words"] for ln in spec.get("lines", [])] + ([spec["words"]] if "words" in spec else [])
    for ws in groups:
        for w in ws:
            w["t"] = round(max(0.0, float(w["t"]) - d), 3)


def split_lines(words: Sequence, cfg: dict) -> list[tuple[int, int]]:
    """Podział słów karty na wiersze pisane: koniec zdania, przecinek, pauza albo `break_words` słów zaczynają nowy wiersz."""
    gap = float(cfg.get("max_gap_s", MAX_GAP_S))
    cap = max(1, int(cfg.get("break_words", LINE_BREAK_WORDS)))
    out, start = [], 0
    for i in range(len(words)):
        last = i == len(words) - 1
        if last or _ends(words[i], SENTENCE_END + (",",)) or float(words[i + 1].start) - float(words[i].end) > gap or i - start + 1 >= cap:
            out.append((start, i))
            start = i + 1
    return out


def line_specs(words: Sequence, marks: Sequence[Sequence[float]], cfg: dict, end: float) -> list[dict]:
    """Wiersze pisane słowami (elementy `typeline`) dla słów karty: każdy wiersz stoi od pierwszego swojego słowa do początku następnego
    (ostatni do końca karty); wiersz z wyróżnionym słowem dostaje elipsę."""
    if not words:
        return []
    lead = float(cfg.get("lead", 0.04))
    style = {k: cfg[k] for k in ("size", "font", "color", "mark_color", "max_width", "cy", "y", "cx", "track", "shadow") if k in cfg}
    rows = split_lines(words, cfg)
    out = []
    for r, (a, b) in enumerate(rows):
        at = max(0.0, float(words[a].start) - lead)
        nxt = max(0.0, float(words[rows[r + 1][0]].start) - lead) if r + 1 < len(rows) else end
        mids = [(float(w.start) + float(w.end)) / 2 for w in words[a:b + 1]]
        flagged = [k for k, m in enumerate(mids) if any(float(mk[0]) - 1e-3 <= m <= float(mk[1]) + 1e-3 for mk in marks)]
        spec = {"type": "typeline", "auto": True, "at": round(at, 3), "dur": round(max(0.2, min(nxt, end) - at), 3), "z": int(cfg.get("z", LINE_Z)),
                "words": [{"w": str(w.text).strip(), "t": round(max(0.0, float(w.start) - lead - at), 3)} for w in words[a:b + 1]], **style}
        if flagged:
            spec["marks"] = flagged
            if cfg.get("mark_circle", True):  # elipsa zaczyna się rysować, gdy pada słowo wyróżnione
                spec["circle"] = True
                spec["circle_at"] = spec["words"][flagged[0]]["t"]
        out.append(spec)
    return out


def from_phrases(words: Sequence, marks: Sequence[Sequence[float]], cfg: dict,
                 scopes: Sequence[dict] | None = None) -> tuple[list[dict], list[list[float]], list[list[float]], list[str]]:
    """Cała mowa jako frazy i karty. `scopes` to ujęcia filmu [{at, end, kind: A|B|slide, style: line|title, color}] w sekundach na osi filmu
    (bez nich cała mowa dostaje ustawienia ujęcia z twarzą). Frazy nie przechodzą przez cięcia; mowa w ujęciu-karcie trafia na kartę.
    Zwraca (elementy planu, przedziały słów pokrytych przez elementy, przedziały do ukrycia zwykłych napisów, uwagi dla autora)."""
    base = {k: v for k, v in cfg.items() if k not in ("A", "B", "slide", "line")}
    if scopes is None:
        end = max((float(w.end) for w in words), default=0.0) + 1.0
        scopes = [{"at": 0.0, "end": end, "kind": "A"}]
    elements: list[dict] = []
    skips: list[list[float]] = []
    hides: list[list[float]] = []
    notes: list[str] = []
    for sc in scopes:
        at, end, kind = float(sc["at"]), float(sc["end"]), sc.get("kind", "A")
        sub = [w for w in words if at - 1e-6 <= (float(w.start) + float(w.end)) / 2 < end]
        if kind == "slide":
            elements.append({"type": "slide", "auto": True, "at": round(at, 3), "dur": round(end - at, 3), "color": sc.get("color", "#F7F4EC"), "z": SLIDE_Z})
            skips.append([round(at, 3), round(end, 3)])
            hides.append([round(at, 3), round(end, 3)])
            if sc.get("style", "line") == "title":
                specs, _, nn = phrase_specs(sub, marks, {**base, **cfg.get("slide", {})})
                notes += nn
            else:
                specs = line_specs(sub, marks, {**base, **cfg.get("line", {})}, end)
            for sp in specs:
                _clamp_start(sp, at)
            _clip(specs, end)
            elements += specs
            continue
        specs, sk, nn = phrase_specs(sub, marks, {**base, **cfg.get(kind if kind in ("A", "B") else "A", {})})
        for sp in specs:
            _clamp_start(sp, at)
        _clip(specs, end)
        elements += specs
        skips += sk
        notes += nn
    return elements, skips, hides, notes


# ---------------------------------------------------------------------------------------------
# Elementy: karta i wiersz pisany słowami
# ---------------------------------------------------------------------------------------------

@register("slide")
class Slide(Element):
    """Karta: jednolity kolor na całym kadrze (Format 4), pod tekstem kart. Pola: color (rola marki, nazwa albo #RRGGBB; domyślnie paper)."""
    default_dur = 2.0
    default_z = SLIDE_Z
    d_in = 0.0
    d_out = 0.0
    free_placement = True
    no_lint = True

    def build(self) -> None:
        from .core import need_pil

        need_pil()
        self.sprite = Image.new("RGBA", (self.ctx.W, self.ctx.H), tuple(self.brand.rgb(self.spec.get("color", "paper"))) + (255,))

    def draw(self, layer: Layer, t: float) -> None:
        layer.img.paste(self.sprite, (0, 0))


@register("typeline")
class TypeLine(Element):
    """Wiersz pisany słowami: słowa dochodzą jedno po drugim w chwili, gdy padają, a wiersz za każdym razem się wyśrodkowuje (karty Formatu 4).
    Za długi wiersz łamie się na kilka; podział liczony jest z całego tekstu, więc słowa nie skaczą między wierszami. Pola: words [{w, t}]
    (t: sekundy od startu elementu), size (wielkość kroju, ułamek H), font (domyślnie display), color (domyślnie panel, czyli tusz), mark_color,
    marks (numery słów wyróżnionych), max_width (ułamek W), cy albo y (środek bloku w pionie, ułamek H), cx, track, shadow,
    circle (odręczna elipsa wokół tekstu; circle_at, circle_dur, circle_color)."""
    default_dur = 2.0
    default_z = LINE_Z
    d_in = 0.0
    d_out = 0.0
    free_placement = True
    no_lint = True

    def build(self) -> None:
        s, b = self.spec, self.brand
        W, H = self.ctx.W, self.ctx.H
        raw = s.get("words")
        if not isinstance(raw, list) or not raw or not all(isinstance(w, dict) and str(w.get("w", "")).strip() for w in raw):
            raise PlanError("Wiersz (typeline) wymaga listy words: [{w, t}].")
        self.items = [(str(w["w"]).strip(), float(w.get("t", 0.0))) for w in raw]
        em = float(s.get("size", LINE_EM)) * H
        role = s.get("font", "display")
        track_k = float(s.get("track", -0.03))
        max_w = float(s.get("max_width", LINE_MAX_W)) * W
        font = b.font(role, em)
        widths = [text_size(t, font, track_k * em)[0] for t, _ in self.items]
        widest = max(widths)
        if widest > max_w:  # pojedyncze słowo szersze niż pole: kurczymy krój
            em *= max_w / widest
            font = b.font(role, em)
            widths = [text_size(t, font, track_k * em)[0] for t, _ in self.items]
        self.space = LINE_SPACE * font.size
        self.rows: list[list[int]] = []
        cur: list[int] = []
        cur_w = 0.0
        for i, w in enumerate(widths):
            add = w + (self.space if cur else 0.0)
            if cur and cur_w + add > max_w:
                self.rows.append(cur)
                cur, cur_w = [i], w
            else:
                cur.append(i)
                cur_w += add
        self.rows.append(cur)
        marks = {int(k) for k in s.get("marks", [])}
        base_rgb, mark_rgb = b.rgb(s.get("color", "panel")), b.rgb(s.get("mark_color", s.get("color", "panel")))
        shadow = float(s.get("shadow", 0.0))
        self.sprites: list[tuple[object, float, float]] = []  # (obraz, linia bazowa w obrazie, przesunięcie x tekstu w obrazie)
        for i, (text, _) in enumerate(self.items):
            fill = tuple(mark_rgb if i in marks else base_rgb) + (255,)
            spr, base = text_sprite(text, font, fill, tracking=track_k * em, pad=4)
            ox = oy = 0
            if shadow > 0:
                spr, (ox, oy) = shadowed(spr, font.size * 0.05, shadow, dy=font.size * 0.02)
            self.sprites.append((spr, base + oy, 4 + ox))
        self.widths = widths
        asc, desc = font.getmetrics()
        self.lh = font.size * 1.12
        block_h = self.lh * (len(self.rows) - 1) + (asc + desc)
        self.cx = float(s.get("cx", 0.5)) * W
        if "y" in s:
            top = float(s["y"]) * H
        else:
            top = float(s.get("cy", 0.5)) * H - block_h / 2
        self.baseline0 = top + asc
        self.asc = asc
        self.cap = font.getbbox("H")[1]
        self.top = top
        self.font_size = font.size
        self.circle = bool(s.get("circle", False))
        if self.circle:
            times = sorted({t for _, t in self.items})
            self.circle_at = float(s.get("circle_at", times[1] if len(times) > 1 else times[0]))
            self.circle_dur = float(s.get("circle_dur", ELLIPSE_DUR))
            self.circle_rgb = b.rgb(s.get("circle_color", s.get("color", "panel")))

    def draw(self, layer: Layer, t: float) -> None:
        u = t - self.start
        x0 = x1 = y0 = y1 = None
        for r, row in enumerate(self.rows):
            vis = [i for i in row if u >= self.items[i][1] - 1e-6]
            if not vis:
                continue
            total = sum(self.widths[i] for i in vis) + self.space * (len(vis) - 1)
            x = self.cx - total / 2
            baseline = self.baseline0 + r * self.lh
            for i in vis:
                spr, base, off = self.sprites[i]
                layer.paste(spr, x - off, baseline - base)
                x += self.widths[i] + self.space
            lo, hi = self.cx - total / 2, self.cx + total / 2
            x0, x1 = (lo if x0 is None else min(x0, lo)), (hi if x1 is None else max(x1, hi))
            top = self.top + r * self.lh + self.cap
            bottom = self.top + r * self.lh + (self.baseline0 - self.top) + 0.22 * self.font_size
            y0, y1 = (top if y0 is None else min(y0, top)), (bottom if y1 is None else max(y1, bottom))
        if self.circle and x0 is not None:  # elipsa obejmuje tekst widoczny w tej chwili, więc rośnie razem z kolejnymi słowami
            draw_ellipse(layer, (x0, y0, x1, y1), self.ctx, u - self.circle_at, self.circle_dur, self.circle_rgb, seed=len(self.items))
