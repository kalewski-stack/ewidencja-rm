"""Scenariusz ze znacznikami: tekst, który mówisz, z grafikami wpisanymi w nawiasach klamrowych.

    Dzisiaj o tym, czym jest {tytuł: Content Strategy | akcent: najgorsza | styl: serif} content strategy.
    {licznik: 700+ | podpis: wydarzeń B2B} Zrobiłem ich ponad siedemset.

Znacznik zaczyna działać od następnego słowa tekstu. Po nagraniu program rozpoznaje mowę, dopasowuje Twój tekst do
transkrypcji (słowa przekręcone przez rozpoznawanie nie przeszkadzają) i z tego wylicza czasy grafik. Na końcu powstaje
zwykły plan grafik (taki jak plik JSON), więc wszystko, co umie plan, umie też scenariusz.

Składnia znacznika: {typ: główna treść | klucz: wartość | klucz: wartość}. Zamknięcie: {/typ} kończy ostatnio otwarty
znacznik tego typu po poprzednim słowie. Poza tym koniec wyznacza `do: fraza` (fraza z tekstu, po której element znika)
albo `czas: sekundy`, a bez nich czas trwania domyślny dla danego elementu. Linie zaczynające się od # albo // i tekst
w nawiasach kwadratowych [tak] to uwagi, które nie są mową.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Sequence

from .anchors import norm
from .core import PlanError

TYPES = {
    "tytul": "title", "title": "title", "plakietka": "badge", "badge": "badge", "karty": "cards", "cards": "cards",
    "profil": "profile", "profile": "profile", "pigulki": "pills", "pills": "pills", "kafelki": "chips", "chips": "chips",
    "kroki": "steps", "steps": "steps", "os": "axis", "axis": "axis", "paski": "bars", "bars": "bars",
    "wyroznienie": "callout", "callout": "callout", "licznik": "stat", "stat": "stat", "ilustracja": "illustration",
    "illustration": "illustration", "rozmycie": "blur", "blur": "blur",
    "tekst": "text", "text": "text", "strzalka": "arrow", "arrow": "arrow", "opisy": "labels", "labels": "labels",
    "lista": "list", "list": "list", "porownanie": "list", "comparison": "list", "pierscien": "ring", "ring": "ring",
    "tarcza": "dial", "dial": "dial", "krok": "step", "step": "step", "final": "finale", "finale": "finale",
    "plansza": "cutaway", "cutaway": "cutaway", "blysk": "glint", "glint": "glint",
    "przejscie": "transition", "transition": "transition",
}
COMPARISON = ("porownanie", "comparison")  # to samo co lista, ale z kolumnami: „Tytuł: wiersz; wiersz // Tytuł: wiersz”
KEYS = {
    "akcent": "accent", "styl": "style", "strefa": "zone", "czas": "dur", "przesun": "shift", "podpis": "label",
    "numer": "number", "tekst": "text", "ikona": "icon", "haslo": "kicker", "obraz": "image", "obrazy": "images",
    "szerokosc": "width", "rozmiar": "size", "od": "from", "przedrostek": "prefix", "przyrostek": "suffix",
    "tryb": "mode", "jednostka": "unit", "pasek": "bar", "licznik": "count", "korona": "crown", "kursor": "cursor",
    "sila": "sigma", "sciemnienie": "dim", "uklad": "layout", "fokus": "focus", "do": "until", "znacznik": "tag",
    "wejscie": "in", "wyjscie": "out", "aktywne": "active", "kotwica": "anchor", "etykiety": "label_style", "poswiata": "glow", "cien": "shadow", "rozmycie": "blur", "tytul": "title", "kolumny": "cols",
    "cel": "to", "luk": "bend", "grot": "head", "kolor": "color", "zaznaczenie": "marker", "odslanianie": "reveal", "kroj": "font",
    "obrot": "rot", "przezroczystosc": "opacity", "za": "behind", "wyswietlenia": "views", "kropki": "dots", "luki": "arcs",
    "pismo": "text_font", "linia": "line", "grubosc": "width", "wystaje": "bleed",
    "nad": "hub_top", "szybkosc": "cps", "najazd": "drift", "zblizenie": "closeup_at", "wielkoscetykiet": "label_k",
    "wyrownanie": "align", "kierunek": "dir", "moc": "strength", "dokladnie": "exact",
}
# Wartości pisane po polsku -> to, czego oczekuje element (klucz: (typ elementu, pole)).
VALUES = {
    ("arrow", "style"): {"ciagla": "solid", "przerywana": "dashed", "kropkowana": "dotted"},
    ("arrow", "head"): {"otwarty": "open", "pelny": "filled", "brak": "none"},
    ("text", "marker"): {"brak": "none", "podkreslenie": "underline", "pedzel": "brush", "nawias": "bracket"},
    ("text", "reveal"): {"zanik": "fade", "pisanie": "type", "slowa": "words"},
    ("text", "font"): {"szeryf": "serif_italic", "gruby": "display", "pogrubiony": "bold", "polgruby": "semibold", "zwykly": "text"},
    ("text", "align"): {"srodek": "center", "lewo": "left", "prawo": "right"},
    ("cutaway", "align"): {"srodek": "center", "lewo": "left"},
    ("list", "marker"): {"brak": "none", "kropka": "dot", "ramka": "box", "pole": "box"},
    ("list", "text_font"): {"szeryf": "serif", "zwykly": "plain"},
    ("cards", "label_style"): {"szeryf": "serif", "pogrubione": "bold", "zolte": "yellow"},
    ("labels", "font"): {"szeryf": "serif", "pogrubiony": "bold", "gruby": "display"},
    ("labels", "line"): {"ciagla": "solid", "przerywana": "dashed", "kropkowana": "dotted", "brak": "none"},
}
FRACTIONS = {"x", "y", "dx", "dy", "rx", "ry", "tx", "ty", "width", "size", "row_gap", "rule_to", "opacity"}  # ułamki kadru: można podać 30%
POINTS = {"from", "to"}  # punkt [x, y]: „0,3; 0,5” albo „30% 50%”
ZONES = {"gora": "top", "lewo": "left", "prawo": "right", "dol": "bottom", "glowa": "head", "calosc": "full", "napisy": "captions"}
MAIN_FIELD = {"title": "text", "badge": "text", "stat": "value", "cards": "items", "steps": "items", "pills": "items",
              "chips": "items", "axis": "items", "bars": "rows", "callout": "title", "profile": "label", "illustration": "image",
              "text": "text", "labels": "items", "list": "rows",
              "dial": "hub_main", "step": "label", "finale": "title", "transition": "kind"}
DEFAULT_BLUR_DUR = 3.0
CUTAWAY_HOLD = 0.3  # plansza zostaje tyle po ostatnim słowie (jak we wzorcu: cięcie wraca chwilę po puencie)
CAPTIONS_FINALE_Y = 0.80  # po cofnięciu kamery napisy schodzą pod schemat, żeby nie zasłaniać tytułu
TRANSITION_SNAP_S = 0.6  # przejście ze scenariusza przyciąga się do najbliższej granicy sceny (początek albo koniec elementu) w tej odległości
MIN_COVERAGE = 0.5  # tyle słów scenariusza musi znaleźć się w mowie, żeby uznać, że to ten sam tekst

_TOKEN = re.compile(r"\{([^{}]*)\}|([^\s{}]+)")
_BRACKETS = re.compile(r"\[[^\]]*\]")
_STAT = re.compile(r"^(\D*?)(\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(.*)$")


@dataclass
class Cue:
    kind: str  # typ elementu ("title", ...) albo "blur"
    spec: dict  # pola jak w planie JSON, bez czasów
    word: int  # numer słowa scenariusza, od którego element startuje
    end_word: int | None = None  # numer ostatniego słowa pod elementem (z zamknięcia {/typ}), jeśli jest
    until: str | None = None  # fraza kończąca element
    raw: str = ""


@dataclass
class Script:
    words: list[str] = field(default_factory=list)  # słowa scenariusza (to, co mówisz), bez gwiazdek
    emph: list[bool] = field(default_factory=list)  # czy słowo jest wyróżnione (*tak*) w tekście scenariusza: duży krój w napisach i na planszach
    cues: list[Cue] = field(default_factory=list)


def _fold(s: str) -> str:
    return norm(s)


def _coerce(value: str):
    v = value.strip()
    low = v.lower()
    if low in ("tak", "true"):
        return True
    if low in ("nie", "false"):
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+[.,]\d+", v):
        return float(v.replace(",", "."))
    if ";" in v:
        return [_coerce(p) for p in v.split(";")]
    return v


def _frac(value: str):
    """Liczba z kropką albo przecinkiem, także w procentach: „30%” -> 0.3. Cokolwiek innego przechodzi jak zwykła wartość."""
    m = re.fullmatch(r"\s*(-?\d+(?:[.,]\d+)?)\s*(%?)\s*", value)
    if not m:
        return _coerce(value)
    x = float(m.group(1).replace(",", "."))
    return x / 100.0 if m.group(2) else x


def _point(value: str, what: str) -> list[float]:
    parts = [p for p in re.split(r"[;\s]+", value.strip()) if p]
    try:
        pt = [float(_frac(p)) for p in parts]
    except (TypeError, ValueError) as exc:
        raise PlanError(f"{what}: podaj punkt jako dwie liczby, np. „0,3; 0,5” albo „30% 50%”.") from exc
    if len(pt) != 2:
        raise PlanError(f"{what}: podaj punkt jako dwie liczby, np. „0,3; 0,5” albo „30% 50%”.")
    return pt


def _arcs(value: str) -> list[list[float]]:
    out = []
    for part in value.split(";"):
        m = re.fullmatch(r"\s*(-?\d+(?:[.,]\d+)?)\s*(?:\.\.|-|do)\s*(-?\d+(?:[.,]\d+)?)\s*", part)
        if not m:
            raise PlanError("luki: podaj zakresy kątów w stopniach, np. „100..260; -80..80”.")
        out.append([float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))])
    return out


_LABEL = re.compile(r"^(?P<text>.+?)\s*@\s*(?P<x>\S+)\s+(?P<y>\S+)(?:\s*>\s*(?P<tx>\S+)\s+(?P<ty>\S+))?\s*$")


def _labels(value: str) -> list[dict]:
    items = []
    for it in _split_items(value):
        m = _LABEL.match(it)
        if not m:
            raise PlanError(f"opisy: „{it}” ma być w postaci „tekst @ x y > cel_x cel_y” (np. Cel @ 20% 12% > 42% 15%).")
        d: dict = {"text": m.group("text").strip(), "x": _frac(m.group("x")), "y": _frac(m.group("y"))}
        if m.group("tx"):
            d["tx"], d["ty"] = _frac(m.group("tx")), _frac(m.group("ty"))
        items.append(d)
    return items


def _list_row(item: str) -> dict:
    """„+ Etykieta = tekst / szczegół”: plus na początku oznacza wiersz odhaczony, etykieta i szczegół są opcjonalne."""
    item = item.strip()
    done = item.startswith("+")
    if done:
        item = item[1:].strip()
    label, _, rest = item.partition("=") if "=" in item else ("", "", item)
    text, _, detail = rest.partition("/")
    row = {"text": text.strip()}
    if label.strip():
        row["label"] = label.strip()
    if detail.strip():
        row["detail"] = detail.strip()
    if done:
        row["state"] = "done"
    return row


def _columns(value: str) -> list[dict]:
    cols = []
    for chunk in value.split("//"):
        title, colon, rows = chunk.partition(":")
        if not colon:
            raise PlanError("porównanie: każda kolumna to „Tytuł: wiersz; wiersz”, kolumny rozdziela //.")
        cols.append({"title": title.strip(), "rows": [_list_row(r) for r in _split_items(rows) if r.strip()]})
    return cols


def _split_items(value: str) -> list[str]:
    return [p.strip() for p in value.split(";")]


def _stat(value: str, spec: dict) -> None:
    m = _STAT.match(value.strip())
    if not m:
        raise PlanError(f"licznik: nie widzę liczby w „{value}” (np. 700+, 15 834 zł, 2,5 mln).")
    prefix, num, suffix = m.group(1), m.group(2), m.group(3)
    digits = re.sub(r"[  ]", "", num)
    frac = re.search(r"[.,](\d+)$", digits)
    spec["value"] = float(digits.replace(",", ".")) if frac else int(digits)
    if frac:
        spec["decimals"] = len(frac.group(1))
    if prefix:
        spec.setdefault("prefix", prefix)
    if suffix:
        spec.setdefault("suffix", suffix)


def _pair(item: str) -> tuple[str, str]:
    left, _, right = item.partition("=")
    return left.strip(), right.strip()


def _main(kind: str, value: str, spec: dict, alias: str = "") -> None:
    f = MAIN_FIELD.get(kind)
    if not f or not value.strip():
        return
    if kind == "stat":
        return _stat(value, spec)
    if kind == "labels":
        spec["items"] = _labels(value)
        return
    if kind == "list":
        if alias in COMPARISON:
            spec["columns"] = _columns(value)
        else:
            spec["rows"] = [_list_row(r) for r in _split_items(value) if r.strip()]
        return
    if kind == "cards":
        items = []
        for it in _split_items(value):
            label, bullets = _pair(it)
            d = {"label": label, "kind": "play"}
            if bullets:
                d["bullets"] = [b.strip() for b in bullets.split("/") if b.strip()]
            items.append(d)
        spec["items"] = items
    elif kind == "steps":
        spec["items"] = [{"title": a, **({"sub": b} if b else {})} for a, b in map(_pair, _split_items(value))]
    elif kind == "chips":
        items = []
        for it in _split_items(value):
            label, val = _pair(it)
            d = {"label": label}
            if val:
                tmp: dict = {}
                _stat(val, tmp)
                d.update(tmp)
            items.append(d)
        spec["items"] = items
    elif kind == "pills":
        spec["items"] = [{"text": a, **({"tag": b} if b else {})} for a, b in map(_pair, _split_items(value))]
    elif kind in ("axis",):
        spec["items"] = _split_items(value)
    elif kind == "bars":
        spec["rows"] = _split_items(value)
    else:
        spec[f] = value.strip()


def _marker(body: str, word: int) -> Cue | tuple[str, str]:
    """Znacznik {typ: treść | klucz: wartość}; zwraca Cue albo ("close", typ) dla {/typ}."""
    body = body.strip()
    if body.startswith("/"):
        t = TYPES.get(_fold(body[1:]))
        if not t:
            raise PlanError(f"Znacznik zamykający „{{{body}}}”: nieznany typ. Dostępne: {', '.join(sorted(set(TYPES)))}.")
        return ("close", t)
    parts = [p.strip() for p in body.split("|")]
    head, _, main = parts[0].partition(":")
    kind = TYPES.get(_fold(head))
    if not kind:
        raise PlanError(f"Znacznik „{{{body}}}”: nieznany typ „{head.strip()}”. Dostępne: "
                        f"{', '.join(sorted({k for k in TYPES if k.isascii()}))} (polskie nazwy mogą mieć ogonki).")
    spec: dict = {"type": kind}
    _main(kind, main, spec, _fold(head))
    until = None
    for seg in parts[1:]:
        if not seg:
            continue
        key, colon, value = seg.partition(":")
        if not colon:
            raise PlanError(f"Znacznik „{{{body}}}”: „{seg}” nie ma dwukropka (pisz klucz: wartość).")
        k = KEYS.get(_fold(key), key.strip())
        if k == "until":
            until = value.strip()
        elif k == "images" and kind == "cards":
            imgs = [i.strip() for i in value.split(";")]
            for i, it in enumerate(spec.get("items", [])):
                if i < len(imgs) and imgs[i]:
                    it["image"], it["kind"] = imgs[i], "image"
        elif k == "views" and kind == "cards":
            views = [v.strip() for v in value.split(";")]
            for i, it in enumerate(spec.get("items", [])):
                if i < len(views) and views[i]:
                    it["views"] = views[i]
        elif k in ("zone", "anchor"):
            spec[k] = ZONES.get(_fold(value), value.strip())
        elif k in POINTS:
            spec[k] = _point(value, f"{key.strip()}")
        elif k == "arcs":
            spec[k] = _arcs(value)
        elif (kind, k) in VALUES:
            spec[k] = VALUES[(kind, k)].get(_fold(value), value.strip())
        elif k in FRACTIONS:
            spec[k] = _frac(value)
        else:
            spec[k] = _coerce(value)
    return Cue(kind, spec, word, None, until, body)


def parse(text: str) -> Script:
    """Rozbija scenariusz na słowa i znaczniki."""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(("#", "//"))]
    clean = _BRACKETS.sub(" ", "\n".join(lines))
    script = Script()
    open_cues: list[Cue] = []
    emph_on = False
    for m in _TOKEN.finditer(clean):
        if m.group(2) is not None:
            tok = m.group(2)
            core = tok.replace("*", "")
            state, word_emph = emph_on, False
            for ch in tok:  # gwiazdka przełącza wyróżnienie; słowo jest wyróżnione, gdy litery stoją w jego zakresie (*celu*. też)
                if ch == "*":
                    state = not state
                elif state:
                    word_emph = True
            emph_on = state
            if _fold(core):
                script.words.append(core)
                script.emph.append(word_emph)
            continue
        res = _marker(m.group(1), len(script.words))
        if isinstance(res, Cue):
            script.cues.append(res)
            open_cues.append(res)
        else:
            for c in reversed(open_cues):
                if c.kind == res[1] and c.end_word is None:
                    c.end_word = len(script.words) - 1
                    break
            else:
                raise PlanError(f"Zamknięcie „{{/{m.group(1)[1:].strip()}}}” nie ma wcześniejszego otwarcia tego typu.")
    leftover = _TOKEN.sub(" ", clean)
    if "{" in leftover or "}" in leftover:
        raise PlanError("W scenariuszu jest nawias klamrowy bez pary: każdy znacznik musi być w całości w { }.")
    return script


def align(script_words: Sequence[str], spoken: Sequence) -> tuple[list[tuple[float, float]], float]:
    """Czasy (start, koniec) każdego słowa scenariusza na podstawie transkrypcji oraz odsetek słów znalezionych w mowie.
    Słowa, których rozpoznawanie nie oddało, dostają czas z interpolacji między sąsiednimi trafieniami."""
    a = [_fold(w) for w in script_words]
    b = [_fold(w.text) for w in spoken]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    match: dict[int, int] = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            match[blk.a + k] = blk.b + k
    if not match:
        return [], 0.0
    idx = sorted(match)
    first, last = idx[0], idx[-1]
    t0, t1 = float(spoken[match[first]].start), float(spoken[match[last]].start)
    per = (t1 - t0) / max(1, last - first) if last > first else 0.35  # średni odstęp słów (do skrajów)
    out: list[tuple[float, float]] = []
    guessed: list[int] = []  # słowa bez trafienia w mowie: ich czasy są wyliczone, więc nie mogą zachodzić na następne słowo
    for i in range(len(a)):
        if i in match:
            w = spoken[match[i]]
            out.append((float(w.start), float(w.end)))
            continue
        guessed.append(i)
        left = max((j for j in idx if j < i), default=None)
        right = min((j for j in idx if j > i), default=None)
        if left is not None and right is not None:
            ts, te = float(spoken[match[left]].end), float(spoken[match[right]].start)
            k = (i - left) / (right - left)
            start = ts + (te - ts) * k
            out.append((start, start + max(0.1, per * 0.8)))
        elif left is None:
            start = max(0.0, t0 - (first - i) * per)
            out.append((start, start + per * 0.8))
        else:
            tail = float(spoken[match[last]].end) + (i - last - 1) * per
            out.append((tail, tail + per * 0.8))
    for i in guessed:  # koniec słowa z interpolacji nie wychodzi za początek następnego (zostaje co najmniej 0,03 s)
        if i + 1 < len(out) and out[i][1] > out[i + 1][0] and out[i + 1][0] > out[i][0]:
            out[i] = (out[i][0], max(out[i][0] + 0.03, out[i + 1][0]))
    return out, len(match) / max(1, len(a))


def _find_phrase(words: list[str], phrase: str, after: int) -> tuple[int, int] | None:
    toks = [t for t in (_fold(p) for p in phrase.split()) if t]
    if not toks:
        return None
    folded = [_fold(w) for w in words]
    for i in range(max(0, after), len(folded) - len(toks) + 1):
        if folded[i:i + len(toks)] == toks:
            return i, i + len(toks) - 1
    return None


def to_plan(text: str, spoken: Sequence, *, allow_plain: bool = False) -> dict:
    """Plan grafik (słownik jak w JSON) wyliczony ze scenariusza i transkrypcji. `allow_plain`: scenariusz bez znaczników jest dozwolony
    (Format 4 sam dobiera duże słowa, więc sam tekst wystarczy: służy do poprawnej pisowni napisów)."""
    script = parse(text)
    if not script.cues and not any(script.emph):
        if allow_plain:
            return {"schema": 1, "elements": [], "effects": []}
        raise PlanError("W scenariuszu nie ma ani jednego znacznika {typ: ...} ani wyróżnienia *tak*.")
    if not spoken:
        raise PlanError("Scenariusz ze znacznikami potrzebuje transkrypcji: uruchom montaż z napisami (rozpoznawanie mowy) "
                        "albo podaj gotową: --words plik.json.")
    if not script.words:
        raise PlanError("W scenariuszu są same znaczniki, bez tekstu do dopasowania do mowy.")
    times, coverage = align(script.words, spoken)
    if coverage < MIN_COVERAGE:
        raise PlanError(f"Scenariusz nie pasuje do nagrania: w mowie znalazłem tylko {coverage * 100:.0f}% jego słów "
                        f"(potrzeba co najmniej {MIN_COVERAGE * 100:.0f}%). Czy to na pewno ten tekst? Porównaj z plikiem .slowa.json.")
    n = len(times)
    elements: list[dict] = []
    effects: list[dict] = []
    transitions: list[dict] = []
    emph_ranges = _emphasis_ranges(script.emph, times)
    last_dial: dict | None = None
    for cue in script.cues:
        spec = dict(cue.spec)
        w = min(cue.word, n - 1)
        at = times[w][0] if cue.word < n else times[-1][1]
        at += float(spec.pop("shift", 0.0) or 0.0)
        dur = spec.pop("dur", None)
        end = None
        if cue.end_word is not None and cue.end_word >= cue.word:
            end = times[min(cue.end_word, n - 1)][1]
        elif cue.until:
            found = _find_phrase(script.words, cue.until, cue.word)
            if not found:
                raise PlanError(f"Znacznik „{{{cue.raw}}}”: fraza do: „{cue.until}” nie występuje w tekście po znaczniku.")
            end = times[found[1]][1]
        if end is not None:
            dur = max(0.4, end - at + (CUTAWAY_HOLD if cue.kind == "cutaway" else 0.0))
        blur_on = spec.pop("blur", None)
        spec["at"] = round(at, 3)
        spec["said"] = " ".join(script.words[cue.word:cue.word + 4])
        if cue.kind == "transition":  # przejście to obróbka klatki w chwili cięcia, a nie element
            if not str(spec.get("kind", "")).strip():
                raise PlanError(f"Znacznik „{{{cue.raw}}}”: przejście potrzebuje rodzaju, np. {{przejście: rozmycie}} "
                                "(rozmycie, zoom, przesunięcie, kurtyna, błysk).")
            transitions.append({k: v for k, v in spec.items() if k != "type"})
            continue
        if cue.kind in ("step", "finale"):  # kroki i finał należą do ostatniej tarczy
            if last_dial is None:
                raise PlanError(f"Znacznik „{{{cue.raw}}}” musi stać po znaczniku {{tarcza: ...}}.")
            if cue.kind == "step":
                if not str(spec.get("label", "")).strip():
                    raise PlanError(f"Znacznik „{{{cue.raw}}}”: krok potrzebuje nazwy, np. {{krok: Cel}}.")
                last_dial["steps"].append({"label": str(spec["label"]).strip(), "at": spec["at"]})
            else:
                last_dial["finale"] = {"at": spec["at"], "title": str(spec.get("title", ""))}
            continue
        if cue.kind == "dial":
            spec["hub"] = [str(spec.pop("hub_top", "")), str(spec.pop("hub_main", ""))]
            spec["steps"] = []
            if not dur:
                dur = max(1.0, times[-1][1] + 0.5 - at)
            last_dial = spec
        if cue.kind == "cutaway":
            spec["emphasis"] = [r for r in emph_ranges if r[1] >= at and r[0] <= at + float(dur or 2.0)]
        if cue.kind == "blur":
            spec["dur"] = round(float(dur) if dur else DEFAULT_BLUR_DUR, 3)
            effects.append(spec)
            continue
        if dur:
            spec["dur"] = round(float(dur), 3)
        elements.append(spec)
        if blur_on:
            d = float(spec.get("dur") or 4.0)
            effects.append({"type": "blur", "at": round(max(0.0, at - 0.1), 3), "dur": round(d + 0.2, 3)})
    _snap_transitions(transitions, elements)
    caps: dict = {}
    if emph_ranges:  # wyróżnienia z tekstu (*tak*) dla napisów kinetycznych; resztę ustawień napisów daje szablon
        caps["emphasis"] = emph_ranges
    finales = [e["finale"]["at"] for e in elements if e.get("type") == "dial" and e.get("finale")]
    if finales:
        caps["shift"] = [{"at": f, "dur": 3600, "y": CAPTIONS_FINALE_Y} for f in finales]
    if caps:
        elements.append({"type": "captions", **caps})
    out = {"schema": 1, "elements": elements, "effects": effects}
    if transitions:
        out["transitions"] = transitions
    return out


def _snap_transitions(transitions: list[dict], elements: list[dict]) -> None:
    """Przejście wpisane w scenariuszu wypada na słowie, a granica sceny (np. koniec planszy: ostatnie słowo plus przytrzymanie) na ogół kilka
    dziesiątych sekundy od niego. Przejście przyciąga się więc do najbliższego początku albo końca elementu (do TRANSITION_SNAP_S), chyba że
    ma `dokładnie: tak`. W planie JSON czas przejścia jest zawsze dokładny."""
    from .elements import REGISTRY

    bounds: set[float] = set()
    for e in elements:
        kind = e.get("type")
        if kind in ("captions", "backdrop", "glint") or "at" not in e:
            continue
        bounds.add(round(float(e["at"]), 3))
        dur = e.get("dur") or (REGISTRY[kind].default_dur if kind in REGISTRY else 0.0)
        if dur:
            bounds.add(round(float(e["at"]) + float(dur), 3))
    for tr in transitions:
        exact = bool(tr.pop("exact", False))
        near = min(bounds, key=lambda b: abs(b - tr["at"]), default=None)
        if not exact and near is not None and abs(near - tr["at"]) <= TRANSITION_SNAP_S:
            tr["at"] = near


def words_from_script(text: str, spoken: Sequence) -> tuple[list, float]:
    """Słowa scenariusza z czasami z mowy: napisy ze scenariusza, gdy lektor czyta tekst (Motion). Zwraca (słowa, pokrycie 0-1)."""
    from .. import captions

    script = parse(text)
    times, coverage = align(script.words, spoken) if script.words and spoken else ([], 0.0)
    return [captions.Word(w, float(a), float(b)) for w, (a, b) in zip(script.words, times)], coverage


def _emphasis_ranges(flags: Sequence[bool], times: Sequence[tuple[float, float]]) -> list[list[float]]:
    """Ciągi słów wyróżnionych gwiazdkami -> przedziały czasu [od, do] w sekundach."""
    out: list[list[float]] = []
    i = 0
    while i < len(flags):
        if flags[i]:
            j = i
            while j + 1 < len(flags) and flags[j + 1]:
                j += 1
            out.append([round(times[i][0], 3), round(times[j][1], 3)])
            i = j + 1
        else:
            i += 1
    return out


def is_script(path) -> bool:
    return str(path).lower().endswith((".txt", ".md"))
