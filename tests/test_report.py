import re
import unittest

from blazettino import report, tips
from tests.helpers import KILL_A, KILL_B, WIPE_C, build_boss, build_night, players


class GlobalTest(unittest.TestCase):
    def setUp(self):
        self.night = build_night()
        self.text = report.render_global(self.night)

    def test_is_marked_global(self):
        self.assertIn("GLOBAL", self.text.splitlines()[0])

    def test_has_podium_with_mvp_and_lvp(self):
        self.assertRegex(self.text, r"MVP — \S+")
        self.assertRegex(self.text, r"LVP — \S+")

    def test_grade_table_has_a_column_per_boss_and_the_night(self):
        header = next(l for l in self.text.splitlines() if l.startswith("| Giocatore"))
        for col in ("Boss Uno", "Boss Due", "Boss Tre (WIPE)", "Serata"):
            self.assertIn(col, header)

    def test_lists_roles_in_sections(self):
        for h in ("Tank", "Healer", "DPS"):
            self.assertIn(f"## {h}", self.text)

    def test_commented_player_has_title_comment_and_boss_tagged_deaths(self):
        self.assertIn("TITOLO MADREH", self.text)
        self.assertIn("Commento per Madreh.", self.text)
        self.assertIn("Boss Uno 7:04 Caustic Waves", self.text)  # Nzotten, tagged with the boss


class BossTest(unittest.TestCase):
    def setUp(self):
        self.night = build_night()

    def test_kill_report(self):
        text = report.render_boss(self.night, self.night.bosses[0])
        self.assertIn("Boss Uno — KILL", text)
        self.assertNotIn(tips.NO_KILL, text)
        self.assertIn("parse", text)
        self.assertRegex(text, r"MVP — \S+")
        self.assertRegex(text, r"LVP — \S+")

    def test_wipe_report_says_no_kill_no_ranking_with_a_tip(self):
        text = report.render_boss(self.night, self.night.bosses[2])
        self.assertIn("Boss Tre — WIPE", text)
        self.assertIn("16.54%", text)
        self.assertIn(tips.NO_KILL, text)
        self.assertTrue(any(t in text for t in tips.TIPS))

    def test_wipe_report_never_claims_a_parse(self):
        text = report.render_boss(self.night, self.night.bosses[2])
        self.assertNotIn("parse", text)
        self.assertIn("pos.", text)

    def test_boss_reports_do_not_repeat_the_boss_in_each_death(self):
        text = report.render_boss(self.night, self.night.bosses[0])
        self.assertNotIn("Boss Uno 7:04", text)
        self.assertIn("7:04 Caustic Waves", text)


class FilesTest(unittest.TestCase):
    def test_one_file_per_boss_marked_kill_or_wipe_plus_global(self):
        self.assertEqual(
            set(report.files(build_night())),
            {"global.md", "boss-uno_kill.md", "boss-due_kill.md", "boss-tre_wipe.md"},
        )


class AttendanceTest(unittest.TestCase):
    def night(self, max_missed):
        tries = [(KILL_A, players(21)), (KILL_B, players(21)), (WIPE_C, [p for p in players(20) if p.name != "Sleãze"])]
        return build_night({"max_missed_fights": max_missed}, tries)

    def test_missing_more_than_allowed_blocks_podium_but_keeps_listing(self):
        text = report.render_global(self.night(0))
        self.assertNotRegex(text, r"LVP — Sleãze")
        self.assertIn("**Sleãze**", text)
        self.assertIn("poche presenze", text)

    def test_missing_within_allowance_can_still_be_lvp(self):
        self.assertRegex(report.render_global(self.night(1)), r"LVP — Sleãze")


class BossFilesTest(unittest.TestCase):
    def test_single_boss_writes_only_its_own_file(self):
        self.assertEqual(set(report.files(build_boss(WIPE_C))), {"boss-tre_wipe.md"})


if __name__ == "__main__":
    unittest.main()
