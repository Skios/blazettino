import json
import unittest
import urllib.error
from unittest import mock
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

    def test_fight_events_noted_on_a_player_reach_the_prompt(self):
        import dataclasses
        p = dataclasses.replace(self.players[0], notes=("Falling Debris: 10 colpi, 3.9M",))
        self.assertIn("Falling Debris: 10 colpi", comment.facts(p, self.players))
        self.assertNotIn("Fatti del fight", comment.facts(self.players[1], self.players))

    def test_award_comments_ride_in_the_same_reply_under_premio_keys(self):
        from blazettino import awards
        aw = [awards.Award("anfetamina", "Premio Fatto di Anfetamina", self.players[0].name, "99% di tempo attivo (mediana del raid 80%)")]
        ctx = comment.awards_context(aw)
        self.assertIn("premio:anfetamina", ctx)
        self.assertIn(self.players[0].name, ctx)
        names = [p.name for p in self.players]
        reply = json.loads(fake_reply(names))
        reply["premio:anfetamina"] = {"titolo": "IL FRULLATORE", "commento": "Mai fermo."}
        reply["premio:inventato"] = {"titolo": "X", "commento": "Y"}
        out = comment.comments(self.players, {}, generate=lambda p, c: json.dumps(reply), context=ctx)
        self.assertEqual(out["premio:anfetamina"].text, "Mai fermo.")
        self.assertEqual(comment.awards_context([]), "")

    def test_each_player_line_carries_the_tone_of_its_grade_band(self):
        top = max(self.players, key=kpi.grade)
        low = min(self.players, key=kpi.grade)
        self.assertIn(f"Tono: {comment.tone(kpi.grade(top))}", comment.facts(top, self.players))
        self.assertIn(f"Tono: {comment.tone(kpi.grade(low))}", comment.facts(low, self.players))
        self.assertNotEqual(comment.tone(9.5), comment.tone(2))

    def test_tone_bands_include_their_floor_and_can_be_overridden_from_config(self):
        self.assertEqual(comment.tone(8.5), comment.TONES[0][1])
        self.assertEqual(comment.tone(8.4), comment.TONES[1][1])
        prompt = comment.build_prompt(self.players, tones=[[0, "TONO UNICO"]])
        self.assertIn("Tono: TONO UNICO", prompt)

    def test_bad_tones_in_config_fall_back_and_unsorted_bands_still_work(self):
        self.assertEqual(comment.tone(5, []), comment.tone(5))
        self.assertEqual(comment.tone(5, ["x"]), comment.tone(5))
        self.assertEqual(comment.tone(9, [[0, "basso"], [8.5, "alto"]]), "alto")

    def test_system_prompt_can_be_replaced_from_config(self):
        seen = []
        comment.comments(self.players, {"system": "SISTEMA NOSTRO"}, generate=lambda p, c: seen.append(p) or "{}")
        self.assertTrue(seen[0].startswith("SISTEMA NOSTRO"))

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

    def test_overloaded_backend_is_retried_then_succeeds(self):
        names = [p.name for p in self.players]
        calls = []

        def flaky(prompt, cfg):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None)
            return fake_reply(names)

        with mock.patch.object(comment, "RETRY_WAIT_S", (0, 0, 0)):
            out = comment.comments(self.players, {}, generate=flaky)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(out), 20)

    def test_a_read_timeout_is_retried_like_a_busy_backend(self):
        names = [p.name for p in self.players]
        calls = []

        def slow(prompt, cfg):
            calls.append(1)
            if len(calls) < 2:
                raise TimeoutError("The read operation timed out")
            return fake_reply(names)

        with mock.patch.object(comment, "RETRY_WAIT_S", (0, 0)):
            self.assertEqual(len(comment.comments(self.players, {}, generate=slow)), 20)
        self.assertEqual(len(calls), 2)

    def test_overloaded_backend_gives_up_after_the_retries(self):
        def down(prompt, cfg):
            raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)

        with mock.patch.object(comment, "RETRY_WAIT_S", (0, 0)), self.assertLogs("blazettino.comment", level="WARNING"):
            self.assertEqual(comment.comments(self.players, {}, generate=down), {})

    def test_invalid_json_returns_empty(self):
        with self.assertLogs("blazettino.comment", level="WARNING"):
            self.assertEqual(comment.comments(self.players, {}, generate=lambda p, c: "non è json"), {})

    def test_unknown_names_in_reply_are_ignored(self):
        reply = json.dumps({"Pippo": {"titolo": "X", "commento": "Y"}})
        self.assertEqual(comment.comments(self.players, {}, generate=lambda p, c: reply), {})


class GeminiKeysTest(unittest.TestCase):
    CFG = {"backend": "gemini", "model": "m"}
    REPLY = {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    def run_with(self, post):
        keys = {"geminiKey": "A", "geminiKey2": "B", "geminiKey3": "C"}
        with mock.patch.object(comment, "env_prefix", lambda p: [keys[k] for k in sorted(keys)]), \
                mock.patch.object(comment, "_post", post):
            return comment.call_backend("p", self.CFG)

    def test_next_key_is_used_when_one_is_out_of_quota(self):
        used = []

        def post(url, body, headers):
            used.append(headers["x-goog-api-key"])
            if headers["x-goog-api-key"] != "C":
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
            return self.REPLY

        self.assertEqual(self.run_with(post), "{}")
        self.assertEqual(used, ["A", "B", "C"])

    def test_error_surfaces_when_every_key_is_exhausted(self):
        def post(url, body, headers):
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)

        with self.assertRaises(urllib.error.HTTPError):
            self.run_with(post)

    def test_other_errors_do_not_burn_the_remaining_keys(self):
        used = []

        def post(url, body, headers):
            used.append(1)
            raise urllib.error.HTTPError(url, 400, "Bad Request", {}, None)

        with self.assertRaises(urllib.error.HTTPError):
            self.run_with(post)
        self.assertEqual(len(used), 1)


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
