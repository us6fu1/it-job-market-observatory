"""Планирование поисковых сегментов с учётом лимита HH в 2 000 записей."""

from collections import deque
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Callable, Iterable, List, Mapping, Sequence, Tuple

from ingestion.models import PlannedSegment, SearchSegment


Probe = Callable[[SearchSegment], int]


def _halves(values: Sequence[str]) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    middle = len(values) // 2
    return tuple(values[:middle]), tuple(values[middle:])


def split_segment(segment: SearchSegment) -> Tuple[SearchSegment, SearchSegment]:
    """Делит сегмент по датам, затем по профролям и регионам."""
    if segment.date_from < segment.date_to:
        span_days = (segment.date_to - segment.date_from).days
        left_end = segment.date_from + timedelta(days=span_days // 2)
        right_start = left_end + timedelta(days=1)
        return (
            segment.child(date_to=left_end),
            segment.child(date_from=right_start),
        )
    if len(segment.professional_role_ids) > 1:
        left, right = _halves(segment.professional_role_ids)
        return (
            segment.child(professional_role_ids=left),
            segment.child(professional_role_ids=right),
        )
    if len(segment.area_ids) > 1:
        left, right = _halves(segment.area_ids)
        return (
            segment.child(area_ids=left),
            segment.child(area_ids=right),
        )
    raise ValueError("Сегмент больше нельзя безопасно разделить")


def plan_segments(
    initial_segments: Iterable[SearchSegment],
    probe: Probe,
    *,
    result_limit: int = 2000,
) -> List[PlannedSegment]:
    """Возвращает непересекающиеся листья плана и не скрывает переполнение."""
    queue = deque(initial_segments)
    result: List[PlannedSegment] = []
    while queue:
        segment = queue.popleft()
        found = int(probe(segment))
        if found <= result_limit:
            result.append(PlannedSegment(segment, found, "ready"))
            continue
        try:
            left, right = split_segment(segment)
        except ValueError:
            result.append(
                PlannedSegment(
                    segment,
                    found,
                    "over_limit",
                    "Даже минимальный сегмент превышает лимит {}".format(result_limit),
                )
            )
        else:
            queue.append(left)
            queue.append(right)
    return result


def load_segments(path: Path) -> List[SearchSegment]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    global_from = payload.get("date_from")
    global_to = payload.get("date_to")
    segments = []
    for item in payload.get("segments", []):
        date_from = item.get("date_from", global_from)
        date_to = item.get("date_to", global_to)
        if not date_from or not date_to:
            raise ValueError("Для каждого сегмента нужны date_from и date_to")
        segments.append(
            SearchSegment(
                job_group=item["job_group"],
                text=item.get("text", ""),
                date_from=date.fromisoformat(date_from),
                date_to=date.fromisoformat(date_to),
                area_ids=tuple(str(value) for value in item.get("area_ids", [])),
                professional_role_ids=tuple(
                    str(value) for value in item.get("professional_role_ids", [])
                ),
            )
        )
    if not segments:
        raise ValueError("Конфигурация не содержит поисковых сегментов")
    return segments
