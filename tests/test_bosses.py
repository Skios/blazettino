import json
import tempfile
import unittest
from pathlib import Path

from blazettino import bosses
from blazettino.attempts import Attempt, Pull


def kill(code, seconds, boss=3492, diff=4):
    return Attempt(1, "Ula'tek", True, 0.0, seconds, boss, diff, code, (Pull(0.0, seconds, True),))


def reports(*kills):
    return {code: {"date": date, "difficulties": {"4": {"kill_s": s}}} for date, code, s in kills}


class LabelsTest(unittest.TestCase):
    def test_first_kill_shows_only_its_time(self):
        self.assertEqual(bosses.labels(reports(("2026-10-14", "A", 600)), "4"), {"A": ""})

    def test_each_new_best_is_a_record_until_beaten(self):
        r = reports(("2026-10-14", "A", 600), ("2026-10-21", "B", 560))
        self.assertEqual(bosses.labels(r, "4"), {"A": "", "B": "NEW RECORD"})
        r = {**r, **reports(("2026-10-28", "C", 540))}
        self.assertEqual(bosses.labels(r, "4"), {"A": "", "B": "+0:20", "C": "NEW RECORD"})

    def test_slower_kill_shows_the_gap_and_a_tie_is_not_a_new_record(self):
        r = reports(("2026-10-14", "A", 600), ("2026-10-21", "B", 640), ("2026-10-28", "C", 600))
        self.assertEqual(bosses.labels(r, "4"), {"A": "", "B": "+0:40", "C": "pari record"})

    def test_difficulties_do_not_mix_and_wipes_are_ignored(self):
        r = {"A": {"date": "2026-10-14", "difficulties": {"4": {"kill_s": None}, "3": {"kill_s": 500}}}}
        self.assertEqual(bosses.labels(r, "4"), {})
        self.assertEqual(bosses.labels(r, "3"), {"A": ""})


class AddReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.site = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def read(self):
        return json.loads((self.site / "data" / "bosses" / "3492.json").read_text())

    def test_writes_report_pulls_labels_and_record(self):
        bosses.add_report(self.site, "2026-10-14", [kill("A", 600)])
        bosses.add_report(self.site, "2026-10-21", [kill("B", 560)])
        d = self.read()
        self.assertEqual(d["name"], "Ula'tek")
        self.assertEqual(d["reports"]["A"]["difficulties"]["4"]["pulls"], [{"pct": 0.0, "s": 600, "kill": True}])
        self.assertEqual(d["labels"], {"A": {"4": ""}, "B": {"4": "NEW RECORD"}})
        self.assertEqual(d["records"], {"4": {"kill_s": 560, "code": "B"}})

    def test_same_log_twice_changes_nothing(self):
        bosses.add_report(self.site, "2026-10-14", [kill("A", 600)])
        first = (self.site / "data" / "bosses" / "3492.json").read_text()
        bosses.add_report(self.site, "2026-10-14", [kill("A", 600)])
        self.assertEqual((self.site / "data" / "bosses" / "3492.json").read_text(), first)

    def test_corrupt_boss_file_stops_with_a_clear_message_and_no_tmp_left(self):
        folder = self.site / "data" / "bosses"
        folder.mkdir(parents=True)
        (folder / "3492.json").write_text('{"name": "Ula')
        with self.assertRaises(SystemExit):
            bosses.add_report(self.site, "2026-10-14", [kill("A", 600)])
        self.assertEqual([p.name for p in folder.iterdir()], ["3492.json"])

    def test_attempts_without_log_code_or_encounter_are_skipped(self):
        bosses.add_report(self.site, "2026-10-14", [Attempt(1, "Boss", True, 0.0, 60)])
        self.assertFalse((self.site / "data").exists())


if __name__ == "__main__":
    unittest.main()
