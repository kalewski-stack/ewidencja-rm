"""Benchmark podcastu: liczby w data/podcast_benchmark.json są spójne i mieszczą się w swoich pasmach, a PODCAST.md i rysunek są z nimi zgodne."""
import json
import pathlib
import statistics
import struct
import unittest
from decimal import ROUND_HALF_UP, Decimal

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "src" / "reelcut" / "data"
B = json.loads((DATA / "podcast_benchmark.json").read_text(encoding="utf-8"))
DOC = (ROOT / "PODCAST.md").read_text(encoding="utf-8")
W, H = B["canvas"]


def n(x, nd=1):
    """Liczba po polsku, zaokrąglona w górę od połowy (tak jak w dokumencie i na rysunku)."""
    v = Decimal(str(x)).quantize(Decimal(1) if nd == 0 else Decimal("0." + "0" * nd), rounding=ROUND_HALF_UP)
    return str(v).replace(".", ",")


def pn(x, nd=0):
    """Ułamek jako liczba procentowa bez znaku %, liczona na Decimal, żeby 0,285 dawało 28,5, a nie 28,499999."""
    return n(Decimal(str(x)) * 100, nd)


def pc(x, nd=0):
    return pn(x, nd) + "%"


def lufs(x):
    return n(x).replace("-", "−")


class DataTests(unittest.TestCase):
    def test_shots_are_contiguous_and_add_up_to_the_duration(self):
        shots = B["shots"]
        self.assertEqual(shots[0]["start_s"], 0.0)
        for a, b in zip(shots, shots[1:]):
            self.assertAlmostEqual(a["start_s"] + a["len_s"], b["start_s"], delta=0.02)
        self.assertAlmostEqual(shots[-1]["start_s"] + shots[-1]["len_s"], B["duration_s"], delta=0.02)
        self.assertEqual({s["kind"] for s in shots}, set(B["kinds"]))

    def test_rhythm_follows_from_the_shots(self):
        r, shots = B["rhythm"], B["shots"]
        lens = [s["len_s"] for s in shots]
        self.assertEqual(r["shots"], len(shots))
        self.assertEqual(r["cuts"], len(shots) - 1)
        self.assertAlmostEqual(r["cuts_per_min"], r["cuts"] / B["duration_s"] * 60, delta=0.06)
        self.assertAlmostEqual(r["shot_s"]["mean"], statistics.mean(lens), delta=0.01)
        self.assertAlmostEqual(r["shot_s"]["median"], statistics.median(lens), delta=0.01)
        self.assertAlmostEqual(r["shot_s"]["min"], min(lens), delta=0.01)
        self.assertAlmostEqual(r["shot_s"]["max"], max(lens), delta=0.01)
        self.assertEqual(r["pattern"], [s["kind"] for s in shots])
        for kind in B["kinds"]:
            mine = [s["len_s"] for s in shots if s["kind"] == kind]
            self.assertEqual(r["count"][kind], len(mine))
            self.assertAlmostEqual(r["kind_s"][kind], statistics.mean(mine), delta=0.01)
            self.assertAlmostEqual(r["share"][kind], sum(mine) / B["duration_s"], delta=0.005)
        self.assertAlmostEqual(sum(r["share"].values()), 1.0, delta=0.005)

    def test_the_grammar_of_the_reference_holds(self):
        pattern = B["rhythm"]["pattern"]
        self.assertTrue(all(a != b for a, b in zip(pattern, pattern[1:])), "dwa takie same kadry obok siebie")
        self.assertEqual(B["rhythm"]["same_kind_in_a_row"], 0)
        tight = {"G1", "P1"}
        self.assertEqual([pattern[i] in tight for i in range(len(pattern))], [i % 2 == 0 and i < 7 for i in range(len(pattern))],
                         "ciasne ujęcia mają być na pozycjach 1, 3, 5, 7")
        self.assertEqual(pattern[-1], B["rhythm"]["last_kind"])
        self.assertEqual(B["rhythm"]["last_kind"], "T")
        self.assertEqual(B["rhythm"]["hard_cuts"], B["rhythm"]["cuts"])

    def test_framing_follows_from_the_shots(self):
        for kind in ("G1", "G2", "P1"):
            mine = [s["face"] for s in B["shots"] if s["kind"] == kind]
            f = B["framing"][kind]
            self.assertAlmostEqual(f["h"], statistics.median(x["h"] for x in mine), delta=0.002)
            self.assertAlmostEqual(f["h_min"], min(x["h"] for x in mine), delta=0.002)
            self.assertAlmostEqual(f["h_max"], max(x["h"] for x in mine), delta=0.002)
            self.assertAlmostEqual(f["cx"], statistics.median(x["cx"] for x in mine), delta=0.002)
            self.assertAlmostEqual(f["cy"], statistics.median(x["cy"] for x in mine), delta=0.002)
            self.assertTrue(f["cy"] - f["h"] / 2 > 0.05, "twarz nie może wychodzić górą z kadru")
        heads = [s["head"] for s in B["shots"] if s["kind"] == "T"]
        self.assertAlmostEqual(B["wide"]["head_h"], statistics.mean(x["h"] for x in heads), delta=0.002)
        self.assertAlmostEqual(B["wide"]["heads_y"], statistics.mean(x["cy"] for x in heads), delta=0.002)
        self.assertLess(B["wide"]["host_x"], 0.5)
        self.assertGreater(B["wide"]["guest_x"], 0.5)
        self.assertTrue(B["framing"]["G1"]["h"] > B["framing"]["P1"]["h"] > B["framing"]["G2"]["h"] > B["wide"]["head_h"])

    def test_geometry_is_consistent_in_pixels_and_fractions(self):
        t = B["text"]
        for key in ("speech", "key", "hero", "question", "closing"):
            self.assertAlmostEqual(t[key]["size_px"] / H, t[key]["size_h"], delta=0.0015, msg=key)
        lt, card = B["lower_third"], B["card"]
        self.assertAlmostEqual(lt["bar"]["h_px"] / H, lt["bar"]["h"], delta=0.001)
        self.assertAlmostEqual(lt["bar"]["x"] * W + lt["bar"]["w_px"] + lt["gap_px"], lt["text_x"] * W, delta=6)
        self.assertAlmostEqual(lt["delay_frames"] / B["fps"], lt["delay_s"], delta=0.01)
        self.assertAlmostEqual(card["x"][1] - card["x"][0], card["w"], delta=0.003)
        self.assertAlmostEqual((card["x"][1] - card["x"][0]) * W / ((card["y"][1] - card["y"][0]) * H), 2 / 3, delta=0.02)
        self.assertAlmostEqual(card["rise_frames"] / B["fps"], card["rise_s"], delta=0.01)
        self.assertAlmostEqual(B["opening"]["flash_frames"] / B["fps"], B["opening"]["flash_s"], delta=0.001)
        self.assertEqual(len(card["swap_s"]), card["swaps"])
        self.assertTrue(all(b > a for a, b in zip(card["swap_s"], card["swap_s"][1:])))
        # strefy: pytanie i zamknięcie leżą w pustej ścianie nad głowami, liczba w pustej podłodze pod pasem światła
        free_top, free_bottom = B["wide"]["free_above"][1], B["wide"]["free_below"][0]
        self.assertLess(t["closing"]["center_y"], free_top + 0.05)
        self.assertLess(t["question"]["center_y"], B["wide"]["heads_y"])
        self.assertGreater(t["hero"]["center_y"], free_bottom)
        self.assertGreater(t["hero"]["center_y"], B["wide"]["floor_strip_y"])
        # napis mowy leży pod brodą gościa w zbliżeniu
        chin = B["framing"]["G1"]["cy"] + B["framing"]["G1"]["h"] / 2
        self.assertGreater(t["speech"]["center_y"], chin + 0.05)
        for v in (t["speech"]["center_y"], t["key"]["center_y"], t["hero"]["center_y"], t["question"]["center_y"], t["closing"]["center_y"], lt["text_x"], lt["bar"]["x"]):
            self.assertTrue(0.0 < v < 1.0)

    def test_the_measured_values_sit_inside_their_bands(self):
        b, r = B["bands"], B["rhythm"]
        inside = lambda v, lo_hi: lo_hi[0] <= v <= lo_hi[1]  # noqa: E731
        self.assertTrue(inside(r["cuts_per_min"], b["cuts_per_min"]))
        self.assertTrue(b["shot_s"][0] <= r["shot_s"]["min"] and r["shot_s"]["max"] <= b["shot_s"][1])
        self.assertTrue(inside(r["shot_s"]["median"], b["median_s"]))
        for kind, rng in b["share"].items():
            self.assertTrue(inside(r["share"][kind], rng), kind)
        for kind in ("G1", "G2", "P1"):
            self.assertTrue(inside(B["framing"][kind]["h"], b["face_h"][kind]), kind)
        self.assertTrue(inside(B["wide"]["head_h"], b["face_h"]["T"]))
        self.assertTrue(inside(B["look"]["mean_y"], b["mean_y"]))
        self.assertTrue(inside(B["look"]["share_below_32"], b["share_below_32"]))
        self.assertTrue(inside(B["look"]["face_to_backdrop"]["G1"], b["face_to_backdrop_g1"]))
        self.assertTrue(inside(B["text"]["coverage"], b["coverage"]))
        self.assertTrue(inside(B["text"]["speech"]["center_y"], b["caption_center_y"]))
        self.assertTrue(inside(B["text"]["speech"]["size_px"], b["caption_px"]))
        self.assertTrue(inside(B["lower_third"]["delay_s"], b["lower_third_delay_s"]))
        self.assertTrue(inside(B["audio"]["lufs"], b["lufs"]))
        self.assertLessEqual(B["audio"]["lra"], b["lra_max"])
        self.assertLessEqual(r["first_cut_s"], b["first_cut_max_s"])
        self.assertTrue(b["safe_y"][0] <= B["safe"]["top"] and B["safe"]["bottom"] <= b["safe_y"][1])
        # wzorzec ma szczyt −0,9 dBTP, a zalecenie to −1,0: celowo zaostrzone, nie z pomiaru
        self.assertGreater(B["audio"]["true_peak"], b["true_peak_max"])

    def test_the_numbers_do_not_carry_reference_material(self):
        raw = (DATA / "podcast_benchmark.json").read_text(encoding="utf-8")
        for banned in BANNED:
            self.assertNotIn(banned, raw)
        self.assertEqual(B["schema"], 1)
        self.assertEqual(B["canvas"], [1080, 1920])
        self.assertTrue(B["source"].startswith("https://www.instagram.com/reel/"))


BANNED = ("Kalloway", "Sandcastles", "Residency", "Pavlov", "780,237", "REPRESENT", "kallaway")


class DocTests(unittest.TestCase):
    def test_the_doc_carries_the_numbers_from_the_json(self):
        r, fr, wd, lk, tx, lt, cd, op, au = (B["rhythm"], B["framing"], B["wide"], B["look"], B["text"], B["lower_third"], B["card"], B["opening"], B["audio"])
        sh, sp, key, hero, q, cl = r["shot_s"], tx["speech"], tx["key"], tx["hero"], tx["question"], tx["closing"]
        g1, g2, p1 = fr["G1"], fr["G2"], fr["P1"]
        wanted = [
            # w skrócie
            f"{n(B['duration_s'])} s, pion {W}×{H}, {n(B['fps'], 3)} kl./s",
            f"{r['shots']} ujęć, {r['cuts']} cięć ({n(r['cuts_per_min'])} na minutę), średnio {n(sh['mean'], 2)} s (mediana {n(sh['median'], 2)} s), od {n(sh['min'], 2)} do {n(sh['max'], 2)} s",
            f"zbliżenie gościa {pc(r['share']['G1'], 1)}, totalny {pc(r['share']['T'], 1)}, plan średni gościa {pc(r['share']['G2'], 1)}, reakcja prowadzącego {pc(r['share']['P1'], 1)}",
            f"zbliżenie gościa {pc(g1['h'])}, reakcja prowadzącego {pc(p1['h'])}, plan średni {pc(g2['h'])}, głowa w totalnym {pc(wd['head_h'], 1)} wysokości kadru",
            f"średnia jasność {n(lk['mean_y'], 0)}/255, {pc(lk['share_below_32'])} pikseli ciemniejszych niż 32/255, tło {lk['colors']['backdrop']}, twarz gościa {n(lk['face_to_backdrop']['G1'])}× jaśniejsza od tła",
            f"na ekranie {pc(tx['coverage'])} czasu",
            f"mowa białym pogrubionym bezszeryfem {sp['size_px']} px ({pc(sp['size_h'], 1)} wysokości) na {pc(sp['center_y'])} wysokości kadru",
            f"hasło {key['size_px']} px ({pc(key['size_h'], 1)})",
            f"czerwony słupek {lt['bar']['h_px']} px, imię i opis krojem mono ({lt['name']['size_px']} i {lt['role']['size_px']} px); wchodzi {lt['delay_frames']} klatek po cięciu",
            f"ekran 2:3 o szerokości {pc(cd['w'])} kadru, tylko w totalnym; wyrasta ze stołu w {n(cd['rise_s'], 2)} s, potem {cd['swaps']} szybkie zmiany slajdu",
            f"{op['flash_frames']} klatki ({n(op['flash_s'], 3)} s) błysku",
            f"{lufs(au['lufs'])} LUFS, szczyt {lufs(au['true_peak'])} dBTP, zakres {n(au['lra'])} LU; sama mowa ({n(au['words_per_s'])} słowa na sekundę)",
            f"({lk['colors']['accent']}, w słupku {lk['colors']['accent_core']})", lk["colors"]["table_top"],
            # kadry
            f"| {pc(g1['h'])} ({pn(g1['h_min'])}–{pc(g1['h_max'])}) | {pc(g1['cx'])} × {pc(g1['cy'])} | {pc(g1['eye_y'])} | średnio {n(r['kind_s']['G1'], 2)} s, {r['count']['G1']} ujęcia |",
            f"| {pc(g2['h'])} | {pc(g2['cx'])} × {pc(g2['cy'])} | {pc(g2['eye_y'])} | średnio {n(r['kind_s']['G2'], 2)} s, {r['count']['G2']} ujęcia |",
            f"| {pc(p1['h'])} | {pc(p1['cx'])} × {pc(p1['cy'])} | {pc(p1['eye_y'])} | {n(r['kind_s']['P1'], 2)} s, {r['count']['P1']} ujęcie |",
            f"| głowa {pc(wd['head_h'], 1)} (ok. {round(wd['head_h'] * H)} px) | prowadzący {pc(wd['host_x'])} × {pc(wd['heads_y'])}, gość {pc(wd['guest_x'])} × {pc(wd['heads_y'])} | {pc(wd['heads_y'])} | średnio {n(r['kind_s']['T'], 2)} s, {r['count']['T']} ujęcia |",
            f"Głowy na {pc(wd['heads_y'], 1)} wysokości, prowadzący na {pc(wd['host_x'], 1)} szerokości, gość na {pc(wd['guest_x'], 1)}",
            f"Pas światła na podłodze na {pc(wd['floor_strip_y'], 1)} wysokości, szeroki na {pc(wd['floor_strip_h'])} wysokości", lk["colors"]["strip_edge"],
            f"blat ok. {pc(wd['table_top_w'])} szerokości, czarna podstawa ok. {pc(wd['table_base_w'])} szerokości",
            "ściana od 0 do 40% wysokości i podłoga od 67% do 100%",
            f"o {wd['backdrop_creep_pct'][0]}% w {n(wd['creep_over_s'][0])} s i o {wd['backdrop_creep_pct'][1]}% w {n(wd['creep_over_s'][1])} s",
            # światło
            f"średnia całego klipu {n(lk['mean_y'], 0)}, mediana {n(lk['median_y'])}, 99. percentyl {lk['p99_y']}; {pc(lk['share_below_32'])} pikseli ciemniejszych niż 32, {pc(lk['share_below_16'])} ciemniejszych niż 16",
            f"ma {lk['face_y']['G1']} przy tle {lk['backdrop_y']}", f"({n(lk['face_to_backdrop']['G1'])}×)", f"prowadzący {lk['face_y']['P1']} ({n(lk['face_to_backdrop']['P1'])}×)",
            f"w planie średnim {lk['face_y']['G2']} ({n(lk['face_to_backdrop']['G2'])}×)", lk["colors"]["wall_top_wide"], lk["colors"]["floor_under_strip"],
            # napisy i grafika
            f"{sp['size_px']} px ({pc(sp['size_h'], 1)} wysokości), środek na {pc(sp['center_y'])} wysokości, do {sp['max_lines']} wierszy co {sp['pitch_px']} px, do {pc(sp['max_w'])} szerokości",
            f"(opóźnienie do {n(sp['lag_s'], 2)} s)",
            f"{key['size_px']} px ({pc(key['size_h'], 1)} wysokości), wyśrodkowane, środek na {pc(key['center_y'])} wysokości ({pn(key['span_y'][0])}–{pc(key['span_y'][1])}), "
            f"{pn(key['width_w'][0])}–{pc(key['width_w'][1])} szerokości",
            f"to {key['glitch_frames']} klatek ({n(key['glitch_frames'] / B['fps'], 2)} s)", f"stoi {n(key['hold_s'][0])}–{n(key['hold_s'][1])} s",
            f"{hero['size_px']} px ({pc(hero['size_h'], 1)} wysokości), środek na {pc(hero['center_y'], 1)} wysokości (pod pasem światła), podpis na {pc(hero['sub']['center_y'], 1)}, szerokość {pc(hero['width_w'])}",
            f"podpis ({hero['sub']['size_px']} px)",
            f"{q['size_px']} px ({pc(q['size_h'], 1)}), 2 wiersze co {q['pitch_px']} px, środek na {pc(q['center_y'], 1)} wysokości, szerokość {pc(q['width_w'])}",
            f"{cl['size_px']} px ({pc(cl['size_h'], 1)}), 2 wiersze co {cl['pitch_px']} px, środek na {pc(cl['center_y'], 1)} wysokości, szerokość {pc(cl['width_w'])}",
            f"wchodzi {n(cl['delay_s'], 2)} s po cięciu",
            f"słupek {lt['bar']['w_px']}×{lt['bar']['h_px']} px ({pc(lt['bar']['h'], 1)} wysokości) na {pc(lt['bar']['x'], 1)} szerokości, tekst od {pc(lt['text_x'], 1)}",
            f"imię wersalikami {lt['name']['size_px']} px (wysokość wersalika {lt['name']['cap_px']} px), opis {lt['role']['size_px']} px",
            f"środek na {pc(lt['center_y'][0], 1)} albo {pc(lt['center_y'][1], 1)} wysokości",
            f"{pc(cd['w'], 1)} szerokości (x od {pc(cd['x'][0], 1)} do {pc(cd['x'][1], 1)}), y od {pc(cd['y'][0], 1)} do {pc(cd['y'][1], 1)}",
            f"od {pc(cd['rise_from_y'], 1)} do 16,7% (górna krawędź) w {cd['rise_frames']} klatkach ({n(cd['rise_s'], 2)} s)",
            f"co {n(cd['swap_s'][1] - cd['swap_s'][0], 2)}–{n(cd['swap_s'][3] - cd['swap_s'][2], 2)} s, ostatni stoi {n(cd['hold_last_s'], 2)} s",
            f"jasność wnętrza {cd['inside_y']} wobec {cd['outside_y']}",
            f"jasność {', '.join(str(v) for v in op['mean_y'])} wobec {op['after_y']} po błysku", *op["colors"],
            f"ok. {au['impact']['over_median_db']} dB nad medianą pasma poniżej 120 Hz, {n(au['impact']['len_s'], 2)} s",
            lk["colors"]["accent_halo"], f"({n(lt['hold_s'][0], 2)} s i {n(lt['hold_s'][1], 2)} s)",
            # dźwięk
            f"{lufs(au['lufs'])} LUFS, szczyt {lufs(au['true_peak'])} dBTP, zakres głośności {n(au['lra'])} LU",
            f"{au['words']} słów w 23 s, {n(au['words_per_s'])} słowa na sekundę", f"korelacja kanałów {n(au['stereo_corr'], 2)}", f"{au['rate'] / 1000:.1f}".replace(".", ",") + " kHz",
            # lista kontrolna
            f"| {n(r['cuts_per_min'])} | {n(B['bands']['cuts_per_min'][0])}–{n(B['bands']['cuts_per_min'][1], 0)} |",
            f"| {n(B['bands']['shot_s'][0])}–{n(B['bands']['shot_s'][1])} s, mediana {n(B['bands']['median_s'][0], 0)}–{n(B['bands']['median_s'][1])} s |",
            f"| do {n(B['bands']['first_cut_max_s'])} s |",
            f"zbliżenie {pn(B['bands']['share']['G1'][0])}–{pc(B['bands']['share']['G1'][1])}, totalny {pn(B['bands']['share']['T'][0])}–{pc(B['bands']['share']['T'][1])}, "
            f"plan średni {pn(B['bands']['share']['G2'][0])}–{pc(B['bands']['share']['G2'][1])}, reakcja do {pc(B['bands']['share']['P1'][1])}",
            f"| {pn(B['bands']['face_h']['G1'][0])}–{pc(B['bands']['face_h']['G1'][1])} |", f"| {pn(B['bands']['face_h']['G2'][0])}–{pc(B['bands']['face_h']['G2'][1])} |",
            f"| {pn(B['bands']['face_h']['P1'][0])}–{pc(B['bands']['face_h']['P1'][1])} |", f"| {pn(B['bands']['face_h']['T'][0], 1)}–{pc(B['bands']['face_h']['T'][1], 1)} |",
            f"| {B['bands']['mean_y'][0]}–{B['bands']['mean_y'][1]} |", f"| {n(B['bands']['face_to_backdrop_g1'][0])}–{n(B['bands']['face_to_backdrop_g1'][1], 0)}× |",
            f"| co najmniej {pc(B['bands']['coverage'][0])} |",
            f"| {pn(B['bands']['caption_center_y'][0])}–{pc(B['bands']['caption_center_y'][1])}, {B['bands']['caption_px'][0]}–{B['bands']['caption_px'][1]} px |",
            f"| {n(B['bands']['lower_third_delay_s'][0], 2)}–{n(B['bands']['lower_third_delay_s'][1], 2)} s po cięciu |",
            f"{lufs(B['bands']['lufs'][0])[:-2]} do {lufs(B['bands']['lufs'][1])} LUFS, szczyt do {lufs(B['bands']['true_peak_max'])} dBTP, zakres do {n(B['bands']['lra_max'], 0)} LU",
            f"między {pc(B['safe']['top'], 1)} a {pc(B['safe']['bottom'], 1)} wysokości kadru",
            f"| {pc(B['safe']['top'], 1).replace('%', '')}–{pc(B['safe']['bottom'], 1)} wysokości | {pn(B['bands']['safe_y'][0])}–{pn(B['bands']['safe_y'][1])}% wysokości |",
        ]
        missing = [w for w in wanted if w not in DOC]
        self.assertEqual(missing, [], "w PODCAST.md brakuje liczb z podcast_benchmark.json")

    def test_the_shot_table_in_the_doc_matches_the_shots(self):
        shots = B["shots"]
        names = {"G1": "zbliżenie gościa", "T": "totalny", "P1": "reakcja prowadzącego", "G2": "plan średni gościa"}
        for i, s in enumerate(shots):
            end = shots[i + 1]["start_s"] if i + 1 < len(shots) else B["duration_s"]
            row = f"| {n(s['start_s'], 2)}–{n(end, 2)} | {names[s['kind']]} |"
            self.assertIn(row, DOC, row)

    def test_the_comparison_with_the_other_formats_matches_the_templates(self):
        def dyn(name):
            return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))["dynamics"]
        f1, f3, f4 = dyn("rolka_DeuOaXKtPBb"), dyn("format3"), dyn("format4h")
        r = B["rhythm"]
        wanted = [f"podcast {n(r['shot_s']['mean'], 2)} s i {n(r['cuts_per_min'])} cięcia na minutę",
                  f"Format 3 {n(f3['shot_s']['mean'], 2)} s i {n(f3['cuts_per_min'])}", f"Format 1 {n(f1['shot_s']['mean'], 2)} s i {n(f1['cuts_per_min'])}",
                  f"Format 4 {n(f4['shot_s']['mean'], 2)} s i {n(f4['cuts_per_min'])}"]
        louds = [f["loudness"]["lufs"] for f in (f1, f3, f4)]
        wanted.append(f"({lufs(B['audio']['lufs'])} LUFS wobec {lufs(max(louds))} do {lufs(min(louds))})")
        self.assertEqual([w for w in wanted if w not in DOC], [])
        self.assertIn(f"{lufs(max(louds))} do {lufs(min(louds))} LUFS", DOC)

    def test_the_brand_mapping_uses_real_tokens_of_the_brand_file(self):
        brand = json.loads((DATA / "brand_kalewski.json").read_text(encoding="utf-8"))
        c = brand["colors"]
        for token in ("yellow", "violet", "ink", "paper"):
            self.assertIn(c[token].upper(), DOC, token)
        self.assertEqual(brand["roles"]["highlight"], "yellow")
        self.assertEqual(brand["roles"]["line"], "violet")
        self.assertIn("serif_italic", brand["fonts"])
        for role in ("`highlight`", "`line`", "`serif_italic`"):
            self.assertIn(role, DOC)
        self.assertIn("Bricolage Grotesque", DOC)
        self.assertIn("Instrument Serif Italic", DOC)

    def test_the_doc_separates_measurement_from_inference_and_states_the_limits(self):
        for must in ("Pomiar", "Wniosek", "Nieznane", "jedna rolka", "jedna próbka", "bez obrazu, mowy i tekstów", "Granice i decyzje", "Format 5", "założenie",
                     "data/podcast_benchmark.json", "docs/podcast_rama.png", "Lista kontrolna", "Oś 180°"):
            self.assertIn(must, DOC, must)
        self.assertNotIn("—", DOC, "bez długich myślników")
        self.assertTrue("nie jest jeszcze szablon" in DOC.lower().replace("**", "") or "jeszcze nie jest szablon" in DOC.lower().replace("**", ""))

    def test_the_doc_keeps_the_reference_material_out_of_the_repo(self):
        for name in ("PODCAST.md", "CLAUDE.md", "README.md", "STYL.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for banned in BANNED:
                self.assertNotIn(banned, text, (name, banned))

    def test_the_benchmark_is_linked_from_the_main_docs_and_not_numbered_as_a_format(self):
        for name in ("README.md", "CLAUDE.md", "STYL.md"):
            self.assertIn("PODCAST.md", (ROOT / name).read_text(encoding="utf-8"), name)
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("Benchmark podcastu", claude)
        self.assertIn("podcast_benchmark.json", claude)
        self.assertIn("Format 5", claude)

    def test_the_sheet_is_a_png_of_the_expected_size(self):
        raw = (ROOT / "docs" / "podcast_rama.png").read_bytes()
        self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", raw[16:24])
        self.assertEqual(width, 2400)
        self.assertTrue(1800 <= height <= 2200, height)
        self.assertLess(len(raw), 2_000_000, "arkusz ma być lekki")


if __name__ == "__main__":
    unittest.main()
