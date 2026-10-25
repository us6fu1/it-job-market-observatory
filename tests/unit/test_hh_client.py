import io
import unittest
from urllib.error import HTTPError

from ingestion.config import HhSettings
from ingestion.hh_client import HhApiError, HhClient


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body.encode("utf-8")
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


class HhClientTests(unittest.TestCase):
    def settings(self, **changes):
        values = {
            "user_agent": "Observatory/1.0 (contact: test@example.test)",
            "max_retries": 2,
            "retry_base_seconds": 0.1,
        }
        values.update(changes)
        return HhSettings(**values)

    def test_sends_user_agent_oauth_and_parses_json(self):
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse('{"found": 7}')

        client = HhClient(
            self.settings(oauth_token="secret-token"),
            opener=opener,
        )
        result = client.search({"text": "data analyst", "area": ["1", "2"]})
        request = captured["request"]
        self.assertEqual(result["found"], 7)
        self.assertIn("area=1&area=2", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertIn("Observatory/1.0", request.get_header("User-agent"))

    def test_retries_429_using_retry_after(self):
        calls = []
        sleeps = []

        def opener(request, timeout):
            calls.append(request)
            if len(calls) == 1:
                raise HTTPError(
                    request.full_url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "0.25"},
                    io.BytesIO(b"{}"),
                )
            return FakeResponse('{"items": []}')

        client = HhClient(self.settings(), opener=opener, sleep=sleeps.append)
        self.assertEqual(client.search({})["items"], [])
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [0.25])

    def test_does_not_retry_non_retryable_http_error(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO(b"{}"))

        client = HhClient(self.settings(), opener=opener, sleep=lambda _: None)
        with self.assertRaises(HhApiError):
            client.get_vacancy("missing")

    def test_explains_403_when_access_token_is_missing(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b"{}"))

        client = HhClient(self.settings(oauth_token=None), opener=opener)
        with self.assertRaisesRegex(HhApiError, "HH_ACCESS_TOKEN"):
            client.search({"text": "data analyst"})


if __name__ == "__main__":
    unittest.main()
