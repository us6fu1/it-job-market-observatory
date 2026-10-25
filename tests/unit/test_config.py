import unittest

from ingestion.config import DEFAULT_USER_AGENT, HhSettings


class HhSettingsTests(unittest.TestCase):
    def test_reads_values_from_mapping(self):
        settings = HhSettings.from_env(
            {
                "HH_BASE_URL": "https://example.test/",
                "HH_USER_AGENT": "Observatory/1.0 (contact: test@example.test)",
                "HH_ACCESS_TOKEN": "access-token",
                "HH_MAX_RETRIES": "3",
                "HH_TIMEOUT_SECONDS": "12.5",
            }
        )
        self.assertEqual(settings.base_url, "https://example.test")
        self.assertEqual(settings.oauth_token, "access-token")
        self.assertEqual(settings.max_retries, 3)
        self.assertEqual(settings.timeout_seconds, 12.5)

    def test_access_token_takes_precedence_over_legacy_name(self):
        settings = HhSettings.from_env(
            {
                "HH_ACCESS_TOKEN": "new-token",
                "HH_OAUTH_TOKEN": "legacy-token",
            }
        )
        self.assertEqual(settings.oauth_token, "new-token")

    def test_legacy_oauth_token_is_still_supported(self):
        settings = HhSettings.from_env({"HH_OAUTH_TOKEN": "legacy-token"})
        self.assertEqual(settings.oauth_token, "legacy-token")

    def test_token_is_optional_for_settings_validation(self):
        settings = HhSettings(
            user_agent="Observatory/1.0 (contact: test@example.test)",
            oauth_token=None,
        )
        settings.validate_for_live_request()

    def test_live_request_rejects_placeholder_user_agent(self):
        with self.assertRaises(ValueError):
            HhSettings(user_agent=DEFAULT_USER_AGENT).validate_for_live_request()


if __name__ == "__main__":
    unittest.main()
