import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from blazettino import wcl


def http429():
    return urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(b""))


class RateLimitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target, value in (("CACHE", Path(self.tmp.name)),):
            p = mock.patch.object(wcl, target, value)
            p.start()
            self.addCleanup(p.stop)
        self.sleeps = []
        p = mock.patch.object(wcl.time, "sleep", self.sleeps.append)
        p.start()
        self.addCleanup(p.stop)

    def run_with(self, replies):
        """replies: results of successive _post calls (an exception is raised, a dict returned)."""
        it = iter(replies)

        def post(query):
            r = next(it)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(wcl, "_post", post):
            return wcl.gql("{q}")

    def test_waits_for_the_reset_then_retries_and_caches_the_answer(self):
        ok = {"data": {"x": 1}}
        out = self.run_with([http429(), {"data": {"rateLimitData": {"pointsResetIn": 1200}}}, ok])
        self.assertEqual(out, ok)
        self.assertEqual(self.sleeps, [1200 + wcl.RESET_MARGIN_S])
        self.assertEqual(wcl.gql("{q}"), ok)  # second call comes from the cache: _post is not patched, it would fail

    def test_graphql_error_about_the_rate_limit_also_waits(self):
        limited = {"errors": [{"message": "You have exceeded the rate limit"}]}
        out = self.run_with([limited, {"data": {"rateLimitData": {"pointsResetIn": 60}}}, {"data": {}}])
        self.assertEqual(out, {"data": {}})
        self.assertEqual(len(self.sleeps), 1)

    def test_when_even_the_limit_query_is_refused_it_waits_a_default_while(self):
        self.run_with([http429(), http429(), {"data": {}}])
        self.assertEqual(self.sleeps, [wcl.RESET_GUESS_S + wcl.RESET_MARGIN_S])

    def test_real_429_carries_retry_after_so_no_extra_query_is_needed(self):
        e = urllib.error.HTTPError("u", 429, "Too Many Requests", {"retry-after": "3078"}, io.BytesIO(b""))
        self.run_with([e, {"data": {}}])  # a second 429 or a limit query would exhaust the replies
        self.assertEqual(self.sleeps, [3078 + wcl.RESET_MARGIN_S])

    def test_other_errors_are_not_retried(self):
        with self.assertRaises(RuntimeError):
            self.run_with([{"errors": [{"message": "syntax"}]}])
        with self.assertRaises(urllib.error.HTTPError):
            self.run_with([urllib.error.HTTPError("u", 500, "boom", {}, io.BytesIO(b""))])
        self.assertEqual(self.sleeps, [])

    def test_gives_up_after_a_day_of_waiting(self):
        with mock.patch.object(wcl, "MAX_WAITS", 2):
            with self.assertRaises(RuntimeError):
                self.run_with([http429(), {"data": {"rateLimitData": {"pointsResetIn": 1}}}] * 2)


class EventsTest(unittest.TestCase):
    def test_follows_next_page_timestamp_until_the_end(self):
        pages = [
            {"data": {"reportData": {"report": {"events": {"data": [{"t": 1}, {"t": 2}], "nextPageTimestamp": 3}}}}},
            {"data": {"reportData": {"report": {"events": {"data": [{"t": 3}], "nextPageTimestamp": None}}}}},
        ]
        queries = []

        def fake(q):
            queries.append(q)
            return pages[len(queries) - 1]

        with mock.patch.object(wcl, "gql", fake):
            out = wcl.events("ABC", 21, 0, 100, "DamageTaken", "Friendlies")
        self.assertEqual(out, [{"t": 1}, {"t": 2}, {"t": 3}])
        self.assertIn("startTime:0", queries[0])
        self.assertIn("startTime:3", queries[1])
        self.assertIn("dataType:DamageTaken", queries[0])
        self.assertIn("hostilityType:Friendlies", queries[0])


if __name__ == "__main__":
    unittest.main()
