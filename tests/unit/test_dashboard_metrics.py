import unittest
from datetime import datetime, timezone

from dashboard.metrics import filtered_skill_rows, filtered_weekly_rows


class DashboardMetricsTests(unittest.TestCase):
    def setUp(self):
        self.run = {
            "parameters": {
                "segments": [
                    {"date_from": "2026-10-01", "date_to": "2026-10-31"}
                ]
            }
        }
        self.vacancies = [
            {
                "vacancy_id": "1",
                "published_at": datetime(2026, 10, 5, tzinfo=timezone.utc),
                "job_groups": ["Data Analyst"],
                "skills": ["SQL", "Python"],
            },
            {
                "vacancy_id": "2",
                "published_at": datetime(2026, 10, 6, tzinfo=timezone.utc),
                "job_groups": ["Data Engineer"],
                "skills": ["SQL", "Airflow"],
            },
            {
                "vacancy_id": "3",
                "published_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "job_groups": ["Data Analyst"],
                "skills": ["Excel"],
            },
        ]

    def test_skills_use_only_already_filtered_vacancies(self):
        rows = filtered_skill_rows(self.vacancies[:1], ["Data Analyst"])
        self.assertEqual(
            rows,
            [
                {"Навык": "Python", "Вакансии": 1, "Направление": "Data Analyst"},
                {"Навык": "SQL", "Вакансии": 1, "Направление": "Data Analyst"},
            ],
        )

    def test_weekly_rows_respect_group_and_analysis_window(self):
        rows = filtered_weekly_rows(self.vacancies, ["Data Analyst"], self.run)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Направление"], "Data Analyst")
        self.assertEqual(rows[0]["Неделя"].isoformat(), "2026-10-05")
        self.assertEqual(rows[0]["Новые вакансии"], 1)


if __name__ == "__main__":
    unittest.main()
