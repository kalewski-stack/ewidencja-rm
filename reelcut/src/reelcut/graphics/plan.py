"""Plan grafik: lista elementów z czasami (JSON) i efektów na obrazie (np. rozmycie głowy)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import script
from .anchors import has_phrases, resolve as resolve_anchors
from .core import Brand, Layer, Layout, PlanError, load_brand
from . import (cards as _cards, diagrams as _diagrams, extras as _extras, format2 as _format2, lockup as _lockup,  # noqa: F401  (rejestrują typy)
               motion as _motion, profile as _profile)
from .elements import REGISTRY, VARIANTS, Context, Element
from .transitions import Transition

EFFECT_TYPES = ("blur",)


@dataclass
class GraphicsPlan:
    elements: list[Element]
    effects: list[dict] = field(default_factory=list)
    brand: Brand | None = None
    warnings: list[str] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)  # przejścia między scenami (obróbka całej klatki w oknie wokół cięcia)

    @property
    def duration(self) -> float:
        ends = ([e.end for e in self.elements] + [float(f["at"]) + float(f["dur"]) for f in self.effects]
                + [tr.end for tr in self.transitions])
        return max(ends) if ends else 0.0

    def active(self, t: float) -> list[Element]:
        return sorted((e for e in self.elements if e.active(t)), key=lambda e: e.z)

    def transitions_at(self, t: float) -> list[Transition]:
        return [tr for tr in self.transitions if tr.active(t)]

    def describe(self) -> str:
        rows = [f"{e.start:6.2f}-{e.end:6.2f} s  {e.kind:<9} {_short(e.spec)}" + (f"  (po słowach „{e.spec['said']}”)" if e.spec.get("said") else "")
                for e in sorted(self.elements, key=lambda e: e.start) if e.kind != "captions"]
        rows += [f"{float(f['at']):6.2f}-{float(f['at']) + float(f['dur']):6.2f} s  efekt: {f['type']}"
                 + (f"  (po słowach „{f['said']}”)" if f.get("said") else "") for f in self.effects]
        rows += [f"{tr.start:6.2f}-{tr.end:6.2f} s  przejście: {tr.kind}" + (f" ({tr.dir})" if tr.dir else "")
                 + (f"  (po słowach „{tr.said}”)" if tr.said else "") for tr in sorted(self.transitions, key=lambda x: x.at)]
        return "\n".join(rows)


def _short(spec: dict) -> str:
    if isinstance(spec.get("lines"), list):  # hasło (lockup): wiersze słów
        return " / ".join(" ".join(str(w.get("w", "")) for w in ln.get("words", []) if isinstance(w, dict))
                          for ln in spec["lines"] if isinstance(ln, dict))[:60]
    for key in ("text", "label", "title", "items", "rows", "number", "value"):
        if key in spec:
            v = spec[key]
            if isinstance(v, list):
                v = ", ".join(str(x.get("label", x.get("text", x.get("title", x))) if isinstance(x, dict) else x) for x in v[:4])
            return str(v)[:50]
    return ""


def _free_placement(e: Element) -> bool:
    """Elementy, które same wyznaczają miejsce (ruchoma ścieżka, nad głową, współrzędne x/y), nie liczą się do stref."""
    s = e.spec
    return (e.kind == "captions" or getattr(e, "free_placement", False) or "x" in s or "y" in s or bool(s.get("path"))
            or s.get("anchor") == "head")


def lint(elements: list[Element]) -> list[str]:
    """Ostrzeżenia o elementach, które w tym samym czasie zajmują tę samą strefę kadru (rysowałyby się jeden na drugim)."""
    out: list[str] = []
    bound = [e for e in elements if not _free_placement(e)]
    for i, a in enumerate(bound):
        for b in bound[i + 1:]:
            zone = a.spec.get("zone", a.default_zone)
            if zone != b.spec.get("zone", b.default_zone):
                continue
            if min(a.end, b.end) - max(a.start, b.start) > 0.5:
                out.append(f"„{a.kind}” ({a.start:.1f}-{a.end:.1f} s) i „{b.kind}” ({b.start:.1f}-{b.end:.1f} s) zajmują strefę „{zone}” "
                           f"w tym samym czasie; przestaw jeden (pole zone albo x/y) albo przesuń czas.")
    for e in elements:
        out += [f"„{e.kind}” ({e.start:.1f}-{e.end:.1f} s): {note}" for note in e.notes]
    return out


def _probe(e: Element, W: int, H: int):
    """Obwiednia elementu pod koniec jego życia (po wejściu i odliczaniu), albo None, gdy nic nie rysuje."""
    t = min(e.end - 0.01, e.start + max(e.d_in + 0.1, e.dur - e.d_out - 0.05))
    layer = Layer((W, H))
    e.draw(layer, t)
    return layer.img.getchannel("A").point(lambda v: 255 if v >= 24 else 0).getbbox()  # bez ledwo widocznych ogonów cienia


def layout_notes(elements: list[Element], effects: list[dict], ctx: Context) -> list[str]:
    """Ostrzeżenia o układzie: element wychodzi poza kadr albo zasłania twarz (chyba że w tym czasie obraz jest rozmyty)."""
    W, H, L = ctx.W, ctx.H, ctx.layout
    fh = L.face_h * H
    fw = 0.78 * fh
    face = (L.face_cx * W - fw / 2, L.face_cy * H - fh / 2, L.face_cx * W + fw / 2, L.face_cy * H + fh / 2)
    out: list[str] = []
    for e in elements:
        if e.kind == "captions" or e.spec.get("path") or getattr(e, "no_lint", False):  # napisy mają własne miejsce, ruchomy profil sam wybiera trasę
            continue
        bb = _probe(e, W, H)
        if bb is None:
            continue
        x0, y0, x1, y1 = bb
        where = "x/y" if ("x" in e.spec or "y" in e.spec) else e.spec.get("zone", e.default_zone)
        label = f"„{e.kind}” ({e.start:.1f}-{e.end:.1f} s)"
        if (x0 <= 0 or y0 <= 0 or x1 >= W or y1 >= H) and not e.spec.get("bleed"):
            out.append(f"{label}: nie mieści się w kadrze (zajmuje {x0}-{x1} px z {W} w poziomie, strefa „{where}”): "
                       "zmniejsz rozmiar (size), skróć tekst albo wybierz inną strefę.")
            continue
        if where == "head" or e.spec.get("anchor") == "head" or e.behind or getattr(e, "thin", False):
            continue  # świadomy wybór albo cienka dekoracja (strzałka, linia, kropki), która może wskazywać na twarz
        ix = max(0.0, min(x1, face[2]) - max(x0, face[0]))
        iy = max(0.0, min(y1, face[3]) - max(y0, face[1]))
        blurred = any(min(e.end, f["at"] + f["dur"]) - max(e.start, f["at"]) > 0.5 for f in effects)
        if ix * iy > 0.15 * fw * fh and not blurred:
            out.append(f"{label}: zasłania twarz (strefa „{where}”): przestaw na inną strefę albo dodaj rozmycie obrazu na ten czas (rozmycie: tak).")
    return out


def build_plan(raw: dict, ctx: Context) -> GraphicsPlan:
    if not isinstance(raw, dict):
        raise PlanError("Plan grafik musi być obiektem JSON z listą elements.")
    if raw.get("schema", 1) != 1:
        raise PlanError("Nieznana wersja planu grafik (oczekiwano schema=1).")
    raw = resolve_anchors(raw, ctx.words)  # frazy z mowy -> sekundy
    elements: list[Element] = []
    for i, spec in enumerate(raw.get("elements", []), 1):
        kind = spec.get("type")
        if kind not in REGISTRY:
            raise PlanError(f"Element {i}: nieznany typ „{kind}”. Dostępne: {', '.join(sorted(REGISTRY))}.")
        try:
            elements.append(VARIANTS.get((kind, spec.get("style")), REGISTRY[kind])(spec, ctx))
        except PlanError as exc:
            raise PlanError(f"Element {i} ({kind}): {exc}") from exc
    effects = []
    for i, f in enumerate(raw.get("effects", []), 1):
        if f.get("type") not in EFFECT_TYPES or "at" not in f or "dur" not in f:
            raise PlanError(f"Efekt {i}: wymagane pola type ({'/'.join(EFFECT_TYPES)}), at i dur.")
        effects.append({"type": f["type"], "at": float(f["at"]), "dur": float(f["dur"]), "sigma": float(f.get("sigma", 14)),
                        "dim": float(f.get("dim", 0.25)), "ramp": float(f.get("ramp", 0.4)), "said": f.get("said")})
    transitions = [Transition.from_spec(spec) for spec in raw.get("transitions", []) or []]
    notes = [str(n) for n in raw.get("_notes", [])]  # uwagi dołożone przy składaniu planu z szablonem (np. za długie wyróżnienie w haśle)
    return GraphicsPlan(elements, effects, ctx.brand, lint(elements) + layout_notes(elements, effects, ctx) + notes, transitions)


def plan_needs_words(path: str | Path) -> bool:
    """Czy plan w pliku używa fraz z mowy (a więc przy montażu potrzebna jest transkrypcja). Zły plik: nie, błąd zgłosi budowa planu."""
    if script.is_script(path):
        return Path(path).exists()  # scenariusz ze znacznikami zawsze wymaga mowy
    try:
        return has_phrases(json.loads(Path(path).read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError):
        return False


def with_template(raw: dict, tpl, words: list, duration_s: float, *, layer_captions: bool) -> dict:
    """Dokłada do planu to, co daje szablon: napisy warstwy grafik (ustawienia szablonu i to, co do nich dopisał scenariusz, np. wyróżnione
    frazy), hasła Formatu 3 ze słów w gwiazdkach (słowa hasła znikają z napisów i napisy się na ten czas chowają) oraz tło trybu motion,
    bo tam cały obraz rysują grafiki. Gdy szablon ma napisy, a użytkownik je wyłączył (`layer_captions` fałsz), element napisów ze scenariusza
    odpada, a hasła zostają."""
    raw.setdefault("elements", [])
    user = next((e for e in raw["elements"] if e.get("type") == "captions"), {})
    made: list[dict] = []
    skip: list[list[float]] = []
    if tpl.graphics.get("lockup") is not None and user.get("emphasis") and words:  # Format 3: wyróżnione frazy (*tak*) to hasła z dużym słowem
        made, skip, notes = _lockup.from_emphasis(words, user["emphasis"], tpl.graphics["lockup"])
        raw["elements"] = [e for e in raw["elements"] if not (e.get("type") == "lockup" and e.get("auto"))] + made
        if notes:
            raw["_notes"] = list(raw.get("_notes", [])) + [f"hasło: {n}" for n in notes]
    if layer_captions and words:
        cap = {"type": "captions", **tpl.graphics.get("captions", {}), **{k: v for k, v in user.items() if k not in ("type", "at", "dur")}}
        if skip:
            cap["skip"] = list(cap.get("skip", [])) + skip
            cap["hide"] = list(cap.get("hide", [])) + [[e["at"], round(e["at"] + e["dur"], 3)] for e in made]
        raw["elements"] = [e for e in raw["elements"] if e.get("type") != "captions"] + [cap]
    elif tpl.graphics.get("captions") is not None:  # szablon z napisami warstwy grafik, ale napisy wyłączone (--no-captions): nie rysujemy ich
        raw["elements"] = [e for e in raw["elements"] if e.get("type") != "captions"]
    if tpl.motion and not any(e.get("type") == "backdrop" for e in raw["elements"]):
        raw["elements"].insert(0, {"type": "backdrop", "at": 0, "dur": round(duration_s + 1.0, 3), **tpl.graphics.get("backdrop", {})})
    return raw


def load_plan(path: str | Path, ctx: Context | None = None, *, size: tuple[int, int] = (1080, 1920), fps: int = 30,
              brand: str | Path | None = None, face: tuple[float, float, float] | None = None,
              avatar: Path | None = None, words: list | None = None, template=None) -> GraphicsPlan:
    """Wczytuje plan z pliku JSON albo scenariusza. Gdy nie podasz ctx, buduje go z marki (domyślnie „Linia Kalewski”) i układu kadru;
    words (transkrypcja) potrzebne jest tylko planom z frazami zamiast sekund. Z szablonem (np. Motion) plan dostaje też to, co
    szablon dokłada przy montażu: tło i napisy ze słów scenariusza, więc podgląd wygląda jak film."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
        raw = script.to_plan(text, list(words or [])) if script.is_script(path) else json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"Nie da się wczytać planu grafik {path}: {exc}") from exc
    spoken, duration = list(words or []), 0.0
    if template is not None:
        cap = template.graphics.get("captions") or {}
        if spoken and cap.get("from_script") and script.is_script(path):
            fixed, coverage = script.words_from_script(text, spoken)
            if fixed and coverage >= 0.8:
                spoken = fixed
        ends = [float(w.end) + 0.5 for w in spoken] + [float(e.get("at", 0)) + float(e.get("dur", 0) or 0) for e in raw.get("elements", [])]
        duration = max(ends, default=0.0)
        raw = with_template(raw, template, spoken, duration, layer_captions=bool(cap) and bool(spoken))
    if ctx is None:
        b = load_brand(brand if brand is not None else raw.get("brand"))
        lay = Layout(size[0], size[1], *(face or (0.55, 0.45, 0.17)))
        ctx = Context(b, lay, fps, path.parent, avatar, spoken, duration)
    return build_plan(raw, ctx)
