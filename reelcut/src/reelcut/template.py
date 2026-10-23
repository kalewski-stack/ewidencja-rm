"""Szablon montażu: typy, wczytanie i walidacja pliku JSON."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_TEMPLATE = DATA_DIR / "rolka_DeuOaXKtPBb.json"
USER_DIR = Path.home() / "ReelCut" / "szablony"  # tu lądują szablony zrobione poleceniem analyze


class TemplateError(ValueError):
    """Szablon jest uszkodzony albo niekompletny."""


@dataclass(frozen=True)
class Fx:
    type: str
    dur: float = 0.3
    edge: str = "start"  # przy którym cięciu ujęcia działa efekt przejścia (flash): "start" = na wejściu w ujęcie, "end" = na wyjściu z niego


@dataclass(frozen=True)
class FaceTarget:
    """Docelowy kadr twarzy w ujęciu wzorca (ułamki kadru): rozmiar i położenie."""
    h: float  # wysokość twarzy / wysokość kadru
    cx: float
    cy: float
    eye_y: float = 0.0


@dataclass(frozen=True)
class Segment:
    frames: int
    role: str  # "A" = mówiąca głowa, "B" = wstawka (B-roll)
    zoom: float = 1.0  # rezerwowy zoom względem najszerszego ujęcia, gdy nie widać twarzy
    alt: int = 0  # numer kadru zastępczego dla roli B, gdy nie ma B-rolla
    fx: tuple[Fx, ...] = ()
    note: str = ""
    face: FaceTarget | None = None


@dataclass(frozen=True)
class Template:
    name: str
    source: str
    fps: int
    canvas: tuple[int, int]
    segments: tuple[Segment, ...]
    hook: int
    outro: int
    elastic: int
    elastic_min_s: float
    elastic_max_s: float
    min_cut_s: float
    snap_tol_s: float
    alts: dict[int, dict]
    max_pause_s: float
    keep_pause_s: float
    lufs: float
    true_peak: float
    lra: float
    captions: dict
    look: dict
    dynamics: dict
    raw: dict
    mode: str = "cuts"  # cuts = rytm cięć z szablonu | single = jedno ujęcie bez cięć (grafiki robią dynamikę) | motion = bez obrazu z nagrania, lektor i grafiki
    graphics: dict = field(default_factory=dict)  # domyślne ustawienia warstwy grafik (napisy biegnące, marka)
    keep_colors: bool = False  # szablon cięć, który nie przenosi kolorów wzorca: nagranie zostaje w swoich kolorach (kolory marki mają grafiki)

    @property
    def motion(self) -> bool:
        """Motion: obraz powstaje z grafik, z pliku bierzemy tylko dźwięk (lektor)."""
        return self.mode == "motion"

    @property
    def preview_layer(self) -> bool:
        """Czy podgląd grafik (`grafiki --template`) ma dołożyć to, co szablon rysuje sam: tło i napisy w motion, napisy i hasła w Formacie 3."""
        return self.motion or self.graphics.get("lockup") is not None

    @property
    def single_take(self) -> bool:
        return self.mode in ("single", "motion")

    @property
    def total_frames(self) -> int:
        return sum(s.frames for s in self.segments)

    @property
    def duration_s(self) -> float:
        return self.total_frames / self.fps

    @property
    def ladder_max(self) -> float:
        """Największy zoom drabinki kadrów (ujęcia A) względem najszerszego ujęcia."""
        return max([s.zoom for s in self.segments if s.role == "A"] + [1.0])


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise TemplateError(msg)


def parse_template(raw: dict) -> Template:
    _require(isinstance(raw, dict), "Szablon musi być obiektem JSON.")
    _require(raw.get("schema") == 1, "Nieznana wersja szablonu (oczekiwano schema=1).")
    fps = raw.get("fps", 25)
    _require(isinstance(fps, int) and 1 <= fps <= 120, "Pole fps musi być liczbą całkowitą 1-120.")
    canvas = raw.get("canvas", [1080, 1920])
    _require(len(canvas) == 2 and all(isinstance(v, int) and v > 0 for v in canvas), "Pole canvas: [szer, wys].")

    segments = []
    for i, s in enumerate(raw.get("segments", []), 1):
        frames, role = s.get("frames"), s.get("role")
        _require(isinstance(frames, int) and frames >= 1, f"Ujęcie {i}: frames musi być liczbą >= 1.")
        _require(role in ("A", "B"), f"Ujęcie {i}: role musi być 'A' albo 'B'.")
        zoom = float(s.get("zoom", 1.0))
        _require(zoom >= 1.0, f"Ujęcie {i}: zoom nie może być mniejszy niż 1.0.")
        fx = tuple(Fx(str(f["type"]), float(f.get("dur", 0.3)), str(f.get("edge", "start"))) for f in s.get("fx", []))
        _require(all(f.edge in ("start", "end") for f in fx), f"Ujęcie {i}: fx.edge to start albo end.")
        face = None
        if s.get("face"):
            fc = s["face"]
            face = FaceTarget(float(fc["h"]), float(fc["cx"]), float(fc["cy"]), float(fc.get("eye_y", 0.0)))
            _require(0.02 < face.h < 0.95 and 0 <= face.cx <= 1 and 0 <= face.cy <= 1,
                     f"Ujęcie {i}: face musi mieć h w (0.02, 0.95) oraz cx, cy w [0, 1].")
        segments.append(Segment(frames, role, zoom, int(s.get("alt", 0)), fx, str(s.get("note", "")), face))
    mode = raw.get("mode", "cuts")
    _require(mode in ("cuts", "single", "motion"), "Pole mode: cuts, single albo motion.")
    st = raw.get("structure", {})
    if mode in ("single", "motion"):
        _require(len(segments) == 1 and segments[0].role == "A",
                 "Szablon jednoujęciowy (mode=single albo motion) ma dokładnie jedno ujęcie z rolą A.")
        hook, outro, elastic = 0, 1, 0
    else:
        _require(len(segments) >= 3, "Szablon musi mieć co najmniej 3 ujęcia.")
        hook, outro = int(st.get("hook", 1)), int(st.get("outro", 1))
        elastic = int(st.get("elastic", len(segments) - 1))
        _require(hook >= 0 and outro >= 1 and hook + outro < len(segments) + 1, "structure: błędne hook/outro.")
        _require(len(segments) - outro <= elastic < len(segments), "structure.elastic musi wskazywać ujęcie z sekcji outro.")
        _require(segments[elastic].role == "A", "Ujęcie elastyczne musi mieć rolę A.")

    pauses, audio = raw.get("pauses", {}), raw.get("audio", {})
    return Template(
        name=str(raw.get("name", "szablon")),
        source=str(raw.get("source", "")),
        fps=fps,
        canvas=(canvas[0], canvas[1]),
        segments=tuple(segments),
        hook=hook,
        outro=outro,
        elastic=elastic,
        elastic_min_s=float(st.get("elastic_min_s", 2.0)),
        elastic_max_s=float(st.get("elastic_max_s", 12.0)),
        min_cut_s=float(st.get("min_cut_s", 0.6)),
        snap_tol_s=float(st.get("snap_tol_s", 0.5)),
        alts={int(k): dict(v) for k, v in raw.get("alts", {}).items()},
        max_pause_s=float(pauses.get("max_pause_s", 0.5)),
        keep_pause_s=float(pauses.get("keep_pause_s", 0.35)),
        lufs=float(audio.get("lufs", -14.0)),
        true_peak=float(audio.get("true_peak", -1.0)),
        lra=float(audio.get("lra", 11.0)),
        captions=dict(raw.get("captions", {})),
        look=dict(raw.get("look", {})),
        dynamics=dict(raw.get("dynamics", {})),
        raw=raw,
        mode=mode,
        graphics=dict(raw.get("graphics", {})),
        keep_colors=bool(raw.get("keep_colors", False)),
    )


# Nazwy, którymi mówimy o formatach: format1 / format-1 / Format 2 itd. (wielkość liter, spacje, myślniki i podkreślenia bez znaczenia).
ALIASES = {"format1": "rolka_DeuOaXKtPBb", "format2": "format2", "format3": "format3", "motion": "motion", "rolkadez4fpjcr74": "format2"}


def resolve_alias(ref: str) -> str:
    return ALIASES.get(re.sub(r"[\s_\-]+", "", ref.lower()), ref)


def load_template(ref: str | Path | None = None) -> Template:
    """Wczytuje szablon: z pliku, z katalogu data/ (po nazwie lub aliasie format1, format2, format3, motion) albo z ~/ReelCut/szablony (user/nazwa)."""
    if ref is None:
        path = DEFAULT_TEMPLATE
    else:
        text = resolve_alias(str(ref))
        path = Path(text)
        if text.startswith("user/"):
            path = USER_DIR / f"{text[5:]}.json"
        elif not path.exists():
            path = DATA_DIR / (text if text.endswith(".json") else f"{text}.json")
        _require(path.exists(), f"Nie znaleziono szablonu: {ref}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateError(f"Plik {path.name} nie jest poprawnym JSON-em: {exc}") from exc
    return parse_template(raw)


def list_templates() -> list[tuple[str, str]]:
    """Lista (id, nazwa czytelna): wbudowane szablony, a po nich użytkownika (id zaczyna się od "user/")."""
    out = []
    for prefix, folder in (("", DATA_DIR), ("user/", USER_DIR)):
        order = {"rolka_DeuOaXKtPBb": 0, "format2": 1, "format3": 2, "motion": 3}  # Formaty 1-3 i motion na początku listy, dalej alfabetycznie
        for p in sorted(folder.glob("*.json"), key=lambda q: (order.get(q.stem, 4), q.stem)) if folder.exists() else []:
            try:
                out.append((prefix + p.stem, parse_template(json.loads(p.read_text(encoding="utf-8"))).name))
            except (TemplateError, json.JSONDecodeError):
                continue
    return out
