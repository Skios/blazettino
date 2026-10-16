import tempfile
import unittest
from pathlib import Path

from blazettino import icons

JPEG = b"\xff\xd8\xff fake jpeg"


class IconsTest(unittest.TestCase):
    def test_returns_inline_data_uris_and_caches_to_disk(self):
        calls = []

        def download(name):
            calls.append(name)
            return JPEG

        with tempfile.TemporaryDirectory() as tmp:
            out = icons.fetch(["Priest-Holy"], Path(tmp), download)
            self.assertTrue(out["Priest-Holy"].startswith("data:image/jpeg;base64,"))
            self.assertTrue((Path(tmp) / "Priest-Holy.jpg").exists())
            icons.fetch(["Priest-Holy"], Path(tmp), download)  # second time: from disk
        self.assertEqual(calls, ["Priest-Holy"])

    def test_failed_download_is_skipped_not_fatal(self):
        def download(name):
            if name == "Bad-Spec":
                raise OSError("404")
            return JPEG

        with tempfile.TemporaryDirectory() as tmp, self.assertLogs("blazettino.icons", level="WARNING"):
            out = icons.fetch(["Bad-Spec", "Priest-Holy"], Path(tmp), download)
        self.assertEqual(set(out), {"Priest-Holy"})

    def test_unsafe_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertLogs("blazettino.icons", level="WARNING"):
            out = icons.fetch(["../../etc/passwd"], Path(tmp), lambda n: JPEG)
        self.assertEqual(out, {})


if __name__ == "__main__":
    unittest.main()
