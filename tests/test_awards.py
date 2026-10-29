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
        self.assertIn("infliggere danni", got["anfetamina"].value)
        self.assertIn("50%", got["bradipo"].value)

    def test_activity_is_measured_on_the_time_the_boss_could_be_targeted(self):
        ps = with_stats({"Karabosca": (150, 300), "Sleãze": (300, 300)})
        ps = [replace(p, targetable_s=200) if p.name == "Karabosca" else p for p in ps]  # 150 s of damage in 200 s of targetable boss
        got = self.by_key(ps)
        self.assertEqual(got["bradipo"].winner, "Sleãze")  # 50% of 600 s; Karabosca 75% of 200 s is not the lowest
        self.assertIn("boss targettabile", got["bradipo"].value)

    def test_most_and_fewest_casts_per_minute(self):
        got = self.by_key(with_stats({"Yorda": (480, 700), "Madreh": (480, 100)}))
        self.assertEqual((got["spaccatastiere"].winner, got["tastiera"].winner), ("Yorda", "Madreh"))
        self.assertIn("70 azioni al minuto", got["spaccatastiere"].value)

    def test_short_fights_and_players_dead_early_do_not_count(self):
        self.assertEqual(awards.compute(with_stats({"Yorda": (594, 300)}), 60), [])
        ps = with_stats({"Yorda": (50, 10)})
        dead = [replace(p, deaths=(kpi.Death(20, "Test", False),)) if p.name == "Yorda" else p for p in ps]
        self.assertNotIn("Yorda", [a.winner for a in awards.compute(dead, 600)])  # Yorda died at 20 s: too little to judge

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

    def test_the_closest_to_full_and_to_zero_activity_win_even_by_a_small_margin(self):
        got = self.by_key(with_stats({"Yorda": (485, 300)}))
        self.assertEqual(got["anfetamina"].winner, "Yorda")
        self.assertNotEqual(got["bradipo"].winner, "Yorda")

    def test_too_few_players_with_data_means_no_prize(self):
        self.assertEqual(awards.compute(with_stats({})[:2], 600), [])

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

    def test_a_tank_needs_damage_twice_the_healing_mostly_from_hots_and_no_time_at_all(self):
        ps = with_stats({})
        tank = next(p for p in ps if p.role == "tank")

        def with_tank(damage, healing, hot=0.8, ttd=4.0, busters=0):
            sd = kpi.SlowDeath(ttd, 9, 8.0, "Stone Venom", damage, healing, hot, busters)
            return [replace(p, slowest_death=sd if p is tank else None) for p in ps]

        got = self.by_key(with_tank(5_000_000, 2_000_000, busters=2))
        self.assertEqual(got["dimenticato"].winner, tank.name)
        self.assertIn("5.0M", got["dimenticato"].value)
        self.assertIn("80% heal nel tempo", got["dimenticato"].value)
        self.assertIn("2 tank buster", got["dimenticato"].value)
        self.assertNotIn("dimenticato", self.by_key(with_tank(3_000_000, 2_000_000)))  # 1.5 : 1, the healers kept up
        self.assertNotIn("dimenticato", self.by_key(with_tank(5_000_000, 2_000_000, hot=0.2)))  # big direct heals did arrive
        self.assertNotIn("dimenticato", self.by_key(with_tank(5_000_000, 0, hot=0.0)))  # no healing at all: a burst, not a forgotten tank

    def test_nineteen_seconds_count_as_twenty_for_dps_and_healers(self):
        ps = with_stats({})
        dps = next(p for p in ps if p.role == "dps")
        for ttd, given in ((19.776, True), (19.1, True), (19.0, False), (18.9, False)):
            sd = kpi.SlowDeath(ttd, 9, 8.0, "Stone Venom")
            self.assertEqual("dimenticato" in self.by_key([replace(p, slowest_death=sd if p is dps else None) for p in ps]), given, ttd)

    def test_a_dps_needs_twenty_seconds_not_the_tank_rule(self):
        ps = with_stats({})
        dps = next(p for p in ps if p.role == "dps")
        sd = kpi.SlowDeath(15.0, 9, 8.0, "Stone Venom", 9_000_000, 1_000_000, 1.0)
        self.assertNotIn("dimenticato", self.by_key([replace(p, slowest_death=sd if p is dps else None) for p in ps]))

    def test_scillata_goes_to_the_highest_item_level_with_the_lowest_parse_inside_the_30_percent(self):
        ps = with_stats({})
        a, b, c, d = [p for p in ps if p.role == "dps"][:4]
        mk = lambda p, ilvl, parse: replace(p, ilvl=ilvl, dps_bracket=parse, hps_bracket=parse)
        ps = [mk(p, *{a.name: (300, 3), b.name: (300, 100), c.name: (320, 20), d.name: (310, 31)}.get(p.name, (310, 60))) for p in ps]
        got = self.by_key(ps)["scillata"]
        self.assertEqual(got.winner, a.name)  # 300 / 3 = 100 beats 320 / 20 = 16
        self.assertIn("parse 3", got.value)

    def test_a_healer_is_judged_on_the_mean_of_healing_and_damage_parse(self):
        ps = with_stats({})
        healer = next(p for p in ps if p.role == "healer")
        base = [replace(p, dps_bracket=60, hps_bracket=60) for p in ps]
        weak_healer_strong_dps = [replace(p, dps_bracket=93, hps_bracket=18, ilvl=325) if p is healer or p.name == healer.name else p for p in base]
        self.assertNotIn("scillata", self.by_key(weak_healer_strong_dps))  # (18 + 93) / 2 = 55: played damage instead of healing, not a disaster
        weak_both = [replace(p, dps_bracket=10, hps_bracket=20, ilvl=325) if p.name == healer.name else p for p in base]
        got = self.by_key(weak_both)["scillata"]
        self.assertEqual(got.winner, healer.name)
        self.assertIn("parse 15", got.value)

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
