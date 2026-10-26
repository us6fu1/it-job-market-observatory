from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from ingestion.models import SearchSegment
from ingestion.segmentation import load_segments, plan_segments


class SegmentationTests(unittest.TestCase):
    def test_splits_date_range_until_every_leaf_is_safe(self):
        segment = SearchSegment(
            job_group="data_analyst",
            text="аналитик данных",
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 4),
        )

        def probe(item):
            return 3000 if item.date_from < item.date_to else 600

        result = plan_segments([segment], probe)
        self.assertEqual(len(result), 4)
        self.assertTrue(all(item.status == "ready" for item in result))
        self.assertTrue(all(item.found <= 2000 for item in result))

    def test_splits_professional_roles_for_one_day(self):
        segment = SearchSegment(
            job_group="data_engineer",
            text="data engineer",
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 1),
            professional_role_ids=("1", "2", "3", "4"),
        )
        result = plan_segments(
            [segment],
            lambda item: len(item.professional_role_ids) * 700,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual({item.found for item in result}, {1400})

    def test_marks_unsplittable_segment_instead_of_hiding_it(self):
        segment = SearchSegment(
            job_group="bi_developer",
            text="BI",
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 1),
        )
        result = plan_segments([segment], lambda _: 2501)
        self.assertEqual(result[0].status, "over_limit")
        self.assertIn("2", result[0].message)

    def test_loads_global_dates_from_config(self):
        payload = {
            "date_from": "2026-10-01",
            "date_to": "2026-10-02",
            "segments": [{"job_group": "data_analyst", "text": "analyst"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "segments.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            segment = load_segments(path)[0]
        self.assertEqual(segment.date_from, date(2026, 10, 1))
        self.assertEqual(segment.date_to, date(2026, 10, 2))

    def test_loads_relative_date_window(self):
        payload = {
            "days_back": 7,
            "date_to": "today",
            "segments": [{"job_group": "data_engineer", "text": "data engineer"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "segments.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            segment = load_segments(path, today=date(2026, 10, 26))[0]
        self.assertEqual(segment.date_from, date(2026, 10, 20))
        self.assertEqual(segment.date_to, date(2026, 10, 26))

    def test_filters_titles_with_source_specific_patterns(self):
        segment = SearchSegment(
            job_group="data_engineer",
            text="инженер данных",
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 1),
            title_patterns=(r"data\s+engineer", r"инженер\s+данн"),
        )
        self.assertTrue(segment.matches_title("Senior Data Engineer"))
        self.assertTrue(segment.matches_title("Инженер данных"))
        self.assertFalse(segment.matches_title("Инженер по охране труда"))

    def test_bi_filter_does_not_treat_business_partner_as_developer(self):
        segment = SearchSegment(
            job_group="bi_developer",
            text="BI разработчик",
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 1),
            title_patterns=(
                r"(?:bi|dwh).*(?:разработ|developer|аналитик|архитект)",
                r"(?:разработ|developer|аналитик|архитект).*(?:bi|dwh)",
            ),
        )
        self.assertTrue(segment.matches_title("BI Developer"))
        self.assertTrue(segment.matches_title("Архитектор DWH"))
        self.assertFalse(segment.matches_title("BI Бизнес-партнер"))


if __name__ == "__main__":
    unittest.main()
