import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from reelcut.planner import build_plan, describe_plan  # noqa: E402
from reelcut.template import load_template  # noqa: E402

TPL = load_template()


class PlannerTests(unittest.TestCase):
    def test_template_length_gives_identical_plan(self):
        plan = build_plan(TPL, TPL.total_frames, snap=False)
        self.assertEqual(plan.mode, "identyczny")
        self.assertEqual([s.frames for s in plan.slots], [s.frames for s in TPL.segments])
        self.assertEqual([s.tpl_index for s in plan.slots], list(range(len(TPL.segments))))
        self.assertEqual(plan.cuts(), [64, 131, 171, 200, 269, 314, 357, 434, 476, 502, 565, 612, 634, 775])

    def test_sum_always_matches_master_length(self):
        for total in range(280, 6000, 37):
            with self.subTest(total=total):
                plan = build_plan(TPL, total, snap=False)
                self.assertEqual(sum(s.frames for s in plan.slots), total)
                self.assertEqual(plan.slots[0].start, 0)
                for a, b in zip(plan.slots, plan.slots[1:]):
                    self.assertEqual(a.end, b.start)
                self.assertTrue(all(s.frames >= 15 for s in plan.slots))
                elastic = [s for s in plan.slots if s.elastic]
                self.assertEqual(len(elastic), 1)
                self.assertTrue(50 <= elastic[0].frames <= 300)

    def test_hook_and_outro_are_preserved(self):
        for total in (400, 850, 1500, 3000):
            plan = build_plan(TPL, total, snap=False)
            idx = [s.tpl_index for s in plan.slots]
            self.assertEqual(idx[:2], [0, 1])
            self.assertEqual(idx[-3:], [12, 13, 14])

    def test_longer_material_cycles_body(self):
        plan = build_plan(TPL, 1500, snap=False)
        self.assertEqual(plan.mode, "dopasowany")
        self.assertGreater(len(plan.slots), len(TPL.segments))

    def test_short_material_scales_and_warns(self):
        plan = build_plan(TPL, 200, snap=False)
        self.assertEqual(plan.mode, "skrócony")
        self.assertEqual(sum(s.frames for s in plan.slots), 200)
        self.assertTrue(plan.warnings)

    def test_tiny_material_is_single_slot(self):
        plan = build_plan(TPL, 20, snap=False)
        self.assertEqual(len(plan.slots), 1)
        self.assertEqual(plan.slots[0].frames, 20)

    def test_snap_moves_cut_to_strong_nearby_break(self):
        plan = build_plan(TPL, 850, breaks=[(64 + 6, 3.0)])
        self.assertEqual(plan.slots[1].start, 70)
        self.assertEqual(plan.slots[1].shifted, 6)
        self.assertEqual(sum(s.frames for s in plan.slots), 850)

    def test_snap_prefers_strong_over_weak_even_if_slightly_farther(self):
        plan = build_plan(TPL, 850, breaks=[(131 + 1, 1.0), (131 - 5, 3.0)])
        self.assertEqual(plan.slots[2].start, 126)

    def test_snap_ignores_breaks_outside_window(self):
        plan = build_plan(TPL, 850, breaks=[(64 + 40, 3.0)])
        self.assertEqual(plan.slots[1].start, 64)

    def test_far_strong_break_does_not_beat_staying_put(self):
        # granica zdania 0,48 s dalej nie jest warta zepsucia rytmu, gdy cięcie i tak wypada przy słowie
        plan = build_plan(TPL, 850, breaks=[(64, 1.0), (64 + 12, 3.0)])
        self.assertEqual(plan.slots[1].start, 64)

    def test_cut_inside_a_word_moves_to_nearest_weak_boundary(self):
        plan = build_plan(TPL, 850, breaks=[(64 + 5, 1.0)])
        self.assertEqual(plan.slots[1].start, 69)

    def test_slot_never_shrinks_below_sixty_percent_of_template(self):
        # ujęcie 10 ma 26 klatek; silne granice próbują je zgnieść z obu stron
        plan = build_plan(TPL, 850, breaks=[(476 + 12, 3.0), (502 - 12, 3.0), (476 + 6, 3.0), (502 - 6, 3.0)])
        s10 = plan.slots[9]
        self.assertGreaterEqual(s10.frames, int(0.6 * 26))

    def test_snap_keeps_minimum_segment_length(self):
        # dwie granice "ciągną" sąsiednie cięcia ku sobie; ujęcie nr 13 ma tylko 22 klatki
        plan = build_plan(TPL, 850, breaks=[(612 + 12, 3.0), (634 - 12, 3.0)])
        self.assertTrue(all(s.frames >= 15 for s in plan.slots))
        self.assertEqual(sum(s.frames for s in plan.slots), 850)

    def test_consecutive_a_slots_have_visibly_different_framing(self):
        for max_zoom in (1.3, 1.6, 2.0):
            plan = build_plan(TPL, 850, snap=False, max_zoom=max_zoom)
            for a, b in zip(plan.slots, plan.slots[1:]):
                if a.source == "A" and b.source == "A":
                    ratio = max(a.zoom, b.zoom) / min(a.zoom, b.zoom) - 1
                    shift = max(abs(a.fx - b.fx), abs(a.fy - b.fy)) * max(a.zoom, b.zoom)
                    self.assertTrue(ratio >= 0.10 - 1e-9 or shift >= 0.12 or max(a.zoom, b.zoom) <= max_zoom + 1e-9 and max_zoom <= 1.0,
                                    (a.index, a.zoom, b.zoom))

    def test_max_zoom_is_respected(self):
        plan = build_plan(TPL, 850, snap=False, max_zoom=1.4)
        self.assertLessEqual(max(s.zoom for s in plan.slots), 1.4 + 1e-9)

    def test_broll_marks_b_slots(self):
        with_b = build_plan(TPL, 850, snap=False, has_broll=True)
        without = build_plan(TPL, 850, snap=False, has_broll=False)
        self.assertEqual([s.source for s in with_b.slots],
                         ["B" if s.role == "B" else "A" for s in with_b.slots])
        self.assertTrue(all(s.source == "A" for s in without.slots))

    def test_fps30_keeps_durations_in_seconds(self):
        plan = build_plan(TPL, 1020, fps=30, snap=False)  # 34 s przy 30 kl./s
        self.assertEqual(sum(s.frames for s in plan.slots), 1020)
        for s, t in zip(plan.slots, TPL.segments):
            if not s.elastic:
                self.assertAlmostEqual(s.frames / 30, t.frames / 25, delta=1 / 30)

    def test_rhythm_scales_with_length_as_documented_in_styl_md(self):
        """Tabela „Długość” w STYL.md: gęstość cięć i obecność wstawek B dla różnych długości materiału."""
        for sec, lo, hi in ((18, 19.0, 21.0), (28, 22.6, 24.6), (34, 24.5, 24.9), (45, 25.7, 27.7), (60, 27.0, 29.0), (90, 27.7, 29.7)):
            with self.subTest(sec=sec):
                plan = build_plan(TPL, sec * 25, snap=False)
                per_min = (len(plan.slots) - 1) / sec * 60
                self.assertTrue(lo <= per_min <= hi, f"{per_min:.1f} cięć/min poza {lo}-{hi}")
        for sec in (12, 13, 14, 15):
            self.assertEqual({s.role for s in build_plan(TPL, sec * 25, snap=False).slots}, {"A"}, f"{sec} s")
        for sec in (16, 18, 20):
            self.assertIn("B", {s.role for s in build_plan(TPL, sec * 25, snap=False).slots}, f"{sec} s")

    def test_describe_plan_mentions_every_slot(self):
        text = describe_plan(build_plan(TPL, 850, snap=False))
        for n in range(1, 16):
            self.assertIn(f" {n:>2}  ", text)


if __name__ == "__main__":
    unittest.main()
