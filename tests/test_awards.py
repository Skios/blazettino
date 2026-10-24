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
        out.append(replace(p, deaths=(), active_s=active, casts=casts, dps_bracket=None, hps_bracket=None))
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
        died = [replace(p, deaths=(kpi.Death(300, "Test", True),), active_s=290) if p.name == "Yorda" else p for p in ps]
        self.assertEqual(self.by_key(died)["anfetamina"].winner, "Yorda")  # 290 s active in the 300 s alive = 97%

    def test_the_forgotten_is_the_slowest_death_if_it_is_slow_enough(self):
        ps = with_stats({})
        slow = kpi.SlowDeath(75.0, 14, 6.0, "Stone Venom")
        quick = kpi.SlowDeath(8.0, 2, 40.0, "Fury Unleashed")
        ps = [replace(p, slowest_death=slow if p.name == "Madreh" else quick if p.name == "Yorda" else None) for p in ps]
        got = self.by_key(ps)
        self.assertEqual(got["dimenticato"].winner, "Madreh")
        self.assertIn("75 secondi", got["dimenticato"].value)
        self.assertIn("14 colpi", got["dimenticato"].value)
        only_quick = [replace(p, slowest_death=quick if p.name == "Yorda" else None) for p in with_stats({})]
        self.assertNotIn("dimenticato", self.by_key(only_quick))  # 8 s is not a slow death: not given tonight

    def test_whoever_died_before_the_wipe_is_left_out_of_the_activity_prizes_only(self):
        ps = with_stats({"Karabosca": (594, 300), "Yorda": (594, 900)})
        early = lambda p: replace(p, deaths=(kpi.Death(500, "Test", False),))
        wipe = lambda p: replace(p, deaths=(kpi.Death(598, "Fury Unleashed", True),))
        ps = [early(p) if p.name == "Karabosca" else wipe(p) if p.name == "Yorda" else p for p in ps]
        got = self.by_key(ps)
        self.assertNotIn("Karabosca", [a.winner for a in got.values()])  # died to a mechanic at 500 s: its activity says nothing
        self.assertEqual(got["spaccatastiere"].winner, "Yorda")  # died with everybody at the wipe: still counts

    def test_a_dead_player_can_still_be_the_forgotten(self):
        slow = kpi.SlowDeath(75.0, 14, 6.0, "Stone Venom")
        ps = [replace(p, deaths=(kpi.Death(300, "Stone Venom", False),), slowest_death=slow if p.name == "Madreh" else None) for p in with_stats({})]
        self.assertEqual(self.by_key(ps)["dimenticato"].winner, "Madreh")

    def test_a_tank_is_forgotten_only_if_damage_beats_healing_two_to_one(self):
        ps = with_stats({})
        tank = next(p for p in ps if p.role == "tank")
        def with_tank(damage, healing, ttd=12.0):
            sd = kpi.SlowDeath(ttd, 9, 8.0, "Stone Venom", damage, healing)
            return [replace(p, slowest_death=sd if p is tank else None) for p in ps]
        got = self.by_key(with_tank(5_000_000, 2_000_000))
        self.assertEqual(got["dimenticato"].winner, tank.name)
        self.assertIn("5.0M", got["dimenticato"].value)
        self.assertNotIn("dimenticato", self.by_key(with_tank(3_000_000, 2_000_000)))  # 1.5 : 1, the healers kept up
        self.assertNotIn("dimenticato", self.by_key(with_tank(5_000_000, 2_000_000, ttd=8.0)))  # under 10 s

    def test_a_dps_needs_twenty_seconds_not_the_tank_rule(self):
        ps = with_stats({})
        dps = next(p for p in ps if p.role == "dps")
        sd = kpi.SlowDeath(15.0, 9, 8.0, "Stone Venom", 9_000_000, 1_000_000)
        self.assertNotIn("dimenticato", self.by_key([replace(p, slowest_death=sd if p is dps else None) for p in ps]))

    def test_scillata_goes_to_the_highest_item_level_with_the_lowest_parse_inside_the_30_percent(self):
        ps = with_stats({})
        a, b, c, d = [p for p in ps if p.role == "dps"][:4]
        mk = lambda p, ilvl, parse: replace(p, ilvl=ilvl, dps_bracket=parse, hps_bracket=parse)
        ps = [mk(p, *{a.name: (300, 3), b.name: (300, 100), c.name: (320, 20), d.name: (310, 31)}.get(p.name, (310, 60))) for p in ps]
        got = self.by_key(ps)["scillata"]
        self.assertEqual(got.winner, a.name if 300 / 3 > 320 / 20 else c.name)
        self.assertEqual(got.winner, a.name)  # 100 beats 16
        self.assertIn("parse 3", got.value)

    def test_scillata_needs_somebody_under_30_and_ranked_data(self):
        ps = with_stats({})
        fine = [replace(p, dps_bracket=60, hps_bracket=60) for p in ps]
        self.assertNotIn("scillata", self.by_key(fine))
        self.assertNotIn("scillata", self.by_key([replace(p, dps_bracket=None, hps_bracket=None) for p in ps]))
        wipe = [replace(p, dps_bracket=3, hps_bracket=3, ranked=False) for p in ps]
        self.assertNotIn("scillata", self.by_key(wipe))  # wipes have no WarcraftLogs ranking: the numbers would be made up

    def test_players_without_data_are_ignored(self):
        ps = [replace(p, active_s=None, casts=None, dps_bracket=None, hps_bracket=None) for p in players(21)]
        self.assertEqual(awards.compute(ps, 600), [])


if __name__ == "__main__":
    unittest.main()
