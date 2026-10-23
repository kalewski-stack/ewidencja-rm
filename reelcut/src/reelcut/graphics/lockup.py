"""Hasło (lockup): kilka wierszy napisów w jednym bloku, wyjustowanych do wspólnej szerokości, słowa wskakują w chwili, gdy padają.

Konstrukcja z rolki wzorcowej „gadająca głowa wersja 3” (DcS25CKkmFM): wiersz małych słów (lekki krój, rozstrzelone odstępy), pod nim jedno
duże słowo kluczowe (we wzorcu gruby szeryf, tu domyślnie Instrument Serif Italic z marki), pod nim znów mały wiersz. Układ liczymy z góry,
więc słowa wchodzą na swoje miejsca i nic się nie przesuwa;
każde słowo pojawia się od razu, bez animacji (we wzorcu tak jest: jedna klatka, zero rozmycia i wjazdu). Hasło zastępuje zwykłe napisy
na czas swojego trwania (robi to szablon: słowa hasła znikają z napisów).

Liczby ze wzorca (ułamki wysokości kadru H i szerokości W): duże słowo 0,101 H (wielkość kroju), małe wiersze 0,44 jego wielkości,
blok zaczyna się na 48,6% wysokości (tuż nad miejscem zwykłych napisów), szerokość bloku = szerokość dużego słowa (0,57 W dla „biggest”),
najwyżej 0,78 W, a przy dłuższym haśle duże słowo się zmniejsza.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .core import Layer, PlanError, shadowed, text_size, text_sprite
from .elements import Element, register

BIG_EM = 0.101  # wielkość kroju dużego słowa (ułamek H)
SMALL_RATIO = 0.44  # małe wiersze względem dużego słowa
MAX_W = 0.78  # największa szerokość bloku (ułamek W)
TOP = 0.486  # górna krawędź wersalików pierwszego wiersza (ułamek H)
HOLD = 0.25  # hasło zostaje tyle po ostatnim słowie
MIN_STRETCH = 0.55  # pojedyncze małe słowo rozstrzeliwamy do szerokości bloku, gdy ma co najmniej tyle jego szerokości
MAX_TRACK = 0.40  # największe rozstrzelenie liter (ułamek wielkości kroju)
MIN_SMALL_SCALE = 0.7  # o tyle najwyżej kurczymy małe słowa, gdy wiersz nie mieści się w bloku
SPACE = 0.38  # naturalny odstęp między małymi słowami (ułamek wielkości kroju): blok nie jest węższy niż wiersz z takimi odstępami
MIN_GAP = 0.12  # najmniejszy odstęp w kurczonym wierszu
PRE_WORDS = 3  # tyle słów przed słowem kluczowym trafia do małego wiersza nad nim (w obrębie zdania)
POST_WORDS = 3  # i tyle za nim
BIG_WORDS = 2  # duży wiersz to jedno albo dwa słowa
MAX_GAP_S = 0.45  # dłuższa pauza w mowie kończy hasło
LEAD_S = 0.04  # słowo pojawia się tyle przed początkiem mowy (tak samo jak napisy)
MIN_VISIBLE_S = 0.25  # ostatnie małe słowo hasła musi być widoczne co najmniej tyle; krótsze (po nim od razu mowa) hasło odpuszcza
SENTENCE_END = (".", "?", "!", "…", ":", ";")
DROP = 0.20  # następny wiersz zaczyna się nie wyżej niż tyle wielkości kroju pod linią pisma (albo pod ogonkami liter, gdy są niżej)
SERIF_BOOST = 1.3  # kroje szeryfowe (nazwa pliku zawiera „serif”) są węższe od groteski: dla podobnej masy wizualnej duże słowo jest o tyle większe


@dataclass
class _Word:
    sprite: object
    x: float
    y: float
    t: float


@register("lockup")
class Lockup(Element):
    """Hasło z wierszy [{words: [{w, t}], tier: small|big}]: `t` to sekundy od początku elementu, w których słowo wskakuje. Pola: color (rola
    koloru dużych słów, domyślnie highlight), small_color (domyślnie text), y (górna krawędź, ułamek H), size (wielkość dużego słowa, ułamek H),
    max_width (ułamek W), big_font (krój dużych słów, domyślnie serif_italic; display daje grubą groteskę) i small_font (domyślnie text)."""
    default_dur = 2.0
    default_z = 12
    d_in = 0.0
    d_out = 0.0
    free_placement = True
    no_lint = True

    def __init__(self, spec: dict, ctx):
        spec = dict(spec)
        lines = spec.get("lines")
        if isinstance(lines, list) and lines and "dur" not in spec:
            last = max((float(w.get("t", 0.0)) for ln in lines if isinstance(ln, dict) for w in ln.get("words", []) if isinstance(w, dict)), default=0.0)
            spec["dur"] = last + HOLD + 0.3
        super().__init__(spec, ctx)

    @staticmethod
    def _parse(lines) -> list[tuple[str, list[tuple[str, float]]]]:
        if not isinstance(lines, list) or not lines:
            raise PlanError("Hasło (lockup) wymaga listy lines: [{words: [{w, t}], tier: small albo big}].")
        parsed: list[tuple[str, list[tuple[str, float]]]] = []
        for i, ln in enumerate(lines, 1):
            if not isinstance(ln, dict) or not ln.get("words"):
                raise PlanError(f"Wiersz {i} hasła: wymagane words [{{w, t}}].")
            tier = str(ln.get("tier", "small"))
            if tier not in ("small", "big"):
                raise PlanError(f"Wiersz {i} hasła: tier to small albo big.")
            words = []
            for w in ln["words"]:
                if not isinstance(w, dict) or not str(w.get("w", "")).strip():
                    raise PlanError(f"Wiersz {i} hasła: każde słowo to {{w, t}}.")
                words.append((str(w["w"]).strip(), float(w.get("t", 0.0))))
            parsed.append((tier, words))
        return parsed

    def build(self) -> None:
        s, b = self.spec, self.brand
        W, H = self.ctx.W, self.ctx.H
        parsed = self._parse(s.get("lines"))
        big_role, small_role = s.get("big_font", "serif_italic"), s.get("small_font", "text")
        base_em = float(s.get("size", BIG_EM)) * H
        big_em = base_em * (SERIF_BOOST if "serif" in str(b.fonts.get(big_role, "")).lower() else 1.0)
        max_w = float(s.get("max_width", MAX_W)) * W
        widest_big = max((text_size(" ".join(w for w, _ in words), b.font(big_role, big_em), -0.02 * big_em)[0]
                          for tier, words in parsed if tier == "big"), default=0.0)
        if widest_big > max_w:  # za długie hasło: duże słowo się zmniejsza, a małe razem z nim
            k = max_w / widest_big
            big_em, base_em, widest_big = big_em * k, base_em * k, max_w
        small_em = SMALL_RATIO * base_em
        small_font = b.font(small_role, small_em)
        small_nat = 0.0  # najdłuższy mały wiersz z naturalnymi odstępami: blok nie jest od niego węższy
        for tier, words in parsed:
            if tier == "small":
                ws = [text_size(w, small_font)[0] for w, _ in words]
                small_nat = max(small_nat, sum(ws) + (len(ws) - 1) * SPACE * small_em)
        block_w = min(max_w, max(widest_big, small_nat) if widest_big > 0 else max(0.45 * W, small_nat))
        left = W / 2 - block_w / 2
        big_rgb, small_rgb = b.rgb(s.get("color", "highlight")), b.rgb(s.get("small_color", "text"))
        self.words: list[_Word] = []
        y_cap = float(s.get("y", TOP)) * H
        prev_base, prev_drop = None, 0.0
        for tier, words in parsed:
            em = big_em if tier == "big" else small_em
            role = big_role if tier == "big" else small_role
            font = b.font(role, em)
            texts = [w for w, _ in words]
            n = len(words)
            track = -0.02 * em if tier == "big" else 0.0
            widths = [text_size(w, font, track)[0] for w in texts]
            if tier == "small":
                scale = 1.0
                for _ in range(4):  # nie mieści się nawet z wąskimi odstępami: kurczymy krój (rozmiary liter nie rosną liniowo, więc kilka podejść)
                    if sum(widths) + (n - 1) * MIN_GAP * font.size <= block_w or scale <= MIN_SMALL_SCALE:
                        break
                    scale = max(MIN_SMALL_SCALE, scale * (block_w - (n - 1) * MIN_GAP * font.size) / max(1.0, sum(widths)))
                    font = b.font(role, em * scale)
                    widths = [text_size(w, font, track)[0] for w in texts]
            asc = font.getmetrics()[0]
            cap_off = font.getbbox("H")[1]  # od góry linii do górnej krawędzi wersalików
            if prev_base is not None:  # następny wiersz zaczyna się pod ogonkami poprzedniego plus mały odstęp
                y_cap = prev_base + prev_drop + 0.005 * H
            baseline = y_cap + (asc - cap_off)
            fill = tuple(big_rgb if tier == "big" else small_rgb) + (255,)
            tracks = [track] * n
            xs: list[float] = []
            if tier == "big":
                total = sum(widths) + (n - 1) * 0.26 * em
                x = W / 2 - total / 2
                for w in widths:
                    xs.append(x)
                    x += w + 0.26 * em
            elif n > 1:  # wyjustowanie: cała nadwyżka idzie w odstępy między słowami
                gap = (block_w - sum(widths)) / (n - 1)
                if gap < 0.8 * MIN_GAP * font.size:  # (drobna tolerancja: szerokość liter nie skaluje się dokładnie z rozmiarem)
                    self.notes.append(f"wiersz „{' '.join(texts)}” nie mieści się w bloku: skróć go albo rozdziel hasło na dwa.")
                gap = max(gap, MIN_GAP * font.size)
                x = left if gap > MIN_GAP * font.size + 1e-6 else W / 2 - (sum(widths) + (n - 1) * gap) / 2
                for w in widths:
                    xs.append(x)
                    x += w + gap
            else:
                wd = widths[0]
                if wd >= MIN_STRETCH * block_w and len(texts[0]) > 1:  # jedno słowo: rozstrzelone litery do szerokości bloku
                    tk = min(MAX_TRACK * font.size, (block_w - wd) / (len(texts[0]) - 1))
                    tracks = [tk]
                    widths = [text_size(texts[0], font, tk)[0]]
                xs = [W / 2 - widths[0] / 2]
            for (text, t0), x, tk in zip(words, xs, tracks):
                spr, base = text_sprite(text, font, fill, tracking=tk, pad=4)
                spr, (ox, oy) = shadowed(spr, font.size * 0.05, float(s.get("shadow", 0.45)), dy=font.size * 0.02)
                self.words.append(_Word(spr, x - 4 - ox, baseline - (base + oy), t0))
            prev_base = baseline
            prev_drop = max(DROP * font.size, max(font.getbbox(w, anchor="ls")[3] for w in texts) + 0.01 * font.size)

    def draw(self, layer: Layer, t: float) -> None:
        u = t - self.start
        for w in self.words:
            if u >= w.t - 1e-6:
                layer.paste(w.sprite, w.x, w.y)


def _ends(word, marks: Sequence[str]) -> bool:
    return str(word.text).rstrip("\"”')»").endswith(tuple(marks))


def from_emphasis(words: Sequence, ranges: Sequence[Sequence[float]], cfg: dict | None = None) -> tuple[list[dict], list[list[float]], list[str]]:
    """Hasła ze słów wyróżnionych w scenariuszu (`*fraza*`): wyróżnione słowa są dużym wierszem, kilka słów przed nimi małym wierszem nad nim,
    kilka po nich małym pod nim; słowa wskakują w chwili, gdy padają. Hasło nie wychodzi poza zdanie (kropka, pytajnik, przecinek) ani poza pauzę
    dłuższą niż max_gap_s. Słowa między dwoma hasłami dzielą się po równo (późniejsze dostaje nadwyżkę).

    Zwraca (elementy `lockup` do planu, przedziały czasu [od, do] słów hasła, uwagi dla autora). Przedziały dostają napisy biegnące (pole `skip`),
    żeby słowa hasła nie pojawiły się dwa razy; hasło schodzi, zanim wrócą zwykłe napisy."""
    cfg = cfg or {}
    pre_max, post_max = int(cfg.get("pre", PRE_WORDS)), int(cfg.get("post", POST_WORDS))
    big_max, gap = max(1, int(cfg.get("big_max", BIG_WORDS))), float(cfg.get("max_gap_s", MAX_GAP_S))
    hold, lead, min_vis = float(cfg.get("hold", HOLD)), float(cfg.get("lead", LEAD_S)), float(cfg.get("min_visible", MIN_VISIBLE_S))
    style = {k: cfg[k] for k in ("color", "small_color", "y", "size", "max_width", "big_font", "small_font", "shadow") if k in cfg}
    mids = [(float(w.start) + float(w.end)) / 2 for w in words]
    notes: list[str] = []
    spans: list[list[int]] = []  # [pierwsze duże słowo, ostatnie duże słowo]
    for a, b in sorted((float(r[0]), float(r[1])) for r in ranges):
        idx = [i for i, m in enumerate(mids) if a - 1e-3 <= m <= b + 1e-3 and (not spans or i > spans[-1][1])]
        if not idx:
            continue
        i0, i1 = idx[0], idx[-1]
        if i1 - i0 + 1 > big_max:
            notes.append(f"wyróżnienie „{' '.join(str(w.text).strip() for w in words[i0:i1 + 1])}” ma {i1 - i0 + 1} słów: duże są pierwsze {big_max}, "
                         "reszta idzie do małego wiersza pod nimi.")
            i1 = i0 + big_max - 1
        spans.append([i0, i1])

    def breaks(i: int) -> bool:  # czy za słowem i kończy się zdanie albo fraza (kropka, przecinek...)
        return _ends(words[i], SENTENCE_END + (",",))

    reach = []  # ile słów w każdą stronę hasło zmieściłoby samo, z pominięciem sąsiednich haseł
    for k, (i0, i1) in enumerate(spans):
        floor = spans[k - 1][1] + 1 if k else 0
        lo = i0
        while lo - 1 >= floor and i0 - (lo - 1) <= pre_max and not breaks(lo - 1) and float(words[lo].start) - float(words[lo - 1].end) <= gap:
            lo -= 1
        ceil = (spans[k + 1][0] - 1) if k + 1 < len(spans) else len(words) - 1
        hi = i1
        while hi + 1 <= ceil and hi - i1 < post_max and not breaks(hi) and float(words[hi + 1].start) - float(words[hi].end) <= gap:
            hi += 1
        reach.append([lo, hi])
    for k in range(len(spans) - 1):  # wspólne słowa dzielą się: pierwsze hasło dostaje połowę (w dół), drugie resztę
        n = reach[k][1] - reach[k + 1][0] + 1
        if n > 0:
            reach[k][1] = reach[k + 1][0] + n // 2 - 1
            reach[k + 1][0] = reach[k][1] + 1
    def leaves_at(h: int) -> float:  # kiedy hasło schodzi, gdy jego ostatnie słowo to h: po przytrzymaniu, ale przed powrotem zwykłych napisów
        e = float(words[h].end) + hold
        return min(e, float(words[h + 1].start) - lead) if h + 1 < len(words) else e

    specs: list[dict] = []
    skips: list[list[float]] = []
    for (i0, i1), (lo, hi) in zip(spans, reach):
        while hi > i1 and leaves_at(hi) - float(words[hi].start) < min_vis:  # słowo, po którym od razu leci mowa, mignęłoby: wypada z hasła
            hi -= 1
        at = max(0.0, float(words[lo].start) - lead)

        def line(first: int, last: int, tier: str) -> dict:
            return {"tier": tier, "words": [{"w": str(words[j].text).strip(), "t": round(max(0.0, float(words[j].start) - lead - at), 3)}
                                            for j in range(first, last + 1)]}

        lines = ([line(lo, i0 - 1, "small")] if lo < i0 else []) + [line(i0, i1, "big")] + ([line(i1 + 1, hi, "small")] if hi > i1 else [])
        end = max(leaves_at(hi), float(words[hi].start) + 0.3)  # (duże słowo, po którym od razu leci mowa, i tak zostaje na 0,3 s)
        specs.append({"type": "lockup", "auto": True, "at": round(at, 3), "dur": round(end - at, 3), "lines": lines, **style})
        skips.append([round(float(words[lo].start) - 0.001, 3), round(float(words[hi].end) + 0.001, 3)])
    return specs, skips, notes
