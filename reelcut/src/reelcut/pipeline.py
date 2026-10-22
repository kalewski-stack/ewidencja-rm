"""Potok główny: wideo użytkownika -> rolka pocięta wg szablonu."""
from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import captions, media, render
from .planner import Plan, build_plan, describe_plan
from .template import DATA_DIR, load_template

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts", ".m2ts", ".mpg", ".mpeg", ".3gp"}
FONT_FILE = DATA_DIR / "Anton-Regular.ttf"

LogFn = Callable[[str], None]
ProgressFn = Callable[[float, str], None]


@dataclass
class Options:
    template: str | None = None
    broll: tuple[Path, ...] = ()
    captions: str = "auto"  # auto = jeśli jest faster-whisper | on = wymagane | off
    lang: str = "pl"
    model: str = "small"
    words_file: Path | None = None  # gotowa transkrypcja (poprawiona ręcznie) zamiast Whispera
    emphasis: str = "auto"  # auto | off
    max_zoom: float = 1.6
    focus: tuple[float, float] = (0.5, 0.40)
    tighten: bool = True
    snap: bool = True
    grade: str = "none"
    fps: int | None = None
    seed: int = 7
    crf: int = 18
    preset: str = "medium"
    normalize: bool = True
    dry_run: bool = False
    keep_temp: bool = False


@dataclass
class Result:
    output: Path | None
    plan: Plan
    plan_text: str
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0
    captions_used: bool = False
    caption_stats: dict = field(default_factory=dict)
    words_file: Path | None = None
    input_seconds: float = 0.0
    master_seconds: float = 0.0


def collect_broll(paths: tuple[Path, ...], warnings: list[str]) -> list[media.MediaInfo]:
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXT and not f.name.startswith("."))
        elif p.exists():
            files.append(p)
        else:
            warnings.append(f"Pomijam B-roll, którego nie ma: {p}")
    clips = []
    for f in files:
        try:
            info = media.probe(f)
        except media.MediaError as exc:
            warnings.append(f"Pomijam B-roll {f.name}: {exc}")
            continue
        if info.has_video and info.duration >= 0.5:
            clips.append(info)
        else:
            warnings.append(f"Pomijam B-roll {f.name}: brak obrazu albo krócej niż 0,5 s.")
    return clips


def default_output(a_roll: Path) -> Path:
    base = a_roll.with_name(f"{a_roll.stem}_rolka.mp4")
    n = 2
    while base.exists():
        base = a_roll.with_name(f"{a_roll.stem}_rolka_{n}.mp4")
        n += 1
    return base


def run(a_roll: str | Path, out: str | Path | None, opts: Options, log: LogFn = print,
        progress: ProgressFn | None = None) -> Result:
    t0 = time.time()
    a_roll = Path(a_roll)
    tpl = load_template(opts.template)
    fps = opts.fps or tpl.fps
    canvas = tpl.canvas
    warnings: list[str] = []

    def prog(lo: float, hi: float, label: str):
        if progress:
            progress(lo, label)
        return (lambda f: progress(lo + (hi - lo) * f, label)) if progress else None

    info = media.probe(a_roll)
    if not info.has_video:
        raise media.MediaError("W pliku nie ma obrazu. Wskaż plik wideo.")
    if info.duration < 3:
        raise media.MediaError("Nagranie jest krótsze niż 3 sekundy. Nie ma czego ciąć.")
    log(f"Wideo: {a_roll.name}, {info.width}x{info.height}, {info.duration:.1f} s, "
        f"{'z dźwiękiem' if info.has_audio else 'BEZ dźwięku'}")
    if info.width > info.height:
        warnings.append("Nagranie jest poziome. Do rolki 9:16 wycinam środek kadru (ustaw --focus, jeśli mówisz z boku). "
                        "Najlepiej nagrywać w pionie.")

    # 1) dźwięk: pauzy i granice mowy
    prog(0.0, 0.05, "Analiza dźwięku")
    env: list[float] = []
    total_f = int(info.duration * fps)
    keep = [(0, total_f)]
    if info.has_audio:
        env = media.level_envelope(media.read_pcm(a_roll))
        if opts.tighten:
            pauses = media.detect_pauses(env, min_pause=tpl.max_pause_s)
            keep = media.keep_ranges(info.duration, pauses, tpl.max_pause_s, tpl.keep_pause_s, fps)
    else:
        warnings.append("Brak ścieżki dźwiękowej: pomijam skracanie pauz i napisy.")
    master_frames = sum(b - a for a, b in keep)
    master_s = master_frames / fps
    if master_s < info.duration - 0.3:
        log(f"Skracam pauzy: {info.duration:.1f} s → {master_s:.1f} s ({len(keep) - 1} cięć w ciszy)")

    # granice mowy z samej głośności (w osi mastera)
    breaks: list[tuple[int, float]] = []
    for f, strength in media.speech_breaks(env, fps) if env else []:
        m = media.map_to_master(f, keep)
        if m is not None:
            breaks.append((int(round(m)), strength))
    breaks += [(j, 3.0) for j in media.join_frames(keep)]

    clips = collect_broll(opts.broll, warnings)
    if opts.broll and not clips:
        warnings.append("Nie znalazłem użytecznego B-rolla: wstawki zrobię z kadrów Twojego nagrania.")

    plan = build_plan(tpl, master_frames, fps, has_broll=bool(clips), breaks=breaks, snap=opts.snap,
                      max_zoom=opts.max_zoom, focus=opts.focus)
    warnings += plan.warnings
    if opts.dry_run:
        return Result(None, plan, describe_plan(plan), warnings, time.time() - t0,
                      input_seconds=info.duration, master_seconds=master_s)

    workdir = Path(tempfile.mkdtemp(prefix="reelcut_"))
    out_path = Path(out) if out else default_output(a_roll)
    try:
        # 2) master
        geom = render.master_geometry(info.width, info.height, canvas, opts.focus[0])
        master = workdir / "master.mkv"
        log("Buduję materiał roboczy (kadr 9:16, skrócone pauzy)...")
        render.build_master(a_roll, info, keep, geom, master, workdir, fps, prog(0.05, 0.35, "Materiał roboczy"))
        master_info = media.probe(master)

        # 3) napisy
        ass_name = fonts_dir = None
        words: list[captions.Word] = []
        cap_stats: dict = {}
        words_path: Path | None = None
        want_caps = opts.captions != "off" and info.has_audio
        if want_caps:
            try:
                if opts.words_file:
                    words = captions.load_words(opts.words_file)
                    log(f"Wczytano gotową transkrypcję: {len(words)} słów.")
                else:
                    prog(0.35, 0.55, "Rozpoznawanie mowy")
                    words = captions.transcribe(media.read_pcm(master), model=opts.model, language=opts.lang, log=log)
                    log(f"Rozpoznano {len(words)} słów.")
            except captions.CaptionsUnavailable as exc:
                if opts.captions == "on":
                    raise
                warnings.append(f"{exc} Robię montaż bez napisów.")
                want_caps = False
            except (OSError, RuntimeError, ValueError) as exc:  # np. brak internetu przy pierwszym pobraniu modelu
                msg = (f"Rozpoznawanie mowy nie powiodło się ({type(exc).__name__}: {exc}). Przy pierwszym uruchomieniu "
                       "model trzeba pobrać z internetu.")
                if opts.captions == "on":
                    raise media.MediaError(msg) from exc
                warnings.append(msg + " Robię montaż bez napisów.")
                want_caps = False
        if want_caps and words:
            ass_text, cap_stats = captions.build_ass(words, tpl.captions, canvas, master_s, opts.emphasis)
            (workdir / "captions.ass").write_text(ass_text, encoding="utf-8")
            (workdir / "fonts").mkdir(exist_ok=True)
            shutil.copy(FONT_FILE, workdir / "fonts" / FONT_FILE.name)
            ass_name, fonts_dir = "captions.ass", "fonts"
            words_path = out_path.with_suffix(".slowa.json")
            captions.save_words(words, words_path)
            # granice zdań z transkrypcji są dokładniejsze niż z samej głośności: przeliczamy plan
            plan = build_plan(tpl, master_frames, fps, has_broll=bool(clips),
                              breaks=breaks + captions.word_breaks(words, fps), snap=opts.snap,
                              max_zoom=opts.max_zoom, focus=opts.focus)
            log(f"Napisy: {cap_stats['groups']} napisów bieżących, {cap_stats['emphasis']} fraz akcentowych.")
        elif want_caps:
            warnings.append("Nie rozpoznano żadnej mowy: robię montaż bez napisów.")

        # 4) render
        picks = render.assign_broll(plan.slots, clips, fps, opts.seed) if clips else {}
        log(f"Składam rolkę: {len(plan.slots)} ujęć, {plan.total_frames / fps:.1f} s...")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            render.render_final(master, master_info, geom.size, plan, picks, out_path, workdir, canvas=canvas,
                                grade=opts.grade, ass_file=ass_name, fonts_dir=fonts_dir, normalize=opts.normalize,
                                lufs=tpl.lufs, tp=tpl.true_peak, lra=tpl.lra, crf=opts.crf, preset=opts.preset,
                                on_progress=prog(0.55 if want_caps else 0.35, 1.0, "Montaż"))
        except Exception:
            out_path.unlink(missing_ok=True)
            raise
        final = media.probe(out_path)
        if abs(final.duration - plan.total_frames / fps) > 0.25:
            warnings.append(f"Długość wyniku ({final.duration:.2f} s) odbiega od planu ({plan.total_frames / fps:.2f} s).")
        if progress:
            progress(1.0, "Gotowe")
        return Result(out_path, plan, describe_plan(plan), warnings, time.time() - t0,
                      captions_used=bool(ass_name), caption_stats=cap_stats, words_file=words_path,
                      input_seconds=info.duration, master_seconds=master_s)
    finally:
        if not opts.keep_temp:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            log(f"Pliki tymczasowe zostawiono w: {workdir}")
