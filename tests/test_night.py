import unittest

from blazettino import kpi
from tests.helpers import KILL_A, KILL_B, WIPE_C, build_night, fake_comments, players


class AssembleTest(unittest.TestCase):
    def test_one_boss_report_per_attempt_in_order(self):
        n = build_night()
        self.assertEqual([b.attempt for b in n.bosses], [KILL_A, KILL_B, WIPE_C])
        self.assertEqual(len(n.players), 20)
        self.assertTrue(all(p.fights == 3 for p in n.players))

    def test_llm_is_called_once_per_boss_plus_once_for_the_night(self):
        seen = []

        def spy(players, cfg, context=""):
            seen.append(context)
            return fake_comments(players, cfg, context)

        build_night(comments_fn=spy)
        self.assertEqual(len(seen), 4)
        self.assertEqual(sum("KILL in" in c for c in seen), 2)
        self.assertEqual(sum("WIPE (miglior tentativo" in c for c in seen), 1)
        self.assertEqual(sum("Serata completa" in c for c in seen), 1)

    def test_every_boss_and_the_night_have_their_own_comments(self):
        n = build_night()
        self.assertEqual(len(n.comments), 20)
        self.assertTrue(all(len(b.comments) == 20 for b in n.bosses))

    def test_night_grade_is_the_mean_of_the_boss_grades(self):
        n = build_night()
        for name in ("Sleãze", "Karabosca", "Madreh"):
            boss_grades = [kpi.grade(next(p for p in b.players if p.name == name)) for b in n.bosses]
            night_player = next(p for p in n.players if p.name == name)
            self.assertEqual(kpi.grade(night_player), round(sum(boss_grades) / 3 * 2) / 2)

    def test_excluded_players_vanish_everywhere(self):
        n = build_night({"exclude": ["Sleãze"]})
        everyone = [*n.players, *(p for b in n.bosses for p in b.players)]
        self.assertFalse(any(p.name == "Sleãze" for p in everyone))
        self.assertNotIn("Sleãze", n.comments)

    def test_death_boss_tags_exist_only_in_the_merged_night(self):
        n = build_night()
        merged = next(p for p in n.players if p.name == "Nzotten")
        self.assertEqual({d.boss for d in merged.deaths}, {"Boss Uno", "Boss Due", "Boss Tre"})
        single = next(p for p in n.bosses[0].players if p.name == "Nzotten")
        self.assertEqual({d.boss for d in single.deaths}, {""})

    def test_max_missed_comes_from_config_with_default_one(self):
        self.assertEqual(build_night().max_missed, 1)
        self.assertEqual(build_night({"max_missed_fights": 2}).max_missed, 2)

    def test_player_missing_from_a_boss_is_merged_with_fewer_fights(self):
        short = [p for p in players(21) if p.name != "Madreh"]
        n = build_night(tries=[(KILL_A, players(21)), (KILL_B, short)])
        self.assertEqual(next(p for p in n.players if p.name == "Madreh").fights, 1)


if __name__ == "__main__":
    unittest.main()
