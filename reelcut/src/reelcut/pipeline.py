"""Potok główny: wideo użytkownika -> rolka pocięta wg szablonu."""
from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from . import captions, faces, graphics, look, media, render
from .planner import Plan, build_plan, describe_plan
from .template import DATA_DIR, load_template

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts", ".m2ts", ".mpg", ".mpeg", ".3gp"}
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".flac", ".aif", ".aiff", ".wma", ".caf"}  # nagranie głosu dla trybu motion
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
    max_zoom: float | None = None  # None = automatycznie z rozdzielczości nagrania (1.6 dla 1080p, do 2.6 dla 4K)
    framing: str = "auto"  # auto = po twarzy, gdy się da | on = wymagane | off = stałe zoomy z szablonu
    focus: tuple[float, float] = (0.5, 0.40)
    tighten: bool = True
    snap: bool = True
    look: float = 1.0  # siła dopasowania kolorów do wzorca, 0-1 (0 = obraz bez zmian)
    graphics: Path | None = None  # plan grafik (JSON): tytuły, karty, listy, liczniki z czasami na osi filmu
    brand: str | None = None  # marka grafik: plik JSON albo nazwa (domyślnie „Linia Kalewski”)
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
    face: dict = field(default_factory=dict)  # co wykryliśmy: pokrycie, wysokość i środek twarzy
    look: dict = field(default_factory=dict)  # jak dopasowaliśmy kolory
    graphics: dict = field(default_factory=dict)  # co narysowano: liczba elementów, marka, napisy biegnące


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


def auto_max_zoom(crop_w: int, canvas_w: int) -> float:
    """Największe sensowne przybliżenie: tyle, żeby wycinek nadal miał ok. 2/3 szerokości kanwy w pikselach źródła."""
    return round(max(1.0, min(2.6, 1.6 * crop_w / canvas_w)), 2)


def run(a_roll: str | Path, out: str | Path | None, opts: Options, log: LogFn = print,
        progress: ProgressFn | None = None) -> Result:
    t0 = time.time()
    # ffmpeg pracuje w katalogu roboczym, więc wszystkie ścieżki od użytkownika muszą być bezwzględne (inaczej „nagranie.mp4” nie istnieje)
    a_roll = Path(a_roll).resolve()
    out = Path(out).resolve() if out else None
    opts = replace(opts, broll=tuple(Path(p).resolve() for p in opts.broll),
                   words_file=Path(opts.words_file).resolve() if opts.words_file else None,
                   graphics=Path(opts.graphics).resolve() if opts.graphics else None)
    tpl = load_template(opts.template)
    fps = opts.fps or tpl.fps
    canvas = tpl.canvas
    warnings: list[str] = []

    def prog(lo: float, hi: float, label: str):
        if progress:
            progress(lo, label)
        return (lambda f: progress(lo + (hi - lo) * f, label)) if progress else None

    info = media.probe(a_roll)
    if tpl.motion:  # Motion: z pliku liczy się tylko dźwięk (lektor), obraz robią grafiki
        if not info.has_audio:
            raise media.MediaError("Motion potrzebuje lektora, a w pliku nie ma dźwięku. "
                                   "Wskaż nagranie głosu (wav, m4a, mp3) albo wideo z dźwiękiem.")
        if not opts.graphics:
            raise media.MediaError("Motion rysuje obraz ze scenariusza, a go nie podano. Dodaj --graphics scenariusz.txt "
                                   "(w interfejsie krok 3 „Grafiki”); składnię znaczników opisuje MOTION.md.")
        if info.has_video:
            warnings.append("Motion bierze z pliku tylko dźwięk: obraz powstaje z grafik, więc obrazu z nagrania nie użyję.")
    elif not info.has_video:
        raise media.MediaError("W pliku nie ma obrazu. Wskaż plik wideo.")
    if info.duration < 3:
        raise media.MediaError("Nagranie jest krótsze niż 3 sekundy. Nie ma czego ciąć.")
    log(f"{'Nagranie' if tpl.motion else 'Wideo'}: {a_roll.name}, "
        f"{f'{info.width}x{info.height}, ' if info.has_video else ''}{info.duration:.1f} s, "
        f"{'z dźwiękiem' if info.has_audio else 'BEZ dźwięku'}")
    log(media.ffmpeg_summary())
    if tpl.motion:
        geom = render.Geometry((canvas[0], canvas[1], 0, 0), (canvas[0], canvas[1]))
    else:
        if canvas[0] <= canvas[1] and info.width > info.height:
            warnings.append("Nagranie jest poziome. Do rolki 9:16 wycinam środek kadru (ustaw --focus, jeśli mówisz z boku). "
                            "Najlepiej nagrywać w pionie.")
        elif canvas[0] > canvas[1] and info.width <= info.height:
            warnings.append("Nagranie jest pionowe, a ten szablon robi film poziomy 16:9: wycinam z niego pas ze środka kadru (traci się góra i dół). "
                            "Najlepiej nagrywać poziomo.")
        geom = render.master_geometry(info.width, info.height, canvas, opts.focus[0])
    max_zoom = opts.max_zoom or auto_max_zoom(geom.crop[0], canvas[0])

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
    plan_args = dict(has_broll=bool(clips), snap=opts.snap, max_zoom=max_zoom, focus=opts.focus)

    if opts.dry_run:
        plan = build_plan(tpl, master_frames, fps, breaks=breaks, **plan_args)
        warnings += plan.warnings
        if opts.framing != "off" and not tpl.motion:
            warnings.append("Kadrowanie po twarzy i dobór napisów są liczone dopiero przy renderze.")
        text = describe_plan(plan)
        if opts.graphics:
            if graphics.plan_needs_words(opts.graphics) and not opts.words_file:
                text += "\n\nPlan grafik używa fraz z mowy: czasy poznasz po rozpoznaniu mowy (bez --dry-run) albo z gotową transkrypcją (--words)."
            else:
                try:
                    dry_words = captions.load_words(opts.words_file) if opts.words_file else []
                    dry_caps = bool(tpl.graphics.get("captions")) and opts.captions != "off" and bool(dry_words)  # frazy i karty też trafiają do planu
                    job = graphics.glue.prepare(opts.graphics, opts.brand, tpl, plan, None, Path("."), Path("."), dry_words, canvas,
                                                master_s, dry_caps, lambda m: None)
                    if job:
                        text += "\n\nGrafiki (czasy na osi gotowego filmu):\n" + job.plan.describe()
                        warnings += job.plan.warnings
                except (graphics.GraphicsUnavailable, graphics.PlanError) as exc:
                    raise media.MediaError(f"Plan grafik: {exc}") from exc
        return Result(None, plan, text, warnings, time.time() - t0,
                      input_seconds=info.duration, master_seconds=master_s)

    workdir = Path(tempfile.mkdtemp(prefix="reelcut_"))
    out_path = Path(out) if out else default_output(a_roll)
    try:
        # 2) master
        master = workdir / "master.mkv"
        if tpl.motion:
            log("Buduję materiał roboczy (dźwięk bez długich pauz, obraz z grafik)...")
            render.build_master_audio(a_roll, keep, canvas, master, workdir, fps, prog(0.05, 0.35, "Materiał roboczy"))
        else:
            log(f"Buduję materiał roboczy (kadr {'16:9' if canvas[0] > canvas[1] else '9:16'}, skrócone pauzy)...")
            render.build_master(a_roll, info, keep, geom, master, workdir, fps, prog(0.05, 0.35, "Materiał roboczy"))
        master_info = media.probe(master)

        # 3) twarz: rozmiar i położenie w Twoim nagraniu (do kadrowania jak we wzorcu)
        track, face_info = None, {}
        if opts.framing != "off" and not tpl.motion:
            try:
                prog(0.35, 0.4, "Szukam twarzy")
                track = faces.FaceTrack(faces.sample_faces(master, every_s=0.4))
                g = track.global_estimate()
                if g is None or track.coverage() < 0.25:
                    msg = "Nie widzę Twojej twarzy w większości nagrania, więc kadruję wg stałych zoomów z szablonu."
                    if opts.framing == "on":
                        raise media.MediaError(msg)
                    warnings.append(msg)
                    track = None
                else:
                    face_info = {"coverage": round(track.coverage(), 2), "h": round(g.h, 3), "cx": round(g.cx, 3),
                                 "cy": round(g.cy, 3)}
                    log(f"Twarz widoczna w {track.coverage() * 100:.0f}% próbek: wysokość {g.h * 100:.0f}% kadru, "
                        f"środek ({g.cx * 100:.0f}%, {g.cy * 100:.0f}%). Kadruję jak we wzorcu.")
            except faces.FacesUnavailable as exc:
                if opts.framing == "on":
                    raise media.MediaError(str(exc)) from exc
                warnings.append(f"{str(exc).rstrip('. ')}. Kadruję wg stałych zoomów z szablonu.")

        # 4) kolory: dopasowanie rozkładu jasności, barwy i nasycenia do wzorca (LUT 3D + winieta)
        look_chain, look_info = None, {}
        ref_look = tpl.look.get("A")
        if opts.look > 0 and ref_look:
            try:
                prog(0.4, 0.45, "Dopasowuję kolory")
                ref_stats = look.LookStats.from_dict(ref_look)
                user_stats = look.measure(look.read_frames(master, fps=2.0, size=(180, 320)))
                angle = look.vignette_angle(user_stats, ref_stats, opts.look, base_L=ref_stats.luma[5])
                if angle:  # krzywa tonalna ma korygować materiał już z winietą
                    user_stats = look.measure(look.read_frames(
                        master, fps=2.0, size=(180, 320),
                        post_filter=f"format=gbrp,{look.vignette_filter(angle)},format=rgb24"))
                look.write_cube(look.build_lut(user_stats, ref_stats, opts.look), workdir / "look.cube")
                look_chain = look.filter_chain("look.cube", angle)
                look_info = {"strength": opts.look, "median_L": [round(user_stats.luma[5], 1), round(ref_stats.luma[5], 1)],
                             "chroma": [round(user_stats.chroma, 1), round(ref_stats.chroma, 1)], "vignette_angle": angle}
                log(f"Kolory: dopasowanie do wzorca w {opts.look * 100:.0f}% (mediana jasności L* {user_stats.luma[5]:.0f} → "
                    f"{ref_stats.luma[5]:.0f}, nasycenie {user_stats.chroma:.0f} → {ref_stats.chroma:.0f}"
                    f"{', dołożona winieta' if angle else ''}).")
            except look.LookUnavailable as exc:
                warnings.append(f"{str(exc).rstrip('. ')}. Kolory zostają bez zmian.")
        elif opts.look > 0 and (tpl.single_take or tpl.keep_colors):
            log("Kolory nagrania zostają bez zmian (ten szablon ich nie zmienia; kolory marki mają grafiki)." if not tpl.motion
                else "Kolory: całe tło i napisy rysują grafiki w kolorach marki.")
        elif opts.look > 0:
            warnings.append("Szablon nie ma opisu kolorów (blok look), więc kolory zostają bez zmian.")

        # 5) napisy
        ass_name = fonts_dir = None
        words: list[captions.Word] = []
        cap_stats: dict = {}
        words_path: Path | None = None
        want_caps = opts.captions != "off" and info.has_audio
        anchored = bool(opts.graphics) and graphics.plan_needs_words(opts.graphics)  # plan z frazami potrzebuje transkrypcji
        if want_caps or (anchored and info.has_audio):
            try:
                if opts.words_file:
                    words = captions.load_words(opts.words_file)
                    log(f"Wczytano gotową transkrypcję: {len(words)} słów.")
                else:
                    prog(0.4, 0.55, "Rozpoznawanie mowy")
                    words = captions.transcribe(media.read_pcm(master), model=opts.model, language=opts.lang, log=log)
                    log(f"Rozpoznano {len(words)} słów.")
            except captions.WordsFileError as exc:  # plik podany wprost: błąd zawsze zatrzymuje montaż
                raise media.MediaError(str(exc)) from exc
            except captions.CaptionsUnavailable as exc:
                if anchored:
                    raise media.MediaError(f"{exc} Plan grafik używa fraz z mowy, więc bez rozpoznawania mowy nie da się go zastosować "
                                           "(albo podaj gotową transkrypcję: --words plik.json).") from exc
                if opts.captions == "on":
                    raise
                warnings.append(f"{exc} Robię montaż bez napisów.")
                want_caps = False
            except (OSError, RuntimeError, ValueError) as exc:  # np. brak internetu przy pierwszym pobraniu modelu
                msg = (f"Rozpoznawanie mowy nie powiodło się ({type(exc).__name__}: {exc}). Przy pierwszym uruchomieniu "
                       "model trzeba pobrać z internetu.")
                if opts.captions == "on" or anchored:
                    raise media.MediaError(msg) from exc
                warnings.append(msg + " Robię montaż bez napisów.")
                want_caps = False
        layer_caps = bool(tpl.graphics.get("captions"))  # napisy rysuje warstwa grafik (krój marki), nie ASS
        cap_words: list[captions.Word] | None = None
        if (words and layer_caps and tpl.graphics["captions"].get("from_script") and opts.graphics
                and graphics.script.is_script(opts.graphics) and Path(opts.graphics).exists()):
            # mówisz (albo lektor czyta) scenariusz, więc napisy i hasła dostają słowa z Twojego tekstu (poprawna pisownia), a czasy z mowy
            fixed, cov = graphics.script.words_from_script(Path(opts.graphics).read_text(encoding="utf-8-sig"), words)
            if fixed and cov >= 0.8:
                cap_words = fixed
                log(f"Napisy: słowa z Twojego scenariusza, czasy z mowy (zgodność {cov * 100:.0f}%).")
            else:
                warnings.append(f"Mowa zgadza się ze scenariuszem tylko w {cov * 100:.0f}%, więc napisy zostają z rozpoznanej mowy. "
                                "Czy to na pewno ten sam tekst, który jest w scenariuszu?")
        if words:
            words_path = out_path.with_suffix(".slowa.json")
            captions.save_words(words, words_path)
            breaks = breaks + captions.word_breaks(words, fps)  # granice zdań z transkrypcji są dokładniejsze
        if want_caps and words:
            if layer_caps:
                cap_stats = {"groups": len(captions.group_words(words, int(tpl.graphics["captions"].get("max_words", 3)))), "emphasis": 0}
                log(f"Napisy: {cap_stats['groups']} napisów bieżących (krój marki).")
            else:
                ass_text, cap_stats = captions.build_ass(words, tpl.captions, canvas, master_s, opts.emphasis)
                (workdir / "captions.ass").write_text(ass_text, encoding="utf-8")
                (workdir / "fonts").mkdir(exist_ok=True)
                shutil.copy(FONT_FILE, workdir / "fonts" / FONT_FILE.name)
                ass_name, fonts_dir = "captions.ass", "fonts"
                log(f"Napisy: {cap_stats['groups']} napisów bieżących, {cap_stats['emphasis']} fraz akcentowych.")
        elif want_caps:
            warnings.append("Nie rozpoznano żadnej mowy: robię montaż bez napisów.")

        # 6) plan i render
        plan = build_plan(tpl, master_frames, fps, breaks=breaks, track=track, **plan_args)
        warnings += plan.warnings
        picks = render.assign_broll(plan.slots, clips, fps, opts.seed) if clips else {}

        # 7) grafiki: tytuły, karty, listy, liczniki (warstwa RGBA) i napisy biegnące w kroju marki
        job, graphics_info = None, {}
        use_layer_caps = layer_caps and want_caps and bool(words)
        if opts.graphics or use_layer_caps or graphics.glue.flash_cuts(plan):
            try:
                prog(0.55, 0.57, "Przygotowuję grafiki")
                job = graphics.glue.prepare(opts.graphics, opts.brand, tpl, plan, track, master, workdir, words,
                                            canvas, plan.total_frames / fps, use_layer_caps, log, cap_words)
            except graphics.GraphicsUnavailable as exc:
                if opts.graphics:
                    raise media.MediaError(str(exc)) from exc
                warnings.append(f"{str(exc).rstrip('. ')}. Robię montaż bez napisów biegnących.")
            except graphics.PlanError as exc:
                raise media.MediaError(f"Plan grafik: {exc}") from exc
            if job:
                warnings += job.plan.warnings
                n_el = len([e for e in job.plan.elements if e.kind != "captions"])
                graphics_info = {"elements": n_el, "effects": len(job.effects), "brand": job.plan.brand.name if job.plan.brand else "",
                                 "captions": use_layer_caps}
        log(f"Składam rolkę: {len(plan.slots)} ujęć, {plan.total_frames / fps:.1f} s...")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            render.render_final(master, master_info, geom.size, plan, picks, out_path, workdir, canvas=canvas,
                                look_chain=look_chain, ass_file=ass_name, fonts_dir=fonts_dir, normalize=opts.normalize,
                                lufs=tpl.lufs, tp=tpl.true_peak, lra=tpl.lra, crf=opts.crf, preset=opts.preset,
                                on_progress=prog(0.57 if job else (0.55 if want_caps else 0.4), 1.0, "Montaż"),
                                graphics_frames=job.frames() if job else None, effects=job.effects if job else (), warn=warnings.append)
        except Exception:
            out_path.unlink(missing_ok=True)
            raise
        final = media.probe(out_path)
        if abs(final.duration - plan.total_frames / fps) > 0.25:
            warnings.append(f"Długość wyniku ({final.duration:.2f} s) odbiega od planu ({plan.total_frames / fps:.2f} s).")
        if progress:
            progress(1.0, "Gotowe")
        plan_text = describe_plan(plan)
        if job and any(e.kind != "captions" for e in job.plan.elements):
            plan_text += "\n\nGrafiki (czasy na osi gotowego filmu):\n" + job.plan.describe()
        return Result(out_path, plan, plan_text, warnings, time.time() - t0,
                      captions_used=bool(ass_name) or use_layer_caps, caption_stats=cap_stats, words_file=words_path,
                      input_seconds=info.duration, master_seconds=master_s, face=face_info, look=look_info,
                      graphics=graphics_info)
    finally:
        if not opts.keep_temp:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            log(f"Pliki tymczasowe zostawiono w: {workdir}")
