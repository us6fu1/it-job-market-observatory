import json
import unittest
from urllib.error import URLError

from ingestion.trudvsem_client import (
    TrudvsemClient,
    TrudvsemSettings,
    extract_skills,
    normalize_trudvsem_vacancy,
)


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


def source_vacancy():
    return {
        "vacancy": {
            "id": "abc-123",
            "job-name": "Аналитик данных",
            "creation-date": "2026-10-01",
            "date_modify": "2026-10-20T12:00:00+0300",
            "salary_min": 100000,
            "salary_max": 160000,
            "currency": "руб.",
            "employment": "Дистанционная (удаленная) работа",
            "schedule": "Полный рабочий день",
            "requirements": "Уверенный SQL, Python, PostgreSQL и Power BI",
            "duty": "Разработка ETL-процессов и отчётов",
            "skills": ["Коммуникация"],
            "company": {
                "companycode": "company-1",
                "name": "Тестовая компания",
                "email": "private@example.test",
            },
            "region": {"region_code": "77", "name": "Москва"},
            "requirement": {"experience": 1, "education": "Высшее"},
            "contact_person": "Не должен попасть в общую модель",
            "contact_list": [{"contact_type": "Телефон", "contact_value": "+7000"}],
            "vac_url": "https://trudvsem.ru/vacancy/card/test",
        }
    }


class TrudvsemNormalizeTests(unittest.TestCase):
    def test_extracts_only_known_technical_skills(self):
        skills = extract_skills(source_vacancy()["vacancy"])
        for expected in ("SQL", "Python", "PostgreSQL", "Power BI", "ETL"):
            with self.subTest(expected=expected):
                self.assertIn(expected, skills)
        self.assertNotIn("Коммуникация", skills)

    def test_normalizes_and_removes_contacts(self):
        result = normalize_trudvsem_vacancy(source_vacancy())
        self.assertEqual(result["id"], "trudvsem:abc-123")
        self.assertEqual(result["salary_range"]["currency"], "RUR")
        self.assertEqual(result["work_format"][0]["id"], "remote")
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("private@example.test", serialized)
        self.assertNotIn("+7000", serialized)
        self.assertNotIn("Не должен попасть", serialized)
        self.assertEqual(result["source_raw_sanitized"]["salary_min"], 100000)
        self.assertEqual(
            result["source_raw_sanitized"]["company"]["name"],
            "Тестовая компания",
        )

    def test_zero_salary_bound_is_treated_as_missing(self):
        payload = source_vacancy()
        payload["vacancy"]["salary_max"] = 0
        result = normalize_trudvsem_vacancy(payload)
        self.assertEqual(result["salary_range"]["from"], 100000.0)
        self.assertIsNone(result["salary_range"]["to"])


class TrudvsemClientTests(unittest.TestCase):
    def test_count_maps_dates_and_pagination(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            return FakeResponse(
                {
                    "status": "200",
                    "meta": {"total": 42, "limit": 1},
                    "results": {"vacancies": []},
                }
            )

        client = TrudvsemClient(TrudvsemSettings(), opener=opener)
        total = client.count(
            {
                "text": "аналитик данных",
                "date_from": "2026-10-01",
                "date_to": "2026-10-02",
            }
        )
        self.assertEqual(total, 42)
        self.assertIn("limit=1", captured["url"])
        self.assertIn("offset=0", captured["url"])
        self.assertIn("modifiedFrom=2026-10-01T00%3A00%3A00Z", captured["url"])

    def test_yields_canonical_items_and_reuses_them_as_details(self):
        def opener(request, timeout):
            return FakeResponse(
                {
                    "status": "200",
                    "meta": {"total": 1, "limit": 100},
                    "results": {"vacancies": [source_vacancy()]},
                }
            )

        client = TrudvsemClient(TrudvsemSettings(), opener=opener)
        page = next(client.iter_search_pages({"text": "аналитик"}))
        vacancy = page["items"][0]
        self.assertEqual(page["found"], 1)
        self.assertEqual(vacancy["id"], "trudvsem:abc-123")
        self.assertEqual(client.get_vacancy(vacancy["id"]), vacancy)

    def test_audits_network_error_before_retry(self):
        events = []
        sleeps = []
        attempts = iter(
            [
                URLError("temporary network failure"),
                FakeResponse(
                    {
                        "status": "200",
                        "meta": {"total": 0},
                        "results": {"vacancies": []},
                    }
                ),
            ]
        )

        def opener(request, timeout):
            result = next(attempts)
            if isinstance(result, Exception):
                raise result
            return result

        client = TrudvsemClient(
            TrudvsemSettings(max_retries=1, retry_base_seconds=0.25),
            opener=opener,
            sleep=sleeps.append,
            request_hook=events.append,
        )
        payload = client.request_json({"text": "аналитик"})

        self.assertEqual(payload["status"], "200")
        self.assertEqual(sleeps, [0.25])
        self.assertEqual(len(events), 2)
        self.assertIn("temporary network failure", events[0]["error"])
        self.assertIsNone(events[0]["status_code"])
        self.assertNotIn("error", events[1])


if __name__ == "__main__":
    unittest.main()

