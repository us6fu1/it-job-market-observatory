"""Чистые функции для пересчёта показателей после фильтров дашборда."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


def analysis_bounds(run: Mapping[str, Any]) -> Optional[Tuple[date, date]]:
    parameters = run.get("parameters")
    if not isinstance(parameters, Mapping):
        return None
    segments = parameters.get("segments")
    if not isinstance(segments, list):
        return None
    starts = []
    ends = []
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        try:
            starts.append(date.fromisoformat(str(segment["date_from"])))
            ends.append(date.fromisoformat(str(segment["date_to"])))
        except (KeyError, TypeError, ValueError):
            continue
    if not starts or not ends:
        return None
    return min(starts), max(ends)


def filtered_skill_rows(
    vacancies: Iterable[Mapping[str, Any]],
    selected_groups: Sequence[str],
    *,
    limit_per_group: int = 10,
) -> List[Dict[str, Any]]:
    selected = set(selected_groups)
    counts: Counter = Counter()
    for vacancy in vacancies:
        groups = set(vacancy.get("job_groups") or [])
        skills = set(vacancy.get("skills") or [])
        for group in groups:
            if selected and group not in selected:
                continue
            for skill in skills:
                counts[(group, skill)] += 1

    grouped: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for (group, skill), count in counts.items():
        grouped[group].append((skill, count))

    rows = []
    for group in sorted(grouped):
        ranked = sorted(grouped[group], key=lambda item: (-item[1], item[0]))
        for skill, count in ranked[:limit_per_group]:
            rows.append(
                {"Навык": skill, "Вакансии": count, "Направление": group}
            )
    return rows


def filtered_weekly_rows(
    vacancies: Iterable[Mapping[str, Any]],
    selected_groups: Sequence[str],
    run: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    selected = set(selected_groups)
    bounds = analysis_bounds(run)
    counts: Counter = Counter()
    for vacancy in vacancies:
        published = vacancy.get("published_at")
        if isinstance(published, datetime):
            published_date = published.date()
        elif isinstance(published, date):
            published_date = published
        else:
            try:
                published_date = datetime.fromisoformat(str(published)).date()
            except (TypeError, ValueError):
                continue
        if bounds and not (bounds[0] <= published_date <= bounds[1]):
            continue
        week_start = published_date - timedelta(days=published_date.weekday())
        for group in set(vacancy.get("job_groups") or []):
            if selected and group not in selected:
                continue
            counts[(week_start, group)] += 1

    return [
        {"Неделя": week, "Направление": group, "Новые вакансии": count}
        for (week, group), count in sorted(counts.items())
    ]
