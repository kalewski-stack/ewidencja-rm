"""Kotwice w mowie: czas elementu grafik podany jako fraza, którą mówisz, zamiast sekund.

W planie zamiast `"at": 12.4` piszesz `"at": "siedemset wydarzeń"`. Przy montażu fraza jest szukana w transkrypcji i zamienia
się na czas, w którym zaczynasz ją mówić. Dzięki temu plan powstaje razem ze scenariuszem i działa przy każdym nagraniu tego
samego tekstu, nawet gdy tempo mowy jest inne.

Pola z frazami (w elemencie i w efekcie):
  at     początek: czas, w którym pada pierwsze słowo frazy (nth: który raz, domyślnie 1; shift: przesunięcie w sekundach)
  until  koniec: czas, w którym kończy się ostatnie słowo frazy, szukanej po początku (until_shift: przesunięcie)
  active (lista kroków), focus_at (karty), count_at (liczniki): fraza zamiast sekund od startu elementu
"""
from __future__ import annotations

import copy
import difflib
import re
import unicodedata
from typing import Sequence

from .core import PlanError

LOCAL_FIELDS = ("focus_at", "count_at")  # pola elementu z czasem względnym (sekundy od jego startu)
MIN_DUR = 0.2


def norm(word: str) -> str:
    """Słowo bez wielkości liter, polskich znaków i interpunkcji: „Wydarzeń,” -> „wydarzen”."""
    s = unicodedata.normalize("NFKD", word.lower().replace("ł", "l"))
    return re.sub(r"[^0-9a-z]+", "", "".join(c for c in s if not unicodedata.combining(c)))


def _same(a: str, b: str) -> bool:
    if a == b:
        return True
    return min(len(a), len(b)) >= 5 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.84  # drobne różnice zapisu


class SpokenIndex:
    """Słowa z transkrypcji (czasy na osi gotowego filmu) z wyszukiwaniem fraz."""

    def __init__(self, words: Sequence):
        rows = [(norm(w.text), float(w.start), float(w.end), str(w.text)) for w in words]
        self.words = [r for r in rows if r[0]]

    def find(self, phrase: str, nth: int = 1, after: float = 0.0) -> tuple[float, float]:
        """(początek pierwszego słowa, koniec ostatniego) n-tego wystąpienia frazy, które zaczyna się nie wcześniej niż `after`."""
        toks = [t for t in (norm(p) for p in str(phrase).split()) if t]
        if not toks:
            raise PlanError("Pusta fraza zamiast czasu.")
        if nth < 1:
            raise PlanError(f"nth musi być co najmniej 1 (fraza „{phrase}”).")
        n = len(toks)
        hits = [i for i in range(len(self.words) - n + 1)
                if self.words[i][1] >= after - 1e-6 and all(_same(toks[j], self.words[i + j][0]) for j in range(n))]
        if len(hits) < nth:
            raise PlanError(self._not_found(phrase, toks, nth, len(hits), after))
        i = hits[nth - 1]
        return self.words[i][1], self.words[i + n - 1][2]

    def _not_found(self, phrase: str, toks: list[str], nth: int, found: int, after: float) -> str:
        msg = f"Nie znalazłem w mowie frazy „{phrase}”"
        if found:
            msg += f" (szukane wystąpienie nr {nth}, jest {found})"
        if after > 0:
            msg += f" po {after:.1f} s"
        n, target, best, at = len(toks), " ".join(toks), 0.0, 0
        for i in range(max(1, len(self.words) - n + 1)):
            win = " ".join(w[0] for w in self.words[i:i + n])
            r = difflib.SequenceMatcher(None, target, win).ratio()
            if r > best:
                best, at = r, i
        if best >= 0.5 and self.words:
            near = " ".join(w[3] for w in self.words[at:at + n])
            msg += f". Najbliższy fragment: „{near}” w {self.words[at][1]:.1f} s"
        return msg + ". Zapisz frazę tak, jak pada w transkrypcji (plik .slowa.json obok filmu)."


def _is_phrase(v) -> bool:
    """Tekst, który nie jest liczbą („siedemset wydarzeń”, ale nie „12.5”)."""
    if not isinstance(v, str):
        return False
    try:
        float(v)
    except ValueError:
        return True
    return False


def _items(raw: dict):
    for i, spec in enumerate(raw.get("elements", []) or [], 1):
        if isinstance(spec, dict):
            yield f"Element {i}", spec
    for i, spec in enumerate(raw.get("effects", []) or [], 1):
        if isinstance(spec, dict):
            yield f"Efekt {i}", spec


def has_phrases(raw) -> bool:
    """Czy plan używa fraz z mowy zamiast sekund (a więc potrzebuje transkrypcji)."""
    if not isinstance(raw, dict):
        return False
    for _, spec in _items(raw):
        if _is_phrase(spec.get("at")) or _is_phrase(spec.get("until")):
            return True
        if any(_is_phrase(spec.get(k)) for k in LOCAL_FIELDS):
            return True
        if isinstance(spec.get("active"), list) and any(_is_phrase(a) for a in spec["active"]):
            return True
    return False


def resolve(raw: dict, words: Sequence) -> dict:
    """Kopia planu, w której frazy zastąpiono czasami (sekundy na osi filmu). Plan bez fraz wraca bez zmian."""
    if not has_phrases(raw):
        return raw
    if not words:
        raise PlanError("Plan używa fraz z mowy zamiast sekund, a nie ma transkrypcji. Uruchom montaż z napisami "
                        "(rozpoznawanie mowy) albo podaj gotową transkrypcję: --words plik.json.")
    index = SpokenIndex(words)
    out = copy.deepcopy(raw)
    for label, spec in _items(out):
        try:
            _resolve_one(spec, index)
        except PlanError as exc:
            kind = f" ({spec['type']})" if spec.get("type") else ""
            raise PlanError(f"{label}{kind}: {exc}") from exc
    return out


def _resolve_one(spec: dict, index: SpokenIndex) -> None:
    if _is_phrase(spec.get("at")):
        start, _ = index.find(spec["at"], int(spec.get("nth", 1)))
        spec["said"] = spec["at"]  # zostaje do opisu harmonogramu
        spec["at"] = round(start + float(spec.get("shift", 0.0)), 3)
    if _is_phrase(spec.get("until")):
        if "at" not in spec:
            raise PlanError("until wymaga czasu startu (at).")
        _, end = index.find(spec["until"], int(spec.get("until_nth", 1)), after=float(spec["at"]))
        dur = end + float(spec.get("until_shift", 0.0)) - float(spec["at"])
        if dur < MIN_DUR:
            raise PlanError(f"koniec (fraza „{spec['until']}”) wypada tuż po początku albo przed nim: element trwałby {dur:.2f} s.")
        spec["dur"] = round(dur, 3)
    base = float(spec["at"]) if isinstance(spec.get("at"), (int, float)) else 0.0
    for key in LOCAL_FIELDS:
        if _is_phrase(spec.get(key)):
            spec[key] = round(index.find(spec[key], 1, after=base)[0] - base, 3)
    act = spec.get("active")
    if isinstance(act, list) and any(_is_phrase(a) for a in act):
        prev, res = base, []
        for a in act:
            if _is_phrase(a):
                t = index.find(a, 1, after=prev)[0]
                prev = t + 0.01  # kolejny krok szukamy dalej niż poprzedni
                res.append(round(t - base, 3))
            else:
                res.append(a)
        spec["active"] = res
