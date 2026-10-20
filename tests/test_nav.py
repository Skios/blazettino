import unittest

from blazettino import nav

PAGE = '<!doctype html><html><head><title>t</title><style>:root{color-scheme:dark light;--bg:#14161c}@media (prefers-color-scheme:light){:root{--bg:#f4f5f8;--fg:#000}}</style></head><body><main>x</main><footer>ridere.<br><a href="../">Home</a></footer></body></html>'


class EnhanceTest(unittest.TestCase):
    def test_bar_with_logo_and_home_one_level_up_for_a_night(self):
        h = nav.enhance(PAGE, "2026-10-19")
        self.assertIn('<nav class="bar"><a class="brand" href="../"><img src="../logo.png"', h)
        self.assertNotIn("Serata", h)

    def test_home_is_two_levels_up_for_a_week(self):
        self.assertIn('class="brand" href="../../"', nav.enhance(PAGE, "settimana/2026-10-07"))

    def test_single_boss_page_also_links_back_to_its_night(self):
        h = nav.enhance(PAGE, "2026-10-14/ulatek")
        self.assertIn('class="brand" href="../../"', h)
        self.assertIn('<a href="../">← Serata</a>', h)

    def test_bar_follows_the_body_and_the_page_gets_the_logo_as_icon(self):
        h = nav.enhance(PAGE, "2026-10-19")
        self.assertIn('<body><!--nav--><nav class="bar">', h)
        self.assertIn('<link rel="icon" href="../logo.png">', h)

    def test_logo_replaces_the_newspaper_emoji_beside_the_title(self):
        page = PAGE.replace("<main>", "<main><h1>📰 Il Blazettino</h1>")
        h = nav.enhance(page, "2026-10-14/ulatek")
        self.assertIn('<h1><img class="logo" src="../../logo.png" alt="">Il Blazettino</h1>', h)
        self.assertNotIn("📰", h)
        self.assertEqual(nav.enhance(h, "2026-10-14/ulatek"), h)

    def test_old_footer_link_is_removed(self):
        self.assertNotIn('<br><a href="../">Home</a>', nav.enhance(PAGE, "2026-10-19"))

    def test_only_the_dark_theme_is_left(self):
        h = nav.enhance(PAGE, "2026-10-19")
        self.assertNotIn("prefers-color-scheme:light", h)
        self.assertNotIn("color-scheme:dark light", h)
        self.assertIn("color-scheme:dark", h)

    def test_is_idempotent(self):
        once = nav.enhance(PAGE, "2026-10-19")
        self.assertEqual(nav.enhance(once, "2026-10-19"), once)

    def test_picker_script_is_injected(self):
        self.assertIn("startViewTransition", nav.enhance(PAGE, "2026-10-19"))

    def test_fragments_without_head_or_body_are_left_alone(self):
        self.assertEqual(nav.enhance("<html>NIGHT</html>", "2026-10-15"), "<html>NIGHT</html>")


if __name__ == "__main__":
    unittest.main()
