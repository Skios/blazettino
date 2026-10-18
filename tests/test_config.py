import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blazettino import config


class EnvPrefixTest(unittest.TestCase):
    def test_numbered_keys_come_in_order_after_the_plain_one(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".env").write_text("geminiKey2: B\ngeminiKey=A\ngeminiKey10 C\nother: X\ngeminiKeyfoo: Y\n")
            with mock.patch.object(config, "ROOT", Path(d)):
                self.assertEqual(config.env_prefix("geminiKey"), ["A", "B", "C"])

    def test_no_key_at_all_fails_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".env").write_text("other: X\n")
            with mock.patch.object(config, "ROOT", Path(d)), self.assertRaises(RuntimeError):
                config.env_prefix("geminiKey")


if __name__ == "__main__":
    unittest.main()
