import unittest

from ingestion.normalize import normalize_vacancy


class NormalizeTests(unittest.TestCase):
    def test_two_bound_salary_has_midpoint(self):
        row = normalize_vacancy(
            {
                "id": "1",
                "name": "Data Analyst",
                "salary_range": {
                    "from": 100000,
                    "to": 200000,
                    "currency": "RUR",
                    "gross": False,
                    "frequency": {"id": "MONTHLY"},
                },
                "key_skills": [{"name": "SQL"}, {"name": "sql"}],
                "work_format": [{"id": "REMOTE"}],
            },
            job_groups=["data_analyst"],
        )
        self.assertEqual(row["salary_midpoint"], 150000.0)
        self.assertEqual(row["salary_period"], "MONTHLY")
        self.assertTrue(row["has_salary"])
        self.assertEqual(row["work_formats"], ["REMOTE"])

    def test_one_bound_salary_does_not_invent_midpoint(self):
        row = normalize_vacancy(
            {
                "id": "2",
                "name": "BI Developer",
                "salary_range": {"from": 120000, "to": None, "currency": "RUR"},
            }
        )
        self.assertEqual(row["salary_from"], 120000.0)
        self.assertIsNone(row["salary_midpoint"])
        self.assertTrue(row["has_salary"])

    def test_falls_back_to_legacy_salary_field(self):
        row = normalize_vacancy(
            {"id": "3", "name": "DE", "salary": {"from": 10, "to": 20}}
        )
        self.assertEqual(row["salary_midpoint"], 15.0)


if __name__ == "__main__":
    unittest.main()
