import unittest
from dataclasses import replace

from blazettino import awards, kpi
from tests.helpers import players


def with_stats(stats, ps=None):
    """stats: {name: (active_s, casts)}; everyone else gets the same plain numbers (80% active, 30 APM over 600 s)."""
    ps = ps or players(21)
    out = []
    for p in ps:
        active, casts = stats.get(p.name, (480, 300))
        out.append(replace(p, deaths=(), active_s=active, casts=casts))
    return out


class AwardsTest(unittest.TestCase):
    def by_key(self, ps, duration=600):
        return {a.key: a for a in awards.compute(ps, duration)}

    def test_most_and_least_active_win_the_twin_prizes(self):
        got = self.by_key(with_stats({"Karabosca": (594, 300), "Sleãze": (300, 300)}))
        self.assertEqual((got["anfetamina"].winner, got["bradipo"].winner), ("Karabosca", "Sleãze"))
        self.assertIn("99%", got["anfetamina"].value)
        self.assertIn("50%", got["bradipo"].value)

    def test_most_and_fewest_casts_per_minute(self):
        got = self.by_key(with_stats({"Yorda": (480, 700), "Madreh": (480, 100)}))
        self.assertEqual((got["spaccatastiere"].winner, got["tastiera"].winner), ("Yorda", "Madreh"))
        self.assertIn("70 azioni al minuto", got["spaccatastiere"].value)

    def test_healers_are_compared_with_healers_not_with_the_dps(self):
        ps = with_stats({})
        healer = next(p for p in ps if p.role == "healer")
        healers = [p for p in ps if p.role == "healer"]
        tuned = [replace(p, active_s=590) if p.role == "healer" else p for p in ps]  # every healer ~98%: that is just healing
        self.assertEqual(self.by_key(tuned), {})
        tuned = [replace(p, active_s=590 if p is not healers[0] else 450) if p.role == "healer" else p for p in ps]
        self.assertEqual(self.by_key(tuned)["bradipo"].winner, healers[0].name)
        self.assertIn("healer", self.by_key(tuned)["bradipo"].value)

    def test_nobody_wins_when_nobody_stands_out(self):
        self.assertEqual(self.by_key(with_stats({"Yorda": (492, 310)})), {})  # +2 points, +3%: inside the noise

    def test_one_side_can_be_missing(self):
        got = self.by_key(with_stats({"Yorda": (594, 300)}))
        self.assertEqual(list(got), ["anfetamina"])

    def test_short_fights_and_players_dead_early_do_not_count(self):
        self.assertEqual(awards.compute(with_stats({"Yorda": (594, 300)}), 60), [])
        ps = with_stats({"Yorda": (50, 10)})
        dead = [replace(p, deaths=(kpi.Death(20, "Test", False),)) if p.name == "Yorda" else p for p in ps]
        self.assertEqual(self.by_key(dead), {})  # Yorda died at 20 s: too little to judge

    def test_active_time_is_measured_against_the_time_alive(self):
        ps = with_stats({})
        died = [replace(p, deaths=(kpi.Death(300, "Test", False),), active_s=290) if p.name == "Yorda" else p for p in ps]
        self.assertEqual(self.by_key(died)["anfetamina"].winner, "Yorda")  # 290 s active in the 300 s alive = 97%

    def test_players_without_data_are_ignored(self):
        ps = [replace(p, active_s=None, casts=None) for p in players(21)]
        self.assertEqual(awards.compute(ps, 600), [])


if __name__ == "__main__":
    unittest.main()
