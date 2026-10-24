import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blazettino import memory

BOOK = {"Tore": {"alts": ["Dàrya", "Tora"]}}
SPELLS = {"falling debris": {"en": "Falling Debris", "it": "Macerie Cadenti", "metric": "avoid", "note": ""}}


def prof(hits_by_char, deaths=()):
    """A fight profile where each character took `hits` Falling Debris hits (none after the cutoff)."""
    return {"damage": {"Falling Debris": {"total": 0, "players": {
        c: {"dmg": 100 * n, "hits": n, "list": [[10, 100, 0]] * n} for c, n in hits_by_char.items() if n}}},
        "deaths": [{"player": c, "s": s, "spell": sp} for c, s, sp in deaths], "interrupts": {}, "dispels": {}}


class DbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = memory.connect(Path(self.tmp.name) / "m.db")

    def night(self, code, date, fights, enc=3492, book=BOOK):
        """fights: list of {char: hits}; every char in a dict is present in that fight."""
        for i, hits in enumerate(fights, 1):
            memory.record(self.db, code, {"id": i, "name": "Ula'tek", "encounter": enc, "kill": i == len(fights), "difficulty": 4},
                          date, list(hits), prof(hits), book)


class ClassifyTest(unittest.TestCase):
    def test_every_case_including_the_grey_zone(self):
        c = memory.classify
        self.assertEqual(c(0, 0), "")
        self.assertEqual(c(0, 2), "nuova")
        self.assertEqual(c(3, 0), "risolta")
        self.assertEqual(c(4, 1), "migliora")
        self.assertEqual(c(2, 5), "peggiora")
        self.assertEqual(c(4, 3), "invariata")  # between half and one and a half times: still failing the same
        self.assertEqual(c(4, 5), "invariata")


class RecordTest(DbCase):
    def test_alts_are_one_person_and_recording_twice_changes_nothing(self):
        self.night("A", "2026-10-14", [{"Dàrya": 2, "Tora": 1}])
        first = self.db.execute("select persona, abilita, colpi from evento").fetchall()
        self.night("A", "2026-10-14", [{"Dàrya": 2, "Tora": 1}])
        self.assertEqual(self.db.execute("select persona, abilita, colpi from evento").fetchall(), first)
        self.assertEqual(first, [("Tore", "Falling Debris", 3)])
        self.assertEqual(self.db.execute("select count(*) from presenza").fetchone()[0], 2)


class TrendTest(DbCase):
    def trend(self, date="2026-10-21", **kw):
        return memory.trend_notes(self.db, "Tore", 3492, SPELLS, date, **kw)

    def test_resolved_mechanic(self):
        self.night("A", "2026-10-07", [{"Tore": 4}, {"Tore": 2}])
        self.night("B", "2026-10-14", [{"Tore": 3}])
        self.night("C", "2026-10-21", [{"Tore": 0}, {"Tore": 0}])
        (line,) = self.trend()
        self.assertIn("Macerie Cadenti", line)
        self.assertIn("non la prende più", line)

    def test_grey_zone_still_failing_and_getting_worse_or_better(self):
        self.night("A", "2026-10-07", [{"Tore": 4}])
        self.night("B", "2026-10-14", [{"Tore": 3}])
        self.assertIn("ancora", self.trend("2026-10-14")[0])
        self.night("C", "2026-10-21", [{"Tore": 9}])
        self.assertIn("di più", self.trend()[0])
        self.night("D", "2026-10-28", [{"Tore": 1}])
        self.assertIn("meno", self.trend("2026-10-28")[0])

    def test_no_history_or_not_present_tonight_gives_nothing(self):
        self.night("A", "2026-10-14", [{"Tore": 4}])
        self.assertEqual(self.trend("2026-10-14"), [])  # first night: nothing to compare with
        self.night("B", "2026-10-21", [{"Altro": 1}])
        self.assertEqual(self.trend(), [])

    def test_only_the_last_n_nights_count(self):
        self.night("A", "2026-10-01", [{"Tore": 20}])
        self.night("B", "2026-10-14", [{"Tore": 0}])
        self.night("C", "2026-10-21", [{"Tore": 0}])
        self.assertEqual(self.trend(nights=2), [])  # the old night is out of the window: 0 -> 0
        self.assertTrue(self.trend(nights=3))

    def test_other_bosses_do_not_count_and_abilities_without_a_metric_are_ignored(self):
        self.night("A", "2026-10-07", [{"Tore": 40}], enc=1)
        self.night("B", "2026-10-14", [{"Tore": 4}])
        self.night("C", "2026-10-21", [{"Tore": 0}])
        self.assertIn("prima 4.0", self.trend()[0])  # the 40 hits of the other boss are not averaged in
        self.assertEqual(memory.trend_notes(self.db, "Tore", 3492, {}, "2026-10-21"), [])

    def test_same_death_on_consecutive_nights_is_noticed(self):
        for code, date in (("A", "2026-10-07"), ("B", "2026-10-14"), ("C", "2026-10-21")):
            memory.record(self.db, code, {"id": 1, "name": "U", "encounter": 3492, "kill": True, "difficulty": 4}, date, ["Tore"],
                          prof({"Tore": 0}, [("Tore", 100, "Caustic Waves")]), BOOK)
        self.assertTrue(any("muore" in line and "3 serate" in line for line in self.trend()))


class CollectTest(DbCase):
    def test_every_boss_pull_of_the_log_is_recorded_with_the_people_present(self):
        info = {"startTime": 1_760_400_000_000, "fights": [
            {"id": 1, "name": "Trash", "encounterID": 0, "difficulty": 4, "kill": None},
            {"id": 2, "name": "Ula'tek", "encounterID": 3492, "difficulty": 4, "kill": False},
            {"id": 3, "name": "Ula'tek", "encounterID": 3492, "difficulty": 4, "kill": True}]}
        with mock.patch.object(memory.wcl, "report", return_value=info), \
             mock.patch.object(memory.profile, "fight_profile", return_value=prof({"Dàrya": 2})), \
             mock.patch.object(memory, "present", return_value=["Dàrya", "Altro"]), \
             mock.patch.object(memory.abilities, "learn") as learn:
            self.assertEqual(memory.collect("CODE", {"players": BOOK}, self.db), 2)
        self.assertEqual(learn.call_count, 2)
        self.assertEqual(self.db.execute("select id, kill from fight order by id").fetchall(), [(2, 0), (3, 1)])
        self.assertEqual(self.db.execute("select count(*) from presenza").fetchone()[0], 4)


if __name__ == "__main__":
    unittest.main()
