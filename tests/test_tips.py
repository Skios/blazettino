import unittest

from blazettino import tips


class TipsTest(unittest.TestCase):
    def test_label_for_wipes(self):
        self.assertEqual(tips.NO_KILL, "No kill no ranking!")

    def test_same_seed_gives_same_tip(self):
        self.assertEqual(tips.wipe_tip("report-19"), tips.wipe_tip("report-19"))

    def test_enough_distinct_non_empty_tips(self):
        self.assertGreaterEqual(len(set(tips.TIPS)), 8)
        self.assertTrue(all(t.strip() for t in tips.TIPS))

    def test_tip_comes_from_the_list_for_any_seed(self):
        for seed in ("a", "b", "report-12", ""):
            self.assertIn(tips.wipe_tip(seed), tips.TIPS)


if __name__ == "__main__":
    unittest.main()
