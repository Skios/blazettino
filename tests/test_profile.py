import unittest

from blazettino import profile

NAMES = {1: "Tank", 2: "Dps", 3: "Heal"}
SPELLS = {10: "Falling Debris", 11: "Stone Venom", 20: "Kick", 30: "Cleanse"}


def hit(t_ms, target, spell, amount):
    return {"timestamp": 1000 + t_ms, "type": "damage", "targetID": target, "abilityGameID": spell, "amount": amount}


def build(**kw):
    args = dict(start=1000, damage=[], deaths=[], interrupts=[], dispels=[], names=NAMES, spells=SPELLS)
    return profile.build(**{**args, **kw})


class ProfileTest(unittest.TestCase):
    def test_damage_per_ability_and_player_uses_amount_and_counts_hits(self):
        p = build(damage=[hit(5000, 1, 10, 100), hit(9000, 1, 10, 50), hit(9000, 2, 10, 70), hit(1000, 2, 11, 5)])
        debris = p["damage"]["Falling Debris"]["players"]
        self.assertEqual((debris["Tank"]["dmg"], debris["Tank"]["hits"]), (150, 2))
        self.assertEqual(debris["Dps"]["hits"], 1)
        self.assertEqual(p["damage"]["Falling Debris"]["total"], 220)
        self.assertEqual(p["damage"]["Stone Venom"]["players"]["Dps"]["dmg"], 5)

    def test_each_hit_remembers_when_and_how_many_raiders_were_already_dead(self):
        death = {"timestamp": 1000 + 4000, "targetID": 3, "killingAbilityGameID": 11}
        p = build(damage=[hit(2000, 1, 10, 1), hit(6000, 1, 10, 1)], deaths=[death])
        self.assertEqual(p["damage"]["Falling Debris"]["players"]["Tank"]["list"], [[2, 1, 0], [6, 1, 1]])

    def test_deaths_interrupts_and_dispels_name_the_player_and_the_spell(self):
        p = build(deaths=[{"timestamp": 3000, "targetID": 3, "killingAbilityGameID": 11}],
                  interrupts=[{"timestamp": 2000, "sourceID": 1, "abilityGameID": 20, "extraAbilityGameID": 11}],
                  dispels=[{"timestamp": 2500, "sourceID": 3, "abilityGameID": 30, "extraAbilityGameID": 10}])
        self.assertEqual(p["deaths"], [{"player": "Heal", "s": 2, "spell": "Stone Venom"}])
        self.assertEqual(p["interrupts"], {"Tank": [{"s": 1, "spell": "Stone Venom"}]})
        self.assertEqual(p["dispels"], {"Heal": [{"s": 1, "spell": "Falling Debris"}]})

    def test_an_interrupt_or_dispel_without_the_target_spell_does_not_crash(self):
        p = build(interrupts=[{"timestamp": 2000, "sourceID": 1, "abilityGameID": 20}], dispels=[{"timestamp": 2000, "sourceID": 3, "abilityGameID": 30}])
        self.assertEqual(p["interrupts"]["Tank"][0]["s"], 1)
        self.assertEqual(len(p["dispels"]["Heal"]), 1)

    def test_unknown_actor_or_spell_does_not_crash(self):
        p = build(damage=[hit(0, 99, 777, 5)])
        self.assertEqual(p["damage"]["777"]["players"]["99"]["dmg"], 5)


LABELS = {"falling debris": {"metric": "avoid", "it": "Macerie Cadenti", "note": ""}, "stone venom": {"metric": "", "it": "", "note": ""}}


def many(spell, per_player):
    """Hits at second 10 so nobody is dead yet: per_player = {target id: (hits, amount each)}."""
    return [hit(10000, t, spell, amt) for t, (n, amt) in per_player.items() for _ in range(n)]


class AvoidableTest(unittest.TestCase):
    def test_only_dodgeable_abilities_count_and_hits_after_the_cutoff_are_ignored(self):
        deaths = [{"timestamp": 1000 + 1000 * i, "targetID": 3, "killingAbilityGameID": 11} for i in range(2)]
        dmg = many(10, {1: (2, 100)}) + many(11, {1: (5, 100)}) + [hit(60000, 2, 10, 999)]
        prof = build(damage=dmg, deaths=deaths)
        out = profile.avoidable(prof, LABELS, cutoff=2)
        self.assertEqual(list(out), ["Falling Debris"])  # Stone Venom has no "avoid" metric
        self.assertEqual(out["Falling Debris"], {"Tank": {"dmg": 200, "hits": 2}, "Dps": {"dmg": 999, "hits": 1}})

    def test_late_hits_are_dropped_when_too_many_raiders_are_already_dead(self):
        deaths = [{"timestamp": 1000 + 1000 * i, "targetID": 3, "killingAbilityGameID": 11} for i in range(3)]
        prof = build(damage=[hit(60000, 2, 10, 999), hit(500, 1, 10, 1)], deaths=deaths)
        self.assertEqual(profile.avoidable(prof, LABELS, cutoff=2)["Falling Debris"], {"Tank": {"dmg": 1, "hits": 1}})


class NotesTest(unittest.TestCase):
    def test_a_player_taking_far_more_than_the_raid_gets_the_ability_with_a_hand_note(self):
        dmg = many(10, {1: (10, 400), 2: (1, 100), 3: (1, 100)})
        table = {"falling debris": {**LABELS["falling debris"], "note": "cade solo in fase 1"}}
        notes = profile.notes(build(damage=dmg), table)
        self.assertIn("Macerie Cadenti", notes["Tank"][0])  # the Italian name when there is one
        self.assertIn("10 colpi", notes["Tank"][0])
        self.assertIn("cade solo in fase 1", notes["Tank"][0])
        self.assertNotIn("Dps", notes)

    def test_a_oneshot_ability_is_noted_for_a_single_hit_even_without_being_an_outlier(self):
        dmg = many(10, {1: (1, 100), 2: (1, 100)})
        wave = {"falling debris": {**LABELS["falling debris"], "kind": "wave"}}
        oneshot = {"falling debris": {**LABELS["falling debris"], "kind": "oneshot"}}
        self.assertEqual(profile.notes(build(damage=dmg), wave), {})
        self.assertEqual(sorted(profile.notes(build(damage=dmg), oneshot)), ["Dps", "Tank"])

    def test_notable_interrupters_are_named_and_a_player_has_at_most_three_notes(self):
        interrupts = [{"timestamp": 1000 + 1000 * i, "sourceID": 2, "abilityGameID": 20, "extraAbilityGameID": 11} for i in range(3)]
        notes = profile.notes(build(interrupts=interrupts), LABELS)
        self.assertIn("3 interruzioni", notes["Dps"][0])
        spells = {i: f"Spell{i}" for i in range(100, 110)}
        labels = {f"spell{i}": {"metric": "avoid", "it": "", "note": ""} for i in range(100, 110)}
        dmg = [e for i in range(100, 110) for e in many(i, {1: (10, 400), 2: (1, 100), 3: (1, 100)})]
        many_notes = profile.notes(profile.build(1000, dmg, [], [], [], NAMES, spells), labels)
        self.assertEqual(len(many_notes["Tank"]), profile.MAX_NOTES)


class AnnotateTest(unittest.TestCase):
    def test_players_get_their_notes_from_the_fight_profile_and_pets_count_for_their_owner(self):
        from unittest import mock
        from blazettino import kpi
        from tests.test_kpi import load
        players = kpi.load_fight(load("summary"), load("taken"), load("rank_dps"), load("rank_hps"))
        who = players[0].name
        prof = {"damage": {"Falling Debris": {"total": 0, "players": {
            who: {"dmg": 4_000_000, "hits": 10, "list": [[10, 400_000, 0]] * 10},
            "Other": {"dmg": 100, "hits": 2, "list": [[10, 50, 0]] * 2}}}},
            "deaths": [], "interrupts": {}, "dispels": {}}
        with mock.patch.object(profile, "fight_profile", return_value=prof):
            out = profile.annotate(players, "CODE", 21, {"falling debris": {"metric": "avoid", "it": "", "note": ""}})
        self.assertIn("Falling Debris", out[0].notes[0])
        self.assertEqual(out[1].notes, ())
        self.assertEqual(out[0].name, who)


class FightProfileTest(unittest.TestCase):
    def test_pet_events_are_credited_to_the_owner_and_streams_are_fetched_once_each(self):
        from unittest import mock
        actors = [{"id": 1, "name": "Mage", "petOwner": None}, {"id": 9, "name": "Totem", "petOwner": 1}]
        calls = []

        def fake_report(code, body):
            if "masterData" in body:
                return {"masterData": {"actors": actors, "abilities": [{"gameID": 30, "name": "Cleanse"}]}}
            return {"fights": [{"startTime": 1000, "endTime": 2000}]}

        def fake_events(code, fight, start, end, kind, host="Friendlies"):
            calls.append(kind)
            return [{"timestamp": 1500, "sourceID": 9, "abilityGameID": 30, "extraAbilityGameID": 30}] if kind == "Dispels" else []

        with mock.patch.object(profile.wcl, "report", fake_report), mock.patch.object(profile.wcl, "events", fake_events):
            prof = profile.fight_profile("CODE", 21)
        self.assertEqual(list(prof["dispels"]), ["Mage"])
        self.assertEqual(sorted(calls), ["DamageTaken", "Deaths", "Dispels", "Interrupts"])


if __name__ == "__main__":
    unittest.main()
