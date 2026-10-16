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


if __name__ == "__main__":
    unittest.main()
