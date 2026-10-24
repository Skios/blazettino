import json
import unittest
from pathlib import Path

from blazettino import kpi

FIX = Path(__file__).parent / "fixtures"

# Voti della pagella di esempio (fight 21, Ula'tek) scritta a mano: target di calibrazione.
EXAMPLE_GRADES = {
    "Ghàdyus": 8.5, "Ulfgaar": 7.5, "Karabosca": 9.5, "Erebòr": 8.5, "Nellob": 6.5,
    "Fardina": 5.5, "Madreh": 4.0, "Itherodan": 9.5, "Jaegeer": 9.0, "Hashirama": 5.0,
    "Ekuså": 6.5, "Yorda": 8.5, "Dàrya": 5.5, "Feroce": 9.0, "Gelsomino": 6.5,
    "Nzotten": 5.5, "Stormrager": 7.0, "Rhaegòn": 5.0, "Pashanda": 4.5, "Sleãze": 2.0,
}
MAX_MEAN_ABS_ERROR = 1.0


def load(name):
    return json.loads((FIX / f"{name}_21.json").read_text())


class KpiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.players = kpi.load_fight(
            load("summary"), load("taken"), load("rank_dps"), load("rank_hps")
        )
        cls.by_name = {p.name: p for p in cls.players}

    def test_icon_id_matches_warcraftlogs_naming(self):
        self.assertEqual(self.by_name["Karabosca"].icon, "Priest-Holy")
        self.assertEqual(self.by_name["Feroce"].icon, "Hunter-BeastMastery")

    def test_returns_all_twenty_raiders(self):
        self.assertEqual(len(self.players), 20)

    def test_tank_stats_match_the_log(self):
        p = self.by_name["Ghàdyus"]
        self.assertEqual(p.role, "tank")
        self.assertAlmostEqual(p.damage / 1e6, 54.07, places=1)
        self.assertAlmostEqual(p.dps / 1e3, 89.7, places=1)
        self.assertAlmostEqual(p.taken / 1e6, 131.57, places=1)
        self.assertEqual(p.dps_parse, 54)
        self.assertEqual(p.deaths, ())

    def test_healer_uses_hps_parse_and_exposes_damage_parse(self):
        p = self.by_name["Nellob"]
        self.assertEqual(p.role, "healer")
        self.assertEqual(p.role_parse, 38)
        self.assertEqual(p.dps_parse, 91)

    def test_death_has_minute_and_ability(self):
        p = self.by_name["Nzotten"]
        first = p.deaths[0]
        self.assertEqual(first.time_s, 424)  # 7:04
        self.assertEqual(first.ability, "Caustic Waves")
        self.assertFalse(first.mass)

    def test_simultaneous_final_deaths_are_flagged_mass(self):
        self.assertTrue(self.by_name["Itherodan"].deaths[0].mass)

    def test_grades_are_in_range_and_half_points(self):
        for p in self.players:
            g = kpi.grade(p)
            self.assertTrue(1 <= g <= 10)
            self.assertEqual(g * 2, int(g * 2))

    def test_podium_picks_expected_extremes(self):
        mvp, lvp = kpi.podium(self.players)
        self.assertIn(mvp.name, {"Karabosca", "Itherodan"})
        self.assertEqual(lvp.name, "Sleãze")

    def test_grades_track_the_hand_written_example(self):
        errs = [abs(kpi.grade(self.by_name[n]) - g) for n, g in EXAMPLE_GRADES.items()]
        self.assertLessEqual(sum(errs) / len(errs), MAX_MEAN_ABS_ERROR)


class MissingEntriesTest(unittest.TestCase):
    def test_raider_absent_from_the_damage_table_is_loaded_with_zero_damage(self):
        summary = load("summary")
        summary["data"]["damageDone"] = [e for e in summary["data"]["damageDone"] if e["name"] != "Stormrager"]
        players = kpi.load_fight(summary, load("taken"), load("rank_dps"), load("rank_hps"))
        p = next(p for p in players if p.name == "Stormrager")
        self.assertEqual((p.damage, p.dps), (0, 0))
        self.assertEqual(len(players), 20)

    def test_damage_taken_entry_without_reduction_means_no_mitigation(self):
        taken = load("taken")
        for e in taken["data"]["entries"]:
            if e["name"] == "Stormrager":
                del e["totalReduced"]
        players = kpi.load_fight(load("summary"), taken, load("rank_dps"), load("rank_hps"))
        self.assertEqual(next(p for p in players if p.name == "Stormrager").mitigation, 0)


class UnknownKillerTest(unittest.TestCase):
    def test_death_without_killing_blow_is_kept_with_a_placeholder_ability(self):
        summary = load("summary")
        event = summary["data"]["deathEvents"][0]
        del event["ability"]
        players = kpi.load_fight(summary, load("taken"), load("rank_dps"), load("rank_hps"))
        deaths = next(p for p in players if p.name == event["name"]).deaths
        self.assertIn(kpi.UNKNOWN_ABILITY, {d.ability for d in deaths})


class WipeTest(unittest.TestCase):
    """A wipe has no WarcraftLogs rankings: parses become percentiles inside the raid, per role."""

    @classmethod
    def setUpClass(cls):
        def w(name):
            return json.loads((FIX / f"{name}_20.json").read_text())

        cls.players = kpi.load_fight(w("summary"), w("taken"), w("rank_dps"), w("rank_hps"))
        cls.by_name = {p.name: p for p in cls.players}

    def test_wipe_players_are_loaded_and_flagged_unranked(self):
        self.assertEqual(len(self.players), 20)
        self.assertFalse(any(p.ranked for p in self.players))

    def test_kill_players_are_flagged_ranked(self):
        kill = kpi.load_fight(load("summary"), load("taken"), load("rank_dps"), load("rank_hps"))
        self.assertTrue(all(p.ranked for p in kill))

    def test_percentiles_span_zero_to_hundred_within_each_role(self):
        for role in ("tank", "healer", "dps"):
            parses = sorted(p.dps_parse for p in self.players if p.role == role)
            self.assertEqual((parses[0], parses[-1]), (0, 100))

    def test_top_dps_of_role_gets_100_and_bottom_gets_0(self):
        dps = [p for p in self.players if p.role == "dps"]
        self.assertEqual(max(dps, key=lambda p: p.damage).dps_parse, 100)
        self.assertEqual(min(dps, key=lambda p: p.damage).dps_parse, 0)

    def test_cross_role_bonus_never_applies_without_real_parses(self):
        for p in self.players:
            with_bonus = kpi.grade(p)
            ranked_twin = kpi.grade(__import__("dataclasses").replace(p, ranked=True))
            self.assertLessEqual(with_bonus, ranked_twin)

    def test_grades_are_in_range(self):
        for p in self.players:
            self.assertTrue(1 <= kpi.grade(p) <= 10)


class BracketTest(unittest.TestCase):
    def test_item_level_bracket_parse_is_read_from_the_rankings(self):
        ps = {p.name: p for p in kpi.load_fight(load("summary"), load("taken"), load("rank_dps"), load("rank_hps"))}
        self.assertEqual(ps["Ghàdyus"].dps_bracket, 28)
        self.assertIsNotNone(ps["Ghàdyus"].hps_bracket)

    def test_wipes_have_no_bracket(self):
        from tests.helpers import players
        self.assertTrue(all(p.dps_bracket is None for p in players(20)))


if __name__ == "__main__":
    unittest.main()
