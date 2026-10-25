import unittest

from ingestion.config import DEFAULT_USER_AGENT, HhSettings


class HhSettingsTests(unittest.TestCase):
    def test_reads_values_from_mapping(self):
        settings = HhSettings.from_env(
            {
                "HH_BASE_URL": "https://example.test/",
                "HH_USER_AGENT": "Observatory/1.0 (contact: test@example.test)",
                "HH_MAX_RETRIES": "3",
                "HH_TIMEOUT_SECONDS": "12.5",
            }
        )
        self.assertEqual(settings.base_url, "https://example.test")
        self.assertEqual(settings.max_retries, 3)
        self.assertEqual(settings.timeout_seconds, 12.5)

    def test_live_request_rejects_placeholder_user_agent(self):
        with self.assertRaises(ValueError):
            HhSettings(user_agent=DEFAULT_USER_AGENT).validate_for_live_request()


if __name__ == "__main__":
    unittest.main()
