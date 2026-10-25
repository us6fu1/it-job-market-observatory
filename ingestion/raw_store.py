"""Файловое RAW-хранилище и аудит, доступные без PostgreSQL."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ingestion.models import PlannedSegment


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def payload_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FileRawStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.run_id: Optional[str] = None
        self.run_dir: Optional[Path] = None
        self._manifest: Dict[str, Any] = {}
        self._detail_state_path = self.root / "state" / "detail_state.json"
        self._detail_state = self._read_json(self._detail_state_path, {})

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _atomic_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _append(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def _require_run(self) -> Path:
        if self.run_dir is None:
            raise RuntimeError("Запуск RAW-хранилища не начат")
        return self.run_dir

    def start_run(self, run_id: str, parameters: Mapping[str, Any]) -> None:
        self.run_id = run_id
        self.run_dir = self.root / "runs" / run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self._manifest = {
            "run_id": run_id,
            "status": "running",
            "started_at": utc_now(),
            "parameters": dict(parameters),
        }
        self._atomic_json(self.run_dir / "manifest.json", self._manifest)

    def record_request(self, event: Mapping[str, Any]) -> None:
        row = dict(event)
        row["run_id"] = self.run_id
        row["requested_at"] = utc_now()
        self._append(self._require_run() / "api_requests.jsonl", row)

    def record_segment(self, planned: PlannedSegment, received: int = 0, status: Optional[str] = None) -> None:
        segment = planned.segment
        self._append(
            self._require_run() / "segments.jsonl",
            {
                "run_id": self.run_id,
                "segment_id": segment.segment_id,
                "parent_id": segment.parent_id,
                "job_group": segment.job_group,
                "query": segment.as_dict(),
                "found": planned.found,
                "received": received,
                "status": status or planned.status,
                "message": planned.message,
                "recorded_at": utc_now(),
            },
        )

    def record_search_item(
        self,
        *,
        segment_id: str,
        page: int,
        vacancy_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        self._append(
            self._require_run() / "search_items.jsonl",
            {
                "run_id": self.run_id,
                "segment_id": segment_id,
                "page": page,
                "vacancy_id": vacancy_id,
                "collected_at": utc_now(),
                "payload": dict(payload),
            },
        )

    def needs_detail(self, vacancy_id: str, comparison_marker: Optional[str], refresh: bool = False) -> bool:
        if refresh:
            return True
        previous = self._detail_state.get(vacancy_id)
        if previous is None:
            return True
        previous_marker = previous.get("comparison_marker", previous.get("source_updated_at"))
        return previous_marker != comparison_marker

    def record_detail(
        self,
        vacancy_id: str,
        source_updated_at: Optional[str],
        payload: Mapping[str, Any],
        comparison_marker: Optional[str] = None,
    ) -> None:
        digest = payload_hash(payload)
        self._append(
            self._require_run() / "vacancy_details.jsonl",
            {
                "run_id": self.run_id,
                "vacancy_id": vacancy_id,
                "source_updated_at": source_updated_at,
                "payload_hash": digest,
                "loaded_at": utc_now(),
                "payload": dict(payload),
            },
        )
        self._detail_state[vacancy_id] = {
            "source_updated_at": source_updated_at,
            "comparison_marker": comparison_marker or source_updated_at,
            "payload_hash": digest,
            "last_loaded_at": utc_now(),
        }

    def finish_run(self, status: str, counts: Mapping[str, Any], error: Optional[str] = None) -> None:
        self._manifest.update(
            {
                "status": status,
                "finished_at": utc_now(),
                "counts": dict(counts),
                "error": error,
            }
        )
        self._atomic_json(self._require_run() / "manifest.json", self._manifest)
        self._atomic_json(self._detail_state_path, self._detail_state)
