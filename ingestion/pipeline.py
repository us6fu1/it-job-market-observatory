"""Оркестрация живой загрузки и воспроизводимого офлайн-примера."""

from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Optional
from uuid import uuid4

from ingestion.hh_client import HhClient
from ingestion.models import PlannedSegment, SearchSegment
from ingestion.normalize import normalize_vacancy
from ingestion.raw_store import payload_hash
from ingestion.segmentation import plan_segments


class CollectionPipeline:
    def __init__(
        self,
        client: HhClient,
        store: Any,
        *,
        refresh_details: bool = False,
        result_limit: int = 2000,
    ) -> None:
        self.client = client
        self.store = store
        self.refresh_details = refresh_details
        self.result_limit = result_limit

    def collect(self, segments: Iterable[SearchSegment]) -> Dict[str, Any]:
        segment_list = list(segments)
        run_id = str(uuid4())
        parameters = {"segments": [segment.as_dict() for segment in segment_list]}
        counts: Dict[str, int] = {
            "segments_ready": 0,
            "segments_over_limit": 0,
            "search_items": 0,
            "unique_vacancies": 0,
            "details_loaded": 0,
            "filtered_out": 0,
        }
        seen_vacancies = set()
        detailed_vacancies = set()
        self.store.start_run(run_id, parameters)
        try:
            planned = plan_segments(
                segment_list,
                lambda segment: self.client.count(segment.hh_params()),
                result_limit=self.result_limit,
            )
            for item in planned:
                if item.status == "over_limit":
                    counts["segments_over_limit"] += 1
                    self.store.record_segment(item, status="over_limit")
                    continue
                counts["segments_ready"] += 1
                self.store.record_segment(item, status="running")
                received = self._collect_segment(
                    item,
                    seen_vacancies,
                    detailed_vacancies,
                    counts,
                )
                self.store.record_segment(item, received=received, status="success")
            counts["unique_vacancies"] = len(seen_vacancies)
            final_status = "partial" if counts["segments_over_limit"] else "success"
            self.store.finish_run(final_status, counts)
            return {"run_id": run_id, "status": final_status, **counts}
        except Exception as exc:
            counts["unique_vacancies"] = len(seen_vacancies)
            self.store.finish_run("failed", counts, str(exc))
            raise

    def _collect_segment(
        self,
        planned: PlannedSegment,
        seen_vacancies: set,
        detailed_vacancies: set,
        counts: Dict[str, int],
    ) -> int:
        segment = planned.segment
        received = 0
        for page_number, response in enumerate(
            self.client.iter_search_pages(segment.hh_params())
        ):
            for payload in response.get("items", []):
                if not segment.matches_title(payload.get("name")):
                    counts["filtered_out"] += 1
                    continue
                vacancy_id = str(payload.get("id"))
                if not vacancy_id or vacancy_id == "None":
                    continue
                received += 1
                counts["search_items"] += 1
                seen_vacancies.add(vacancy_id)
                self.store.record_search_item(
                    segment_id=segment.segment_id,
                    page=page_number,
                    vacancy_id=vacancy_id,
                    payload=payload,
                )
                comparison_marker = payload.get("updated_at") or payload_hash(payload)
                if (
                    vacancy_id not in detailed_vacancies
                    and self.store.needs_detail(
                        vacancy_id,
                        comparison_marker,
                        self.refresh_details,
                    )
                ):
                    detail = self.client.get_vacancy(vacancy_id)
                    detail_changed_at = detail.get("updated_at") or payload.get("updated_at")
                    self.store.record_detail(
                        vacancy_id,
                        detail_changed_at,
                        detail,
                        comparison_marker=comparison_marker,
                    )
                    detailed_vacancies.add(vacancy_id)
                    counts["details_loaded"] += 1
        return received


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def build_sample(sample_dir: Path, output_dir: Path) -> Dict[str, Any]:
    """Создаёт офлайн-результат. Эти строки нельзя считать данными рынка."""
    search = json.loads((sample_dir / "search_response.json").read_text(encoding="utf-8"))
    details = json.loads((sample_dir / "vacancy_details.json").read_text(encoding="utf-8"))
    groups_payload = json.loads((sample_dir / "sample_groups.json").read_text(encoding="utf-8"))

    groups_by_vacancy = defaultdict(set)
    for item in groups_payload.get("assignments", []):
        groups_by_vacancy[str(item["vacancy_id"])].add(item["job_group"])

    search_by_id = {
        str(item["id"]): item for item in search.get("items", []) if item.get("id") is not None
    }
    detail_by_id = {
        str(item["id"]): item for item in details if item.get("id") is not None
    }
    vacancy_ids = sorted(set(search_by_id) | set(detail_by_id))
    normalized: List[Dict[str, Any]] = []
    raw_rows = []
    for vacancy_id in vacancy_ids:
        payload = dict(search_by_id.get(vacancy_id, {}))
        payload.update(detail_by_id.get(vacancy_id, {}))
        raw_rows.append({"vacancy_id": vacancy_id, "payload": payload})
        normalized.append(
            normalize_vacancy(payload, job_groups=groups_by_vacancy.get(vacancy_id, set()))
        )

    skill_rows = [
        {"vacancy_id": row["vacancy_id"], "skill": skill}
        for row in normalized
        for skill in row["key_skills"]
    ]
    salary_values = [
        row["salary_midpoint"]
        for row in normalized
        if row["salary_midpoint"] is not None
    ]
    skill_counts = Counter(row["skill"] for row in skill_rows)
    group_counts = Counter(
        group for row in normalized for group in row.get("job_groups", [])
    )
    salary_count = sum(1 for row in normalized if row["has_salary"])
    summary = {
        "data_kind": "synthetic_demo",
        "warning": "Демонстрационные записи не являются результатами исследования HH.",
        "unique_vacancies": len(normalized),
        "vacancies_with_salary": salary_count,
        "salary_coverage": round(salary_count / len(normalized), 4) if normalized else 0,
        "median_two_bound_salary_midpoint": median(salary_values) if salary_values else None,
        "skill_rows": len(skill_rows),
        "top_skills": dict(skill_counts.most_common(10)),
        "vacancies_by_job_group": dict(sorted(group_counts.items())),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "raw_vacancies.jsonl", raw_rows)
    _write_jsonl(output_dir / "vacancies.jsonl", normalized)
    _write_jsonl(output_dir / "skills.jsonl", skill_rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
