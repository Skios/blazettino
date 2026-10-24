import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blazettino import comment, config, kpi, roster
from tests.helpers import build_night, players

BOOK = {"Karabosca": {"gender": "f", "alts": ["Madreh"]}, "Feroce": {"gender": "m"}}


class RosterTest(unittest.TestCase):
    def test_canon_maps_an_alt_to_its_main_and_leaves_others_alone(self):
        self.assertEqual(roster.canon("Madreh", BOOK), "Karabosca")
        self.assertEqual(roster.canon("Feroce", BOOK), "Feroce")
        self.assertEqual(roster.canon("Sleãze", BOOK), "Sleãze")

    def test_apply_renames_the_alt_and_sets_gender(self):
        out = {p.name: p for p in roster.apply([p for p in players(21) if p.name != "Karabosca"], BOOK)}
        self.assertIn("Karabosca", out)
        self.assertNotIn("Madreh", out)
        self.assertEqual((out["Karabosca"].gender, out["Feroce"].gender, out["Sleãze"].gender), ("f", "m", ""))

    def test_main_and_alt_in_the_same_fight_stay_two_players(self):
        names = [p.name for p in roster.apply(players(21), BOOK)]
        self.assertIn("Madreh", names)
        self.assertIn("Karabosca", names)

    def test_night_counts_the_alt_as_its_main_and_exclude_covers_both(self):
        n = build_night({"players": BOOK, "exclude": ["Karabosca"]})
        names = {p.name for p in n.players}
        self.assertFalse({"Karabosca", "Madreh"} & names)

    def test_gender_reaches_the_prompt_only_when_known(self):
        ps = roster.apply(players(21), BOOK)
        feroce = next(p for p in ps if p.name == "Feroce")
        sleaze = next(p for p in ps if p.name == "Sleãze")
        self.assertIn("genere m", comment.facts(feroce, ps))
        self.assertNotIn("genere", comment.facts(sleaze, ps))


class ConfigTest(unittest.TestCase):
    def test_players_json_is_loaded_into_the_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "players.json").write_text(json.dumps(BOOK))
            with mock.patch.object(config, "ROOT", Path(tmp)):
                self.assertEqual(config.load_config()["players"], BOOK)
                (Path(tmp) / "players.json").unlink()
                self.assertNotIn("players", config.load_config())


if __name__ == "__main__":
    unittest.main()
