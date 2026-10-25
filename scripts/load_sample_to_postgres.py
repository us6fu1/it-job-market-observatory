#!/usr/bin/env python3
"""Загружает вымышленные примеры в RAW для интеграционной проверки PostgreSQL."""

import argparse
from collections import defaultdict
from datetime import date
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.models import PlannedSegment, SearchSegment
from ingestion.postgres_store import PostgresRawStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--sample-dir", type=Path, default=ROOT / "data" / "sample")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("Задайте DATABASE_URL или передайте --database-url")

    search = json.loads((args.sample_dir / "search_response.json").read_text(encoding="utf-8"))
    details = json.loads((args.sample_dir / "vacancy_details.json").read_text(encoding="utf-8"))
    assignments = json.loads(
        (args.sample_dir / "sample_groups.json").read_text(encoding="utf-8")
    )["assignments"]

    groups_by_vacancy = defaultdict(set)
    vacancy_ids_by_group = defaultdict(set)
    for item in assignments:
        vacancy_id = str(item["vacancy_id"])
        job_group = item["job_group"]
        groups_by_vacancy[vacancy_id].add(job_group)
        vacancy_ids_by_group[job_group].add(vacancy_id)

    search_by_id = {str(item["id"]): item for item in search["items"]}
    details_by_id = {str(item["id"]): item for item in details}
    run_id = str(uuid4())
    store = PostgresRawStore(args.database_url, source="synthetic_demo")
    counts = {
        "search_items": 0,
        "unique_vacancies": len(search_by_id),
        "details_loaded": len(details_by_id),
    }
    store.start_run(
        run_id,
        {
            "data_kind": "synthetic_demo",
            "warning": "Вымышленные данные для интеграционной проверки",
        },
    )
    try:
        for job_group, vacancy_ids in sorted(vacancy_ids_by_group.items()):
            segment = SearchSegment(
                job_group=job_group,
                text="synthetic demo",
                date_from=date(2026, 10, 1),
                date_to=date(2026, 10, 5),
            )
            planned = PlannedSegment(segment, len(vacancy_ids), "ready")
            store.record_segment(planned, status="running")
            for vacancy_id in sorted(vacancy_ids):
                store.record_search_item(
                    segment_id=segment.segment_id,
                    page=0,
                    vacancy_id=vacancy_id,
                    payload=search_by_id[vacancy_id],
                )
                counts["search_items"] += 1
            store.record_segment(planned, received=len(vacancy_ids), status="success")

        for vacancy_id, payload in sorted(details_by_id.items()):
            store.record_detail(
                vacancy_id,
                payload.get("updated_at"),
                payload,
                comparison_marker=payload.get("updated_at"),
            )
        store.finish_run("success", counts)
    except Exception as exc:
        store.finish_run("failed", counts, str(exc))
        raise
    finally:
        store.close()

    print(
        json.dumps(
            {"run_id": run_id, "status": "success", **counts},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
