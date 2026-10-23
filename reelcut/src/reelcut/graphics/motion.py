"""Motion: schemat z kamerą jak w rolce wzorcowej, z lektorem zamiast mówiącej głowy.

Elementy: `backdrop` (papier z siatką kropek), `dial` (tarcza z piastą i szprychami: wzrost na szerokim ujęciu, cięcie na zbliżenie,
obroty o jedną szprychę, pisanie etykiet z blokiem-kursorem, cofnięcie kamery z tytułem), `cutaway` (plansza z napisami kinetycznymi
w trzech rozmiarach), `glint` (błysk na piaście) oraz napisy kinetyczne (wariant `captions` ze `style: kinetic`).

Liczby w stałych poniżej są zmierzone w rolce wzorcowej (klatki 720x1280, 30 kl./s) i podane jako ułamki szerokości kadru W,
chyba że napisano inaczej. Rysujemy z nadpróbkowaniem (SS) i redukcją pudełkową, tekst Pillow rysuje na końcu w docelowej wielkości.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from .core import Layer, PlanError, blur, clamp01, ease_out, ease_out_back, lerp, prog, text_size, text_sprite
from .elements import Element, register

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    pass

SS_DIAL = 2  # nadpróbkowanie geometrii tarczy (redukcja pudełkowa daje poprawne wygładzenie krawędzi)

# --- tło: papier z siatką kropek (rolka: #F4F4F4, siatka widoczna w eliptycznej winiecie) ---
GRID_PITCH = 0.0175  # odstęp kropek (system marki: 28 px przy 1600 px szerokości)
GRID_ALPHA = 0.16  # krycie kropek na papierze; system marki podaje 13% dla grafik statycznych, w filmie po kompresji trzeba trochę mocniej
GRID_ALPHA_DARK = 0.12  # na planszy ciemnej
VIGNETTE = (0.5, 0.37, 0.46, 0.40)  # środek x, y (ułamki kadru) i półosie (W, H) elipsy, w której kropki są widoczne

# --- kamera i tarcza (promień piasty R: ułamek W) ---
R_WIDE_BUILD = 0.156  # szeroko, po rozbudowie
R_WIDE_FINAL = 0.147  # szeroko, po finale
R_CLOSE = 0.345  # zbliżenie po osiadaniu
CY_WIDE = 0.520  # środek piasty (ułamek wysokości H)
CY_CLOSE = 0.884
CY_CUT = 0.93  # w pierwszej klatce zbliżenia piasta jest niżej i osiada do CY_CLOSE
CUT_SCALE = 0.907  # skala pierwszej klatki zbliżenia względem osiadłej
SETTLE_S = 0.22  # osiadanie po cięciu na zbliżenie (łagodzenie wyjściowe)
CUT_BLUR = 0.011  # rozmycie pierwszej klatki zbliżenia (ułamek W), znika w 0,16 s
FINAL_BLUR = 0.010  # rozmycie po cofnięciu kamery, znika w 0,8 s
DRIFT = 0.0078  # wolny najazd w zbliżeniu: +0,78% promienia na sekundę, także pod planszami
ROT_POW = 5.0  # obrót: łagodzenie wejściowe i wyjściowe o potędze 5 (ruch widoczny ok. 0,67 s, 10-90% w 0,36 s)
ROT_S = 1.2  # nominalny czas obrotu (połowa ruchu w środku tego czasu)
ROT_LEAD = 0.10  # połowa obrotu następuje tyle przed pierwszym znakiem etykiety
FINAL_ROT_POW, FINAL_ROT_S, FINAL_ROT_MID = 4.0, 1.0, 0.65  # ósmy obrót po finale: wraca szprycha startowa
TYPE_CPS = 18.0  # znaków na sekundę przy pisaniu etykiet
CURSOR_HOLD = 0.25  # cienki kursor po dopisaniu
LABEL_K = 0.25  # wielkość etykiet jako ułamek promienia piasty
LABEL_MIN_K = 0.15  # poniżej tego etykieta jest za drobna na telefonie (ok. 24 px przy szerokości 1080): zamiast kurczyć dalej, ostrzegamy
BUILD_MIN_S = 1.5  # krótsza rozbudowa na szerokim ujęciu wygląda jak błąd, a nie jak ruch kamery
HUB_MIN_K = 0.14  # najmniejszy sensowny rozmiar tekstu w piaście (ułamek promienia); krótszy tekst piasty jest po cofnięciu kamery nieczytelny
HUB_BUILD = ((0.0, 0.22), (0.03, 0.29), (0.07, 0.42), (0.10, 0.54), (0.13, 0.60), (0.17, 0.67), (0.2, 0.71), (0.27, 0.80), (0.5, 0.80), (0.9, 0.83),
             (1.0, 0.87), (1.2, 0.91), (1.5, 0.96), (2.0, 1.0))
SPOKE_START, SPOKE_STEP = 0.06, 0.055  # szprychy rosną po kolei zgodnie z ruchem wskazówek od góry (wszystkie osiem w 0,45 s)
SPOKE_GROW, DOT_AT, BAR_AT = 0.14, 0.09, 0.13  # czasy względem startu szprychy

# --- geometria tarczy w jednostkach promienia piasty R ---
HUB_IN = 0.88  # wewnętrzna cienka linia w piaście
RING = 1.10  # obrys zewnętrzny, z jego wierzchołków wychodzą szprychy
DOT_RADIUS_AT = 1.94  # środek kropki
DOT_R = 0.073
LINE_W = 0.0105  # grubość linii (nie mniej niż MIN_LINE_PX przy szerokości 1080)
MIN_LINE_PX = 2.2

# --- napisy kinetyczne (ułamki W) ---
TIER_CUT = {"small": ("semibold", 0.05), "big": ("display", 0.078), "tiny": ("semibold", 0.031)}
TIER_CAP = {"small": ("semibold", 0.055), "big": ("display", 0.088), "tiny": ("semibold", 0.034)}
CAP_Y = 0.255  # górna linia napisów na scenie ze schematem (ułamek H)
CUT_Y = 0.45  # środek bloku napisów na planszy (ułamek H)
CUT_X = 0.14  # lewa krawędź bloku na planszy


def measured() -> dict:
    """Zmierzone liczby do karty stylu i testów (te same, których używa silnik)."""
    return {
        "wide_hub_r": R_WIDE_BUILD, "wide_final_hub_r": R_WIDE_FINAL, "close_hub_r": R_CLOSE, "zoom_ratio": round(R_CLOSE / R_WIDE_FINAL, 2),
        "cut_scale": CUT_SCALE, "settle_s": SETTLE_S, "drift_per_s": DRIFT, "rotation_pow": ROT_POW, "rotation_nominal_s": ROT_S,
        "type_cps": TYPE_CPS, "spoke_step_s": SPOKE_STEP, "grid_pitch": GRID_PITCH,
    }


# ---------------------------------------------------------------------------------------------
# Łagodzenie i klatki kluczowe
# ---------------------------------------------------------------------------------------------

def ease_pow(x: float, p: float) -> float:
    """Łagodny start i koniec o potędze p (3 = sześcienne, 5 = ostre „quint”)."""
    x = clamp01(x)
    return 0.5 * (2 * x) ** p if x < 0.5 else 1 - 0.5 * (2 * (1 - x)) ** p


def keyed(points: tuple[tuple[float, float], ...], t: float) -> float:
    """Wartość z kluczy (czas, wartość) z łagodzeniem wyjściowym w każdym odcinku."""
    if t <= points[0][0]:
        return points[0][1]
    for (a, va), (b, vb) in zip(points[:-1], points[1:]):
        if t <= b:
            return lerp(va, vb, ease_out(prog(t, a, b - a)))
    return points[-1][1]


# ---------------------------------------------------------------------------------------------
# Tło
# ---------------------------------------------------------------------------------------------

def _smooth(x: float) -> float:
    x = clamp01(x)
    return x * x * (3 - 2 * x)


@lru_cache(maxsize=8)
def vignette_mask(size: tuple[int, int], center_x: float, center_y: float, rx: float, ry: float):
    """Maska „L”: 255 w środku elipsy, miękko do 0 na jej brzegu."""
    W, H = size
    g = Image.radial_gradient("L").resize((max(2, int(rx * W * 2)), max(2, int(ry * H * 2))), Image.BICUBIC)
    g = g.point([int(round(255 * (1 - _smooth((v / 255 - 0.30) / 0.70)))) for v in range(256)])
    mask = Image.new("L", size, 0)
    mask.paste(g, (int(center_x * W - rx * W), int(center_y * H - ry * H)))
    return mask


@lru_cache(maxsize=8)
def grid_mask(size: tuple[int, int], pitch: float):
    """Maska „L” z siatką kropek (wygładzone, 255 w środku kropki)."""
    W, H = size
    step = max(6.0, pitch * W)
    k = 3
    big = Image.new("L", (W * k, H * k), 0)
    d = ImageDraw.Draw(big)
    r = max(1.0, step * 0.075) * k
    y = step / 2
    while y < H:
        x = step / 2
        while x < W:
            d.ellipse([x * k - r, y * k - r, x * k + r, y * k + r], fill=255)
            x += step
        y += step
    return big.reduce(k)


@lru_cache(maxsize=8)
def paper_grid(size: tuple[int, int], bg: tuple, dot: tuple, alpha: float, pitch: float):
    """Nieprzezroczysty obraz RGBA: tło `bg` z siatką kropek `dot` w eliptycznej winiecie."""
    from PIL import ImageChops

    mask = ImageChops.multiply(grid_mask(size, pitch), vignette_mask(size, *VIGNETTE))
    mask = mask.point([int(round(v * alpha)) for v in range(256)])
    im = Image.new("RGBA", size, tuple(bg) + (255,))
    im.paste(Image.new("RGBA", size, tuple(dot) + (255,)), (0, 0), mask)
    return im


@register("backdrop")
class Backdrop(Element):
    """Tło całego filmu: papier z siatką kropek (dark: true to ciemna plansza). Pola: dark, grid (krycie kropek), pitch (odstęp, ułamek W)."""
    default_dur = 3600.0
    default_z = 0
    d_in = 0.0
    d_out = 0.0
    free_placement = True
    no_lint = True

    def build(self) -> None:
        s, b = self.spec, self.brand
        size = (self.ctx.W, self.ctx.H)
        dark = bool(s.get("dark", False))
        bg, dot = (b.rgb("ink"), b.rgb("paper")) if dark else (b.rgb("paper"), b.rgb("ink"))
        alpha = float(s.get("grid", GRID_ALPHA_DARK if dark else GRID_ALPHA))
        self.image = paper_grid(size, tuple(bg), tuple(dot), alpha, float(s.get("pitch", GRID_PITCH)))

    def draw(self, layer: Layer, t: float) -> None:
        layer.img.paste(self.image, (0, 0))


# ---------------------------------------------------------------------------------------------
# Napisy kinetyczne: słowa w trzech rozmiarach (small, big, tiny), pojawiające się po kolei
# ---------------------------------------------------------------------------------------------

@dataclass
class _Placed:
    sprite: object
    x: float
    y: float
    t0: float
    px: float


class KBlock:
    """Blok słów ułożony w wierszach: wiersz to kolejne słowa tego samego rozmiaru (tier). Słowo wchodzi w swojej chwili t0:
    rozmycie i wjazd od dołu w 0,16 s. Układ liczymy z góry dla wszystkich słów, więc nic się nie przesuwa, gdy dochodzą kolejne."""

    def __init__(self, brand, size: tuple[int, int], tokens: list[tuple[str, str, float]], *, x: float, y: float, align: str = "left",
                 tiers: dict | None = None, colors: dict | None = None, max_w: float = 0.74, valign: str = "center"):
        W, H = size
        tiers = tiers or TIER_CUT
        colors = colors or {}
        self.W, self.H = W, H
        fonts, px = {}, {}
        for tier, (role, frac) in tiers.items():
            px[tier] = frac * W
            fonts[tier] = brand.font(role, px[tier])
        gap = {t: 0.26 * px[t] for t in px}
        lines: list[dict] = []
        for text, tier, t0 in tokens:
            if tier not in fonts:
                raise PlanError(f"Napisy kinetyczne: nieznany rozmiar „{tier}” (small, big, tiny).")
            w = text_size(text, fonts[tier], -0.02 * px[tier])[0]
            cur = lines[-1] if lines else None
            if cur is None or cur["tier"] != tier or (cur["items"] and cur["w"] + gap[tier] + w > max_w * W):
                cur = {"tier": tier, "items": [], "w": 0.0}
                lines.append(cur)
            cur["w"] += (gap[tier] if cur["items"] else 0.0) + w
            cur["items"].append((text, w, t0))
        heights = [sum(fonts[ln["tier"]].getmetrics()) * 0.92 for ln in lines]
        line_gap = 0.012 * W
        total = sum(heights) + line_gap * max(0, len(lines) - 1)
        top = y * H - total / 2 if valign == "center" else (y * H - heights[0] / 2 if valign == "first" and heights else y * H)
        self.items: list[_Placed] = []
        self.height = total
        yy = top
        prev_right = None
        for ln, lh in zip(lines, heights):
            tier = ln["tier"]
            if align == "center":
                x0 = x * W - ln["w"] / 2
            elif tier == "tiny" and prev_right is not None:
                x0 = prev_right - ln["w"]  # dopisek: do prawej krawędzi poprzedniego wiersza
            else:
                x0 = x * W
            cx = x0
            col = colors.get(tier, brand.rgb("paper"))
            for text, w, t0 in ln["items"]:
                pad = int(0.2 * px[tier]) + 2
                sprite, base = text_sprite(text, fonts[tier], tuple(col) + (255,), tracking=-0.02 * px[tier], pad=pad)
                self.items.append(_Placed(sprite, cx - pad, yy - pad - 0.04 * px[tier], t0, px[tier]))
                cx += w + gap[tier]
            prev_right = x0 + ln["w"]
            yy += lh + line_gap

    def draw(self, layer: Layer, t: float, alpha: float = 1.0, dy: float = 0.0) -> None:
        for it in self.items:
            u = t - it.t0
            if u < 0:
                continue
            k = ease_out(clamp01(u / 0.16))
            a = clamp01(u / 0.07) * alpha
            sprite = it.sprite
            r = (1 - k) * 0.16 * it.px
            if r > 0.6:
                sprite = blur(sprite, r)
            layer.paste(sprite, it.x, it.y + dy + (1 - k) * 0.18 * it.px, a)


# ---------------------------------------------------------------------------------------------
# Plansza (czarna karta z napisami między ujęciami schematu)
# ---------------------------------------------------------------------------------------------

def words_in(ctx, start: float, end: float) -> list:
    """Słowa mowy rozpoczęte w oknie [start, end) na osi gotowego filmu."""
    return [w for w in ctx.words if start - 1e-6 <= float(w.start) < end]


def in_ranges(t: float, ranges) -> bool:
    return any(float(a) - 1e-6 <= t <= float(b) + 1e-6 for a, b in ranges)


@register("cutaway")
class Cutaway(Element):
    """Plansza na całym kadrze (ciemny papier z siatką), twarde cięcie wejścia i wyjścia. Słowa z mowy w oknie planszy wchodzą po kolei:
    zwykłe małym krojem, wyróżnione dużym (żółtym). Pola: emphasis [[od, do], ...] (sekundy), text (tekst z *wyróżnieniem*, gdy nie ma mowy),
    words [{w, t, tier}] (własne słowa i rozmiary: small, big, tiny), align (left|center), x, y (ułamki kadru)."""
    default_dur = 2.0
    default_z = 20
    d_in = 0.0
    d_out = 0.0
    free_placement = True
    no_lint = True

    def build(self) -> None:
        s, b = self.spec, self.brand
        size = (self.ctx.W, self.ctx.H)
        emph = [tuple(map(float, r)) for r in s.get("emphasis", [])]
        tokens: list[tuple[str, str, float]] = []
        if s.get("words"):
            for w in s["words"]:
                tokens.append((str(w["w"]), str(w.get("tier", "small")), self.start + float(w.get("t", 0.0))))
        else:
            spoken = words_in(self.ctx, self.start, self.end)
            if spoken:
                for w in spoken:
                    mid = (float(w.start) + float(w.end)) / 2
                    tokens.append((str(w.text), "big" if in_ranges(mid, emph) else "small", float(w.start)))
            elif s.get("text"):  # bez mowy: słowa z pola text rozłożone równo w czasie planszy
                parts, big = [], False
                for chunk in str(s["text"]).split("*"):
                    parts += [(wd, big) for wd in chunk.split()]
                    big = not big
                step = self.dur * 0.8 / max(1, len(parts))
                tokens = [(wd, "big" if bg else "small", self.start + 0.1 + i * step) for i, (wd, bg) in enumerate(parts)]
            else:
                self.notes.append("plansza nie ma słów: nie znalazłem mowy w jej oknie (czy jest transkrypcja?) ani pola text.")
        self.backdrop = paper_grid(size, tuple(b.rgb("ink")), tuple(b.rgb("paper")), GRID_ALPHA_DARK, GRID_PITCH)
        colors = {"small": b.rgb("paper"), "big": b.rgb(s.get("big_color", "highlight")), "tiny": b.rgb("paper")}
        self.block = KBlock(b, size, tokens, x=float(s.get("x", CUT_X if s.get("align", "left") == "left" else 0.5)),
                            y=float(s.get("y", CUT_Y)), align=s.get("align", "left"), tiers=TIER_CUT, colors=colors) if tokens else None

    def draw(self, layer: Layer, t: float) -> None:
        layer.img.paste(self.backdrop, (0, 0))
        if self.block:
            self.block.draw(layer, t)


# ---------------------------------------------------------------------------------------------
# Tarcza: piasta z szprychami, obroty, pisanie etykiet, kamera
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Cam:
    R: float  # promień piasty w pikselach
    cx: float  # środek piasty w pikselach
    cy: float
    blur: float  # rozmycie całej sceny w pikselach (cięcie na zbliżenie i cofnięcie kamery)
    phase: str  # build (szeroko, rozbudowa) | close (zbliżenie) | final (szeroko po finale)
    u: float  # sekundy od początku fazy


def _polygon(cx: float, cy: float, r: float, angles: list[float]) -> list[tuple[float, float]]:
    return [(cx + r * math.sin(math.radians(a)), cy - r * math.cos(math.radians(a))) for a in angles]


@register("dial")
class Dial(Element):
    """Tarcza schematu jak w rolce wzorcowej. Pola: hub [mały wiersz, duży wiersz] (albo sam tekst), steps [{label, at}] (od 2 do 12 szprych;
    `at` to chwila, w której mówisz hasło: wtedy tarcza obraca się do tej szprychy i etykieta się wpisuje), closeup_at (cięcie na zbliżenie,
    domyślnie 0,3 s przed pierwszym hasłem), finale {at, title} (cofnięcie kamery: widać cały schemat i tytuł), cps (znaków na sekundę),
    drift (najazd w zbliżeniu na sekundę), label_k (wielkość etykiet jako ułamek promienia piasty)."""
    default_dur = 3600.0
    default_z = 2
    d_in = 0.0
    d_out = 0.0
    free_placement = True
    no_lint = True

    def build(self) -> None:
        s, b = self.spec, self.brand
        steps = s.get("steps")
        if not isinstance(steps, list) or len(steps) < 2:
            raise PlanError("Tarcza (dial) wymaga listy steps: co najmniej dwie szprychy [{label, at}].")
        if len(steps) > 12:
            raise PlanError("Tarcza ma najwyżej 12 szprych (przy większej liczbie etykiety się zlewają).")
        self.labels: list[str] = []
        self.at: list[float] = []
        for i, st in enumerate(steps, 1):
            if not isinstance(st, dict) or not str(st.get("label", "")).strip() or "at" not in st:
                raise PlanError(f"Krok {i} tarczy: wymagane pola label i at.")
            self.labels.append(str(st["label"]).strip())
            self.at.append(float(st["at"]))
        for a, c in zip(self.at[:-1], self.at[1:]):
            if c <= a:
                raise PlanError("Czasy kroków tarczy (at) muszą rosnąć.")
        tight = [f"„{self.labels[i + 1]}” ({self.at[i + 1] - self.at[i]:.1f} s po poprzednim)" for i in range(len(self.at) - 1)
                 if self.at[i + 1] - self.at[i] < 1.0]
        if tight:
            self.notes.append("kroki bliżej niż 1 s od poprzedniego, obrót się nie zmieści: " + ", ".join(tight[:3]))
        self.n = len(self.labels)
        self.delta = 360.0 / self.n
        hub = s.get("hub", ["", ""])
        if isinstance(hub, str):
            hub = ["", hub]
        self.hub_small, self.hub_big = (str(hub[0]), str(hub[1])) if len(hub) >= 2 else ("", str(hub[0]))
        if self.hub_big:
            w100 = text_size(self.hub_big, b.font("display", 100), -2.0)[0]
            fit = 1.36 * 100.0 / max(1.0, w100)  # największy rozmiar tekstu (ułamek promienia), przy którym mieści się w piaście
            if fit < HUB_MIN_K:
                self.notes.append(f"tekst piasty „{self.hub_big}” jest za długi i po cofnięciu kamery będzie drobny: "
                                  f"skróć go do ok. {int(len(self.hub_big) * fit / HUB_MIN_K)} znaków.")
        self.closeup_at = float(s.get("closeup_at", max(self.start, self.at[0] - 0.3)))
        if self.closeup_at < self.start:
            raise PlanError("closeup_at jest przed startem tarczy.")
        if self.closeup_at > self.at[0]:
            raise PlanError("closeup_at jest po pierwszym kroku: kamera musi najechać, zanim wpisze się pierwsza etykieta.")
        if self.closeup_at - self.start < BUILD_MIN_S:
            self.notes.append(f"pierwszy krok pada {self.at[0] - self.start:.1f} s po starcie tarczy, więc rozbudowa na szerokim ujęciu "
                              f"(ok. {HUB_BUILD[-1][0]:.0f} s) zostanie ucięta: dodaj przed nim zdanie wstępne (ok. {HUB_BUILD[-1][0] + 0.3:.1f} s mowy).")
        fin = s.get("finale")
        self.finale_at: float | None = None
        self.title = ""
        if fin:
            self.finale_at = float(fin["at"])
            self.title = str(fin.get("title", ""))
            if self.finale_at <= self.at[-1] + 0.2:
                raise PlanError("finale.at musi być po ostatnim kroku tarczy.")
        self.cps = float(s.get("cps", TYPE_CPS))
        self.drift = float(s.get("drift", DRIFT))
        self.ink, self.paper = b.rgb("ink"), b.rgb("paper")
        self.violet, self.yellow = b.rgb("violet"), b.rgb("highlight")
        W = self.ctx.W
        # wielkość etykiet: taka, by każda mieściła się w kadrze: w zbliżeniu nad kropką (92% szerokości) i po finale (szeroko) przy szprychach
        # z boku, aż do krawędzi kadru; najmniejszy sensowny rozmiar to LABEL_MIN_K, dłuższe etykiety dostają ostrzeżenie
        ratio = float(s.get("label_k", LABEL_K))
        f100 = b.font("semibold", 100)
        r_fin = R_WIDE_FINAL * W
        limits: list[tuple[str, float]] = []
        for i, label in enumerate(self.labels):
            w100 = text_size(label, f100, -2.0)[0]
            if w100 <= 0:
                continue
            limit = 0.92 * 100.0 / (w100 * R_CLOSE)
            sin_a = abs(math.sin(math.radians(i * self.delta)))
            if sin_a > 0.3:
                avail = 0.47 * W - DOT_RADIUS_AT * r_fin * sin_a - 0.16 * r_fin
                limit = min(limit, avail * 100.0 / w100 / r_fin) if avail > 0 else 0.0
            limits.append((label, limit))
            ratio = min(ratio, limit)
        self.label_k = max(LABEL_MIN_K, ratio)
        too_long = [f"„{label}” (do ok. {int(len(label) * limit / LABEL_MIN_K)} znaków)" for label, limit in limits if limit < LABEL_MIN_K - 1e-9]
        if too_long:
            self.notes.append("etykieta za długa, wychodzi poza kadr albo jest za drobna do czytania: skróć ją: " + ", ".join(too_long[:3]))

    # --- czas ---
    def camera(self, t: float, W: int, H: int) -> Cam:
        if self.finale_at is not None and t >= self.finale_at:
            u = t - self.finale_at
            k = ease_out(clamp01(u / 0.7))
            return Cam(R_WIDE_FINAL * W * lerp(0.955, 1.0, k), 0.5 * W, CY_WIDE * H,
                       FINAL_BLUR * W * (1 - ease_out(clamp01(u / 0.8))), "final", u)
        if t >= self.closeup_at:
            u = t - self.closeup_at
            k = ease_out(clamp01(u / SETTLE_S))
            drift = 1.0 + self.drift * max(0.0, u - SETTLE_S)
            return Cam(R_CLOSE * W * lerp(CUT_SCALE, 1.0, k) * drift, 0.5 * W, H * lerp(CY_CUT, CY_CLOSE, k),
                       CUT_BLUR * W * (1 - ease_out(clamp01(u / 0.16))), "close", u)
        u = max(0.0, t - self.start)
        return Cam(R_WIDE_BUILD * W * keyed(HUB_BUILD, u), 0.5 * W, CY_WIDE * H, 0.0, "build", u)

    def angle(self, t: float) -> float:
        """Obrót tarczy w stopniach przeciwnie do ruchu wskazówek: jedna szprycha na krok, a po finale ósmy obrót, który zamyka okrąg."""
        th = 0.0
        for i in range(1, self.n):
            mid = self.at[i] - ROT_LEAD
            th += self.delta * ease_pow((t - (mid - ROT_S / 2)) / ROT_S, ROT_POW)
        if self.finale_at is not None:
            mid = self.finale_at + FINAL_ROT_MID
            th += self.delta * ease_pow((t - (mid - FINAL_ROT_S / 2)) / FINAL_ROT_S, FINAL_ROT_POW)
        return th

    def typed(self, k: int, t: float) -> float:
        """Ile etykiety k jest już wpisane (0-1)."""
        if self.finale_at is not None and t >= self.finale_at:
            return 1.0
        return clamp01((t - self.at[k]) * self.cps / max(1, len(self.labels[k])))

    def active(self, t: float) -> bool:
        return self.start - 1e-6 <= t <= self.end + 1e-6

    # --- rysowanie ---
    def draw(self, layer: Layer, t: float) -> None:
        W, H = layer.size
        cam = self.camera(t, W, H)
        if cam.blur > 0.4:
            tmp = Layer((W, H))
            self._scene(tmp, t, cam)
            layer.img.alpha_composite(blur(tmp.img, cam.blur))
        else:
            self._scene(layer, t, cam)

    def _build_state(self, k: int, t: float, cam: Cam) -> tuple[float, float, float]:
        """(wysunięcie szprychy, kropka, pasek) w rozbudowie na szerokim ujęciu; później wszystko jest gotowe."""
        if cam.phase != "build":
            return 1.0, 1.0, 1.0
        u = cam.u
        u_k = SPOKE_START + SPOKE_STEP * k
        return (ease_out(prog(u, u_k, SPOKE_GROW)), ease_out_back(prog(u, u_k + DOT_AT, 0.10), 2.0),
                ease_out(prog(u, u_k + BAR_AT, 0.10)))

    def _label_geometry(self, phi: float, dot: tuple[float, float], R: float, w: float, h: float) -> tuple[float, float, str]:
        """Lewy górny róg ramki etykiety i wyrównanie (left | right | center) zależnie od kierunku szprychy."""
        s, c = math.sin(math.radians(phi)), math.cos(math.radians(phi))
        dx, dy = dot
        if abs(s) < 0.3:  # góra albo dół: wyśrodkowana nad albo pod kropką
            y = dy - 0.22 * R - h if c > 0 else dy + 0.22 * R
            return dx - w / 2, y, "center"
        if abs(c) < 0.3:  # z boku: obok kropki, na jej wysokości
            return (dx + 0.13 * R, dy - h / 2, "left") if s > 0 else (dx - 0.13 * R - w, dy - h / 2, "right")
        if c > 0:  # ukośnie w górę: nad kropką, wysunięta na zewnątrz
            return (dx - 0.1 * R, dy - 0.26 * R - h / 2, "left") if s > 0 else (dx + 0.1 * R - w, dy - 0.26 * R - h / 2, "right")
        return (dx + 0.2 * R - w / 2, dy + 0.24 * R - h / 2, "center") if s > 0 else (dx - 0.2 * R - w / 2, dy + 0.24 * R - h / 2, "center")

    def _scene(self, layer: Layer, t: float, cam: Cam) -> None:
        W, H = layer.size
        R, cx, cy = cam.R, cam.cx, cam.cy
        theta = self.angle(t)
        n, delta = self.n, self.delta
        label_px = max(self.label_k * R, 0.0)
        font = self.brand.font("semibold", label_px) if label_px >= 4 else None
        asc, desc = font.getmetrics() if font else (0, 0)
        h_box = asc + desc
        lw = max(MIN_LINE_PX * W / 1080.0, LINE_W * R)
        ink, paper, violet, yellow = self.ink, self.paper, self.violet, self.yellow
        active_k = max([k for k in range(n) if self.at[k] <= t] or [0]) if cam.phase == "close" else -1
        spokes = []
        wmax = 0.0
        for k in range(n):
            phi = k * delta - theta
            ext, dot_k, bar_k = self._build_state(k, t, cam)
            u = (math.sin(math.radians(phi)), -math.cos(math.radians(phi)))
            end_r = lerp(RING, DOT_RADIUS_AT, ext)
            dot = (cx + u[0] * DOT_RADIUS_AT * R, cy + u[1] * DOT_RADIUS_AT * R)
            w = text_size(self.labels[k], font, -0.02 * label_px)[0] if font else 0.0
            wmax = max(wmax, w)
            spokes.append({"k": k, "phi": phi, "u": u, "end_r": end_r, "dot": dot, "dot_k": dot_k, "bar_k": bar_k, "w": w})
        # obszar rysowania geometrii: piasta ze szprychami i etykietami, przycięty do kadru
        m = DOT_RADIUS_AT * R + wmax + 0.6 * R + 8
        x0, y0 = int(max(0, cx - m)), int(max(0, cy - m))
        x1, y1 = int(min(W, cx + m)) + 1, int(min(H, cy + m)) + 1
        if x1 <= x0 or y1 <= y0:
            return
        S = SS_DIAL
        canvas = Image.new("RGBA", ((x1 - x0) * S, (y1 - y0) * S), tuple(ink) + (0,))
        d = ImageDraw.Draw(canvas)

        def P(p):
            return ((p[0] - x0) * S, (p[1] - y0) * S)

        vertex_angles = [sp["phi"] for sp in spokes]
        ring_a = clamp01(prog(cam.u, 0.9, 0.3)) if cam.phase == "build" else 1.0
        ring_pts = [P(p) for p in _polygon(cx, cy, RING * R, vertex_angles)]
        if ring_a > 0.02:
            d.line(ring_pts + [ring_pts[0]], fill=tuple(violet) + (int(255 * ring_a),), width=max(1, int(lw * 0.9 * S)), joint="curve")
        hub_pts = [P(p) for p in _polygon(cx, cy, R, vertex_angles)]
        d.polygon(hub_pts, fill=tuple(ink) + (255,))
        inner = [P(p) for p in _polygon(cx, cy, HUB_IN * R, vertex_angles)]
        d.line(inner + [inner[0]], fill=tuple(violet) + (200,), width=max(1, int(lw * 0.8 * S)), joint="curve")
        for sp in spokes:
            if sp["end_r"] > RING + 0.01:
                a = P((cx + sp["u"][0] * RING * R, cy + sp["u"][1] * RING * R))
                b = P((cx + sp["u"][0] * sp["end_r"] * R, cy + sp["u"][1] * sp["end_r"] * R))
                d.line([a, b], fill=tuple(ink) + (255,), width=max(1, int(lw * S)))
            if sp["dot_k"] > 0.02:
                r = DOT_R * R * sp["dot_k"]
                px, py = P(sp["dot"])
                d.ellipse([px - r * S, py - r * S, px + r * S, py + r * S], fill=tuple(ink) + (255,))
                if sp["k"] == active_k:  # aktywna szprycha: żółta kropka w tuszowym kółku (jedyny akcent)
                    r2 = r * 0.58
                    d.ellipse([px - r2 * S, py - r2 * S, px + r2 * S, py + r2 * S], fill=tuple(yellow) + (255,))
        # paski (miejsca na etykiety) i kursor pisania
        texts = []
        if font:
            for sp in spokes:
                k = sp["k"]
                if sp["bar_k"] <= 0.02 and self.typed(k, t) <= 0:
                    continue
                w = sp["w"]
                bx, by, align = self._label_geometry(sp["phi"], sp["dot"], R, w, h_box)
                if bx > W + 4 or bx + w < -4 or by > H + 4 or by + h_box < -4:
                    continue
                p = self.typed(k, t)
                mid_y = by + h_box / 2
                bar_h = 0.9 * label_px
                if p <= 0:  # jeszcze nie wpisana: pełny pasek rośnie od strony kropki
                    bw = w * sp["bar_k"]
                    bxs = bx if align == "left" else (bx + w - bw if align == "right" else bx + (w - bw) / 2)
                    d.rectangle([P((bxs, mid_y - bar_h / 2)), P((bxs + bw, mid_y + bar_h / 2))], fill=tuple(ink) + (255,))
                    continue
                lab = self.labels[k]
                shown = p * len(lab)
                whole = int(shown)
                reveal = (font.getlength(lab[:whole]) if whole else 0.0) + (shown - whole) * (font.getlength(lab[:whole + 1]) - font.getlength(lab[:whole])
                                                                                            if whole < len(lab) else 0.0)
                reveal = min(w, reveal)
                if p < 1.0:  # blok-kursor przesuwa się za wpisanym tekstem i kurczy z szerokości reszty do szerokości znaku
                    cur_w = max(0.5 * label_px, (w - reveal) * (1 - p) ** 1.5)
                    d.rectangle([P((bx + reveal, mid_y - bar_h / 2)), P((bx + reveal + cur_w, mid_y + bar_h / 2))], fill=tuple(ink) + (255,))
                elif t < self.at[k] + len(lab) / self.cps + CURSOR_HOLD and cam.phase == "close":
                    d.rectangle([P((bx + w + 0.04 * label_px, mid_y - 0.45 * label_px)), P((bx + w + 0.11 * label_px, mid_y + 0.45 * label_px))],
                                fill=tuple(ink) + (255,))
                texts.append((lab, bx, by, reveal, p))
        layer.img.alpha_composite(canvas.reduce(S), (x0, y0))
        # napisy: piasta, etykiety, tytuł
        self._hub_text(layer, cx, cy, R)
        if font:
            for lab, bx, by, reveal, p in texts:
                sprite, _ = text_sprite(lab, font, tuple(ink) + (255,), tracking=-0.02 * label_px, pad=0)
                if p < 1.0:
                    sprite = sprite.crop((0, 0, max(1, int(math.ceil(reveal))), sprite.size[1]))
                layer.paste(sprite, bx, by)
        if cam.phase == "final" and self.title:
            tf = self.brand.font("display", 0.047 * W)
            sprite, _ = text_sprite(self.title, tf, tuple(ink) + (255,), tracking=-0.02 * 0.047 * W, pad=4)
            layer.paste(sprite, 0.5 * W - sprite.size[0] / 2, 0.24 * H - sprite.size[1] / 2)

    def _hub_text(self, layer: Layer, cx: float, cy: float, R: float) -> None:
        b = self.brand
        paper = self.paper
        big, small = self.hub_big, self.hub_small
        if not (big or small):
            return
        px_big = 0.285 * R
        f100 = b.font("display", 100)
        if big:
            w100 = text_size(big, f100, -2.0)[0]
            px_big = min(px_big, 1.36 * R * 100.0 / max(1.0, w100))
        px_small = 0.55 * min(0.265 * R, px_big * 1.3)
        if small:
            fs100 = b.font("semibold", 100)
            w100 = text_size(small, fs100, -1.0)[0]
            px_small = min(px_small, 1.2 * R * 100.0 / max(1.0, w100))
        if px_big < 4:
            return
        if small and px_small >= 3:
            sprite, _ = text_sprite(small, b.font("semibold", px_small), tuple(paper) + (255,), tracking=-0.01 * px_small, pad=0)
            layer.paste(sprite, cx - sprite.size[0] / 2, cy - 0.11 * R - sprite.size[1] / 2)
        if big:
            sprite, _ = text_sprite(big, b.font("display", px_big), tuple(paper) + (255,), tracking=-0.02 * px_big, pad=0)
            layer.paste(sprite, cx - sprite.size[0] / 2, cy + 0.08 * R - sprite.size[1] / 2)


# ---------------------------------------------------------------------------------------------
# Napisy kinetyczne na scenie ze schematem (wariant elementu captions)
# ---------------------------------------------------------------------------------------------

@dataclass
class _Unit:
    tokens: list
    start: float
    end: float
    block: object = None


@register("captions", style="kinetic")
class KineticCaptions(Element):
    """Napisy słowo po słowie jak w rolce wzorcowej: 1-2 słowa małym krojem w górnej części kadru, wjeżdżają z dołu z lekkim rozmyciem.
    Frazy wyróżnione (pole emphasis: [[od, do], ...] w sekundach, w scenariuszu to `*fraza*`) wchodzą dużym krojem w wierszu pod małymi
    słowami, które je poprzedzają. Pola: max_words (domyślnie 2), y (środek pierwszego wiersza, ułamek H), hold (sekundy po ostatnim słowie),
    shift [{at, dur, y}] (w tych oknach napisy stoją na innej wysokości), from_script (napisy ze słów scenariusza: ustawia szablon)."""
    default_dur = 0.0
    default_z = 9
    d_in = 0.0
    d_out = 0.0
    free_placement = True
    no_lint = True

    def __init__(self, spec: dict, ctx):
        spec = dict(spec)
        spec.setdefault("at", 0.0)
        spec.setdefault("dur", getattr(ctx, "duration", 0.0) or 1.0)
        super().__init__(spec, ctx)

    def build(self) -> None:
        from .. import captions as cap

        s, b = self.spec, self.brand
        size = (self.ctx.W, self.ctx.H)
        words = list(getattr(self.ctx, "words", []) or [])
        emph = [tuple(map(float, r)) for r in s.get("emphasis", [])]
        max_words = int(s.get("max_words", 2))
        segments: list[tuple[str, list]] = []
        i, n = 0, len(words)
        mid = lambda w: (float(w.start) + float(w.end)) / 2  # noqa: E731
        while i < n:
            big = in_ranges(mid(words[i]), emph)
            j = i
            while j < n and in_ranges(mid(words[j]), emph) == big:
                j += 1
            if big:
                segments.append(("big", words[i:j]))
            else:
                segments += [("small", list(g.words)) for g in cap.group_words(words[i:j], max_words, int(s.get("short_max", 3)))]
            i = j
        hold = float(s.get("hold", 0.25))
        units: list[_Unit] = []
        for tier, ws in segments:
            toks = [(str(w.text), tier, float(w.start)) for w in ws]
            start, end = float(ws[0].start), float(ws[-1].end)
            if tier == "big" and units and len(units[-1].tokens) and units[-1].tokens[0][1] == "small" and start - units[-1].end <= 0.25:
                units[-1].tokens += toks  # wyróżniona fraza pod małymi słowami, które ją poprzedzają
                units[-1].end = end
            else:
                units.append(_Unit(toks, start, end))
        for k, u in enumerate(units):
            nxt = units[k + 1].start if k + 1 < len(units) else float("inf")
            u.end = min(u.end + hold + (0.1 if any(t[1] == "big" for t in u.tokens) else 0.0), nxt)
        ink = b.rgb("ink")
        colors = {"small": ink, "big": ink, "tiny": ink}
        y = float(s.get("y", CAP_Y))
        shifts = [(float(w["at"]), float(w["at"]) + float(w["dur"]), float(w["y"])) for w in s.get("shift", [])]
        for u in units:
            yy = next((sy for a, e, sy in shifts if a <= u.start < e), y)  # po finale napisy schodzą pod schemat
            u.block = KBlock(b, size, u.tokens, x=0.5, y=yy, align="center", tiers=TIER_CAP, colors=colors, valign="first", max_w=0.84)
        self.units = units
        self.starts = [u.start for u in units]
        self.dur = max([self.dur] + [u.end for u in units])

    def active(self, t: float) -> bool:
        return bool(self.units)

    def draw(self, layer: Layer, t: float) -> None:
        import bisect

        i = bisect.bisect_right(self.starts, t + 1e-6) - 1  # bez wyprzedzenia: nowa grupa wchodzi dopiero w swoim słowie, a do tej chwili stoi poprzednia
        if i < 0:
            return
        u = self.units[i]
        if t > u.end:
            return
        k = ease_out(clamp01((t - u.start) / 0.30))
        u.block.draw(layer, t, dy=(1 - k) * 0.02 * layer.size[1])


# ---------------------------------------------------------------------------------------------
# Błysk na piaście
# ---------------------------------------------------------------------------------------------

@register("glint")
class Glint(Element):
    """Krótki jasny błysk (miękka plama z poziomą smugą) w wyznaczonym miejscu, np. na piaście przy ważnym słowie. Pola: x, y (środek,
    ułamki kadru; domyślnie piasta na szerokim ujęciu), w (szerokość, ułamek W), dur (domyślnie 0,2 s), strength (0-1)."""
    default_dur = 0.2
    default_z = 6
    d_in = 0.0
    d_out = 0.0
    free_placement = True
    no_lint = True
    thin = True

    def draw(self, layer: Layer, t: float) -> None:
        s = self.spec
        W, H = layer.size
        u = clamp01((t - self.start) / self.dur)
        a = (u / 0.35 if u < 0.35 else (1 - u) / 0.65) * float(s.get("strength", 0.9))
        if a <= 0.01:
            return
        w = float(s.get("w", 0.20)) * W
        h = w * 0.34
        pad = int(w * 0.35)
        sprite = Image.new("RGBA", (int(w) + 2 * pad, int(h) + 2 * pad), tuple(self.brand.rgb("paper")) + (0,))
        d = ImageDraw.Draw(sprite)
        d.ellipse([pad, pad, pad + w, pad + h], fill=tuple(self.brand.rgb("paper")) + (255,))
        d.rectangle([pad - w * 0.15, pad + h * 0.42, pad + w * 1.15, pad + h * 0.58], fill=tuple(self.brand.rgb("paper")) + (255,))
        sprite = blur(sprite, w * 0.07)
        layer.paste(sprite, float(s.get("x", 0.5)) * W - sprite.size[0] / 2, float(s.get("y", CY_WIDE)) * H - sprite.size[1] / 2, a)
