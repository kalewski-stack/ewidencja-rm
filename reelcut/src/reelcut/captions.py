"""Napisy w stylu rolki wzorcowej: słowo po słowie + frazy akcentowe (stosy), render do ASS (libass)."""
from __future__ import annotations

import copy
import json
import re
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .anton_metrics import CAP_HEIGHT, UNITS_PER_EM, text_width

# Kalibracja libass dla Antona: Fontsize 100 => em ~57 px => wersalik ~49 px; środek wersalika leży
# ok. 6% rozmiaru poniżej punktu \pos przy wyrównaniu \an5.
EM_PER_FONTSIZE = 0.57
CAP_RATIO = CAP_HEIGHT / UNITS_PER_EM
CAP_CENTER_OFFSET = 0.06
SENT_END = ".?!…"
CLAUSE_END = ",;:–—"

DEFAULTS: dict = {
    "font": "Anton",
    "scale_x": 113,
    "color": "#FFFFFF",
    "accent_color": "#E2FB77",
    "running": {"cap_px": 57, "cap_top_px": 1211, "max_words": 2, "short_word_max_chars": 3,
                "lead_s": 0.04, "hold_after_s": 0.25},
    "emphasis": {"every_s": 6.8, "min_gap_s": 4.5, "min_words": 2, "max_words": 5,
                 "order": ["center_build", "right_top", "right_bottom", "center_stack", "mega"]},
    "styles": {
        "center_build": {"align": "center", "x": 540, "top": 1123, "cap": 68, "accent_cap": 105, "gap": 17,
                         "hold_s": 0.5, "blocks_running": True},
        "right_top": {"align": "right", "x": 1005, "top": 390, "cap": 75, "pitch": 95,
                      "hold_s": 1.0, "blocks_running": False},
        "right_bottom": {"align": "right", "x": 1017, "top": 1204, "cap": 100, "pitch": 130,
                         "hold_s": 0.25, "blocks_running": True},
        "center_stack": {"align": "center", "x": 540, "top": 668, "cap": 80, "pitch": 124,
                         "hold_s": 0.5, "blocks_running": False},
        "mega": {"align": "center", "x": 540, "center_y": 1260, "cap": 205, "max_width": 926,
                 "hold_s": 0.45, "blocks_running": True},
    },
}

CARDINALS = {
    "zero", "jeden", "jedna", "dwa", "dwie", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć",
    "dziesięć", "dwadzieścia", "dwudziestu", "trzydzieści", "pięćdziesiąt", "sto", "tysiąc", "tysiące", "tysięcy",
    "milion", "miliony", "milionów",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "hundred", "thousand", "million",
}
NUMBER_WORDS = CARDINALS | {"procent", "złotych", "koła", "koło", "razy", "percent", "times", "dollars"}


class CaptionsUnavailable(RuntimeError):
    """Brak zależności do rozpoznawania mowy (faster-whisper)."""


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Group:
    words: tuple[Word, ...]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end


@dataclass(frozen=True)
class Emphasis:
    words: tuple[Word, ...]
    style: str
    start: float
    end: float


# ----------------------------------------------------------------------------------------------
# Rozpoznawanie mowy
# ----------------------------------------------------------------------------------------------

def transcribe(pcm16k: array, *, model: str = "small", language: str = "pl",
               log: Callable[[str], None] | None = None) -> list[Word]:
    try:
        import numpy as np
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise CaptionsUnavailable(
            "Do napisów potrzebny jest pakiet faster-whisper. Zainstaluj: pip install faster-whisper") from exc
    if log:
        log(f"Ładuję model mowy „{model}” (przy pierwszym uruchomieniu pobierze się z internetu)...")
    audio = np.frombuffer(pcm16k, dtype=np.int16).astype(np.float32) / 32768.0
    whisper = WhisperModel(model, device="auto", compute_type="auto")
    lang = None if language in ("", "auto", None) else language
    if log:
        log("Rozpoznaję mowę...")
    segments, _ = whisper.transcribe(audio, language=lang, word_timestamps=True, beam_size=5,
                                     vad_filter=False, condition_on_previous_text=False)
    words = [Word(w.word.strip(), float(w.start), float(w.end))
             for seg in segments for w in (seg.words or []) if w.word.strip()]
    return clean_words(words)


def clean_words(words: Sequence[Word]) -> list[Word]:
    """Usuwa znaczniki bez liter/cyfr (doklejając je do poprzedniego słowa) i naprawia zachodzące czasy."""
    out: list[Word] = []
    for w in words:
        if not any(ch.isalnum() for ch in w.text):
            if out:
                out[-1] = Word(out[-1].text + w.text, out[-1].start, max(out[-1].end, w.end))
            continue
        start = max(w.start, out[-1].start) if out else w.start
        out.append(Word(w.text, start, max(w.end, start + 0.02)))
    return out


def save_words(words: Sequence[Word], path: str | Path) -> None:
    Path(path).write_text(json.dumps([{"w": w.text, "start": round(w.start, 3), "end": round(w.end, 3)}
                                      for w in words], ensure_ascii=False, indent=1), encoding="utf-8")


def load_words(path: str | Path) -> list[Word]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("words", [])
    return clean_words([Word(str(d["w"]), float(d["start"]), float(d["end"])) for d in data])


def word_breaks(words: Sequence[Word], fps: int) -> list[tuple[int, float]]:
    """Granice między słowami jako kandydaci na cięcie: 3 = koniec zdania, 2 = przecinek/pauza, 1 = zwykłe słowo."""
    out = []
    for a, b in zip(words, words[1:]):
        t = (a.end + b.start) / 2 if b.start > a.end else a.end
        last = a.text.rstrip()[-1:]
        if last and last in SENT_END:
            s = 3.0
        elif (last and last in CLAUSE_END) or b.start - a.end >= 0.18:
            s = 2.0
        else:
            s = 1.0
        out.append((int(round(t * fps)), s))
    return out


# ----------------------------------------------------------------------------------------------
# Grupowanie i wybór fraz akcentowych
# ----------------------------------------------------------------------------------------------

def _letters(text: str) -> int:
    return sum(ch.isalnum() for ch in text)


def _ends(text: str, chars: str) -> bool:
    t = text.rstrip()
    return bool(t) and t[-1] in chars


def group_words(words: Sequence[Word], max_words: int = 2, short_max: int = 3) -> list[Group]:
    """1-2 słowa na napis. Krótkie słowa (do 3 liter, np. „w”, „na”, „nie”) wiążą się z następnym."""
    groups, i, n = [], 0, len(words)
    while i < n:
        take = 1
        while (take < max_words and i + take < n
               and _letters(words[i + take - 1].text) <= short_max
               and not _ends(words[i + take - 1].text, SENT_END + CLAUSE_END)
               and words[i + take].start - words[i + take - 1].end < 0.35):
            take += 1
        groups.append(Group(tuple(words[i:i + take])))
        i += take
    return groups


def _norm(text: str) -> str:
    return re.sub(r"[^\wąćęłńóśźż]", "", text.lower())


def _has_number(ws: Sequence[Word]) -> bool:
    return any(any(ch.isdigit() for ch in w.text) or _norm(w.text) in NUMBER_WORDS for w in ws)


def _is_cardinal(w: Word) -> bool:
    return any(ch.isdigit() for ch in w.text) or _norm(w.text) in CARDINALS


def _clauses(words: Sequence[Word]) -> list[tuple[int, int]]:
    """Zakresy indeksów słów dzielone na znakach interpunkcyjnych i pauzach (zdania, zdania podrzędne)."""
    spans, start = [], 0
    for i, w in enumerate(words):
        gap = words[i + 1].start - w.end if i + 1 < len(words) else 9.0
        if _ends(w.text, SENT_END + CLAUSE_END) or gap >= 0.35 or i + 1 == len(words):
            spans.append((start, i + 1))
            start = i + 1
    return spans


def _candidates(words: Sequence[Word], e: dict) -> list[dict]:
    """Wszystkie okna 2-5 słów w obrębie klauzuli, każde z oceną "jak dobrze nadaje się na akcent"."""
    out = []
    lo, hi = int(e["min_words"]), int(e["max_words"])
    for a, b in _clauses(words):
        for length in range(lo, min(hi, b - a) + 1):
            for s in range(a, b - length + 1):
                ws = words[s:s + length]
                avg_len = sum(_letters(w.text) for w in ws) / length
                score = (3.0 if _has_number(ws) else 0.0) + 0.15 * avg_len
                score += 0.5 if length in (3, 4) else 0.0
                score += 0.6 if s + length == b else 0.0  # kończy się na końcu klauzuli
                score += 0.8 if _ends(ws[-1].text, SENT_END) else 0.0
                score += 0.4 if s == a else 0.0
                score += 1.2 if s == 0 else 0.0  # haczyk: okno od pierwszego słowa nagrania
                score -= 1.0 if _letters(ws[-1].text) <= 2 else 0.0  # wiszące "w", "na" na końcu
                score -= 1.5 if _is_cardinal(ws[-1]) and s + length < b else 0.0  # liczebnik bez rzeczownika
                score -= 0.3 if s != a and _letters(ws[0].text) <= 2 else 0.0  # okno zaczyna się od "w", "na"
                gap_before = ws[0].start - words[s - 1].end if s > 0 else 0.0
                out.append({"score": score, "a": s, "b": s + length, "gap": gap_before,
                            "sent_end": _ends(ws[-1].text, SENT_END)})
    return out


def pick_emphasis(words: Sequence[Word], duration: float, cfg: dict) -> list[Emphasis]:
    e = cfg["emphasis"]
    if not words or e.get("every_s", 0) <= 0 or duration < 8:
        return []
    cands = _candidates(words, e)
    k = max(1, round(duration / float(e["every_s"])))
    min_gap = float(e["min_gap_s"])

    def clear(chosen: list[dict], c: dict) -> bool:
        return all(abs(words[c["a"]].start - words[x["a"]].start) >= min_gap and (c["b"] <= x["a"] or c["a"] >= x["b"])
                   for x in chosen)

    order = [s for s in (e.get("order") or DEFAULTS["emphasis"]["order"])]
    # "mega": krótka puenta (2-3 słowa) po wyraźnej pauzie, kończąca zdanie; w rolce wzorcowej to "Nie był..."
    mega = None
    if "mega" in order:
        shots = [c for c in cands if 2 <= c["b"] - c["a"] <= 3 and c["gap"] >= 0.45 and c["sent_end"]
                 and words[c["a"]].start >= 0.25 * duration]
        if shots:
            mega = max(shots, key=lambda c: c["gap"] + c["score"] * 0.3)
    chosen: list[dict] = [mega] if mega else []
    # akcenty rozkładamy równomiernie: po jednym najlepszym oknie na każdy przedział czasu (jak w rolce, co ~7 s)
    for i in range(k):
        lo, hi = duration * i / k, duration * (i + 1) / k
        if mega and lo <= words[mega["a"]].start < hi:
            continue
        pool = [c for c in cands if lo <= words[c["a"]].start < hi and c["score"] >= 1.2 and clear(chosen, c)]
        if pool:
            chosen.append(max(pool, key=lambda c: c["score"]))
    chosen.sort(key=lambda c: c["a"])
    stack_styles = [s for s in order if s != "mega"] or ["center_stack"]
    lead = float(cfg["running"]["lead_s"])
    picks, n_stack = [], 0
    for c in chosen:
        ws = tuple(words[c["a"]:c["b"]])
        if c is mega:
            style = "mega"
        else:
            style = stack_styles[n_stack % len(stack_styles)]
            n_stack += 1
        hold = float(cfg["styles"][style].get("hold_s", 0.5))
        picks.append(Emphasis(ws, style, max(0.0, ws[0].start - lead), ws[-1].end + hold))
    fixed = []  # stos nie może zachodzić na następny
    for i, p in enumerate(picks):
        end = min(p.end, picks[i + 1].start - 0.05) if i + 1 < len(picks) else p.end
        fixed.append(Emphasis(p.words, p.style, p.start, max(end, p.start + 0.4)))
    return fixed


# ----------------------------------------------------------------------------------------------
# ASS
# ----------------------------------------------------------------------------------------------

def _ass_time(t: float) -> str:
    cs = max(0, int(round(t * 100)))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _ass_color(hex_rgb: str) -> str:
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{b}{g}{r}&".upper()


def _clean_text(text: str, strip_end: bool = False) -> str:
    text = text.upper().replace("{", "").replace("}", "").replace("\\", "").replace("\n", " ")
    if strip_end:
        text = text.rstrip(".,;: ")
    return text.strip()


def _fit_cap(text: str, cap: float, max_w: float, scale_x: float) -> float:
    em = cap / CAP_RATIO
    w = text_width(text, em, scale_x / 100.0)
    return cap if w <= max_w else max(cap * 0.45, cap * max_w / w)


class _Ass:
    def __init__(self, cfg: dict, canvas: tuple[int, int]):
        self.cfg, self.canvas = cfg, canvas
        self.scale_x = int(cfg["scale_x"])
        self.lines: list[tuple[int, float, float, str]] = []
        self.color, self.accent = _ass_color(cfg["color"]), _ass_color(cfg["accent_color"])

    def add(self, start: float, end: float, text: str, cap: float, x: float, cap_center_y: float, *,
            anchor: int = 5, accent: bool = False) -> None:
        if end - start < 0.04 or not text:
            return
        fs = cap / (CAP_RATIO * EM_PER_FONTSIZE)
        y = cap_center_y - CAP_CENTER_OFFSET * fs
        sx = self.scale_x
        pop = f"\\fscx{sx * 0.92:.0f}\\fscy92\\t(0,70,\\fscx{sx}\\fscy100)"
        base = f"\\an{anchor}\\fs{fs:.1f}\\fscx{sx}"
        color = self.accent if accent else self.color
        shadow = f"{{{base}\\pos({x:.0f},{y + 3:.0f})\\1c&H000000&\\1a&H78&\\blur5{pop}}}{text}"
        main = f"{{{base}\\pos({x:.0f},{y:.0f})\\1c{color}{pop}}}{text}"
        self.lines.append((0, start, end, shadow))
        self.lines.append((1, start, end, main))

    def render(self) -> str:
        W, H = self.canvas
        head = (
            "[Script Info]\nScriptType: v4.00+\n"
            f"PlayResX: {W}\nPlayResY: {H}\nScaledBorderAndShadow: yes\nWrapStyle: 2\nYCbCr Matrix: None\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
            "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Cap,{self.cfg['font']},100,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,"
            f"{self.scale_x},100,0,0,1,0,0,5,0,0,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        body = "".join(f"Dialogue: {layer},{_ass_time(s)},{_ass_time(e)},Cap,,0,0,0,,{text}\n"
                       for layer, s, e, text in sorted(self.lines, key=lambda r: (r[1], r[0])))
        return head + body


def _line_groups(ws: Sequence[Word], max_lines: int = 4) -> list[list[Word]]:
    groups = [list(g.words) for g in group_words(ws, 3, 3)]
    while len(groups) > max_lines:  # za dużo wierszy: sklejamy najkrótsze sąsiednie
        i = min(range(len(groups) - 1), key=lambda k: len(groups[k]) + len(groups[k + 1]))
        groups[i:i + 2] = [groups[i] + groups[i + 1]]
    return groups


def _add_emphasis(a: _Ass, em: Emphasis, cfg: dict, canvas: tuple[int, int]) -> None:
    st = cfg["styles"][em.style]
    sx = a.scale_x
    lines = _line_groups(em.words)
    texts = [_clean_text(" ".join(w.text for w in ln), strip_end=True) for ln in lines]
    starts = [max(em.start, ln[0].start - float(cfg["running"]["lead_s"])) for ln in lines]
    x = st["x"]
    if em.style == "mega":
        text = _clean_text(" ".join(w.text for w in em.words), strip_end=True)
        cap = _fit_cap(text, float(st["cap"]), float(st["max_width"]), sx)
        a.add(em.start, em.end, text, cap, x, float(st["center_y"]))
        return
    if em.style == "center_build":
        acc = max(range(len(texts)), key=lambda i: (_letters(max(texts[i].split(), key=len)), -i))
        caps = [float(st["accent_cap"]) if i == acc else float(st["cap"]) for i in range(len(texts))]
    else:
        caps = [float(st["cap"])] * len(texts)
    max_w = 940.0 if st["align"] == "center" else 900.0
    caps = [_fit_cap(t, c, max_w, sx) for t, c in zip(texts, caps)]
    top = float(st["top"])
    for i, (t, c, s0) in enumerate(zip(texts, caps, starts)):
        a.add(s0, em.end, t, c, x, top + c / 2, anchor=6 if st["align"] == "right" else 5,
              accent=(em.style == "center_build" and c > float(st["cap"]) * 1.2))
        top += c + (float(st["gap"]) if em.style == "center_build" else float(st["pitch"]) - float(st["cap"]))


def merge_cfg(over: dict | None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)

    def merge(dst: dict, src: dict) -> None:
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                merge(dst[k], v)
            else:
                dst[k] = v

    merge(cfg, over or {})
    return cfg


def build_ass(words: Sequence[Word], cfg_override: dict | None, canvas: tuple[int, int], duration: float,
              emphasis: str = "auto") -> tuple[str, dict]:
    """Zwraca (tekst pliku ASS, statystyki)."""
    cfg = merge_cfg(cfg_override)
    run, a = cfg["running"], _Ass(cfg, canvas)
    picks = pick_emphasis(words, duration, cfg) if emphasis != "off" else []
    used = {id(w) for p in picks for w in p.words}
    for p in picks:
        _add_emphasis(a, p, cfg, canvas)

    # napisy bieżące: tylko słowa spoza fraz akcentowych, grupowane w ciągłych odcinkach
    runs, cur = [], []
    for w in words:
        if id(w) in used:
            if cur:
                runs.append(cur)
            cur = []
        else:
            cur.append(w)
    if cur:
        runs.append(cur)
    blocked = [(p.start, p.end) for p in picks if cfg["styles"][p.style].get("blocks_running")]
    lead, hold = float(run["lead_s"]), float(run["hold_after_s"])
    cap = float(run["cap_px"])
    center_y = float(run["cap_top_px"]) + cap / 2
    n_groups = 0
    for chunk in runs:
        groups = group_words(chunk, int(run["max_words"]), int(run["short_word_max_chars"]))
        for k, g in enumerate(groups):
            nxt = groups[k + 1] if k + 1 < len(groups) else None
            start = max(0.0, g.start - lead)
            end = (nxt.start - lead) if nxt and nxt.start - g.end < 0.5 else g.end + hold
            if nxt:
                end = min(end, nxt.start - lead)
            end = max(end, start + 0.12)
            if any(start < b1 and end > b0 for b0, b1 in blocked):
                continue  # pod takim stosem napis bieżący by się na niego nakładał (w rolce też go tam nie ma)
            a.add(start, end, _clean_text(g.text), cap, canvas[0] / 2, center_y)
            n_groups += 1
    return a.render(), {"words": len(words), "groups": n_groups, "emphasis": len(picks),
                        "styles": [p.style for p in picks]}
