import dataclasses
import re
import unittest

from blazettino import kpi, night, page, tips
from blazettino.attempts import Pull
from blazettino.comment import Comment
from tests.helpers import KILL_A, KILL_B, WIPE_C, build_boss, build_night, fake_comments, players

URI = "data:image/jpeg;base64,AAAA"


def build(night=None, icons=None):
    return page.render_html(night or build_night(), icons)


def panels(html):
    """Panel markup, in order: global first, then one per boss."""
    return ['<div class="panel"' + part for part in html.split('<div class="panel"')[1:]]


class BossDataTest(unittest.TestCase):
    def kill(self, pulls=()):
        a = dataclasses.replace(KILL_A, encounter=3492, difficulty=4, code="AbC", pulls=pulls)
        return page.render_html(build_boss(a))

    def test_page_declares_its_kpi_version(self):
        self.assertIn(f'<meta name="blazettino-kpi" content="{kpi.KPI_VERSION}">', build())

    def test_kill_banner_has_a_placeholder_for_the_record_label(self):
        self.assertIn('<span class="rec" data-boss="3492" data-diff="4" data-code="AbC"></span>', self.kill())

    def test_no_placeholder_without_log_code(self):
        self.assertNotIn('class="rec"', build())

    def test_pulls_chart_has_one_bar_per_pull_and_only_with_several(self):
        pulls = (Pull(80.0, 100, False), Pull(35.5, 200, False), Pull(0.0, 300, True))
        html = self.kill(pulls)
        self.assertEqual(html.count("<rect"), 3)
        self.assertIn("boss al 35.5%", html)
        self.assertNotIn("<rect", self.kill((Pull(0.0, 300, True),)))


class StructureTest(unittest.TestCase):
    def test_is_a_responsive_html_document(self):
        h = build()
        self.assertTrue(h.lower().startswith("<!doctype html>"))
        self.assertIn('name="viewport"', h)

    def test_is_self_contained(self):
        h = build()
        self.assertNotRegex(h, r'(src|href)\s*=\s*"https?:')
        self.assertNotIn("@import", h)

    def test_llm_text_is_escaped(self):
        def evil(players, cfg, context=""):
            return {p.name: Comment("<b>X</b>", "<script>alert(1)</script>") for p in players}

        h = build(build_night(comments_fn=evil))
        self.assertNotIn("<script>alert(1)</script>", h)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", h)

    def test_one_tab_and_one_panel_for_the_night_and_each_boss(self):
        h = build()
        self.assertEqual(h.count('class="tab"'), 4)
        ps = panels(h)
        self.assertEqual(len(ps), 4)
        self.assertIn('id="global"', ps[0])
        self.assertIn("boss-uno", ps[1])
        self.assertIn("boss-tre", ps[3])

    def test_only_the_first_panel_is_visible_at_load(self):
        ps = panels(build())
        self.assertNotIn("hidden", ps[0].split(">")[0])
        self.assertTrue(all("hidden" in p.split(">")[0] for p in ps[1:]))


class PanelContentTest(unittest.TestCase):
    def setUp(self):
        self.ps = panels(build())

    def test_every_panel_has_twenty_cards_filters_and_sort(self):
        for p in self.ps:
            self.assertEqual(p.count('<article class="card"'), 20)
            for role in ("all", "tank", "healer", "dps"):
                self.assertIn(f'data-filter="{role}"', p)
            self.assertIn('class="sort"', p)

    def test_cards_carry_role_and_grade_for_filtering(self):
        cards = re.findall(r'<article class="card"[^>]*data-role="(\w+)"[^>]*data-grade="([\d.]+)"', self.ps[0])
        self.assertEqual({r for r, _ in cards}, {"tank", "healer", "dps"})

    def test_every_panel_has_a_podium_with_mvp_and_lvp(self):
        for p in self.ps:
            podium = re.search(r'<section class="podium">(.*?)</section>', p, re.S).group(1)
            self.assertIn("MVP", podium)
            self.assertIn("LVP", podium)

    def test_podium_comments_start_open_and_the_rest_closed(self):
        for p in self.ps:
            self.assertEqual(p.count('<details class="say" open'), 4)
            self.assertEqual(p.count('<details class="say"'), 20)

    def test_global_panel_has_the_grade_table_with_wipe_marked(self):
        self.assertIn('class="heat"', self.ps[0])
        self.assertIn("Boss Tre", self.ps[0])
        self.assertIn("WIPE", self.ps[0])

    def test_kill_panels_show_parses_and_no_wipe_banner(self):
        for p in self.ps[1:3]:
            self.assertNotIn(tips.NO_KILL, p)
            self.assertIn("parse", p)

    def test_wipe_panel_says_no_kill_no_ranking_with_tip_and_no_parse(self):
        p = self.ps[3]
        self.assertIn(tips.NO_KILL, p)
        self.assertTrue(any(t in p for t in tips.TIPS))
        self.assertIn("16.54%", p)
        self.assertNotIn("parse", p.split('<section class="podium">')[0] + p.split('class="grid"')[1])
        self.assertIn("pos.", p)


class AttendanceTest(unittest.TestCase):
    def test_benched_player_is_marked_and_off_the_global_podium(self):
        tries = [(KILL_A, players(21)), (KILL_B, players(21)), (WIPE_C, [p for p in players(20) if p.name != "Sleãze"])]
        h = build(build_night({"max_missed_fights": 0}, tries))
        g = panels(h)[0]
        self.assertIn("poche presenze", g)
        podium = re.search(r'<section class="podium">(.*?)</section>', g, re.S).group(1)
        self.assertNotIn("Sleãze", podium)


class IconsTest(unittest.TestCase):
    def test_icon_data_is_inlined_once_and_reused_by_class(self):
        h = build(icons={"Priest-Holy": URI})
        self.assertEqual(h.count(URI), 1)
        self.assertIn(".i-Priest-Holy{background-image:url(" + URI + ")}", h)
        for p in panels(h):
            self.assertEqual(p.count('class="spec i-Priest-Holy"'), 1)  # Karabosca, the only Holy Priest

    def test_no_icons_means_no_icon_elements(self):
        self.assertNotIn('class="spec', build())


class BossPageTest(unittest.TestCase):
    def test_boss_page_has_no_tabs_and_a_single_panel_with_the_banner(self):
        h = page.render_html(build_boss(WIPE_C))
        self.assertEqual(len(panels(h)), 1)
        self.assertNotIn('class="tab"', h)
        self.assertIn(tips.NO_KILL, h)
        self.assertEqual(h.count('class="card"'), 20)

    def test_kill_banner_and_podium(self):
        h = page.render_html(build_boss(KILL_A))
        self.assertIn("KILL</strong> in", h)
        self.assertIn("LVP", h)


class SharingTest(unittest.TestCase):
    URL = "https://example.github.io/blazettino-site/2026-10-15/"

    def test_link_preview_tags_describe_the_night(self):
        h = page.render_html(build_night(), None, self.URL)
        self.assertIn('property="og:title" content="Il Blazettino · The Venomous Abyss', h)
        desc = re.search(r'property="og:description" content="([^"]*)"', h).group(1)
        self.assertIn("MVP", desc)
        self.assertIn("LVP", desc)
        self.assertIn(f'property="og:url" content="{self.URL}"', h)

    def test_no_og_url_when_the_page_is_not_hosted_yet(self):
        self.assertNotIn("og:url", build())

    def test_page_is_dark_only_and_has_no_link_at_the_bottom(self):
        h = page.render_html(build_night(), None, self.URL)
        self.assertNotIn("prefers-color-scheme:light", h)
        self.assertNotIn("Home", h)

    def test_week_page_is_labelled_as_such_and_links_two_levels_up(self):
        week = night.assemble_week([build_night(date="2026-10-07"), build_night(date="2026-10-08")], {}, fake_comments)
        h = page.render_html(week, None, self.URL)
        self.assertIn('data-tab="global" aria-pressed="true">Settimana<', h)
        self.assertIn("<th>Settimana</th>", h)

    def test_page_is_unlisted(self):
        self.assertIn('name="robots" content="noindex"', build())


if __name__ == "__main__":
    unittest.main()
