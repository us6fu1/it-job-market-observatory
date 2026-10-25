"""Преобразование ответа HH в плоскую запись без спорных допущений."""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional


def _number(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _object_id(value: Any) -> Optional[str]:
    if isinstance(value, Mapping):
        raw = value.get("id")
        return str(raw) if raw is not None else None
    return None


def _object_name(value: Any) -> Optional[str]:
    if isinstance(value, Mapping):
        raw = value.get("name")
        return str(raw) if raw is not None else None
    return None


def _salary(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    value = payload.get("salary_range") or payload.get("salary") or {}
    return value if isinstance(value, Mapping) else {}


def _salary_period(value: Mapping[str, Any]) -> Optional[str]:
    for key in ("frequency", "mode", "period"):
        item = value.get(key)
        if isinstance(item, Mapping) and item.get("id") is not None:
            return str(item["id"])
        if isinstance(item, str):
            return item
    return None


def _work_formats(payload: Mapping[str, Any]) -> List[str]:
    source = payload.get("work_format") or payload.get("work_formats") or []
    if isinstance(source, Mapping):
        source = [source]
    result = []
    for item in source if isinstance(source, list) else []:
        value = _object_id(item) or _object_name(item)
        if value and value not in result:
            result.append(value)
    return result


def normalize_vacancy(
    payload: Mapping[str, Any],
    *,
    job_groups: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    salary = _salary(payload)
    salary_from = _number(salary.get("from"))
    salary_to = _number(salary.get("to"))
    midpoint = None
    if salary_from is not None and salary_to is not None:
        midpoint = (salary_from + salary_to) / Decimal("2")

    employer = payload.get("employer") if isinstance(payload.get("employer"), Mapping) else {}
    area = payload.get("area") if isinstance(payload.get("area"), Mapping) else {}
    key_skills = payload.get("key_skills") if isinstance(payload.get("key_skills"), list) else []
    roles = (
        payload.get("professional_roles")
        if isinstance(payload.get("professional_roles"), list)
        else []
    )
    groups = sorted(set(job_groups or []))
    return {
        "vacancy_id": str(payload.get("id")) if payload.get("id") is not None else None,
        "name": payload.get("name"),
        "employer_id": str(employer.get("id")) if employer.get("id") is not None else None,
        "employer_name": employer.get("name"),
        "area_id": str(area.get("id")) if area.get("id") is not None else None,
        "area_name": area.get("name"),
        "published_at": payload.get("published_at"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "alternate_url": payload.get("alternate_url"),
        "experience_id": _object_id(payload.get("experience")),
        "employment_id": _object_id(payload.get("employment")),
        "schedule_id": _object_id(payload.get("schedule")),
        "salary_from": float(salary_from) if salary_from is not None else None,
        "salary_to": float(salary_to) if salary_to is not None else None,
        "salary_midpoint": float(midpoint) if midpoint is not None else None,
        "salary_currency": salary.get("currency"),
        "salary_gross": salary.get("gross"),
        "salary_period": _salary_period(salary),
        "has_salary": salary_from is not None or salary_to is not None,
        "work_formats": _work_formats(payload),
        "key_skills": sorted(
            {
                str(item.get("name")).strip()
                for item in key_skills
                if isinstance(item, Mapping) and item.get("name")
            },
            key=str.casefold,
        ),
        "professional_role_ids": sorted(
            {
                str(item.get("id"))
                for item in roles
                if isinstance(item, Mapping) and item.get("id") is not None
            }
        ),
        "job_groups": groups,
    }
