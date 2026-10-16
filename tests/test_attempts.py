import json
import unittest
from pathlib import Path

from blazettino import attempts

FIGHTS = json.loads((Path(__file__).parent / "fixtures" / "report_fights.json").read_text())["data"]


def only_wipes(names):
    return [f for f in FIGHTS if not (f["name"] in names and f["kill"])]


class BestTriesTest(unittest.TestCase):
    def test_kill_is_chosen_when_present_in_order_of_first_attempt(self):
        got = attempts.best_tries(FIGHTS)
        self.assertEqual([(a.name, a.id, a.kill) for a in got], [
            ("Nek'zali the Soulcoiler", 1, True),
            ("The Coiled Altar", 17, True),
            ("Ula'tek", 21, True),
        ])

    def test_without_a_kill_the_wipe_closest_to_a_kill_wins(self):
        got = {a.name: a for a in attempts.best_tries(only_wipes({"The Coiled Altar", "Ula'tek"}))}
        self.assertEqual((got["The Coiled Altar"].id, got["The Coiled Altar"].pct), (15, 0.53))
        self.assertEqual((got["Ula'tek"].id, got["Ula'tek"].kill), (19, False))

    def test_trash_and_unknown_encounters_are_ignored(self):
        names = {a.name for a in attempts.best_tries(FIGHTS)}
        self.assertNotIn("Gorefang the Reaver", names)

    def test_duration_is_in_seconds(self):
        ulatek = attempts.best_tries(FIGHTS)[-1]
        self.assertEqual(ulatek.seconds, 602)

    def test_slug_is_filename_safe(self):
        by = {a.name: a.slug for a in attempts.best_tries(FIGHTS)}
        self.assertEqual(by["The Coiled Altar"], "the-coiled-altar")
        self.assertEqual(by["Ula'tek"], "ulatek")

    def test_no_boss_fights_gives_empty_list(self):
        self.assertEqual(attempts.best_tries([f for f in FIGHTS if not f["encounterID"]]), [])


if __name__ == "__main__":
    unittest.main()
