"""Kotwice w mowie: czasy grafik podane jako frazy z transkrypcji (bez Pillow i ffmpeg)."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from reelcut import captions  # noqa: E402
from reelcut.graphics import anchors  # noqa: E402
from reelcut.graphics.core import PlanError  # noqa: E402

TEXT = "To jest test napisów w kroju marki. Dzisiaj siedemset wydarzeń B2B, a potem znowu test napisów."


def spoken(text=TEXT, step=0.5, dur=0.4):
    return [captions.Word(w, i * step, i * step + dur) for i, w in enumerate(text.split())]


class NormTests(unittest.TestCase):
    def test_norm_drops_case_diacritics_and_punctuation(self):
        self.assertEqual(anchors.norm("Wydarzeń,"), "wydarzen")
        self.assertEqual(anchors.norm("Łódź"), "lodz")
        self.assertEqual(anchors.norm("B2B!"), "b2b")
        self.assertEqual(anchors.norm("—"), "")


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.words = spoken()
        self.idx = anchors.SpokenIndex(self.words)

    def test_finds_a_phrase_start_and_end(self):
        start, end = self.idx.find("siedemset wydarzeń B2B")
        i = [w.text for w in self.words].index("siedemset")
        self.assertAlmostEqual(start, self.words[i].start)
        self.assertAlmostEqual(end, self.words[i + 2].end)

    def test_ignores_case_diacritics_and_punctuation(self):
        self.assertEqual(self.idx.find("SIEDEMSET wydarzen b2b"), self.idx.find("siedemset wydarzeń B2B"))
        self.assertEqual(self.idx.find("kroju marki"), self.idx.find("Kroju, marki."))

    def test_nth_occurrence_and_after(self):
        first = self.idx.find("test napisów")
        second = self.idx.find("test napisów", nth=2)
        self.assertLess(first[0], second[0])
        self.assertEqual(self.idx.find("test napisów", after=first[0] + 0.1), second)
        self.assertEqual(self.idx.find("test napisów", after=first[0]), first)  # „nie wcześniej niż” włącznie

    def test_small_spelling_differences_are_tolerated_only_in_longer_words(self):
        self.assertEqual(self.idx.find("wydarzenie")[0], self.idx.find("wydarzeń")[0])
        with self.assertRaises(PlanError):
            self.idx.find("tes")  # krótkie słowa muszą być dokładne

    def test_not_found_names_the_closest_fragment(self):
        with self.assertRaises(PlanError) as cm:
            self.idx.find("siedemset wydarzen B2C")
        msg = str(cm.exception)
        self.assertIn("Nie znalazłem w mowie frazy „siedemset wydarzen B2C”", msg)
        self.assertIn("Najbliższy fragment: „siedemset wydarzeń B2B,”", msg)
        self.assertIn(".slowa.json", msg)

    def test_missing_nth_says_how_many_there_are(self):
        with self.assertRaises(PlanError) as cm:
            self.idx.find("test napisów", nth=3)
        self.assertIn("wystąpienie nr 3, jest 2", str(cm.exception))

    def test_empty_phrase_and_bad_nth(self):
        for phrase, nth in (("  ", 1), ("—", 1), ("test", 0)):
            with self.assertRaises(PlanError):
                self.idx.find(phrase, nth)


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.words = spoken()
        self.idx = anchors.SpokenIndex(self.words)

    def t(self, phrase, **kw):
        return self.idx.find(phrase, **kw)

    def test_plan_without_phrases_is_returned_untouched(self):
        raw = {"elements": [{"type": "title", "at": 3, "dur": 2, "text": "x"}], "effects": [{"type": "blur", "at": "4.5", "dur": 1}]}
        self.assertFalse(anchors.has_phrases(raw))
        self.assertIs(anchors.resolve(raw, []), raw)  # numeryczne napisy „4.5” to liczby, nie frazy

    def test_at_shift_and_until(self):
        raw = {"elements": [{"type": "badge", "text": "x", "at": "siedemset wydarzeń", "shift": -0.3, "until": "B2B", "until_shift": 0.2}]}
        before = copy.deepcopy(raw)
        out = anchors.resolve(raw, self.words)
        self.assertEqual(raw, before)  # oryginał nietknięty
        e = out["elements"][0]
        start, end = self.t("siedemset wydarzeń")[0], self.t("B2B")[1]
        self.assertAlmostEqual(e["at"], start - 0.3, places=3)
        self.assertAlmostEqual(e["dur"], end + 0.2 - (start - 0.3), places=3)
        self.assertEqual(e["said"], "siedemset wydarzeń")

    def test_nth_picks_the_later_occurrence(self):
        out = anchors.resolve({"elements": [{"type": "x", "at": "test napisów", "nth": 2}]}, self.words)
        self.assertAlmostEqual(out["elements"][0]["at"], self.t("test napisów", nth=2)[0], places=3)

    def test_until_is_searched_after_the_start(self):
        raw = {"elements": [{"type": "x", "at": "kroju marki", "until": "test napisów"}]}
        e = anchors.resolve(raw, self.words)["elements"][0]
        self.assertAlmostEqual(e["at"] + e["dur"], self.t("test napisów", after=e["at"])[1], places=3)

    def test_until_before_the_start_is_an_error(self):
        raw = {"elements": [{"type": "x", "at": "siedemset", "until": "marki"}]}
        with self.assertRaises(PlanError) as cm:
            anchors.resolve(raw, self.words)
        self.assertIn("Element 1 (x)", str(cm.exception))
        raw = {"elements": [{"type": "x", "until": "marki", "dur": 2}]}
        with self.assertRaises(PlanError) as cm:
            anchors.resolve(raw, self.words)
        self.assertIn("until wymaga", str(cm.exception))

    def test_local_times_are_relative_to_the_start(self):
        raw = {"elements": [{"type": "steps", "at": "kroju marki", "dur": 8, "focus_at": "siedemset", "count_at": "B2B",
                             "active": ["dzisiaj", 3.5, "znowu"]}]}
        e = anchors.resolve(raw, self.words)["elements"][0]
        base = e["at"]
        self.assertAlmostEqual(e["focus_at"], self.t("siedemset")[0] - base, places=3)
        self.assertAlmostEqual(e["count_at"], self.t("B2B")[0] - base, places=3)
        self.assertAlmostEqual(e["active"][0], self.t("dzisiaj")[0] - base, places=3)
        self.assertEqual(e["active"][1], 3.5)
        self.assertAlmostEqual(e["active"][2], self.t("znowu")[0] - base, places=3)

    def test_active_steps_never_go_backwards(self):
        raw = {"elements": [{"type": "steps", "at": 0, "dur": 20, "active": ["test napisów", "test napisów"]}]}
        a = anchors.resolve(raw, self.words)["elements"][0]["active"]
        self.assertLess(a[0], a[1])  # powtórzona fraza oznacza kolejne wystąpienie, nie to samo

    def test_effects_take_phrases_too(self):
        raw = {"effects": [{"type": "blur", "at": "potem", "until": "znowu"}]}
        f = anchors.resolve(raw, self.words)["effects"][0]
        self.assertAlmostEqual(f["at"], self.t("potem")[0], places=3)
        self.assertAlmostEqual(f["dur"], self.t("znowu")[1] - self.t("potem")[0], places=3)

    def test_errors_point_at_the_element(self):
        raw = {"elements": [{"type": "title", "at": 1}, {"type": "badge", "at": "nie padło w mowie"}]}
        with self.assertRaises(PlanError) as cm:
            anchors.resolve(raw, self.words)
        self.assertTrue(str(cm.exception).startswith("Element 2 (badge): Nie znalazłem"))
        with self.assertRaises(PlanError) as cm:
            anchors.resolve({"effects": [{"type": "blur", "at": "nie padło", "dur": 1}]}, self.words)
        self.assertTrue(str(cm.exception).startswith("Efekt 1 (blur):"))

    def test_phrases_without_a_transcript_are_refused_with_a_hint(self):
        with self.assertRaises(PlanError) as cm:
            anchors.resolve({"elements": [{"type": "x", "at": "coś"}]}, [])
        self.assertIn("--words", str(cm.exception))

    def test_has_phrases_looks_at_every_time_field(self):
        base = {"type": "x", "at": 1, "dur": 2}
        for extra in ({"at": "fraza"}, {"until": "fraza"}, {"focus_at": "fraza"}, {"count_at": "fraza"}, {"active": [1, "fraza"]}):
            self.assertTrue(anchors.has_phrases({"elements": [dict(base, **extra)]}), extra)
        self.assertFalse(anchors.has_phrases({"elements": [dict(base, active=[1, 2], focus_at=1.5)]}))
        self.assertFalse(anchors.has_phrases([]))
        self.assertFalse(anchors.has_phrases({"elements": ["nie-słownik"]}))


class PlanFileTests(unittest.TestCase):
    def test_plan_needs_words_reads_the_file(self):
        from reelcut import graphics

        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "z.json").write_text(json.dumps({"elements": [{"type": "badge", "text": "x", "at": "fraza"}]}), encoding="utf-8")
            (d / "bez.json").write_text(json.dumps({"elements": [{"type": "badge", "text": "x", "at": 1}]}), encoding="utf-8")
            (d / "zly.json").write_text("{nie json", encoding="utf-8")
            self.assertTrue(graphics.plan_needs_words(d / "z.json"))
            self.assertFalse(graphics.plan_needs_words(d / "bez.json"))
            self.assertFalse(graphics.plan_needs_words(d / "zly.json"))  # błąd zgłosi dopiero budowa planu
            self.assertFalse(graphics.plan_needs_words(d / "nie_ma.json"))


class WordsFileTests(unittest.TestCase):
    def test_load_words_reports_a_bad_file_in_plain_words(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "a.json").write_text("{nie json", encoding="utf-8")
            (d / "b.json").write_text(json.dumps([{"tekst": "brak pól"}]), encoding="utf-8")
            (d / "c.json").write_text(json.dumps({"words": [{"w": "ok", "start": 0.1, "end": 0.4}]}), encoding="utf-8")
            for name in ("a.json", "b.json", "nie_ma.json"):
                with self.assertRaises(captions.WordsFileError) as cm:
                    captions.load_words(d / name)
                self.assertIn("Nie da się wczytać transkrypcji", str(cm.exception))
                self.assertIn('"start"', str(cm.exception))
            self.assertEqual([w.text for w in captions.load_words(d / "c.json")], ["ok"])


if __name__ == "__main__":
    unittest.main()
