import json
from pathlib import Path
import tempfile
import unittest

from ingestion.pipeline import build_sample


ROOT = Path(__file__).resolve().parents[2]


class SamplePipelineTests(unittest.TestCase):
    def test_builds_reproducible_offline_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            summary = build_sample(ROOT / "data" / "sample", output)
            vacancies = [
                json.loads(line)
                for line in (output / "vacancies.jsonl").read_text(encoding="utf-8").splitlines()
            ]
        self.assertEqual(summary["data_kind"], "synthetic_demo")
        self.assertEqual(summary["unique_vacancies"], 6)
        self.assertEqual(summary["vacancies_with_salary"], 5)
        self.assertEqual(len(vacancies), 6)
        one_bound = next(row for row in vacancies if row["vacancy_id"] == "demo-1004")
        self.assertIsNone(one_bound["salary_midpoint"])


if __name__ == "__main__":
    unittest.main()
