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

    def test_archive_lists_every_night_newest_first_unlisted_and_styled(self):
        old = self.site / "2026-10-01"
        old.mkdir()
        (old / "index.html").write_text("old")
        self.run_publish()
        archive = (self.site / "archivio" / "index.html").read_text()
        self.assertLess(archive.index("2026-10-15/"), archive.index("2026-10-01/"))
        self.assertIn('href="../2026-10-15/"', archive)
        self.assertIn("noindex", archive)
        self.assertIn("<style>", archive)
        self.assertIn('name="viewport"', archive)

    def test_archive_shows_readable_date_title_summary_and_marks_the_latest(self):
        (self.folder / "pagella.html").write_text(
            '<html><head><title>Il Blazettino · The Venomous Abyss 2026-10-15</title>'
            '<meta property="og:description" content="MVP Karabosca (9.5) · LVP Madreh (4.5)"></head></html>'
        )
        self.run_publish()
        archive = (self.site / "archivio" / "index.html").read_text()
        self.assertIn("15 ottobre 2026", archive)
        self.assertIn("The Venomous Abyss", archive)
        self.assertIn("MVP Karabosca (9.5)", archive)
        self.assertEqual(archive.count("Ultima"), 1)

    def test_archive_text_from_pages_is_escaped(self):
        (self.folder / "pagella.html").write_text(
            '<title>Il Blazettino · &lt;script&gt;x&lt;/script&gt; 2026-10-15</title>'
        )
        self.run_publish()
        self.assertNotIn("<script>x", (self.site / "archivio" / "index.html").read_text())

    def test_root_opens_straight_on_the_latest_night(self):
        old = self.site / "2026-10-01"
        old.mkdir()
        (old / "index.html").write_text("old")
        self.run_publish()
        root = (self.site / "index.html").read_text()
        self.assertIn('http-equiv="refresh" content="0; url=2026-10-15/"', root)
        self.assertIn("location.replace(\"2026-10-15/\")", root)
        self.assertIn('href="2026-10-15/"', root)  # visible fallback link
        self.assertIn('href="archivio/"', root)
        self.assertIn("noindex", root)

    def test_root_without_nights_does_not_redirect(self):
        (self.folder / "pagella.html").write_text("x")
        self.run_publish()
        publish.remove("2026-10-15", self.site, FakeGit())
        root = (self.site / "index.html").read_text()
        self.assertNotIn("refresh", root)
        self.assertNotIn("location.replace", root)
        self.assertIn("Nessuna pagella", root)

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
        archive = (self.site / "archivio" / "index.html").read_text()
        self.assertNotIn("2026-10-15", archive)
        self.assertIn("2026-10-01", archive)
        self.assertIn("url=2026-10-01/", (self.site / "index.html").read_text())  # root falls back to the previous night

    def test_commits_and_pushes_the_removal(self):
        git = FakeGit()
        publish.remove("2026-10-15", self.site, git)
        self.assertEqual([c[:2] for c in git.calls], [["git", "add"], ["git", "status"], ["git", "commit"], ["git", "push"]])
        self.assertIn("2026-10-15", " ".join(git.calls[2]))

    def test_only_dated_folders_can_be_removed(self):
        for bad in ("../x", "..", "index.html", "2026-10-1", ""):
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
        self.assertIn("url=2026-10-15/", (self.site / "index.html").read_text())
        self.assertIn("2026-10-01/", (self.site / "archivio" / "index.html").read_text())
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
