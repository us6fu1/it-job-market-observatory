from datetime import date
from pathlib import Path
import tempfile
import unittest

from ingestion.models import SearchSegment
from ingestion.pipeline import CollectionPipeline
from ingestion.raw_store import FileRawStore


class FakeClient:
    def __init__(self):
        self.detail_calls = []

    def count(self, params):
        return 2

    def iter_search_pages(self, params):
        yield {
            "found": 2,
            "pages": 1,
            "items": [
                {"id": "1", "name": "DA", "published_at": "2026-10-01T10:00:00+03:00"},
                {"id": "2", "name": "DE", "published_at": "2026-10-01T11:00:00+03:00"},
            ],
        }

    def get_vacancy(self, vacancy_id):
        self.detail_calls.append(vacancy_id)
        return {"id": vacancy_id, "name": "Vacancy {}".format(vacancy_id)}


class CollectionPipelineTests(unittest.TestCase):
    def segment(self):
        return SearchSegment(
            job_group="data_analyst",
            text="аналитик",
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 1),
        )

    def test_reuses_details_when_search_item_did_not_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_client = FakeClient()
            first = CollectionPipeline(first_client, FileRawStore(root)).collect([self.segment()])
            second_client = FakeClient()
            second = CollectionPipeline(second_client, FileRawStore(root)).collect([self.segment()])

        self.assertEqual(first["details_loaded"], 2)
        self.assertEqual(second["details_loaded"], 0)
        self.assertEqual(first_client.detail_calls, ["1", "2"])
        self.assertEqual(second_client.detail_calls, [])


if __name__ == "__main__":
    unittest.main()
