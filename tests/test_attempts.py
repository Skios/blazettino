import json
import unittest
from pathlib import Path

from blazettino import attempts

FIGHTS = json.loads((Path(__file__).parent / "fixtures" / "report_fights.json").read_text())["data"]


def only_wipes(names):
    return [f for f in FIGHTS if not (f["name"] in names and f["kill"])]


def fight(id, diff, kill, pct=0.0, name="Kith'ix"):
    return {"id": id, "name": name, "encounterID": 9, "difficulty": diff, "kill": kill,
            "fightPercentage": pct, "startTime": id * 1000, "endTime": id * 1000 + 200_000}


class DifficultyTest(unittest.TestCase):
    def test_same_boss_on_two_difficulties_gives_two_attempts_labelled(self):
        got = attempts.best_tries([fight(1, 3, True), fight(5, 4, False, 91.0), fight(19, 4, True)])
        self.assertEqual([(a.name, a.id, a.kill) for a in got], [("Kith'ix (Normal)", 1, True), ("Kith'ix (HC)", 19, True)])
        self.assertEqual([a.slug for a in got], ["kithix-normal", "kithix-hc"])

    def test_a_single_difficulty_keeps_the_plain_boss_name(self):
        got = attempts.best_tries([fight(5, 4, False, 91.0), fight(19, 4, True)])
        self.assertEqual([a.name for a in got], ["Kith'ix"])

    def test_each_difficulty_picks_its_own_best_try(self):
        got = attempts.best_tries([fight(1, 3, False, 50.0), fight(2, 3, False, 20.0), fight(3, 4, False, 70.0)])
        self.assertEqual([(a.id, a.pct) for a in got], [(2, 20.0), (3, 70.0)])


class PullsTest(unittest.TestCase):
    def test_attempt_keeps_encounter_difficulty_and_every_pull(self):
        a = attempts.best_tries([fight(5, 4, False, 91.0), fight(7, 4, False, 40.5), fight(19, 4, True)])[0]
        self.assertEqual((a.encounter, a.difficulty), (9, 4))
        self.assertEqual([(p.pct, p.kill) for p in a.pulls], [(91.0, False), (40.5, False), (0.0, True)])
        self.assertEqual(a.pulls[0].seconds, 200)


class LastTryTest(unittest.TestCase):
    wipes = [fight(1, 4, False, 20.0), fight(2, 4, False, 60.0)]

    def test_last_mode_takes_the_final_pull_instead_of_the_best_wipe(self):
        self.assertEqual(attempts.best_tries(self.wipes)[0].id, 1)
        self.assertEqual(attempts.best_tries(self.wipes, "last")[0].id, 2)

    def test_a_kill_wins_in_both_modes(self):
        fights = self.wipes + [fight(3, 4, True)]
        self.assertEqual(attempts.best_tries(fights, "last")[0].id, 3)


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
