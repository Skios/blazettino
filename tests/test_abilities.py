import json
import tempfile
import unittest
from pathlib import Path

from blazettino import abilities

TRANSITIONS = [{"id": 1, "startTime": 1000}, {"id": 2, "startTime": 5000}]
ACTORS = {1: {"name": "Boss", "type": "NPC"}, 2: {"name": "Add", "type": "NPC"}, 3: {"name": "Tank", "type": "Player"},
          4: {"name": "Totem", "type": "NPC", "petOwner": 3}}
SPELLS = {10: "Slam", 11: "Debris", 12: "Egg Burst"}


def cast(t, src, spell, kind="cast"):
    return {"timestamp": t, "type": kind, "sourceID": src, "abilityGameID": spell}


def hit(t, src, spell):
    return {"timestamp": t, "type": "damage", "sourceID": src, "targetID": 3, "abilityGameID": spell, "amount": 5}


def collect(casts=(), damage=()):
    return abilities.collect(TRANSITIONS, list(casts), list(damage), ACTORS, SPELLS)


class CollectTest(unittest.TestCase):
    def test_casts_and_hits_are_counted_per_ability_source_and_phase(self):
        got = collect(casts=[cast(1500, 1, 10), cast(1600, 1, 10, "begincast"), cast(6000, 2, 10)],
                      damage=[hit(2000, 1, 11), hit(2100, 1, 11), hit(6000, 2, 12)])
        self.assertEqual(got[10]["phases"], {1: {"casts": 1, "hits": 0}, 2: {"casts": 1, "hits": 0}})  # begincast ignored
        self.assertEqual(got[10]["sources"], ["Add", "Boss"])
        self.assertEqual(got[11]["phases"], {1: {"casts": 0, "hits": 2}})
        self.assertEqual(got[12]["sources"], ["Add"])

    def test_only_enemy_npcs_count_not_players_nor_pets(self):
        got = collect(casts=[cast(1500, 3, 10), cast(1500, 4, 11)], damage=[hit(1500, 3, 12), hit(1500, 99, 12)])
        self.assertEqual(got, {})

    def test_events_before_the_first_transition_go_to_the_first_phase(self):
        self.assertEqual(collect(casts=[cast(10, 1, 10)])[10]["phases"], {1: {"casts": 1, "hits": 0}})


class MergeTest(unittest.TestCase):
    def merged(self, data=None, key="A#1", **kw):
        return abilities.merge(data or {}, 3492, "Boss", {1: "Stage One", 2: "Stage Two"}, key, collect(**kw), SPELLS)

    def test_new_ability_gets_empty_hand_fields_and_phase_names(self):
        d = self.merged(casts=[cast(1500, 1, 10)])
        a = d["abilities"]["10"]
        self.assertEqual((a["en"], a["it"], a["metric"], a["note"]), ("Slam", "", "", ""))
        self.assertEqual(d["phases"], {"1": "Stage One", "2": "Stage Two"})
        self.assertEqual(a["phases"]["1"], {"casts": 1, "hits": 0, "fights": 1})

    def test_second_run_adds_counts_and_keeps_hand_edits(self):
        d = self.merged(casts=[cast(1500, 1, 10)])
        d["abilities"]["10"].update(it="Schianto", metric="avoid", note="si schiva", custom="x")
        d = self.merged(d, "B#2", casts=[cast(1500, 1, 10), cast(1600, 1, 10)])
        a = d["abilities"]["10"]
        self.assertEqual((a["it"], a["metric"], a["note"], a["custom"]), ("Schianto", "avoid", "si schiva", "x"))
        self.assertEqual(a["phases"]["1"], {"casts": 3, "hits": 0, "fights": 2})

    def test_the_same_fight_twice_changes_nothing(self):
        d = self.merged(casts=[cast(1500, 1, 10)])
        self.assertEqual(self.merged(d, casts=[cast(1500, 1, 10)]), d)


class FileTest(unittest.TestCase):
    def test_roundtrip_and_corrupt_file_stops_with_a_message(self):
        with tempfile.TemporaryDirectory() as t:
            folder = Path(t)
            self.assertEqual(abilities.load(folder, 3492), {})
            abilities.save(folder, 3492, {"name": "Boss"})
            self.assertEqual(abilities.load(folder, 3492), {"name": "Boss"})
            (folder / "3492.json").write_text("{oops")
            with self.assertRaises(SystemExit):
                abilities.load(folder, 3492)
            self.assertEqual([p.name for p in folder.iterdir()], ["3492.json"])


class TableTest(unittest.TestCase):
    def folder(self, tmp, **fields):
        folder = Path(tmp)
        data = {"abilities": {"1292403": {"en": "Caustic Waves", "it": "Onde Caustiche", "metric": "avoid", "note": "", **fields}}}
        abilities.save(folder, 3492, data)
        return folder

    def test_table_is_keyed_by_id_and_lowercase_name_and_skips_untouched_abilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = abilities.table(self.folder(tmp))
            self.assertEqual(t[1292403], t["caustic waves"])
            self.assertEqual(t["caustic waves"]["it"], "Onde Caustiche")
            self.assertEqual(abilities.table(self.folder(tmp, metric="", it="")), {})
        self.assertEqual(abilities.table(Path("/nonexistent")), {})

    def test_unknown_metric_stops_with_the_file_and_the_valid_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as cm:
                abilities.table(self.folder(tmp, metric="avod"))
        self.assertIn("avod", str(cm.exception))
        self.assertIn("avoid", str(cm.exception))


class TagTest(unittest.TestCase):
    def test_deaths_get_the_text_of_the_metric_of_their_killing_ability(self):
        from tests.helpers import players
        ps = players(21)
        table = {"caustic waves": {"metric": "avoid", "it": "", "note": ""}}
        labelled = [d for p in abilities.tag_deaths(ps, table) for d in p.deaths if d.label]
        self.assertTrue(labelled)
        self.assertTrue(all(d.ability == "Caustic Waves" and d.label == abilities.METRIC_TEXT["avoid"] for d in labelled))
        self.assertEqual(abilities.tag_deaths(ps, {}), ps)


if __name__ == "__main__":
    unittest.main()
