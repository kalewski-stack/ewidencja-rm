"""Wiersz poleceń: rolka.py cut | serve | analyze | style | grafiki."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .captions import CaptionsUnavailable, load_words
from .graphics.core import GraphicsUnavailable, PlanError
from .media import MediaError
from .pipeline import Options, run
from .template import USER_DIR, TemplateError, list_templates, load_template

COMMANDS = {"cut", "serve", "analyze", "style", "grafiki"}

DESCRIPTION = """\
reelcut: tnie Twoje wideo dokładnie wg schematu montażu rolki wzorcowej
(rytm cięć, ujęcia z mową i wstawki, kadry po twarzy, kolory, napisy słowo po słowie, dźwięk -14 LUFS).
Styl rolki (kolory, kadry, cięcia, scenariusz) opisuje STYL.md, a karta każdego szablonu: python rolka.py style.
"""


def _face_arg(text: str) -> tuple[float, float, float]:
    try:
        h, x, y = (float(v) for v in text.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("podaj trzy liczby: wysokość, x, y, np. 0.17,0.55,0.45") from exc
    return h, x, y


def _focus(text: str) -> tuple[float, float]:
    try:
        x, y = (float(v) for v in text.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("podaj dwie liczby 0-1, np. 0.5,0.4") from exc
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise argparse.ArgumentTypeError("wartości muszą być z zakresu 0-1")
    return x, y


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rolka.py", description=DESCRIPTION,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"reelcut {__version__}")
    sub = p.add_subparsers(dest="command")

    c = sub.add_parser("cut", help="potnij wideo wg szablonu (domyślne polecenie)",
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    c.add_argument("video", type=Path, help="Twoje nagranie (najlepiej pionowe, z mową); w trybie motion (--template motion) wystarczy samo nagranie głosu: .m4a, .wav, .mp3")
    c.add_argument("-o", "--out", type=Path, help="plik wynikowy (domyślnie: <nazwa>_rolka.mp4 obok nagrania)")
    c.add_argument("--broll", type=Path, action="append", default=[], metavar="FOLDER|PLIK",
                   help="B-roll do wstawek (folder albo plik; można podać kilka razy). Bez tego wstawki to kadry z nagrania")
    c.add_argument("--template", metavar="NAZWA|PLIK.json", help="szablon montażu (domyślnie: wbudowany z rolki wzorcowej)")
    c.add_argument("--captions", choices=("auto", "on", "off"), default="auto",
                   help="napisy: auto = gdy zainstalowany faster-whisper, on = wymagane, off = bez")
    c.add_argument("--no-captions", dest="captions", action="store_const", const="off", help="skrót od --captions off")
    c.add_argument("--lang", default="pl", help="język mowy (pl, en, ... albo auto)")
    c.add_argument("--model", default="small", help="model Whisper: tiny, base, small, medium, large-v3")
    c.add_argument("--words", type=Path, metavar="PLIK.json",
                   help="gotowa (np. poprawiona ręcznie) transkrypcja zamiast rozpoznawania mowy")
    c.add_argument("--emphasis", choices=("auto", "off"), default="auto", help="frazy akcentowe w napisach")
    c.add_argument("--max-zoom", type=float, default=None,
                   help="największe przybliżenie kadru (1.0 = bez zbliżeń; domyślnie automatycznie: 1.6 dla 1080p, do 2.6 dla 4K)")
    c.add_argument("--framing", choices=("auto", "on", "off"), default="auto",
                   help="kadrowanie po Twojej twarzy jak we wzorcu (auto = gdy się da, off = stałe zoomy z szablonu)")
    c.add_argument("--focus", type=_focus, default=(0.5, 0.40), metavar="X,Y",
                   help="gdzie w kadrze jest twarz (0-1), wokół tego punktu robimy zbliżenia")
    c.add_argument("--no-tighten", dest="tighten", action="store_false", help="nie skracaj długich pauz")
    c.add_argument("--no-snap", dest="snap", action="store_false",
                   help="tnij dokładnie w sekundach szablonu, bez dosuwania do granic zdań")
    c.add_argument("--look", type=float, default=1.0, metavar="0-1",
                   help="siła dopasowania kolorów do wzorca: jasność, nasycenie, ton, winieta (1 = jak we wzorcu, 0 = obraz bez zmian)")
    c.add_argument("--graphics", type=Path, metavar="SCENARIUSZ.txt|PLAN.json",
                   help="grafiki na filmie (tytuły, karty, listy, liczniki; w trybie motion tarcza, plansze): scenariusz ze znacznikami {…} albo plan JSON, patrz GRAFIKI.md")
    c.add_argument("--brand", metavar="NAZWA|PLIK.json",
                   help="marka grafik: kolory i kroje (domyślnie „Linia Kalewski”)")
    c.add_argument("--fps", type=int, help="klatki na sekundę wyniku (domyślnie jak w szablonie)")
    c.add_argument("--seed", type=int, default=7, help="ziarno losowania B-rolla (to samo ziarno = ten sam wynik)")
    c.add_argument("--crf", type=int, default=18, help="jakość H.264 (niżej = lepiej, 18 to bardzo dobra)")
    c.add_argument("--preset", default="medium",
                   choices=("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"),
                   help="szybkość kodowania (wolniej = mniejszy plik przy tej samej jakości)")
    c.add_argument("--no-normalize", dest="normalize", action="store_false", help="nie normalizuj głośności do -14 LUFS")
    c.add_argument("--dry-run", action="store_true", help="pokaż plan cięć i nic nie renderuj")
    c.add_argument("--keep-temp", action="store_true", help="zostaw pliki tymczasowe (do diagnozy)")

    s = sub.add_parser("serve", help="uruchom lokalny interfejs w przeglądarce (przeciągnij i upuść)")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true", help="nie otwieraj przeglądarki automatycznie")
    s.add_argument("--workdir", type=Path, help="gdzie trzymać wgrane pliki i wyniki (domyślnie ~/ReelCut)")

    a = sub.add_parser("analyze", help="zrób szablon z innej rolki wzorcowej (plik wideo)")
    a.add_argument("reference", type=Path, help="plik wideo rolki wzorcowej")
    a.add_argument("-o", "--out", type=Path, required=True,
                   help="plik szablonu .json albo sama nazwa (wtedy trafi do ~/ReelCut/szablony i będzie widoczny w interfejsie)")
    a.add_argument("--threshold", type=float, default=0.18, help="czułość wykrywania cięć (0.1 czułe, 0.4 tylko ostre)")
    a.add_argument("--roles", help="role ujęć jako ciąg liter A/B, np. AABBABAB (A = mówiąca głowa, B = wstawka)")
    a.add_argument("--name", help="nazwa szablonu")
    a.add_argument("--speech", action="store_true",
                   help="zmierz też tempo mowy (słowa na sekundę, pauzy; potrzebny faster-whisper, pierwszy raz pobierze model)")
    a.add_argument("--model", default="small", help="model rozpoznawania mowy dla --speech (tiny, base, small, medium)")
    a.add_argument("--lang", default="pl", help="język mowy w rolce dla --speech (pl, en, auto...)")

    g = sub.add_parser("grafiki", help="podgląd grafik (scenariusz ze znacznikami albo plan JSON) na jednolitym tle albo na Twoim nagraniu, bez montażu")
    g.add_argument("plan", type=Path, help="scenariusz ze znacznikami (.txt, .md) albo plan grafik (.json)")
    g.add_argument("-o", "--out", type=Path, default=Path("podglad_grafik.mp4"), help="plik podglądu")
    g.add_argument("--tlo", type=Path, metavar="WIDEO|OBRAZ", help="tło: Twoje nagranie albo zdjęcie (domyślnie ciemne, jednolite)")
    g.add_argument("--od", type=float, default=0.0, help="początek wycinka tła (s)")
    g.add_argument("--czas", type=float, help="długość podglądu (s; domyślnie do końca planu)")
    g.add_argument("--klatka", type=float, metavar="S", help="zamiast filmu zapisz jedną klatkę (PNG) z sekundy S")
    g.add_argument("--brand", metavar="NAZWA|PLIK.json", help="marka grafik (domyślnie „Linia Kalewski”)")
    g.add_argument("--template", metavar="NAZWA", help="szablon, którego napisy, hasła i tło dokładamy do podglądu: potrzebny w trybie motion "
                   "(cały obraz rysują grafiki) i w Formacie 3 (hasła ze słów w *gwiazdkach*); kadr twarzy bierze z szablonu, gdy nie podasz --twarz")
    g.add_argument("--words", type=Path, metavar="PLIK.json",
                   help="transkrypcja (plik .slowa.json): potrzebna, gdy plan podaje czasy jako frazy z mowy albo to scenariusz ze znacznikami")
    g.add_argument("--fps", type=int, default=30)
    g.add_argument("--twarz", type=_face_arg, metavar="H,X,Y", default=None,
                   help="gdzie jest twarz w kadrze: wysokość, środek x, środek y (ułamki), np. 0.17,0.55,0.45")

    y = sub.add_parser("style", help="opisz styl szablonu: cięcia, tempo, kadry, kolory, napisy (karta w Markdown)")
    y.add_argument("template", nargs="?", default=None, help="nazwa szablonu albo plik .json (domyślnie wbudowany)")
    y.add_argument("-o", "--out", type=Path, help="zapisz kartę do pliku zamiast wypisywać na ekran")
    return p


def _progress_printer():
    tty = sys.stdout.isatty()
    last = {"label": None}

    def cb(frac: float, label: str) -> None:
        if tty:
            sys.stdout.write(f"\r  {label:<26} {frac * 100:5.1f}%")
            sys.stdout.flush()
            if frac >= 1.0:
                sys.stdout.write("\n")
        elif label != last["label"]:
            print(f"  [{frac * 100:3.0f}%] {label}")
        last["label"] = label

    return cb


def cmd_cut(args: argparse.Namespace) -> int:
    opts = Options(template=args.template, broll=tuple(args.broll), captions=args.captions, lang=args.lang,
                   model=args.model, words_file=args.words, emphasis=args.emphasis, max_zoom=args.max_zoom, framing=args.framing,
                   focus=args.focus, tighten=args.tighten, snap=args.snap, look=args.look, fps=args.fps,
                   graphics=args.graphics, brand=args.brand,
                   seed=args.seed, crf=args.crf, preset=args.preset, normalize=args.normalize, dry_run=args.dry_run,
                   keep_temp=args.keep_temp)
    if not args.video.exists():
        print(f"Nie ma pliku: {args.video}", file=sys.stderr)
        return 2
    res = run(args.video, args.out, opts, log=print, progress=None if args.dry_run else _progress_printer())
    print()
    print(res.plan_text)
    for w in res.warnings:
        print(f"UWAGA: {w}")
    if res.output:
        print(f"\nGotowe w {res.seconds:.0f} s: {res.output}")
        if res.words_file:
            print(f"Transkrypcja do ewentualnej poprawki: {res.words_file}  (użyj potem: --words {res.words_file.name})")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import serve

    return serve(args.port, open_browser=not args.no_browser, workdir=args.workdir)


def cmd_analyze(args: argparse.Namespace) -> int:
    from .analyze import analyze_reference

    out = args.out
    by_name = out.suffix == "" and len(out.parts) == 1  # sama nazwa => szablon użytkownika
    if by_name:
        out = USER_DIR / f"{out.name}.json"
    path = analyze_reference(args.reference, out, threshold=args.threshold, roles=args.roles,
                             name=args.name or (out.stem if by_name else None), speech=args.speech, model=args.model,
                             language=args.lang, log=print)
    ref = f"user/{path.stem}" if by_name else str(path)
    print(f"Zapisano szablon: {path}\nUżyj: python rolka.py cut TWOJE.mp4 --template {ref}"
          + ("   (widać go też w interfejsie: python rolka.py serve)" if by_name else ""))
    return 0


def cmd_grafiki(args: argparse.Namespace) -> int:
    from . import graphics

    if not args.plan.exists():
        print(f"Nie ma pliku: {args.plan}", file=sys.stderr)
        return 2
    face = None
    if args.twarz:
        h, x, y = args.twarz
        face = (x, y, h)
    words = load_words(args.words) if args.words else None
    tpl = load_template(args.template) if args.template else None
    size = tpl.canvas if tpl is not None else (1080, 1920)  # podgląd ma kanwę szablonu (pion albo poziom)
    if face is None and tpl is not None:  # bez --twarz: kadr twarzy z pierwszego ujęcia z mową w szablonie
        seg = next((s for s in tpl.segments if s.role == "A" and s.face), None)
        face = (seg.face.cx, seg.face.cy, seg.face.h) if seg else None
    plan = graphics.load_plan(args.plan, size=size, fps=args.fps, brand=args.brand, face=face, words=words,
                              template=tpl if tpl is not None and tpl.preview_layer else None)
    print("Harmonogram grafik (sekundy na osi filmu):")
    print(plan.describe())
    for w in plan.warnings:
        print(f"UWAGA: {w}")
    warned = len(plan.warnings)
    bg = args.tlo
    if args.klatka is not None:
        base = graphics.background_frame(bg, args.od + args.klatka, size) if bg else None
        matte = graphics.glue.matte_for_background(plan, bg, size, frame=base, log=print)
        for w in plan.warnings[warned:]:
            print(f"UWAGA: {w}")
        out = args.out if args.out.suffix.lower() == ".png" else args.out.with_suffix(".png")
        graphics.render_png(plan, args.klatka, size, base, matte).convert("RGB").save(out)
        print(f"Zapisano klatkę: {out}")
        return 0

    def cb(frac: float) -> None:
        if sys.stdout.isatty():
            sys.stdout.write(f"\r  Rysuję grafiki {frac * 100:3.0f}%")
            sys.stdout.flush()

    matte = graphics.glue.matte_for_background(plan, bg, size, start=args.od, duration=args.czas, log=print)
    for w in plan.warnings[warned:]:
        print(f"UWAGA: {w}")
    path = graphics.preview(plan, args.out, size=size, fps=args.fps, duration=args.czas, background=bg, start=args.od, progress=cb, matte=matte)
    if sys.stdout.isatty():
        sys.stdout.write("\n")
    print(f"Zapisano podgląd: {path}")
    return 0


def cmd_style(args: argparse.Namespace) -> int:
    from .style import describe
    from .template import load_template

    text = describe(load_template(args.template))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Zapisano kartę stylu: {args.out}")
    else:
        print(text, end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "cut")  # skrót: python rolka.py moje.mp4
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        names = ", ".join(n for n, _ in list_templates())
        print(f"\nWbudowane szablony: {names}")
        return 0
    try:
        return {"cut": cmd_cut, "serve": cmd_serve, "analyze": cmd_analyze, "style": cmd_style, "grafiki": cmd_grafiki}[args.command](args)
    except (MediaError, TemplateError, PlanError, GraphicsUnavailable, CaptionsUnavailable) as exc:
        print(f"\nBŁĄD: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nPrzerwano.", file=sys.stderr)
        return 130
    except BrokenPipeError:  # stdout zamknięty po drugiej stronie (np. `| head`): kończymy po cichu
        import os

        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
