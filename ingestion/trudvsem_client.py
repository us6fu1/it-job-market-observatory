"""Клиент открытого API «Работа России» и приведение ответа к общей модели."""

from dataclasses import dataclass
from datetime import datetime
import json
import os
import re
import time
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ingestion.hh_client import HhApiError, RequestHook


DEFAULT_BASE_URL = "https://opendata.trudvsem.ru/api/v1"


@dataclass(frozen=True)
class TrudvsemSettings:
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 30.0
    max_retries: int = 4
    retry_base_seconds: float = 1.0
    user_agent: str = "IT-Job-Market-Observatory/0.2"

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "TrudvsemSettings":
        values = os.environ if env is None else env
        return cls(
            base_url=values.get("TRUDVSEM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            timeout_seconds=float(values.get("TRUDVSEM_TIMEOUT_SECONDS", "30")),
            max_retries=int(values.get("TRUDVSEM_MAX_RETRIES", "4")),
            retry_base_seconds=float(values.get("TRUDVSEM_RETRY_BASE_SECONDS", "1")),
            user_agent=values.get(
                "TRUDVSEM_USER_AGENT", "IT-Job-Market-Observatory/0.2"
            ).strip(),
        )


# Поле skills у источника заполнено не всегда. Небольшой прозрачный словарь
# позволяет извлечь только явно упомянутые технологии из описания вакансии.
SKILL_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("SQL", r"(?<![a-z])sql(?![a-z])"),
    ("Python", r"(?<![a-z])python(?![a-z])"),
    ("PostgreSQL", r"postgres(?:ql)?"),
    ("Greenplum", r"greenplum"),
    ("ClickHouse", r"clickhouse"),
    ("Oracle", r"(?<![a-z])oracle(?![a-z])"),
    ("MS SQL Server", r"(?:ms\s*sql|sql\s*server)"),
    ("MySQL", r"mysql"),
    ("Hadoop", r"hadoop"),
    ("Spark", r"(?<![a-z])spark(?![a-z])"),
    ("Hive", r"(?<![a-z])hive(?![a-z])"),
    ("Kafka", r"kafka"),
    ("Airflow", r"airflow"),
    ("Power BI", r"power\s*bi"),
    ("Tableau", r"tableau"),
    ("Qlik", r"qlik(?:view|sense)?"),
    ("Superset", r"superset"),
    ("DAX", r"(?<![a-z])dax(?![a-z])"),
    ("Excel", r"excel"),
    ("Pandas", r"pandas"),
    ("NumPy", r"numpy"),
    ("Git", r"(?<![a-z])git(?![a-z])"),
    ("Docker", r"docker"),
    ("Kubernetes", r"kubernetes|k8s"),
    ("Linux", r"linux"),
    ("ETL", r"(?<![a-z])etl(?![a-z])"),
    ("REST API", r"rest(?:ful)?\s*api|rest\s+api"),
    ("FastAPI", r"fastapi"),
    ("RabbitMQ", r"rabbitmq"),
    ("DWH", r"(?<![a-z])dwh(?![a-z])|data\s*warehouse|хранилищ(?:е|ем)\s+данных"),
    ("Data Quality", r"data\s*quality|качество\s+данных"),
    ("Machine Learning", r"machine\s+learning|машинн(?:ое|ого)\s+обучен"),
    ("LLM", r"(?<![a-z])llm(?![a-z])|large\s+language\s+model|больш(?:ая|ие)\s+языков"),
    ("NLP", r"(?<![a-z])nlp(?![a-z])|natural\s+language\s+processing|обработк\S*\s+естественн\S*\s+язык"),
    ("PySpark", r"pyspark"),
)


SENSITIVE_SOURCE_KEY_PARTS = (
    "contact",
    "email",
    "phone",
    "telephone",
    "fax",
)


def sanitize_source_record(value: Any) -> Any:
    """Удаляет контактные поля, сохраняя остальные поля ответа источника."""
    if isinstance(value, Mapping):
        sanitized = {}
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-zа-я0-9]+", "", str(key).casefold())
            if any(part in normalized_key for part in SENSITIVE_SOURCE_KEY_PARTS):
                continue
            sanitized[str(key)] = sanitize_source_record(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_source_record(item) for item in value]
    return value


def _as_number(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _salary_bound(value: Any) -> Optional[float]:
    number = _as_number(value)
    # Источник использует 0 как техническое значение отсутствующей границы.
    return number if number is not None and number > 0 else None


def _timestamp(value: Any) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return "{}T00:00:00+00:00".format(text)
    return text


def extract_skills(vacancy: Mapping[str, Any]) -> List[str]:
    explicit = vacancy.get("skills") if isinstance(vacancy.get("skills"), list) else []
    text = " ".join(str(value) for value in explicit if str(value).strip()) + " "
    text += " ".join(
        str(vacancy.get(field) or "")
        for field in ("job-name", "requirements", "duty", "qualification")
    )
    text = text.casefold()
    found = set()
    for name, pattern in SKILL_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.add(name)
    return sorted(found, key=str.casefold)


def normalize_trudvsem_vacancy(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Возвращает обезличенную запись в формате общей модели проекта."""
    vacancy = payload.get("vacancy") if isinstance(payload.get("vacancy"), Mapping) else payload
    source_id = str(vacancy.get("id") or "").strip()
    if not source_id:
        raise ValueError("В ответе «Работы России» отсутствует id вакансии")

    company = vacancy.get("company") if isinstance(vacancy.get("company"), Mapping) else {}
    region = vacancy.get("region") if isinstance(vacancy.get("region"), Mapping) else {}
    requirement = (
        vacancy.get("requirement")
        if isinstance(vacancy.get("requirement"), Mapping)
        else {}
    )
    employment = str(vacancy.get("employment") or "")
    schedule = str(vacancy.get("schedule") or "")
    work_formats = []
    if "дистан" in "{} {}".format(employment, schedule).casefold():
        work_formats.append({"id": "remote", "name": "Удалённая работа"})
    elif employment or schedule:
        work_formats.append({"id": "on_site", "name": "Работа на месте"})

    salary_from = _salary_bound(vacancy.get("salary_min"))
    salary_to = _salary_bound(vacancy.get("salary_max"))
    salary_quality_issue = None
    if salary_from is not None and salary_to is not None and salary_from > salary_to:
        salary_quality_issue = "upper_bound_below_lower_bound"
        salary_to = None
    currency = str(vacancy.get("currency") or "").casefold()
    if "руб" in currency:
        currency = "RUR"
    else:
        currency = str(vacancy.get("currency") or "") or None

    descriptions = [
        str(vacancy.get("requirements") or "").strip(),
        str(vacancy.get("duty") or "").strip(),
    ]
    description = "\n\n".join(value for value in descriptions if value)
    experience = requirement.get("experience")
    experience_id = str(experience) if experience not in (None, "") else None
    return {
        "id": "trudvsem:{}".format(source_id),
        "source": {"id": "trudvsem", "name": "Работа России"},
        "source_vacancy_id": source_id,
        "name": vacancy.get("job-name"),
        "employer": {
            "id": str(company.get("companycode")) if company.get("companycode") else None,
            "name": company.get("name"),
        },
        "area": {
            "id": str(region.get("region_code")) if region.get("region_code") else None,
            "name": region.get("name"),
        },
        "published_at": _timestamp(vacancy.get("creation-date")),
        "created_at": _timestamp(vacancy.get("creation-date")),
        "updated_at": _timestamp(vacancy.get("date_modify")),
        "alternate_url": vacancy.get("vac_url"),
        "experience": {"id": experience_id, "name": experience_id},
        "employment": {"id": employment or None, "name": employment or None},
        "schedule": {"id": schedule or None, "name": schedule or None},
        "salary_range": {
            "from": salary_from,
            "to": salary_to,
            "currency": currency,
            "gross": None,
            "frequency": {"id": "month", "name": "За месяц"},
        },
        "work_format": work_formats,
        "key_skills": [{"name": name} for name in extract_skills(vacancy)],
        "professional_roles": [],
        "description": description,
        "source_metadata": {
            "typical_position": vacancy.get("typicalPosition"),
            "category": (
                vacancy.get("category", {}).get("specialisation")
                if isinstance(vacancy.get("category"), Mapping)
                else None
            ),
            "education": requirement.get("education"),
            "salary_quality_issue": salary_quality_issue,
        },
        # RAW сохраняет не только общую модель, но и обезличенную запись источника.
        # Контактные поля намеренно удаляются и не должны попадать в Git или DWH.
        "source_raw_sanitized": sanitize_source_record(vacancy),
    }


class TrudvsemClient:
    """Совместим с CollectionPipeline, но не требует токена."""

    def __init__(
        self,
        settings: TrudvsemSettings,
        *,
        opener: Callable[..., Any] = urlopen,
        sleep: Callable[[float], None] = time.sleep,
        request_hook: Optional[RequestHook] = None,
    ) -> None:
        self.settings = settings
        self._opener = opener
        self._sleep = sleep
        self._request_hook = request_hook
        self._details: Dict[str, Dict[str, Any]] = {}

    def _emit(self, event: Mapping[str, Any]) -> None:
        if self._request_hook is not None:
            self._request_hook(event)

    @staticmethod
    def _api_params(params: Mapping[str, Any]) -> Dict[str, Any]:
        if params.get("area"):
            raise ValueError(
                "Фильтр area из HH нельзя молча применять к «Работе России». "
                "Используйте отдельные региональные сегменты источника."
            )
        result: Dict[str, Any] = {
            "text": params.get("text", ""),
            "limit": min(int(params.get("per_page", 100)), 100),
            # В API offset является номером страницы, а не числом пропущенных строк.
            "offset": int(params.get("page", 0)),
        }
        if params.get("date_from"):
            result["modifiedFrom"] = "{}T00:00:00Z".format(params["date_from"])
        if params.get("date_to"):
            result["modifiedTo"] = "{}T23:59:59Z".format(params["date_to"])
        return result

    def request_json(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        api_params = self._api_params(params)
        url = "{}/vacancies?{}".format(self.settings.base_url, urlencode(api_params))
        attempts = self.settings.max_retries + 1
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            request = Request(
                url,
                headers={"Accept": "application/json", "User-Agent": self.settings.user_agent},
                method="GET",
            )
            try:
                with self._opener(request, timeout=self.settings.timeout_seconds) as response:
                    status = getattr(response, "status", 200)
                    payload = json.loads(response.read().decode("utf-8"))
                if str(payload.get("status")) != "200":
                    self._emit(
                        {
                            "path": "/vacancies",
                            "params": api_params,
                            "status_code": status,
                            "attempt": attempt,
                            "duration_ms": round((time.monotonic() - started) * 1000),
                            "error": "API status {}".format(payload.get("status")),
                        }
                    )
                    raise HhApiError("«Работа России» вернула ошибку в JSON-ответе")
                self._emit(
                    {
                        "path": "/vacancies",
                        "params": api_params,
                        "status_code": status,
                        "attempt": attempt,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                    }
                )
                return payload
            except HTTPError as exc:
                retryable = exc.code == 429 or 500 <= exc.code < 600
                self._emit(
                    {
                        "path": "/vacancies",
                        "params": api_params,
                        "status_code": exc.code,
                        "attempt": attempt,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        "error": str(exc),
                    }
                )
                if not retryable or attempt >= attempts:
                    raise HhApiError(
                        "API «Работа России» вернул HTTP {}".format(exc.code)
                    ) from exc
                self._sleep(self.settings.retry_base_seconds * (2 ** (attempt - 1)))
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                self._emit(
                    {
                        "path": "/vacancies",
                        "params": api_params,
                        "status_code": None,
                        "attempt": attempt,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        "error": str(exc),
                    }
                )
                if attempt >= attempts:
                    raise HhApiError(
                        "Не удалось получить корректный ответ «Работы России»"
                    ) from exc
                self._sleep(self.settings.retry_base_seconds * (2 ** (attempt - 1)))
        raise AssertionError("Недостижимая ветка")

    def count(self, params: Mapping[str, Any]) -> int:
        count_params = dict(params)
        count_params.update({"page": 0, "per_page": 1})
        payload = self.request_json(count_params)
        return int(payload.get("meta", {}).get("total", 0))

    def iter_search_pages(self, params: Mapping[str, Any]) -> Iterator[Dict[str, Any]]:
        page = 0
        per_page = 100
        while True:
            page_params = dict(params)
            page_params.update({"page": page, "per_page": per_page})
            payload = self.request_json(page_params)
            total = int(payload.get("meta", {}).get("total", 0))
            source_rows = payload.get("results", {}).get("vacancies", [])
            items = [normalize_trudvsem_vacancy(row) for row in source_rows]
            for item in items:
                self._details[str(item["id"])] = item
            pages = (total + per_page - 1) // per_page if total else 0
            yield {
                "items": items,
                "found": total,
                "pages": pages,
                "page": page,
                "per_page": per_page,
            }
            if not items or page + 1 >= pages:
                break
            page += 1

    def get_vacancy(self, vacancy_id: str) -> Dict[str, Any]:
        try:
            return self._details[vacancy_id]
        except KeyError as exc:
            raise HhApiError(
                "Карточка {} отсутствует в текущей странице источника".format(vacancy_id)
            ) from exc

