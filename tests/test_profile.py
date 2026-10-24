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


class PerformanceTest(unittest.TestCase):
    def test_active_seconds_by_role_and_casts_per_player(self):
        from unittest import mock

        def fake_report(code, body):
            if "fights(" in body:
                return {"fights": [{"startTime": 0, "endTime": 600_000}]}
            if "masterData" in body:
                return {"masterData": {"actors": [{"id": 1, "name": "Tank", "type": "Player"}, {"id": 2, "name": "Heal", "type": "Player"},
                                                  {"id": 9, "name": "Pet", "type": "Pet"}]}}
            entries = {"DamageDone": [{"name": "Tank", "activeTime": 500_000}, {"name": "Heal", "activeTime": 10_000}],
                       "Healing": [{"name": "Heal", "activeTime": 570_000}]}
            kind = "DamageDone" if "DamageDone" in body else "Healing"
            return {"table": {"data": {"entries": entries[kind]}}}

        casts = [{"type": "cast", "sourceID": 1}] * 3 + [{"type": "begincast", "sourceID": 1}, {"type": "cast", "sourceID": 2}, {"type": "cast", "sourceID": 9}]
        with mock.patch.object(profile.wcl, "report", fake_report), mock.patch.object(profile.wcl, "events", return_value=casts):
            got = profile.performance("CODE", 5)
        self.assertEqual(got["Tank"], {"damage_s": 500.0, "healing_s": 0.0, "casts": 3})
        self.assertEqual(got["Heal"], {"damage_s": 10.0, "healing_s": 570.0, "casts": 1})
        self.assertNotIn("Pet", got)

    def test_stats_go_on_the_players_by_role(self):
        from unittest import mock
        from blazettino import kpi
        from tests.test_kpi import load
        ps = kpi.load_fight(load("summary"), load("taken"), load("rank_dps"), load("rank_hps"))
        healer = next(p for p in ps if p.role == "healer")
        dps = next(p for p in ps if p.role == "dps")
        perf = {healer.name: {"damage_s": 5.0, "healing_s": 500.0, "casts": 40}, dps.name: {"damage_s": 400.0, "healing_s": 3.0, "casts": 90}}
        with mock.patch.object(profile, "performance", return_value=perf):
            out = {p.name: p for p in profile.with_performance(ps, "CODE", 21)}
        self.assertEqual((out[healer.name].active_s, out[healer.name].casts), (500.0, 40))
        self.assertEqual(out[dps.name].active_s, 400.0)
        other = next(p for p in ps if p.name not in perf)
        self.assertIsNone(out[other.name].active_s)


def tick(t_ms, target, hp, amount, max_hp=1000, absorbed=0):
    """A hit on `target` leaving it at `hp`, with the resources WarcraftLogs adds."""
    return {"timestamp": 1000 + t_ms, "type": "damage", "targetID": target, "abilityGameID": 10, "amount": amount, "absorbed": absorbed,
            "hitPoints": hp, "maxHitPoints": max_hp, "resourceActor": 2}


def dead(t_ms, target, spell=11):
    return {"timestamp": 1000 + t_ms, "type": "death", "targetID": target, "killingAbilityGameID": spell}


class SlowDeathTest(unittest.TestCase):
    def run_it(self, damage, deaths):
        return profile.slow_deaths(damage, deaths, NAMES, SPELLS)

    def test_time_runs_from_the_last_time_at_full_health_to_the_death(self):
        dmg = [tick(0, 2, 900, 100), tick(5000, 2, 800, 100), tick(30000, 2, 950, 50), tick(40000, 2, 500, 450), tick(60000, 2, 100, 400)]
        # at 5 s: 100/1000 lost, healed back; at 30 s the hit finds the player at 1000 (950+50): that is the last full health
        out = self.run_it(dmg, [dead(61000, 2)])
        d = out["Dps"]
        self.assertEqual((d.ttd_s, d.hits), (31.0, 3))
        self.assertEqual(d.biggest_pct, 45.0)
        self.assertEqual(d.spell, "Stone Venom")

    def test_hits_before_a_previous_death_do_not_count(self):
        dmg = [tick(0, 2, 900, 100), tick(5000, 2, 400, 500), tick(20000, 2, 500, 100)]
        out = self.run_it(dmg, [dead(6000, 2), dead(30000, 2)])
        self.assertEqual(out["Dps"].ttd_s, 6.0)  # the second death never saw full health again: it must not borrow the first moment

    def test_mass_deaths_late_deaths_and_players_never_seen_full_are_left_out(self):
        crowd = {i: f"P{i}" for i in range(1, 12)}
        dmg = [tick(0, i, 500, 500) for i in crowd]
        out = profile.slow_deaths(dmg, [dead(20000, i) for i in crowd], crowd, SPELLS)
        self.assertEqual(out, {})  # everyone died together: nobody was forgotten
        self.assertEqual(self.run_it([tick(0, 2, 500, 100)], [dead(30000, 2)]), {})  # first seen already hurt: no full-health moment

    def test_damage_and_healing_between_full_health_and_death_are_summed(self):
        dmg = [tick(0, 2, 900, 100), tick(5000, 2, 700, 200), tick(10000, 2, 100, 600)]
        heals = [{"timestamp": 1000 + 3000, "targetID": 2, "amount": 150}, {"timestamp": 1000 + 8000, "targetID": 2, "amount": 50},
                 {"timestamp": 1000 + 8000, "targetID": 3, "amount": 999}, {"timestamp": 1000 + 20000, "targetID": 2, "amount": 777},
                 {"timestamp": 1000 + 9000, "type": "absorbed", "targetID": 2}, {"timestamp": 1000 + 9000, "type": "removebuff"}]  # events without an amount or a target
        d = profile.slow_deaths(dmg, [dead(11000, 2)], NAMES, SPELLS, heals)["Dps"]
        self.assertEqual((d.damage, d.healing), (900, 200))  # only target 2, only inside the window

    def test_hot_share_and_tank_busters_in_the_window(self):
        dmg = [tick(0, 2, 900, 100), tick(5000, 2, 700, 200), {**tick(8000, 2, 100, 600), "abilityGameID": 12}]
        heals = [{"timestamp": 1000 + 3000, "targetID": 2, "amount": 150, "tick": True}, {"timestamp": 1000 + 6000, "targetID": 2, "amount": 50}]
        d = profile.slow_deaths(dmg, [dead(9000, 2)], NAMES, {**SPELLS, 12: "Mauling Blow"}, heals, frozenset({"mauling blow"}))["Dps"]
        self.assertEqual((d.healing, d.hot_share, d.busters), (200, 0.75, 1))

    def test_the_slowest_of_several_deaths_is_kept_and_unknown_targets_are_ignored(self):
        dmg = [tick(0, 2, 900, 100), tick(10000, 2, 100, 900), tick(50000, 2, 950, 50), tick(80000, 2, 100, 850), tick(0, 99, 900, 100)]
        out = self.run_it(dmg, [dead(11000, 2), dead(81000, 2), dead(5000, 99)])
        self.assertEqual(list(out), ["Dps"])
        self.assertEqual(out["Dps"].ttd_s, 31.0)


if __name__ == "__main__":
    unittest.main()
