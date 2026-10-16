import dataclasses
import unittest

from blazettino import kpi, report
from blazettino.comment import Comment
from tests.test_kpi import load


def fight(boss):
    players = kpi.load_fight(load("summary"), load("taken"), load("rank_dps"), load("rank_hps"))
    return [
        dataclasses.replace(p, deaths=tuple(dataclasses.replace(d, boss=boss) for d in p.deaths))
        for p in players
    ]


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.once = {p.name: p for p in fight("A")}
        self.twice = {p.name: p for p in kpi.merge([fight("A"), fight("B")])}

    def test_sums_totals_and_keeps_every_death(self):
        a, b = self.once["Nzotten"], self.twice["Nzotten"]
        self.assertEqual(b.damage, 2 * a.damage)
        self.assertEqual(len(b.deaths), 2 * len(a.deaths))
        self.assertEqual({d.boss for d in b.deaths}, {"A", "B"})

    def test_rates_and_parses_are_averaged_not_summed(self):
        a, b = self.once["Ghàdyus"], self.twice["Ghàdyus"]
        self.assertAlmostEqual(b.dps, a.dps)
        self.assertEqual(b.dps_parse, a.dps_parse)

    def test_night_grade_is_mean_of_fight_grades_not_death_total(self):
        self.assertEqual(kpi.grade(self.twice["Sleãze"]), kpi.grade(self.once["Sleãze"]))

    def test_player_missing_from_a_fight_is_still_merged(self):
        partial = [p for p in fight("B") if p.name != "Madreh"]
        merged = {p.name: p for p in kpi.merge([fight("A"), partial])}
        self.assertEqual(merged["Madreh"].damage, self.once["Madreh"].damage)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.players = kpi.merge([fight("Ula'tek")])
        self.text = report.render(
            "The Venomous Abyss", "2026-10-15", ["Ula'tek"], self.players,
            {"Sleãze": Comment("CALAMITA", "Due morti evitabili.")},
        )

    def test_has_podium_with_mvp_and_lvp(self):
        self.assertIn("MVP", self.text)
        self.assertIn("LVP", self.text)
        self.assertRegex(self.text, r"LVP.*Sleãze")

    def test_includes_comment_and_numbers_for_commented_player(self):
        self.assertIn("CALAMITA", self.text)
        self.assertIn("Due morti evitabili.", self.text)
        self.assertIn("Caustic Waves", self.text)  # morti elencate

    def test_player_without_comment_still_listed_with_grade(self):
        self.assertIn("Madreh", self.text)

    def test_lists_roles_in_sections(self):
        for h in ("Tank", "Healer", "DPS"):
            self.assertIn(h, self.text)


class AttendanceTest(unittest.TestCase):
    def setUp(self):
        missing = [p for p in fight("C") if p.name != "Sleãze"]
        self.players = kpi.merge([fight("A"), fight("B"), missing])  # Sleãze present in 2 of 3

    def render(self, max_missed):
        return report.render("T", "d", ["A", "B", "C"], self.players, {}, max_missed=max_missed)

    def test_fights_attended_are_counted(self):
        by = {p.name: p for p in self.players}
        self.assertEqual((by["Sleãze"].fights, by["Ghàdyus"].fights), (2, 3))

    def test_missing_more_than_allowed_blocks_podium_but_keeps_listing(self):
        text = self.render(max_missed=0)
        self.assertNotRegex(text, r"LVP.*Sleãze")
        self.assertIn("**Sleãze**", text)

    def test_missing_within_allowance_can_still_be_lvp(self):
        self.assertRegex(self.render(max_missed=1), r"LVP.*Sleãze")


if __name__ == "__main__":
    unittest.main()
