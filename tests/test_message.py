import unittest

from blazettino import message, night, report
from tests.helpers import build_night, fake_comments

URL = "https://example.github.io/blazettino-site/2026-10-15/"


class MessageTest(unittest.TestCase):
    def setUp(self):
        self.night = build_night()
        _, _, top = report.standings(self.night.players, len(self.night.bosses), self.night.max_missed)
        self.mvp, self.lvp = top[0], top[-1]

    def test_names_mvp_and_lvp_with_their_titles(self):
        text = message.render(self.night, URL)
        self.assertIn(self.mvp.name, text)
        self.assertIn(self.lvp.name, text)
        self.assertIn(f"«TITOLO {self.mvp.name.upper()}»", text)
        self.assertIn(f"«TITOLO {self.lvp.name.upper()}»", text)

    def test_link_is_last_and_only_when_known(self):
        self.assertEqual(message.render(self.night, URL).splitlines()[-1], f"👉 {URL}")
        self.assertNotIn("http", message.render(self.night, None))

    def test_marks_kills_and_the_wipe_with_boss_health(self):
        text = message.render(self.night, URL)
        self.assertIn("Boss Uno ✅", text)
        self.assertIn("Boss Tre ❌ 16.54%", text)

    def test_fits_a_discord_message_and_has_no_markdown(self):
        text = message.render(self.night, URL)
        self.assertLess(len(text), 2000)
        self.assertNotIn("**", text)

    def test_date_is_day_slash_month(self):
        self.assertIn("(15/10)", message.render(self.night, URL))

    def test_week_message_has_the_range_and_no_single_day(self):
        week = night.assemble_week([build_night(date="2026-10-07"), build_night(date="2026-10-08")], {}, fake_comments)
        text = message.render(week, URL)
        self.assertIn("Settimana 07/10–08/10", text)
        self.assertNotIn("(07/10)\n", text)  # no single-day suffix after the title


if __name__ == "__main__":
    unittest.main()
