"""Опциональная запись RAW и аудита в PostgreSQL."""

import json
from typing import Any, Mapping, Optional

from ingestion.models import PlannedSegment
from ingestion.raw_store import payload_hash


class PostgresRawStore:
    def __init__(self, database_url: str, *, source: str = "hh_api") -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "Для записи в PostgreSQL установите зависимости: python3 -m pip install ."
            ) from exc
        self._connection = psycopg.connect(database_url, autocommit=True)
        self.run_id: Optional[str] = None
        self.source = source

    def start_run(self, run_id: str, parameters: Mapping[str, Any]) -> None:
        self.run_id = run_id
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit.etl_run (run_id, source, status, parameters)
                VALUES (%s, %s, 'running', %s::jsonb)
                """,
                (run_id, self.source, json.dumps(dict(parameters), ensure_ascii=False)),
            )

    def record_request(self, event: Mapping[str, Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit.api_request
                    (run_id, endpoint, query_params, status_code, attempt, duration_ms, error_message)
                VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)
                """,
                (
                    self.run_id,
                    event.get("path"),
                    json.dumps(event.get("params", {}), ensure_ascii=False),
                    event.get("status_code"),
                    event.get("attempt"),
                    event.get("duration_ms"),
                    event.get("error"),
                ),
            )

    def record_segment(self, planned: PlannedSegment, received: int = 0, status: Optional[str] = None) -> None:
        segment = planned.segment
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit.search_segment
                    (run_id, segment_id, parent_segment_id, job_group_code, query_params,
                     found, received, status, error_message)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                ON CONFLICT (run_id, segment_id) DO UPDATE SET
                    found = EXCLUDED.found,
                    received = EXCLUDED.received,
                    status = EXCLUDED.status,
                    error_message = EXCLUDED.error_message,
                    finished_at = CASE WHEN EXCLUDED.status IN ('success', 'over_limit', 'error')
                                       THEN now() ELSE NULL END
                """,
                (
                    self.run_id,
                    segment.segment_id,
                    segment.parent_id,
                    segment.job_group,
                    json.dumps(segment.as_dict(), ensure_ascii=False),
                    planned.found,
                    received,
                    status or planned.status,
                    planned.message,
                ),
            )

    def record_search_item(
        self,
        *,
        segment_id: str,
        page: int,
        vacancy_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO raw.search_response
                    (run_id, segment_id, page_number, vacancy_id, payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (run_id, segment_id, vacancy_id) DO UPDATE SET
                    page_number = EXCLUDED.page_number,
                    payload = EXCLUDED.payload,
                    ingested_at = now()
                """,
                (
                    self.run_id,
                    segment_id,
                    page,
                    vacancy_id,
                    json.dumps(dict(payload), ensure_ascii=False),
                ),
            )

    def record_detail(
        self,
        vacancy_id: str,
        source_updated_at: Optional[str],
        payload: Mapping[str, Any],
        comparison_marker: Optional[str] = None,
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO raw.vacancy_detail
                    (run_id, vacancy_id, source_updated_at, payload_hash, payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (vacancy_id, payload_hash) DO NOTHING
                """,
                (
                    self.run_id,
                    vacancy_id,
                    source_updated_at,
                    payload_hash(payload),
                    json.dumps(dict(payload), ensure_ascii=False),
                ),
            )

    def finish_run(self, status: str, counts: Mapping[str, Any], error: Optional[str] = None) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE audit.etl_run
                SET status = %s,
                    finished_at = now(),
                    rows_received = %s,
                    unique_vacancies = %s,
                    details_loaded = %s,
                    error_message = %s
                WHERE run_id = %s
                """,
                (
                    status,
                    counts.get("search_items", 0),
                    counts.get("unique_vacancies", 0),
                    counts.get("details_loaded", 0),
                    error,
                    self.run_id,
                ),
            )

    def close(self) -> None:
        self._connection.close()


class CompositeStore:
    """Записывает одно событие в файловое и PostgreSQL-хранилище."""

    def __init__(self, file_store: Any, *additional: Any) -> None:
        self.file_store = file_store
        self.stores = (file_store,) + additional

    def start_run(self, run_id: str, parameters: Mapping[str, Any]) -> None:
        started = []
        for store in self.stores:
            try:
                store.start_run(run_id, parameters)
            except Exception as exc:
                for previous in started:
                    try:
                        previous.finish_run("failed", {}, str(exc))
                    except Exception:
                        pass
                raise
            started.append(store)

    def record_request(self, event: Mapping[str, Any]) -> None:
        for store in self.stores:
            store.record_request(event)

    def record_segment(self, planned: PlannedSegment, received: int = 0, status: Optional[str] = None) -> None:
        for store in self.stores:
            store.record_segment(planned, received, status)

    def record_search_item(self, **kwargs: Any) -> None:
        for store in self.stores:
            store.record_search_item(**kwargs)

    def needs_detail(self, vacancy_id: str, comparison_marker: Optional[str], refresh: bool = False) -> bool:
        return self.file_store.needs_detail(vacancy_id, comparison_marker, refresh)

    def record_detail(
        self,
        vacancy_id: str,
        source_updated_at: Optional[str],
        payload: Mapping[str, Any],
        comparison_marker: Optional[str] = None,
    ) -> None:
        for store in self.stores:
            store.record_detail(
                vacancy_id,
                source_updated_at,
                payload,
                comparison_marker=comparison_marker,
            )

    def finish_run(self, status: str, counts: Mapping[str, Any], error: Optional[str] = None) -> None:
        for store in self.stores:
            store.finish_run(status, counts, error)
