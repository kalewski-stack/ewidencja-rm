"""Scenariusz ze znacznikami: składnia, dopasowanie tekstu do mowy i plan grafik z czasami (bez Pillow i ffmpeg)."""
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import captions  # noqa: E402
from reelcut.graphics import plan_needs_words, script  # noqa: E402
from reelcut.graphics.core import PlanError  # noqa: E402

SPOKEN = ("Dzisiaj o tym czym jest content strategy w firmie Zrobiłem ich ponad siedemset wydarzeń i to uczy "
          "Krok po kroku zrobimy film To już koniec").split()

SCRIPT = """
# Scenariusz testowy (uwaga, nie jest mową)
{plakietka: Scenariusz wideo | numer: 1}
Dzisiaj o tym, czym jest {tytuł: Content Strategy | akcent: najgorsza | styl: serif} content strategy w firmie. [pauza]
{licznik: 700+ | podpis: wydarzeń B2B | strefa: lewo} Zrobiłem ich ponad siedemset wydarzeń,
{karty: Za kulisami; Dema = Pierwszy punkt / Drugi *ważny*; Wnioski | rozmycie: tak | do: koniec} i to uczy.
Krok po kroku {kroki: Plan = Hak; Nagranie} zrobimy film. {/kroki}
To już koniec.
"""


def spoken(words=SPOKEN, step=0.5, dur=0.4):
    return [captions.Word(w, i * step, i * step + dur) for i, w in enumerate(words)]


class ParseTests(unittest.TestCase):
    def test_words_exclude_comments_stage_directions_and_markers(self):
        s = script.parse(SCRIPT)
        self.assertEqual(s.words[:3], ["Dzisiaj", "o", "tym,"])
        self.assertNotIn("Scenariusz", s.words)  # linia zaczynająca się od # to uwaga
        self.assertNotIn("[pauza]", s.words)
        self.assertNotIn("pauza", s.words)
        self.assertEqual([c.kind for c in s.cues], ["badge", "title", "stat", "cards", "steps"])

    def test_cue_starts_at_the_next_spoken_word(self):
        s = script.parse(SCRIPT)
        by = {c.kind: c for c in s.cues}
        self.assertEqual(by["badge"].word, 0)
        self.assertEqual(s.words[by["title"].word], "content")
        self.assertEqual(s.words[by["stat"].word], "Zrobiłem")

    def test_polish_names_with_diacritics_and_english_names_are_both_fine(self):
        for head in ("tytuł", "TYTUŁ", "title", "Tytul"):
            self.assertEqual(script.parse("{" + head + ": X} a").cues[0].kind, "title")
        for head, kind in (("wyróżnienie", "callout"), ("pigułki", "pills"), ("oś", "axis"), ("rozmycie", "blur")):
            self.assertEqual(script.parse("{" + head + ": A; B} a").cues[0].kind, kind)

    def test_items_pairs_and_bullets(self):
        s = script.parse("{karty: Pierwsza = a / b; Druga; Trzecia = *c*} x")
        items = s.cues[0].spec["items"]
        self.assertEqual([i["label"] for i in items], ["Pierwsza", "Druga", "Trzecia"])
        self.assertEqual(items[0]["bullets"], ["a", "b"])
        self.assertNotIn("bullets", items[1])
        self.assertEqual(items[2]["bullets"], ["*c*"])
        steps = script.parse("{kroki: Plan = opis; Bez opisu} x").cues[0].spec["items"]
        self.assertEqual(steps, [{"title": "Plan", "sub": "opis"}, {"title": "Bez opisu"}])
        chips = script.parse("{kafelki: Klient = 15 834 zł; Drugi = 9082 zł} x").cues[0].spec["items"]
        self.assertEqual((chips[0]["label"], chips[0]["value"], chips[0]["suffix"]), ("Klient", 15834, " zł"))
        self.assertEqual(chips[1]["value"], 9082)

    def test_card_images_go_to_the_matching_items(self):
        spec = script.parse("{karty: A; B; C | obrazy: a.jpg; ; c.png} x").cues[0].spec
        self.assertEqual([(i.get("image"), i["kind"]) for i in spec["items"]], [("a.jpg", "image"), (None, "play"), ("c.png", "image")])

    def test_stat_value_prefix_and_suffix(self):
        cases = {"700+": (700, "", "+"), "15 834 zł": (15834, "", " zł"), "2,5 mln": (2.5, "", " mln"), "$120": (120, "$", ""),
                 "700 wydarzeń": (700, "", " wydarzeń"), "100%": (100, "", "%")}
        for text, (value, prefix, suffix) in cases.items():
            spec = script.parse("{licznik: " + text + "} x").cues[0].spec
            self.assertEqual((spec["value"], spec.get("prefix", ""), spec.get("suffix", "")), (value, prefix, suffix), text)
        self.assertEqual(script.parse("{licznik: 2,5 mln} x").cues[0].spec["decimals"], 1)
        with self.assertRaises(PlanError):
            script.parse("{licznik: sporo} x")

    def test_keys_are_translated_coerced_and_unknown_ones_pass_through(self):
        spec = script.parse("{profil: Info | tryb: mini | licznik: 25; 60 | pasek: 0.3; 1 | korona: tak | strefa: dół | size: 0,07} x").cues[0].spec
        self.assertEqual((spec["label"], spec["mode"], spec["count"], spec["bar"], spec["crown"], spec["zone"], spec["size"]),
                         ("Info", "mini", [25, 60], [0.3, 1], True, "bottom", 0.07))

    def test_closing_marker_ends_the_last_open_one_of_that_type(self):
        s = script.parse("a b {tytuł: X} c d {/tytuł} e")
        self.assertEqual((s.cues[0].word, s.cues[0].end_word), (2, 3))
        s = script.parse("{tytuł: A} a {tytuł: B} b {/tytuł} c {/tytuł} d")
        self.assertEqual([(c.word, c.end_word) for c in s.cues], [(0, 2), (1, 1)])  # zamknięcia parują się od końca: pierwsze z B, drugie z A

    def test_syntax_errors_are_explained(self):
        cases = {
            "{kometa: X} a": "nieznany typ „kometa”",
            "{tytuł: X | bez dwukropka} a": "nie ma dwukropka",
            "{/tytuł} a": "nie ma wcześniejszego otwarcia",
            "{/kometa} a": "nieznany typ",
            "{tytuł: X a": "bez pary",
            "a } b": "bez pary",
        }
        for text, needle in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(PlanError) as cm:
                    script.parse(text)
                self.assertIn(needle, str(cm.exception))


class AlignTests(unittest.TestCase):
    def test_perfect_match_gives_the_spoken_times(self):
        words = "to jest test mowy".split()
        times, cov = script.align(words, spoken(words))
        self.assertEqual(cov, 1.0)
        self.assertEqual([round(t[0], 2) for t in times], [0.0, 0.5, 1.0, 1.5])

    def test_ignores_case_diacritics_and_punctuation(self):
        times, cov = script.align(["Zrobiłem,", "ŁÓDŹ!"], spoken(["zrobilem", "lodz"]))
        self.assertEqual(cov, 1.0)

    def test_misheard_words_are_interpolated_between_neighbours(self):
        script_words = "jeden dwa trzy cztery pięć".split()
        heard = "jeden dwa trzej cztery pięć".split()  # „trzy” rozpoznane jako „trzej”
        times, cov = script.align(script_words, spoken(heard))
        self.assertAlmostEqual(cov, 4 / 5)
        self.assertGreater(times[2][0], times[1][1] - 1e-6)
        self.assertLess(times[2][0], times[3][0])

    def test_guessed_words_never_run_into_the_next_word(self):
        # mowa ma zamiast „dwa trzy cztery” jedno przekręcone słowo, więc trzy słowa scenariusza dostają czasy z interpolacji
        heard = [captions.Word("jeden", 0.0, 0.4), captions.Word("xx", 0.5, 0.6), captions.Word("pięć", 0.9, 1.2), captions.Word("sześć", 1.3, 1.6)]
        times, cov = script.align("jeden dwa trzy cztery pięć sześć".split(), heard)
        self.assertAlmostEqual(cov, 0.5)
        for (a0, a1), (b0, b1) in zip(times, times[1:]):
            self.assertLessEqual(a1, b0 + 1e-9)
            self.assertLess(a0, a1)

    def test_extra_words_in_speech_do_not_break_the_alignment(self):
        script_words = "zaczynamy od hasła i kończymy".split()
        heard = "yyy zaczynamy no od hasła i eee kończymy".split()
        times, cov = script.align(script_words, spoken(heard))
        self.assertEqual(cov, 1.0)
        self.assertAlmostEqual(times[0][0], 0.5)  # „zaczynamy” jest drugie w mowie
        self.assertAlmostEqual(times[-1][0], 3.5)

    def test_words_before_the_first_and_after_the_last_hit_are_extrapolated(self):
        heard = [captions.Word(w, 5.0 + i, 5.4 + i) for i, w in enumerate(["dwa", "trzy", "cztery"])]
        times, _ = script.align("raz dwa trzy cztery pięć".split(), heard)
        self.assertLess(times[0][0], times[1][0])  # „raz” jest przed pierwszym trafieniem
        self.assertGreater(times[4][0], times[3][0])  # „pięć” po ostatnim

    def test_nothing_in_common(self):
        self.assertEqual(script.align(["a"], spoken(["b"])), ([], 0.0))


class ToPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = script.to_plan(SCRIPT, spoken())
        self.el = {e["type"]: e for e in self.plan["elements"]}

    def test_times_follow_the_spoken_words(self):
        self.assertAlmostEqual(self.el["badge"]["at"], 0.0)
        self.assertAlmostEqual(self.el["title"]["at"], 2.5)  # „content” to szóste słowo
        self.assertAlmostEqual(self.el["stat"]["at"], 4.5)
        self.assertAlmostEqual(self.el["steps"]["at"], 10.0)  # „zrobimy” to dwudzieste pierwsze słowo

    def test_end_comes_from_phrase_closing_marker_or_default(self):
        self.assertAlmostEqual(self.el["cards"]["at"] + self.el["cards"]["dur"], 12.4, places=2)  # do: koniec -> koniec słowa „koniec”
        self.assertAlmostEqual(self.el["steps"]["at"] + self.el["steps"]["dur"], 10.9, places=2)  # {/kroki} po słowie „film.”
        self.assertNotIn("dur", self.el["title"])  # bez końca: domyślny czas elementu

    def test_blur_is_attached_to_the_cards_window(self):
        (fx,) = self.plan["effects"]
        self.assertEqual(fx["type"], "blur")
        self.assertAlmostEqual(fx["at"], self.el["cards"]["at"] - 0.1, places=2)
        self.assertAlmostEqual(fx["dur"], self.el["cards"]["dur"] + 0.2, places=2)

    def test_shift_and_seconds(self):
        plan = script.to_plan("a b c {tytuł: X | przesuń: -0.3 | czas: 1,5} d e", spoken("a b c d e".split()))
        e = plan["elements"][0]
        self.assertAlmostEqual(e["at"], 1.5 - 0.3, places=3)
        self.assertEqual(e["dur"], 1.5)
        self.assertNotIn("shift", e)

    def test_explicit_blur_marker(self):
        plan = script.to_plan("a {rozmycie | siła: 20} b c {/rozmycie} d", spoken("a b c d".split()))
        (fx,) = plan["effects"]
        self.assertEqual((fx["type"], fx["sigma"]), ("blur", 20))
        self.assertAlmostEqual(fx["dur"], 0.9, places=2)  # od początku „b” (0,5 s) do końca „c” (1,4 s)
        plan = script.to_plan("a {rozmycie} b", spoken("a b".split()))
        self.assertEqual(plan["effects"][0]["dur"], script.DEFAULT_BLUR_DUR)

    def test_a_marker_after_the_last_word_starts_when_speech_ends(self):
        plan = script.to_plan("a b {tytuł: Koniec}", spoken("a b".split()))
        self.assertAlmostEqual(plan["elements"][0]["at"], 0.5 + 0.4, places=3)

    def test_errors(self):
        with self.assertRaises(PlanError) as cm:
            script.to_plan("Bez znaczników w ogóle", spoken())
        self.assertIn("ani jednego znacznika", str(cm.exception))
        with self.assertRaises(PlanError) as cm:
            script.to_plan("{tytuł: X} a b", [])
        self.assertIn("--words", str(cm.exception))
        with self.assertRaises(PlanError) as cm:
            script.to_plan("{tytuł: X}", spoken())
        self.assertIn("bez tekstu", str(cm.exception))
        with self.assertRaises(PlanError) as cm:  # to nie jest ten tekst
            script.to_plan("{tytuł: X} zupełnie inny tekst niż w nagraniu", spoken())
        self.assertIn("nie pasuje do nagrania", str(cm.exception))
        with self.assertRaises(PlanError) as cm:
            script.to_plan("{tytuł: X | do: nie padło} Dzisiaj o tym czym jest", spoken())
        self.assertIn("fraza do:", str(cm.exception))

    def test_result_is_a_normal_plan(self):
        self.assertEqual(self.plan["schema"], 1)
        for e in self.plan["elements"]:
            self.assertIsInstance(e["at"], float)
            self.assertTrue(e["said"])


class FilesTests(unittest.TestCase):
    def test_plan_needs_words_for_script_files_only_when_they_exist(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "s.txt").write_text("{tytuł: X} a", encoding="utf-8")
            (d / "s.md").write_text("{tytuł: X} a", encoding="utf-8")
            self.assertTrue(plan_needs_words(d / "s.txt"))
            self.assertTrue(plan_needs_words(d / "s.md"))
            self.assertFalse(plan_needs_words(d / "brak.txt"))
        self.assertTrue(script.is_script("A.TXT") and script.is_script("x.md") and not script.is_script("p.json"))


if __name__ == "__main__":
    unittest.main()
