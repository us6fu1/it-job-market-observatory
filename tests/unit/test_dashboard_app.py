import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]


class DashboardAppTests(unittest.TestCase):
    def test_offline_demo_starts_without_database(self):
        with patch.dict(os.environ, {}, clear=True):
            app = AppTest.from_file(str(ROOT / "dashboard" / "app.py")).run(
                timeout=20
            )

        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any("DATABASE_URL" in warning.value for warning in app.warning)
        )


if __name__ == "__main__":
    unittest.main()
