import unittest
from datetime import datetime, timezone

from dashboard.metrics import (
    analysis_bounds,
    filtered_salary_rows,
    filtered_skill_rows,
    filtered_weekly_rows,
)


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
                "salary_from": 100000,
                "salary_to": 140000,
                "salary_currency": "RUR",
            },
            {
                "vacancy_id": "2",
                "published_at": datetime(2026, 10, 6, tzinfo=timezone.utc),
                "job_groups": ["Data Engineer"],
                "skills": ["SQL", "Airflow"],
                "salary_from": 160000,
                "salary_to": 200000,
                "salary_currency": "RUR",
            },
            {
                "vacancy_id": "3",
                "published_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "job_groups": ["Data Analyst"],
                "skills": ["Excel"],
                "salary_from": 90000,
                "salary_to": None,
                "salary_currency": "RUR",
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

    def test_analysis_bounds_combines_latest_runs_from_multiple_sources(self):
        runs = [
            self.run,
            {
                "parameters": {
                    "segments": [
                        {"date_from": "2026-09-01", "date_to": "2026-09-30"}
                    ]
                }
            },
        ]
        self.assertEqual(
            analysis_bounds(runs),
            (datetime(2026, 9, 1).date(), datetime(2026, 10, 31).date()),
        )

    def test_salary_rows_use_only_complete_ranges_and_selected_groups(self):
        rows = filtered_salary_rows(self.vacancies, ["Data Analyst"])
        self.assertEqual(
            rows,
            [
                {
                    "Направление": "Data Analyst",
                    "Валюта": "RUR",
                    "Полных вилок": 1,
                    "Медиана середины вилки": 120000.0,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
