import json
import tempfile
import unittest
from pathlib import Path

from blazettino import kpi, mythictrap

def page(boss) -> str:
    data = {"props": {"pageProps": {"boss": boss}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'

BOSS = {"name": "Ula'tek", "bossPhases": [
    {"phaseName": "Phase 1", "bossAbilities": [{"spellID": 1292403, "name": "Caustic Waves", "category": "Dodge waves"}],
     "bossAbilitiesWithVideos": [{"spellID": 7, "name": "Circling Prey", "category": "Move out"}]},
    {"phaseName": "Phase 2", "bossAbilities": [{"spellID": 1292403, "name": "Caustic Waves", "category": "Dodge waves"},
                                              {"spellID": None, "name": "no id", "category": "x"}], "bossAbilitiesWithVideos": []},
]}


class ParseTest(unittest.TestCase):
    def test_abilities_are_deduplicated_by_spell_and_keep_their_phases(self):
        got = mythictrap.parse_boss(page(BOSS))
        self.assertEqual(got["name"], "Ula'tek")
        by = {a["spell"]: a for a in got["abilities"]}
        self.assertEqual(set(by), {1292403, 7})  # the entry without a spell id is dropped
        self.assertEqual(by[1292403]["phases"], ["Phase 1", "Phase 2"])
        self.assertEqual(by[7]["label"], "Move out")

    def test_no_guide_text_is_kept(self):
        boss = {**BOSS, "bossPhases": [{"phaseName": "P", "bossAbilities": [
            {"spellID": 1, "name": "A", "category": "c", "descriptionHTML": "TESTO LORO"}], "bossAbilitiesWithVideos": []}]}
        self.assertNotIn("TESTO LORO", json.dumps(mythictrap.parse_boss(page(boss))))

    def test_a_changed_page_format_fails_with_a_clear_message(self):
        for html in ("<html>niente</html>", page({"name": "x"}), page({"name": "x", "bossPhases": None})):
            with self.assertRaisesRegex(ValueError, "MythicTrap"):
                mythictrap.parse_boss(html)


class RaidTest(unittest.TestCase):
    def fetch(self, url):
        if url.endswith("/venomous-abyss"):
            return '<a href="/en/venomous-abyss/ulatek"></a><a href="/en/aberrus/kazzara"></a><a href="/en/venomous-abyss/ulatek"></a>'
        return page(BOSS)

    def test_boss_links_of_the_raid_only_without_repeats(self):
        self.assertEqual(mythictrap.boss_slugs(self.fetch("/venomous-abyss"), "venomous-abyss"), ["ulatek"])

    def test_raid_file_round_trips_into_spell_labels(self):
        raid = mythictrap.build_raid("venomous-abyss", self.fetch, pause=0)
        with tempfile.TemporaryDirectory() as tmp:
            mythictrap.save(raid, Path(tmp))
            self.assertEqual(mythictrap.labels(Path(tmp)), {1292403: "Dodge waves", 7: "Move out", "caustic waves": "Dodge waves", "circling prey": "Move out"})
        self.assertEqual(mythictrap.labels(Path("/nonexistent")), {})

    def test_raid_without_bosses_fails(self):
        with self.assertRaises(ValueError):
            mythictrap.build_raid("x", lambda url: "<html></html>", pause=0)


class TagTest(unittest.TestCase):
    def test_deaths_get_the_label_of_their_killing_ability(self):
        from tests.helpers import players
        ps = players(21)
        tagged = mythictrap.tag_deaths(ps, {1292403: "Dodge waves"})
        labelled = [d for p in tagged for d in p.deaths if d.label]
        self.assertTrue(labelled)
        self.assertTrue(all(d.ability == "Caustic Waves" for d in labelled))
        self.assertEqual(mythictrap.tag_deaths(ps, {}), ps)

    def test_a_death_without_a_matching_id_is_labelled_by_ability_name(self):
        from tests.helpers import players
        tagged = mythictrap.tag_deaths(players(21), {"caustic waves": "Dodge waves"})
        self.assertTrue(any(d.label == "Dodge waves" for p in tagged for d in p.deaths))


if __name__ == "__main__":
    unittest.main()
