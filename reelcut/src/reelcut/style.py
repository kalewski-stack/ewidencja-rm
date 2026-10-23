"""Karta stylu: czytelny opis szablonu (cięcia, tempo, kadry, kolory, napisy) do przenoszenia stylu na inne materiały."""
from __future__ import annotations

import statistics

from .template import Template

ROLE_NAMES = {"A": "mówiąca głowa", "B": "wstawka"}

# Elementy planu grafik widoczne na karcie stylu (test pilnuje, żeby lista zgadzała się z rejestrem elementów).
GRAPHICS_ELEMENTS = {
    "title": "duży napis (żółty, szeryfowy kursywą albo krojem marki) z małym słowem-akcentem nad prawym końcem",
    "badge": "plakietka: numer w kole i tytuł obok, np. „1 Scenariusz”",
    "cards": "miniatury 9:16 z etykietą (pogrubioną, szeryfową kursywą albo żółtą), punktami i licznikiem wyświetleń pod spodem: w rzędzie, "
             "siatce albo w dowolnym miejscu i pod kątem, jedna może się powiększyć",
    "profile": "chip z awatarem (Twoja twarz z nagrania), licznikiem, paskiem postępu i kursorem jadącym po kadrze",
    "pills": "krótkie hasła z ikoną, wlatujące jedna po drugiej (biała, szklana, fioletowa, żółta)",
    "chips": "małe kafelki z etykietą i liczbą, np. wartości do porównania",
    "steps": "lista kroków w szklanym panelu, która przewija się do aktywnego kroku",
    "axis": "wykres schodkowy z podpisanymi punktami (rosnący trend)",
    "bars": "wiersze z etykietami (podwójne, pojedyncze, ze spinnerem)",
    "callout": "wyróżnienie: ikona, tytuł i tekst „pisany” na żywo, opcjonalnie karta po prawej",
    "stat": "duża liczba odliczana od zera z podpisem i paskiem",
    "illustration": "obraz z miękką poświatą, np. nad głową; może jechać po ścieżce, rosnąć, obracać się i wychodzić poza kadr",
    "arrow": "strzałka albo linia rysowana na żywo: łuk, linia ciągła, przerywana lub kropkowana, grot otwarty lub pełny",
    "labels": "opisy z cienką linią i kropką, które wskazują miejsca na obrazie albo karcie",
    "text": "tekst z wyróżnieniami (*żółte*, _szeryfowe_), odsłaniany albo pisany na żywo, z podkreśleniem, pędzlem lub nawiasem",
    "list": "wiersze pojawiające się po kolei z „pisaniem” treści, polami do odhaczenia albo w dwóch kolumnach (porównanie)",
    "ring": "pierścień z kropek wokół wskazanego miejsca: cały albo dwa łuki",
}

# Elementy Motion: obraz powstaje z nich, bo z pliku liczy się tylko dźwięk.
MOTION_ELEMENTS = {
    "backdrop": "tło całego filmu: papier z siatką kropek w eliptycznej winiecie (dark: true to ciemna plansza)",
    "dial": "tarcza schematu: piasta z tekstem, szprychy z kropkami i etykietami; rozbudowa na szerokim ujęciu, cięcie na zbliżenie, "
            "obrót o jedną szprychę na krok, pisanie etykiet z blokiem-kursorem, cofnięcie kamery z tytułem",
    "cutaway": "plansza na cały kadr z napisami w trzech rozmiarach (małe, duże, drobne), twarde cięcie wejścia i wyjścia",
    "glint": "krótki jasny błysk na piaście przy ważnym słowie",
}

# Elementy Formatu 3 (gadająca głowa v3: cięcia, wstawki z błyskiem, hasła): dochodzą do elementów Formatu 2.
FORMAT3_ELEMENTS = {
    "lockup": "hasło: blok z dużym słowem kluczowym (szeryfowa kursywa, żółty) i małymi słowami nad nim i pod nim, wyjustowanymi do jego szerokości; "
              "słowa wskakują w chwili, gdy padają; powstaje samo ze słów wyróżnionych w scenariuszu (`*tak*`)",
}

BRAND_ROLES = {
    "text": "napisy i tekst na grafikach",
    "title": "tytuły",
    "accent": "etykiety, linie, pierścienie",
    "accent_strong": "plakietki i tła kart",
    "highlight": "jedyny jasny element naraz: liczba, kursor, aktywna pozycja, słowo kluczowe",
    "panel": "tło paneli",
}


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
        if len(with_face) == 1:
            f = with_face[0][1].face
            out += ["", f"Kadr stały, bez najazdów. Nad czubkiem głowy zostaje ok. {max(0.0, f.cy - 0.78 * f.h) * 100:.0f}% wysokości kadru "
                        "wolnego miejsca na grafiki; napisy stoją na wysokości klatki piersiowej."]
        else:
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


def _single_section(tpl: Template) -> list[str]:
    """Montaż i tempo rolki z jednym ujęciem: cięć nie ma, więc liczą się tempo mowy, pauzy i głośność."""
    dyn = tpl.dynamics
    out = ["## Montaż i tempo", "",
           f"- Jedno ujęcie bez cięć, {_n(tpl.duration_s)} s. Dynamika pochodzi z warstwy grafik i napisów, nie z montażu.",
           f"- Pauzy w mowie: powyżej {_n(tpl.max_pause_s, 2)} s skracane do {_n(tpl.keep_pause_s, 2)} s."]
    if dyn.get("words_per_s"):
        out.append(f"- Tempo mowy: {_n(dyn['words_per_s'])} słowa na sekundę.")
    ld = dyn.get("loudness")
    if ld:
        out.append(f"- Głośność rolki: {_n(ld['lufs'])} LUFS, szczyt {_n(ld['true_peak'])} dBTP, zakres LRA {_n(ld['lra'])} LU "
                   f"(cel w szablonie: {_n(tpl.lufs)} LUFS).")
    reels = dyn.get("reels") or []
    if reels:
        out += ["", f"Rolki wzorcowe tego formatu ({len(reels)}, mediany powyżej); położenie i rozmiary jako ułamki kadru:", "",
                "| Rolka | Czas (s) | Słów/s | LUFS | LRA | Twarz: wys. | Twarz: x | Twarz: y | Napisy: góra | Napisy: wys. linii |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for r in reels:
            f, c = r.get("face", {}), r.get("caption", {})
            out.append(f"| {r['id']} | {_n(r['seconds'])} | {_n(r['words_per_s'], 2)} | {_n(r['lufs'])} | {_n(r['lra'])} | "
                       f"{_n(f.get('h', 0) * 100)}% | {_n(f.get('cx', 0) * 100)}% | {_n(f.get('cy', 0) * 100)}% | "
                       f"{_n(c.get('top', 0) * 100)}% | {_n(c.get('height', 0) * 100, 2)}% |")
    return out + [""]


def _motion_section(tpl: Template) -> list[str]:
    """Motion: obraz z grafik i lektor. Liczby ruchu pochodzą z pomiaru rolki wzorcowej (blok dynamics.motion)."""
    dyn = tpl.dynamics
    m = dyn.get("motion", {})
    out = ["## Montaż i kamera", "",
           f"- Obraz powstaje z grafik, z pliku liczy się tylko dźwięk (lektor). Wzorzec: {_n(tpl.duration_s)} s, bez cięć montażowych; "
           "zmiany ujęć robi kamera w schemacie i dwie plansze.",
           f"- Pauzy w mowie: powyżej {_n(tpl.max_pause_s, 2)} s skracane do {_n(tpl.keep_pause_s, 2)} s."]
    if dyn.get("words_per_s"):
        out.append(f"- Tempo napisów: ok. {_n(dyn['words_per_s'])} słowa na sekundę (z liczby zmian napisów).")
    ld = dyn.get("loudness")
    if ld:
        out.append(f"- Głośność rolki: {_n(ld['lufs'])} LUFS, zakres LRA {_n(ld['lra'])} LU (cel w szablonie: {_n(tpl.lufs)} LUFS).")
    if m:
        pct = lambda v: f"{_n(v * 100)}%"  # noqa: E731
        out += ["", "## Ruch (zmierzony)", "",
                f"- Rozbudowa na szerokim ujęciu: promień piasty {pct(m['wide_hub_r'])} szerokości kadru, {m['spokes']} szprych wyrasta po kolei "
                f"zgodnie z ruchem wskazówek od góry co {_n(m['spoke_step_s'], 3)} s, całość trwa ok. {_n(m['build_s'])} s.",
                f"- Cięcie na zbliżenie: jedna klatka, skala {_n(m['cut_scale'], 2)} → 1 w {_n(m['settle_s'], 2)} s z doostrzeniem; "
                f"zbliżenie ×{_n(m['zoom_ratio'], 2)} (promień piasty {pct(m['close_hub_r'])}). W zbliżeniu piasta stoi przy dolnej krawędzi, "
                "widać szprychę na górze i jej etykietę.",
                f"- Wolny najazd w zbliżeniu: +{_n(m['drift_per_s'] * 100, 2)}% na sekundę, także pod planszami.",
                f"- Obrót o jedną szprychę na krok ({m['rotations']} obrotów w rolce), przeciwnie do ruchu wskazówek, łagodzenie wejściowe "
                f"i wyjściowe o potędze {_n(m['rotation_pow'], 0)}: ruch widać ok. {_n(m['rotation_visible_s'], 2)} s, 10-90% w "
                f"{_n(m['rotation_10_90_s'], 2)} s. Połowa obrotu wypada 0,1 s przed pierwszym znakiem etykiety.",
                f"- Pisanie etykiet: {_n(m['type_cps'], 0)} znaków na sekundę, blok-kursor kurczy się do szerokości znaku, po dopisaniu "
                "cienki kursor jeszcze 0,25 s.",
                f"- Plansze ({m['cutaways']} w rolce, {_n(m['cutaway_s'][0])} i {_n(m['cutaway_s'][1])} s): twarde cięcie na ciemną kartę "
                "i z powrotem; słowa wchodzą po kolei, małe i duże w dwóch wierszach, wyróżnione frazy dużym krojem.",
                f"- Finał: twarde cofnięcie kamery do widoku całości z rozmyciem, które znika w 0,8 s; tarcza obraca się jeszcze o jedną "
                f"szprychę ({_n(m['finale_rotation_s'], 1)} s), wraca szprycha startowa, na górze pojawia się tytuł.",
                f"- Napisy: małe słowo po słowie nad schematem (1-2 słowa), wyróżnione frazy dużym krojem pod małymi; po finale schodzą pod schemat."]
    return out + [""]


def _brand_section(tpl: Template) -> list[str]:
    """Kolory grafik z marki. Kolory nagrania szablon jednego ujęcia zostawia bez zmian."""
    from .graphics.core import PlanError, load_brand

    out = ["## Kolory", "", "Szablon nie zmienia kolorów nagrania. Kolory mają grafiki i napisy, z marki."]
    try:
        brand = load_brand(tpl.graphics.get("brand"))
    except PlanError:
        return out + [""]
    out += ["", f"Marka: {brand.name}.", "", "| Rola | Kolor | Do czego |", "|---|---|---|"]
    for role, use in BRAND_ROLES.items():
        r, g, b = brand.rgb(role)
        out.append(f"| {role} | `#{r:02X}{g:02X}{b:02X}` | {use} |")
    return out + [""]


MOTION_COLORS = (
    ("paper", "papier", "tło z siatką kropek (w eliptycznej winiecie), tekst w piaście tarczy i małe słowa na planszach"),
    ("ink", "tusz", "piasta, szprychy, kropki i etykiety tarczy, napisy, tło plansz"),
    ("violet", "fiolet", "obrys piasty i cienka linia wewnątrz niej"),
    ("highlight", "żółty", "aktywna kropka na szprysze i wyróżnione słowa na planszach: jedyny jasny akcent naraz"),
)


def _motion_colors_section(tpl: Template) -> list[str]:
    """Motion: nie ma nagrania, więc kolory to wyłącznie kolory marki, rozdzielone między tło, tarczę i plansze."""
    from .graphics.core import PlanError, load_brand

    out = ["## Kolory", "", "Nagrania nie ma, więc nie ma czego dopasowywać: cały obraz rysują grafiki w kolorach marki."]
    try:
        brand = load_brand(tpl.graphics.get("brand"))
    except PlanError:
        return out + [""]
    out += ["", f"Marka: {brand.name}.", "", "| Kolor | Wartość | Gdzie |", "|---|---|---|"]
    for role, name, use in MOTION_COLORS:
        r, g, b = brand.rgb(role)
        out.append(f"| {name} | `#{r:02X}{g:02X}{b:02X}` | {use} |")
    return out + [""]


def _motion_graphics_section(tpl: Template) -> list[str]:
    out = ["## Grafiki i napisy", ""]
    c = (tpl.graphics or {}).get("captions")
    if c:
        out.append(f"- Napisy kinetyczne rysuje warstwa grafik w kroju marki: do {c.get('max_words', 2)} słów naraz, górna linia na "
                   f"{_n(c.get('y', 0) * 100)}% wysokości kadru; słowa wchodzą z rozmyciem i wjazdem od dołu."
                   + (" Napisy biorą słowa z Twojego scenariusza, a czasy z mowy." if c.get("from_script") else ""))
    out += ["- Plan grafik to scenariusz ze znacznikami `{...}` albo plik JSON (`--graphics`); kroki tarczy i plansze mają czasy z mowy.",
            "- Elementy planu:"]
    out += [f"  - `{k}`: {v}" for k, v in MOTION_ELEMENTS.items()]
    out += ["- Wyróżnienia w tekście scenariusza (`*fraza*`) dostają duży krój: na planszach w kolorze wyróżnika (żółtym), w napisach tuszem."]
    return out + [""]


def _graphics_section(tpl: Template) -> list[str]:
    out = ["## Grafiki i napisy", ""]
    c = (tpl.graphics or {}).get("captions")
    if c:
        out.append(f"- Napisy rysuje warstwa grafik, w kroju marki: do {c.get('max_words', 3)} słów naraz, wysokość wersalików "
                   f"{_n(c.get('size', 0) * 100)}% wysokości kadru (ok. {round(c.get('size', 0) * tpl.canvas[1])} px z {tpl.canvas[1]}), "
                   f"górna krawędź na {_n(c.get('y', 0) * 100)}% wysokości.")
    out += ["- Resztę dynamiki daje plan grafik: plik JSON z czasami (`--graphics plan.json` albo przeciągnięcie w interfejsie).",
            "- Elementy planu:"]
    out += [f"  - `{k}`: {v}" for k, v in GRAPHICS_ELEMENTS.items()]
    out += ["- Efekt: `blur` rozmywa i przyciemnia obraz na czas pokazywania kart, żeby grafiki były czytelne.",
            "- Każdy element może stać „za postacią” (`behind: true`, w scenariuszu `za: tak`): program wycina Twoją sylwetkę "
            "i rysuje element pod nią, np. poświatę za głową albo kartę za ramieniem.",
            "- Miejsce w kadrze wynika z położenia Twojej twarzy: grafiki trafiają nad głowę, na boki albo pod napisy, nigdy na twarz."]
    return out + [""]


def _cuts_graphics_section(tpl: Template) -> list[str]:
    """Format 3: cięcia jak w Formacie 1, ale napisy, hasła i błyski rysuje warstwa grafik w kolorach i kroju marki."""
    from .graphics import lockup, transitions

    g = tpl.graphics or {}
    c, k = g.get("captions") or {}, g.get("lockup") or {}
    out = ["## Napisy, hasła i błyski", ""]
    if c:
        out.append(f"- Napisy rysuje warstwa grafik, w kroju marki: statyczne porcje do {c.get('max_words', 3)} słów (cała porcja pojawia się naraz, "
                   f"bez animacji), wysokość wersalików {_n(c.get('size', 0) * 100)}% wysokości kadru (ok. {round(c.get('size', 0) * tpl.canvas[1])} px "
                   f"z {tpl.canvas[1]}), górna krawędź na {_n(c.get('y', 0) * 100)}% wysokości, pod brodą. Kolor biały, z lekkim cieniem."
                   + (" Słowa biorą się z Twojego scenariusza (poprawna pisownia), a czasy z mowy; bez scenariusza z rozpoznanej mowy."
                      if c.get("from_script") else ""))
    if k:
        big = float(k.get("size", lockup.BIG_EM))
        out.append(f"- Hasło: słowa wyróżnione w scenariuszu (`*tak*`) wchodzą jako blok. Duży wiersz ({k.get('big_max', 2)} słowa najwyżej, "
                   f"szeryfowa kursywa, żółty, ok. {_n(big * 100)}% wysokości kadru), nad nim do {k.get('pre', 3)} małych słów, pod nim do "
                   f"{k.get('post', 3)}: małe wiersze są wyjustowane do szerokości dużego słowa, a blok ma najwyżej {_n(lockup.MAX_W * 100, 0)}% "
                   f"szerokości kadru. Blok zaczyna się na {_n(lockup.TOP * 100)}% wysokości. Każde słowo wskakuje od razu w chwili, gdy pada "
                   "(bez animacji), a na czas hasła jego słowa znikają ze zwykłych napisów. Hasło nie wychodzi poza zdanie ani poza pauzę "
                   f"dłuższą niż {_n(k.get('max_gap_s', lockup.MAX_GAP_S), 2)} s.")
    flashes = [(i, f) for i, s_ in enumerate(tpl.segments) for f in s_.fx if f.type == "flash"]
    if flashes:
        peak = max(transitions.FLASH)
        out.append(f"- Błysk: biała nakładka na całym obrazie, także na nagraniu: krycie rośnie do {_n(peak * 100, 0)}% w pierwszej klatce nowego "
                   f"ujęcia i schodzi do zera w {len(transitions.FLASH)} klatkach ({_n(len(transitions.FLASH) / 30, 2)} s). We wzorcu jest tylko przy "
                   "drugiej wstawce, na wejściu w nią i na wyjściu z niej; pozostałe cięcia, także wejście w pierwszą wstawkę, są twarde.")
    out += ["- Przejścia w planie grafik: `przejście` (rozmycie, najazd, przesunięcie, kurtyna, błysk). Przy nagraniu pod spodem działa pełnym "
            "obrazem tylko błysk, reszta obrabia same grafiki (opis w PRZEJSCIA.md).",
            "- Plan grafik to scenariusz ze znacznikami `{...}` albo plik JSON (`--graphics`); wyróżnienia `*tak*` wystarczą, żeby powstały hasła.",
            "- Elementy planu:"]
    out += [f"  - `{name}`: {text}" for name, text in {**GRAPHICS_ELEMENTS, **FORMAT3_ELEMENTS}.items()]
    out += ["- Efekt: `blur` rozmywa i przyciemnia obraz na czas pokazywania kart, żeby grafiki były czytelne.",
            "- „Za postacią” (`za: tak`) działa tylko w Formacie 2, w jednym ujęciu; przy cięciach grafiki leżą przed postacią.",
            "- Miejsce w kadrze wynika z położenia Twojej twarzy: grafiki trafiają nad głowę, na boki albo pod napisy, nigdy na twarz."]
    return out + [""]


def describe(tpl: Template) -> str:
    """Karta stylu w Markdown."""
    head = [f"# Karta stylu: {tpl.name}", "",
            f"Źródło: {tpl.source or 'brak'}. Format {tpl.canvas[0]}x{tpl.canvas[1]}, {tpl.fps} kl./s, {_n(tpl.duration_s)} s.", ""]
    notes = [f"{i + 1}. ({s.role}) {s.note}" for i, s in enumerate(tpl.segments) if s.note]
    if tpl.motion:
        body = _motion_section(tpl) + _motion_colors_section(tpl) + _motion_graphics_section(tpl)
    elif tpl.mode == "single":
        body = _single_section(tpl) + _framing_section(tpl) + _brand_section(tpl) + _graphics_section(tpl)
    elif tpl.keep_colors and (tpl.graphics or {}).get("captions"):  # Format 3: cięcia z napisami, hasłami i błyskami z warstwy grafik
        body = _cuts_section(tpl) + _framing_section(tpl) + _brand_section(tpl) + _cuts_graphics_section(tpl)
    else:
        body = _cuts_section(tpl) + _framing_section(tpl) + _look_section(tpl) + _captions_section(tpl)
    if notes:
        body += ["## Opis ujęć", ""] + notes + [""]
    return "\n".join(head + body).rstrip() + "\n"
