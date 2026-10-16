import re
import unittest

from blazettino import kpi, page
from blazettino.comment import Comment
from tests.test_report import fight


def build(comments=None, max_missed=1, fights=None, bosses=("Ula'tek",), icons=None):
    players = kpi.merge(fights or [fight("Ula'tek")])
    if comments is None:
        comments = {"Sleãze": Comment("CALAMITA", "Due morti evitabili.")}
    return page.render_html(
        "The Venomous Abyss", "2026-10-15", list(bosses), players, comments, max_missed, icons
    )


class PageTest(unittest.TestCase):
    def test_is_a_responsive_html_document(self):
        html = build()
        self.assertTrue(html.lower().startswith("<!doctype html>"))
        self.assertIn('name="viewport"', html)

    def test_is_self_contained(self):
        html = build()
        self.assertNotRegex(html, r'(src|href)\s*=\s*"https?:')
        self.assertNotIn("@import", html)

    def test_llm_text_is_escaped(self):
        html = build({"Sleãze": Comment("<b>X</b>", "<script>alert(1)</script>")})
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_one_card_per_player_with_role_and_grade_for_filtering(self):
        cards = re.findall(
            r'<article class="card"[^>]*data-role="(\w+)"[^>]*data-grade="([\d.]+)"', build()
        )
        self.assertEqual(len(cards), 20)
        self.assertEqual({r for r, _ in cards}, {"tank", "healer", "dps"})

    def test_filter_and_sort_controls_present(self):
        html = build()
        for role in ("all", "tank", "healer", "dps"):
            self.assertIn(f'data-filter="{role}"', html)
        self.assertIn('id="sort"', html)

    def test_podium_shows_mvp_and_lvp(self):
        html = build()
        self.assertRegex(html, r"MVP[\s\S]*Karabosca")
        self.assertRegex(html, r"LVP[\s\S]*Sleãze")

    def test_comment_and_deaths_are_in_the_card(self):
        html = build()
        self.assertIn("CALAMITA", html)
        self.assertIn("Caustic Waves", html)

    def test_benched_player_is_marked_and_off_podium(self):
        short = [p for p in fight("C") if p.name != "Sleãze"]
        html = build(fights=[fight("A"), fight("B"), short], max_missed=0, bosses=("A", "B", "C"))
        self.assertIn("poche presenze", html)
        podium = html.split('id="grid"')[0]
        self.assertNotIn("Sleãze", podium)

    def test_spec_icon_is_inlined_on_matching_cards_only(self):
        uri = "data:image/jpeg;base64,AAAA"
        html = build(icons={"Priest-Holy": uri})
        self.assertEqual(html.count(f'<img class="spec" src="{uri}"'), 1)  # Karabosca, the only Holy Priest
        self.assertIn('alt="Holy Priest"', html)

    def test_no_icons_means_no_img_tags(self):
        self.assertNotIn("<img", build())


if __name__ == "__main__":
    unittest.main()
