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

    def test_unknown_actor_or_spell_does_not_crash(self):
        p = build(damage=[hit(0, 99, 777, 5)])
        self.assertEqual(p["damage"]["777"]["players"]["99"]["dmg"], 5)


if __name__ == "__main__":
    unittest.main()
