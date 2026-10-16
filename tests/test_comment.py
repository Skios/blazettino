import json
import unittest

from blazettino import comment, kpi
from tests.test_kpi import load


def fake_reply(names):
    return json.dumps({n: {"titolo": f"TITOLO {n.upper()}", "commento": f"Commento per {n}."} for n in names})


class CommentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.players = kpi.load_fight(
            load("summary"), load("taken"), load("rank_dps"), load("rank_hps")
        )

    def test_prompt_contains_facts_for_each_player(self):
        prompt = comment.build_prompt(self.players)
        self.assertIn("Sleãze", prompt)
        self.assertIn("Caustic Waves", prompt)  # abilità della morte
        self.assertIn("8:49", prompt)  # minuto della morte
        self.assertIn("strage", prompt)  # morti di massa marcate come non colpa del singolo

    def test_excluded_players_are_not_in_prompt(self):
        prompt = comment.build_prompt(self.players, exclude={"Sleãze"})
        self.assertNotIn("Sleãze", prompt)
        self.assertIn("Madreh", prompt)

    def test_comments_maps_reply_to_players(self):
        names = [p.name for p in self.players]
        out = comment.comments(self.players, {}, generate=lambda prompt, cfg: fake_reply(names))
        self.assertEqual(out["Madreh"].title, "TITOLO MADREH")
        self.assertEqual(out["Madreh"].text, "Commento per Madreh.")

    def test_excluded_players_get_no_comment(self):
        names = [p.name for p in self.players]
        out = comment.comments(
            self.players, {"exclude": ["Madreh"]}, generate=lambda prompt, cfg: fake_reply(names)
        )
        self.assertNotIn("Madreh", out)
        self.assertIn("Sleãze", out)

    def test_backend_failure_returns_empty_without_crashing(self):
        def boom(prompt, cfg):
            raise OSError("rete giù")

        with self.assertLogs("blazettino.comment", level="WARNING"):
            self.assertEqual(comment.comments(self.players, {}, generate=boom), {})

    def test_invalid_json_returns_empty(self):
        with self.assertLogs("blazettino.comment", level="WARNING"):
            self.assertEqual(comment.comments(self.players, {}, generate=lambda p, c: "non è json"), {})

    def test_unknown_names_in_reply_are_ignored(self):
        reply = json.dumps({"Pippo": {"titolo": "X", "commento": "Y"}})
        self.assertEqual(comment.comments(self.players, {}, generate=lambda p, c: reply), {})


if __name__ == "__main__":
    unittest.main()
