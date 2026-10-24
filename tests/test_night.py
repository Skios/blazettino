import unittest

from blazettino import kpi, night
from tests.helpers import KILL_A, KILL_B, WIPE_C, build_boss, build_night, fake_comments, players


class AssembleTest(unittest.TestCase):
    def test_one_boss_report_per_attempt_in_order(self):
        n = build_night()
        self.assertEqual([b.attempt for b in n.bosses], [KILL_A, KILL_B, WIPE_C])
        self.assertEqual(len(n.players), 20)
        self.assertTrue(all(p.fights == 3 for p in n.players))

    def test_llm_is_called_once_per_boss_plus_once_for_the_night(self):
        seen = []

        def spy(players, cfg, context=""):
            seen.append(context)
            return fake_comments(players, cfg, context)

        build_night(comments_fn=spy)
        self.assertEqual(len(seen), 4)
        self.assertEqual(sum("KILL in" in c for c in seen), 2)
        self.assertEqual(sum("WIPE (miglior tentativo" in c for c in seen), 1)
        self.assertEqual(sum("Serata completa" in c for c in seen), 1)

    def test_a_boss_gets_its_awards_and_the_llm_hears_about_them(self):
        from dataclasses import replace
        from blazettino import awards
        seen = []
        stats = {p.name: replace(p, active_s=480, casts=300, deaths=(), dps_bracket=None, hps_bracket=None) for p in players(21)}
        stats["Karabosca"] = replace(stats["Karabosca"], active_s=594)

        def spy(ps, cfg, context=""):
            seen.append(context)
            return fake_comments(ps, cfg, context)

        n = build_night(tries=[(KILL_B, list(stats.values()))], comments_fn=spy)
        self.assertEqual([a.key for a in n.bosses[0].awards], ["anfetamina"])
        self.assertTrue(any("premio:anfetamina" in c for c in seen))

    def test_every_boss_and_the_night_have_their_own_comments(self):
        n = build_night()
        self.assertEqual(len(n.comments), 20)
        self.assertTrue(all(len(b.comments) == 20 for b in n.bosses))

    def test_night_grade_is_the_mean_of_the_boss_grades(self):
        n = build_night()
        for name in ("Sleãze", "Karabosca", "Madreh"):
            boss_grades = [kpi.grade(next(p for p in b.players if p.name == name)) for b in n.bosses]
            night_player = next(p for p in n.players if p.name == name)
            self.assertEqual(kpi.grade(night_player), round(sum(boss_grades) / 3 * 2) / 2)

    def test_excluded_players_vanish_everywhere(self):
        n = build_night({"exclude": ["Sleãze"]})
        everyone = [*n.players, *(p for b in n.bosses for p in b.players)]
        self.assertFalse(any(p.name == "Sleãze" for p in everyone))
        self.assertNotIn("Sleãze", n.comments)

    def test_death_boss_tags_exist_only_in_the_merged_night(self):
        n = build_night()
        merged = next(p for p in n.players if p.name == "Nzotten")
        self.assertEqual({d.boss for d in merged.deaths}, {"Boss Uno", "Boss Due", "Boss Tre"})
        single = next(p for p in n.bosses[0].players if p.name == "Nzotten")
        self.assertEqual({d.boss for d in single.deaths}, {""})

    def test_max_missed_comes_from_config_with_default_one(self):
        self.assertEqual(build_night().max_missed, 1)
        self.assertEqual(build_night({"max_missed_fights": 2}).max_missed, 2)

    def test_player_missing_from_a_boss_is_merged_with_fewer_fights(self):
        short = [p for p in players(21) if p.name != "Madreh"]
        n = build_night(tries=[(KILL_A, players(21)), (KILL_B, short)])
        self.assertEqual(next(p for p in n.players if p.name == "Madreh").fights, 1)


class CleanTitleTest(unittest.TestCase):
    def test_keeps_only_the_raid_name_before_a_glued_date(self):
        self.assertEqual(night.clean_title("The Venomous Abyss2026-10-1926Kith'ix (Kill, 12 Pulls)"), "The Venomous Abyss")

    def test_plain_titles_are_untouched(self):
        self.assertEqual(night.clean_title("The Venomous Abyss"), "The Venomous Abyss")
        self.assertEqual(night.clean_title("2026-10-19 raid"), "2026-10-19 raid")  # nothing before the date: keep it


class BossTest(unittest.TestCase):
    def test_single_boss_is_a_night_of_one_boss_with_its_own_title(self):
        b = build_boss(WIPE_C)
        self.assertEqual(b.kind, "Boss")
        self.assertEqual([x.attempt for x in b.bosses], [WIPE_C])
        self.assertIn("Boss Tre", b.title)
        self.assertIn("15/10", b.title)
        self.assertEqual(len(b.players), 20)

    def test_one_llm_call_and_the_boss_comments_are_the_page_comments(self):
        seen = []

        def spy(players, cfg, context=""):
            seen.append(context)
            return fake_comments(players, cfg, context)

        b = build_boss(KILL_A, spy)
        self.assertEqual(len(seen), 1)
        self.assertIn("KILL in", seen[0])
        self.assertEqual(b.comments, b.bosses[0].comments)

    def test_excluded_players_vanish(self):
        b = night.assemble_boss("T", "2026-10-15", KILL_A, players(21), {"exclude": ["Sleãze"]}, fake_comments)
        self.assertFalse(any(p.name == "Sleãze" for p in b.players))


class WeekTest(unittest.TestCase):
    def setUp(self):
        self.seen = []

        def spy(players, cfg, context=""):
            self.seen.append(context)
            return fake_comments(players, cfg, context)

        nights = [build_night(date="2026-10-07"), build_night(date="2026-10-08")]
        self.week = night.assemble_week(nights, {}, spy)

    def test_week_is_a_night_starting_on_the_first_date_with_every_boss_of_every_night(self):
        self.assertEqual(self.week.kind, "Settimana")
        self.assertEqual(self.week.date, "2026-10-07")
        self.assertEqual(len(self.week.bosses), 6)
        self.assertIn("07/10", self.week.title)
        self.assertIn("08/10", self.week.title)

    def test_boss_tabs_carry_the_day_so_repeated_bosses_stay_distinct(self):
        names = [b.attempt.name for b in self.week.bosses]
        self.assertEqual(len(set(names)), 6)
        self.assertIn("Boss Uno (07/10)", names)
        self.assertIn("Boss Uno (08/10)", names)

    def test_week_grade_is_the_mean_over_all_boss_grades_and_fights_add_up(self):
        p = next(p for p in self.week.players if p.name == "Karabosca")
        grades = [kpi.grade(next(q for q in b.players if q.name == "Karabosca")) for b in self.week.bosses]
        self.assertEqual(p.fights, 6)
        self.assertEqual(kpi.grade(p), round(sum(grades) / 6 * 2) / 2)

    def test_death_tags_name_the_boss_and_the_day(self):
        p = next(p for p in self.week.players if p.name == "Nzotten")
        self.assertIn("Boss Uno (07/10)", {d.boss for d in p.deaths})

    def test_one_extra_llm_call_for_the_whole_week(self):
        self.assertEqual(len(self.seen), 1)
        self.assertIn("Settimana", self.seen[0])
        self.assertEqual(len(self.week.comments), 20)

    def test_allowed_absences_scale_with_the_number_of_nights(self):
        self.assertEqual(self.week.max_missed, 2)


if __name__ == "__main__":
    unittest.main()
