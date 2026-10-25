from pathlib import Path
import tempfile
import unittest

from ingestion.raw_store import FileRawStore


class RawStoreTests(unittest.TestCase):
    def test_detail_state_survives_between_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = FileRawStore(root)
            first.start_run("00000000-0000-0000-0000-000000000001", {})
            self.assertTrue(first.needs_detail("42", "2026-10-01T00:00:00+00:00"))
            first.record_detail(
                "42",
                None,
                {"id": "42", "name": "Example"},
                comparison_marker="search-hash-1",
            )
            first.finish_run("success", {})

            second = FileRawStore(root)
            self.assertFalse(second.needs_detail("42", "search-hash-1"))
            self.assertTrue(second.needs_detail("42", "search-hash-2"))
            self.assertTrue(
                second.needs_detail("42", "search-hash-1", refresh=True)
            )


if __name__ == "__main__":
    unittest.main()
