"""Небольшие модели, общие для планировщика и загрузчика."""

from dataclasses import dataclass, replace
from datetime import date
import hashlib
import json
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class SearchSegment:
    job_group: str
    text: str
    date_from: date
    date_to: date
    area_ids: Tuple[str, ...] = ()
    professional_role_ids: Tuple[str, ...] = ()
    parent_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.date_from > self.date_to:
            raise ValueError("date_from не может быть позже date_to")
        if not self.job_group.strip():
            raise ValueError("job_group не может быть пустым")

    @property
    def segment_id(self) -> str:
        raw = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
        return "{}-{}".format(self.job_group, digest)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "job_group": self.job_group,
            "text": self.text,
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "area_ids": list(self.area_ids),
            "professional_role_ids": list(self.professional_role_ids),
        }

    def hh_params(self, page: int = 0, per_page: int = 100) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "text": self.text,
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "page": page,
            "per_page": per_page,
        }
        if self.area_ids:
            params["area"] = list(self.area_ids)
        if self.professional_role_ids:
            params["professional_role"] = list(self.professional_role_ids)
        return params

    def child(self, **changes: Any) -> "SearchSegment":
        return replace(self, parent_id=self.segment_id, **changes)


@dataclass(frozen=True)
class PlannedSegment:
    segment: SearchSegment
    found: int
    status: str
    message: Optional[str] = None
