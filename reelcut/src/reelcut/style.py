"""Karta stylu: czytelny opis szablonu (cięcia, tempo, kadry, kolory, napisy) do przenoszenia stylu na inne materiały."""
from __future__ import annotations

import statistics

from .template import Template

ROLE_NAMES = {"A": "mówiąca głowa", "B": "wstawka"}


def _n(x: float, nd: int = 1) -> str:
    """Liczba z przecinkiem dziesiętnym (karta jest dokumentem po polsku)."""
    return f"{x:.{nd}f}".replace(".", ",")


def shot_class(zoom: float) -> str:
    """Nazwa planu wg zoomu względem najszerszego ujęcia drabinki."""
    if zoom <= 1.2:
        return "plan ogólny"
    if zoom <= 2.0:
        return "plan średni"
    return "zbliżenie"


def _brightness(L: float) -> str:
    return "bardzo ciemny (low-key)" if L < 30 else "ciemny" if L < 50 else "średni" if L < 65 else "jasny (high-key)"


def _saturation(C: float) -> str:
    return "mocno stonowane" if C < 12 else "stonowane" if C < 20 else "umiarkowane" if C < 35 else "żywe"


def _timeline(tpl: Template):
    t, rows = 0.0, []
    for i, s in enumerate(tpl.segments):
        d = s.frames / tpl.fps
        rows.append((i, s, t, t + d))
        t += d
    return rows


def _cuts_section(tpl: Template) -> list[str]:
    total = tpl.duration_s
    lens = [s.frames / tpl.fps for s in tpl.segments]
    n_cuts = len(lens) - 1
    hook = sum(lens[:tpl.hook])
    outro = sum(lens[len(lens) - tpl.outro:])
    a_share = sum(s.frames for s in tpl.segments if s.role == "A") / tpl.total_frames
    out = ["## Cięcia i tempo", "",
           f"- {n_cuts} cięć w {_n(total)} s, czyli {_n(n_cuts / total * 60)} cięć na minutę.",
           f"- Ujęcie trwa średnio {_n(statistics.fmean(lens), 2)} s (mediana {_n(statistics.median(lens), 2)}, "
           f"od {_n(min(lens), 2)} do {_n(max(lens), 2)} s).",
           f"- Hak {_n(hook)} s, rozwinięcie {_n(total - hook - outro)} s, zakończenie {_n(outro)} s.",
           f"- Mówiąca głowa (A) to {a_share * 100:.0f}% czasu, wstawki (B) {100 - a_share * 100:.0f}%.",
           f"- Wzór ujęć: `{''.join(s.role for s in tpl.segments)}`. Ujęcie elastyczne (przejmuje różnicę długości): "
           f"nr {tpl.elastic + 1}, {_n(lens[tpl.elastic], 2)} s.",
           "- Rytm (s): " + ", ".join(f"{_n(d, 2)}{s.role}" for d, s in zip(lens, tpl.segments)) + ".",
           f"- Pauzy w mowie: powyżej {_n(tpl.max_pause_s, 2)} s skracane do {_n(tpl.keep_pause_s, 2)} s."]
    dyn = tpl.dynamics
    if dyn.get("motion"):
        m = dyn["motion"]
        out.append(f"- Ruch w kadrze (średnia różnica kolejnych klatek, skala 0-255): mówiąca głowa {_n(m.get('A', 0))}, "
                   f"wstawki {_n(m.get('B', 0))}. Im bliżej zera, tym bardziej statyczny kadr.")
    if dyn.get("loudness"):
        ld = dyn["loudness"]
        out.append(f"- Głośność rolki: {_n(ld['lufs'])} LUFS, szczyt {_n(ld['true_peak'])} dBTP, zakres LRA {_n(ld['lra'])} LU "
                   f"(cel w szablonie: {_n(tpl.lufs)} LUFS).")
    sp = dyn.get("speech")
    if sp:
        out.append(f"- Mowa: {_n(sp['words_per_s'])} słowa na sekundę, {sp['words']} słów w całości.")
        if sp.get("words_per_shot"):
            out.append("- Słów w kolejnych ujęciach: " + ", ".join(str(v) for v in sp["words_per_shot"]) + ".")
        if sp.get("pauses_s"):
            p = sp["pauses_s"]
            out.append(f"- Pauzy między słowami (od 0,15 s): {p['count']}, mediana {_n(p['median'], 2)} s, najdłuższa {_n(p['max'], 2)} s.")
    return out + [""]


def _framing_section(tpl: Template) -> list[str]:
    a_rows = [r for r in _timeline(tpl) if r[1].role == "A"]
    out = ["## Kadry", ""]
    with_face = [r for r in a_rows if r[1].face]
    if with_face:
        out += ["Rozmiar i położenie twarzy w ujęciach z mową, jako ułamki kadru (x: 0% = lewa krawędź, y: 0% = góra).", "",
                "| Ujęcie | Czas (s) | Plan | Twarz: wysokość | Twarz: x | Twarz: y | Oczy: y |",
                "|---|---|---|---|---|---|---|"]
        h_min = min(r[1].face.h for r in with_face)
        for i, s, t0, t1 in with_face:
            f = s.face
            eyes = f"{f.eye_y * 100:.0f}%" if f.eye_y else ""
            out.append(f"| {i + 1} | {_n(t0)}-{_n(t1)} | {shot_class(f.h / h_min)} | {f.h * 100:.0f}% | {f.cx * 100:.0f}% | "
                       f"{f.cy * 100:.0f}% | {eyes} |")
        hs = [r[1].face.h for r in with_face]
        cys = [r[1].face.cy for r in with_face]
        out += ["", f"Drabinka: najszerszy kadr ma twarz {min(hs) * 100:.0f}% wysokości, zbliżenia do {max(hs) * 100:.0f}% "
                    f"({_n(max(hs) / min(hs))} raza więcej). Środek twarzy leży między {min(cys) * 100:.0f}% a {max(cys) * 100:.0f}% "
                    "wysokości kadru, więc dół kadru zostaje wolny na napisy."]
    elif a_rows:
        zs = sorted({s.zoom for _, s, _, _ in a_rows})
        out.append("Szablon nie ma pomiaru twarzy; kadry to drabinka zoomu względem najszerszego ujęcia: "
                   + ", ".join(f"x{_n(z, 2)}" for z in zs) + ".")
    b_alts = sorted({s.alt for _, s, _, _ in _timeline(tpl) if s.role == "B" and s.alt})
    if b_alts:
        out += ["", "Gdy nie ma osobnego materiału na wstawkę B, wycinamy ją z nagrania z mową:"]
        for k in b_alts:
            a = tpl.alts.get(k, {})
            out.append(f"- detal {k}: {a.get('note', '')}, zoom x{_n(float(a.get('zoom', 1.0)), 2)}")
    return out + [""]


def _palette_line(pal: list[dict]) -> str:
    return ", ".join(f"`{p['hex']}` {p['share'] * 100:.0f}%" for p in pal)


def _look_section(tpl: Template) -> list[str]:
    look = tpl.look
    out = ["## Kolory", ""]
    if not look.get("A"):
        return out + ["Szablon nie ma opisu kolorów (blok look).", ""]
    out += ["L* to jasność w skali 0-100, C* to nasycenie (0 = szarość, ok. 100 = skrajnie żywy kolor), odcień w stopniach "
            "(0° czerwień, 90° żółć, 180° zieleń-cyjan, 270° błękit). Skala CIE Lab, D65.", ""]
    for key, title in (("A", "Ujęcia z mową (A)"), ("B", "Wstawki (B)")):
        st = look.get(key)
        if not st:
            continue
        L, v = st["luma"], st["vignette"]
        out += [f"**{title}**", "",
                f"- Jasność: {_brightness(L[5])}. Mediana L* {L[5]:.0f}, połowa kadru mieści się między L* {L[4]:.0f} a L* {L[6]:.0f}, "
                f"cienie (5. percentyl) L* {L[2]:.0f}, światła (99. percentyl) L* {L[9]:.0f}.",
                f"- Nasycenie: {_saturation(st['chroma'])}, średnie C* {st['chroma']:.0f}.",
                f"- Winieta: kolejne pierścienie od środka mają {v[0] * 100:.0f}%, {v[1] * 100:.0f}% i {v[2] * 100:.0f}% jasności środka "
                f"(w rogach {v[2] * 100:.0f}%)."]
        if look.get(f"palette_{key}"):
            out.append(f"- Paleta (udział pikseli): {_palette_line(look[f'palette_{key}'])}.")
        out.append("")
    skin = look.get("skin")
    if skin:
        out += [f"**Skóra**: L* {skin['L']:.0f}, C* {skin['C']:.0f}, odcień {skin['hue']:.0f}°. Jaśniej: kafelek „dark skin” wzornika "
                "ColorChecker ma L* 38, C* 20, odcień 46°, a „light skin” L* 66, C* 25, odcień 50°.", ""]
    acc = look.get("accents") or {}
    cap = tpl.captions.get("accent_color")
    parts = ([f"napisy `{cap}`"] if cap else []) + ([f"ciepłe światło w ujęciach z mową `{acc['A']}`"] if acc.get("A") else []) \
        + ([f"tło wstawek `{acc['B']}`"] if acc.get("B") else [])
    if parts:
        out += ["**Akcenty**: " + ", ".join(parts) + ".", ""]
    return out


def _captions_section(tpl: Template) -> list[str]:
    c = tpl.captions
    if not c:
        return []
    out = ["## Napisy", "", f"- Krój {c.get('font', '?')}, wersaliki, kolor {c.get('color', '?')}, akcent {c.get('accent_color', '?')}."]
    r = c.get("running")
    if r:
        out.append(f"- Napisy biegnące: słowo po słowie, do {r.get('max_words', 2)} słów naraz, wysokość wersalików {r.get('cap_px', '?')} px, "
                   f"górna krawędź na {r.get('cap_top_px', '?')} px z 1920.")
    e = c.get("emphasis")
    if e:
        out.append(f"- Wyróżnienia: fraza {e.get('min_words', 2)}-{e.get('max_words', 5)} słów mniej więcej co {_n(e.get('every_s', 0))} s "
                   f"(nie częściej niż co {_n(e.get('min_gap_s', 0))} s). Kolejność układów: " + ", ".join(e.get("order", [])) + ".")
    return out + [""]


def describe(tpl: Template) -> str:
    """Karta stylu w Markdown."""
    head = [f"# Karta stylu: {tpl.name}", "",
            f"Źródło: {tpl.source or 'brak'}. Format {tpl.canvas[0]}x{tpl.canvas[1]}, {tpl.fps} kl./s, {_n(tpl.duration_s)} s.", ""]
    notes = [f"{i + 1}. ({s.role}) {s.note}" for i, s in enumerate(tpl.segments) if s.note]
    body = _cuts_section(tpl) + _framing_section(tpl) + _look_section(tpl) + _captions_section(tpl)
    if notes:
        body += ["## Opis ujęć", ""] + notes + [""]
    return "\n".join(head + body).rstrip() + "\n"
