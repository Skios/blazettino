import json
import unittest
from pathlib import Path

from blazettino import attempts, comment, kpi
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


class HighlightsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.players = kpi.load_fight(
            load("summary"), load("taken"), load("rank_dps"), load("rank_hps")
        )
        cls.by = {p.name: p for p in cls.players}

    def hints(self, name):
        return comment.highlights(self.by[name], self.players)

    def test_few_survivors_are_called_out(self):
        self.assertTrue(any("soli 3" in h for h in self.hints("Feroce")))

    def test_cross_role_parse_is_called_out(self):
        self.assertTrue(any("93" in h and "danni" in h for h in self.hints("Fardina")))

    def test_most_hit_of_role_is_called_out(self):
        self.assertTrue(any("piu' colpito" in h and "healer" in h for h in self.hints("Madreh")))

    def test_top_and_bottom_of_role(self):
        self.assertTrue(any("primo" in h for h in self.hints("Karabosca")))
        self.assertTrue(any("ultimo" in h for h in self.hints("Sleãze")))

    def test_prompt_includes_highlights(self):
        self.assertIn("soli 3", comment.build_prompt(self.players))


KILL = attempts.Attempt(21, "Ula'tek", True, 0.0, 602)
WIPE = attempts.Attempt(19, "Ula'tek", False, 16.54, 553)


class ContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def w(name):
            return json.loads((Path(__file__).parent / "fixtures" / f"{name}_20.json").read_text())

        cls.wipe = kpi.load_fight(w("summary"), w("taken"), w("rank_dps"), w("rank_hps"))
        cls.kill = kpi.load_fight(load("summary"), load("taken"), load("rank_dps"), load("rank_hps"))

    def test_kill_context_is_in_the_prompt(self):
        prompt = comment.build_prompt(self.kill, context=comment.attempt_context(KILL))
        self.assertIn("KILL", prompt)
        self.assertIn("10:02", prompt)

    def test_wipe_context_mentions_boss_health_and_no_ranking(self):
        text = comment.attempt_context(WIPE)
        self.assertIn("WIPE", text)
        self.assertIn("16.54%", text)
        self.assertIn("ranking", text)

    def test_unranked_facts_do_not_claim_a_parse(self):
        facts = comment.facts(self.wipe[0], self.wipe)
        self.assertNotIn("parse", facts)
        self.assertIn("posizione", facts)

    def test_ranked_facts_keep_the_parse(self):
        self.assertIn("parse", comment.facts(self.kill[0], self.kill))

    def test_no_cross_role_callout_without_real_parses(self):
        for p in self.wipe:
            self.assertFalse(any("non e' il suo ruolo" in h for h in comment.highlights(p, self.wipe)))

    def test_comments_forwards_context_to_the_prompt(self):
        seen = []
        comment.comments(self.kill, {}, generate=lambda prompt, cfg: seen.append(prompt) or "{}", context="CTX-XYZ")
        self.assertIn("CTX-XYZ", seen[0])


if __name__ == "__main__":
    unittest.main()
