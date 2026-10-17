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

    def test_index_lists_every_night_newest_first_and_is_noindex(self):
        old = self.site / "2026-10-01"
        old.mkdir()
        (old / "index.html").write_text("old")
        self.run_publish()
        index = (self.site / "index.html").read_text()
        self.assertLess(index.index("2026-10-15"), index.index("2026-10-01"))
        self.assertIn('href="2026-10-15/"', index)
        self.assertIn("noindex", index)

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


if __name__ == "__main__":
    unittest.main()
