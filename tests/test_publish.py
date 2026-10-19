import tempfile
import unittest
from pathlib import Path

from blazettino import publish

SITE_URL = "https://example.github.io/blazettino-site/"


class FakeGit:
    def __init__(self, dirty="M 2026-10-15/index.html"):
        self.calls = []
        self.dirty = dirty

    def __call__(self, cmd, cwd):
        self.calls.append(cmd)
        return self.dirty if cmd[:2] == ["git", "status"] else ""


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.folder, self.site = root / "out" / "2026-10-15", root / "site"
        self.folder.mkdir(parents=True)
        self.site.mkdir()
        (self.folder / "pagella.html").write_text("<html>NIGHT</html>")

    def tearDown(self):
        self.tmp.cleanup()

    def run_publish(self, git=None):
        git = git or FakeGit()
        url = publish.publish(self.folder, "2026-10-15", self.site, SITE_URL, git)
        return url, git

    def test_page_is_copied_as_the_index_of_a_dated_folder(self):
        self.run_publish()
        self.assertEqual((self.site / "2026-10-15" / "index.html").read_text(), "<html>NIGHT</html>")

    def test_returns_the_public_url_with_one_slash(self):
        url, _ = self.run_publish()
        self.assertEqual(url, "https://example.github.io/blazettino-site/2026-10-15/")

    def test_site_is_unlisted_and_static(self):
        self.run_publish()
        self.assertIn("Disallow: /", (self.site / "robots.txt").read_text())
        self.assertTrue((self.site / ".nojekyll").exists())

    def home(self):
        return (self.site / "index.html").read_text()

    def test_home_lists_every_night_newest_first_unlisted_and_styled(self):
        old = self.site / "2026-10-01"
        old.mkdir()
        (old / "index.html").write_text("old")
        self.run_publish()
        home = self.home()
        self.assertLess(home.index('href="2026-10-15/"'), home.index('href="2026-10-01/"'))
        self.assertIn("noindex", home)
        self.assertIn("<style>", home)
        self.assertIn('name="viewport"', home)

    def test_home_does_not_redirect_and_offers_the_latest_night_first(self):
        self.run_publish()
        home = self.home()
        self.assertNotIn("refresh", home)
        self.assertNotIn("location.replace", home)
        self.assertIn('class="btn" href="2026-10-15/"', home)

    def test_home_shows_readable_date_title_summary_and_marks_the_latest(self):
        (self.folder / "pagella.html").write_text(
            '<html><head><title>Il Blazettino · The Venomous Abyss 2026-10-15</title>'
            '<meta property="og:description" content="MVP Karabosca (9.5) · LVP Madreh (4.5)"></head></html>'
        )
        self.run_publish()
        home = self.home()
        self.assertIn("15 ottobre 2026", home)
        self.assertIn("The Venomous Abyss", home)
        self.assertIn("MVP Karabosca (9.5)", home)
        self.assertEqual(home.count("Ultima</span>"), 1)

    def test_home_text_from_pages_is_escaped(self):
        (self.folder / "pagella.html").write_text(
            '<title>Il Blazettino · &lt;script&gt;x&lt;/script&gt; 2026-10-15</title>'
        )
        self.run_publish()
        self.assertNotIn("<script>x", self.home())

    def test_old_archive_link_goes_to_the_home(self):
        self.run_publish()
        self.assertIn('url=../"', (self.site / "archivio" / "index.html").read_text())

    def test_home_without_nights_says_so(self):
        (self.folder / "pagella.html").write_text("x")
        self.run_publish()
        publish.remove("2026-10-15", self.site, FakeGit())
        self.assertIn("Nessuna pagella", self.home())

    def test_week_is_published_under_settimana_and_listed_apart_from_the_nights(self):
        (self.folder / "pagella.html").write_text(
            '<title>Il Blazettino · Settimana 07/10–12/10 · The Venomous Abyss 2026-10-07</title>'
        )
        url = publish.publish(self.folder, "2026-10-07", self.site, SITE_URL, FakeGit(), "settimana")
        self.assertEqual(url, "https://example.github.io/blazettino-site/settimana/2026-10-07/")
        self.assertTrue((self.site / "settimana" / "2026-10-07" / "index.html").exists())
        home = self.home()
        self.assertIn('href="settimana/2026-10-07/"', home)
        self.assertIn("Settimana 07/10–12/10 · The Venomous Abyss", home)
        self.assertNotIn('href="2026-10-07/"', home)  # not mistaken for a night
        self.assertNotIn('class="btn"', home)  # no night yet, so no "latest night" button

    def test_single_boss_goes_under_its_night_and_is_listed_in_its_own_section(self):
        (self.folder / "pagella.html").write_text(
            "<title>Il Blazettino · Ula'tek (14/10) · The Venomous Abyss 2026-10-14</title>"
        )
        night_dir = self.site / "2026-10-14"
        night_dir.mkdir()
        (night_dir / "index.html").write_text("hand edited night")
        url = publish.publish(self.folder, "ulatek", self.site, SITE_URL, FakeGit(), "2026-10-14")
        self.assertEqual(url, "https://example.github.io/blazettino-site/2026-10-14/ulatek/")
        self.assertEqual((night_dir / "index.html").read_text(), "hand edited night")
        home = self.home()
        self.assertIn("Boss singoli", home)
        self.assertIn('href="2026-10-14/ulatek/"', home)
        self.assertIn("Ula&#x27;tek (14/10)", home)

    def test_home_has_no_boss_section_without_boss_pages(self):
        self.run_publish()
        self.assertNotIn("Boss singoli", self.home())

    def test_commits_and_pushes_when_something_changed(self):
        _, git = self.run_publish()
        self.assertEqual([c[:2] for c in git.calls], [["git", "add"], ["git", "status"], ["git", "commit"], ["git", "push"]])
        self.assertIn("2026-10-15", " ".join(git.calls[2]))

    def test_nothing_to_commit_means_no_commit_and_no_push(self):
        _, git = self.run_publish(FakeGit(dirty=""))
        self.assertEqual([c[:2] for c in git.calls], [["git", "add"], ["git", "status"]])

    def test_missing_page_fails_clearly(self):
        (self.folder / "pagella.html").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_publish()


class RemoveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.site = Path(self.tmp.name)
        for d in ("2026-10-01", "2026-10-15"):
            (self.site / d).mkdir()
            (self.site / d / "index.html").write_text(d)

    def tearDown(self):
        self.tmp.cleanup()

    def test_removes_the_night_and_unlists_it(self):
        git = FakeGit()
        publish.remove("2026-10-15", self.site, git)
        self.assertFalse((self.site / "2026-10-15").exists())
        self.assertTrue((self.site / "2026-10-01").exists())
        home = (self.site / "index.html").read_text()
        self.assertNotIn("2026-10-15", home)
        self.assertIn('class="btn" href="2026-10-01/"', home)  # latest falls back to the previous night

    def test_commits_and_pushes_the_removal(self):
        git = FakeGit()
        publish.remove("2026-10-15", self.site, git)
        self.assertEqual([c[:2] for c in git.calls], [["git", "add"], ["git", "status"], ["git", "commit"], ["git", "push"]])
        self.assertIn("2026-10-15", " ".join(git.calls[2]))

    def test_a_week_can_be_removed_with_its_section(self):
        week = self.site / "settimana" / "2026-10-07"
        week.mkdir(parents=True)
        (week / "index.html").write_text("w")
        publish.remove("settimana/2026-10-07", self.site, FakeGit())
        self.assertFalse(week.exists())
        self.assertTrue((self.site / "2026-10-15").exists())

    def test_a_single_boss_page_can_be_removed_without_the_night(self):
        boss = self.site / "2026-10-15" / "ulatek"
        boss.mkdir()
        (boss / "index.html").write_text("b")
        publish.remove("2026-10-15/ulatek", self.site, FakeGit())
        self.assertFalse(boss.exists())
        self.assertTrue((self.site / "2026-10-15" / "index.html").exists())

    def test_only_dated_folders_can_be_removed(self):
        for bad in ("../x", "..", "index.html", "2026-10-1", "", "settimana/..", "altro/2026-10-15"):
            with self.assertRaises(ValueError):
                publish.remove(bad, self.site, FakeGit())
        self.assertTrue((self.site / "2026-10-15").exists())

    def test_unknown_night_fails_clearly(self):
        with self.assertRaises(FileNotFoundError):
            publish.remove("2026-12-31", self.site, FakeGit())


class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.site = Path(self.tmp.name)
        for d in ("2026-10-01", "2026-10-15"):
            (self.site / d).mkdir()
            (self.site / d / "index.html").write_text(d)
        (self.site / "index.html").write_text("ugly old index")

    def tearDown(self):
        self.tmp.cleanup()

    def test_rewrites_root_and_archive_from_the_published_nights_and_pushes(self):
        git = FakeGit()
        publish.refresh(self.site, git)
        home = (self.site / "index.html").read_text()
        self.assertIn('class="btn" href="2026-10-15/"', home)
        self.assertIn('href="2026-10-01/"', home)
        self.assertEqual([c[:2] for c in git.calls], [["git", "add"], ["git", "status"], ["git", "commit"], ["git", "push"]])

    def test_does_not_touch_the_night_pages(self):
        publish.refresh(self.site, FakeGit())
        self.assertEqual((self.site / "2026-10-15" / "index.html").read_text(), "2026-10-15")

    def test_nothing_changed_means_no_commit(self):
        git = FakeGit(dirty="")
        publish.refresh(self.site, git)
        self.assertEqual([c[:2] for c in git.calls], [["git", "add"], ["git", "status"]])


if __name__ == "__main__":
    unittest.main()
