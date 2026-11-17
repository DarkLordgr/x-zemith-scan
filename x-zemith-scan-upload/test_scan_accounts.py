import io
import json
import os
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

import scan_accounts


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return io.BytesIO(json.dumps(self.payload).encode("utf-8"))

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class ScannerTests(unittest.TestCase):
    def test_watchlist_comments_duplicates_and_blank_lines(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as source:
            source.write("@AaveAave\nAaveAave\n# comment\nCoinDesk # inline\n\n")
            path = source.name
        try:
            with mock.patch.object(scan_accounts, "WATCHLIST", path):
                self.assertEqual(scan_accounts.load_watchlist(), ["AaveAave", "CoinDesk"])
        finally:
            os.unlink(path)

    def test_api_uses_expected_endpoint_auth_and_latest_query(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({"tweets": [], "has_next_page": False})

        with mock.patch.object(scan_accounts.urllib.request, "urlopen", fake_urlopen):
            result = scan_accounts.api_get("from:AaveAave since_time:1 until_time:2 -filter:replies", "test-secret")

        self.assertEqual(result["tweets"], [])
        request = captured["request"]
        parsed = urlparse(request.full_url)
        self.assertEqual(parsed.scheme + "://" + parsed.netloc + parsed.path, scan_accounts.API_URL)
        params = parse_qs(parsed.query)
        self.assertEqual(params["queryType"], ["Latest"])
        self.assertIn("from:AaveAave", params["query"][0])
        self.assertEqual(request.get_header("X-api-key"), "test-secret")
        self.assertEqual(captured["timeout"], scan_accounts.REQUEST_TIMEOUT)

    def test_format_post_handles_twitter_timestamp_and_metrics(self):
        post = {
            "id": "123",
            "text": "A  test\npost",
            "createdAt": "Tue Nov 17 10:30:00 +0000 2026",
            "likeCount": 8,
            "retweetCount": 3,
            "quoteCount": 2,
            "author": {"userName": "AaveAave", "name": "Aave"},
        }
        formatted = scan_accounts.fmt_post("AaveAave", post)
        self.assertEqual(formatted["text"], "A test post")
        self.assertEqual(formatted["ts"], "2026-11-17 10:30 UTC")
        self.assertEqual(formatted["score"], 13)
        self.assertEqual(formatted["url"], "https://x.com/AaveAave/status/123")

    def test_missing_key_fails_before_network_access(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(scan_accounts.urllib.request, "urlopen") as urlopen:
                with self.assertRaises(SystemExit) as raised:
                    scan_accounts.main()
        self.assertIn("TWITTERAPI_IO_KEY", str(raised.exception))
        urlopen.assert_not_called()

    def test_main_writes_digest_without_exposing_key(self):
        tweet = {
            "id": "456",
            "url": "https://x.com/AaveAave/status/456",
            "text": "Read-only test post",
            "createdAt": "2026-11-17T10:30:00Z",
            "likeCount": 2,
            "retweetCount": 1,
            "quoteCount": 0,
            "author": {"userName": "AaveAave", "name": "Aave"},
        }
        with tempfile.TemporaryDirectory() as directory:
            watchlist = os.path.join(directory, "accounts.txt")
            with open(watchlist, "w", encoding="utf-8") as destination:
                destination.write("AaveAave\n")
            out_dir = os.path.join(directory, "digest")
            with mock.patch.dict(os.environ, {"TWITTERAPI_IO_KEY": "do-not-disclose"}, clear=True):
                with mock.patch.object(scan_accounts, "WATCHLIST", watchlist):
                    with mock.patch.object(scan_accounts, "OUT_DIR", out_dir):
                        with mock.patch.object(scan_accounts, "SLEEP_BETWEEN", 0):
                            with mock.patch.object(scan_accounts, "api_get", return_value={"tweets": [tweet]}):
                                scan_accounts.main()
            with open(os.path.join(out_dir, "latest.md"), encoding="utf-8") as digest:
                text = digest.read()
            self.assertIn("Read-only test post", text)
            self.assertIn("https://x.com/AaveAave/status/456", text)
            self.assertNotIn("do-not-disclose", text)


if __name__ == "__main__":
    unittest.main()
