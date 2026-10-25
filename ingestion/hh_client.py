"""Минимальный клиент официального API HeadHunter."""

import json
import time
from typing import Any, Callable, Dict, Iterator, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ingestion.config import HhSettings


class HhApiError(RuntimeError):
    """Ошибка API после исчерпания повторных попыток."""


RequestHook = Callable[[Mapping[str, Any]], None]


class HhClient:
    def __init__(
        self,
        settings: HhSettings,
        *,
        opener: Callable[..., Any] = urlopen,
        sleep: Callable[[float], None] = time.sleep,
        request_hook: Optional[RequestHook] = None,
    ) -> None:
        self.settings = settings
        self._opener = opener
        self._sleep = sleep
        self._request_hook = request_hook

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.settings.user_agent,
            "HH-User-Agent": self.settings.user_agent,
        }
        if self.settings.oauth_token:
            headers["Authorization"] = "Bearer {}".format(self.settings.oauth_token)
        return headers

    def _emit(self, event: Mapping[str, Any]) -> None:
        if self._request_hook is not None:
            self._request_hook(event)

    def request_json(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        query = urlencode(params or {}, doseq=True)
        url = "{}{}{}".format(
            self.settings.base_url,
            path if path.startswith("/") else "/{}".format(path),
            "?{}".format(query) if query else "",
        )
        attempts = self.settings.max_retries + 1
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            request = Request(url, headers=self._headers(), method="GET")
            try:
                with self._opener(request, timeout=self.settings.timeout_seconds) as response:
                    status = getattr(response, "status", 200)
                    payload = json.loads(response.read().decode("utf-8"))
                self._emit(
                    {
                        "path": path,
                        "params": dict(params or {}),
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
                        "path": path,
                        "params": dict(params or {}),
                        "status_code": exc.code,
                        "attempt": attempt,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        "error": str(exc),
                    }
                )
                if not retryable or attempt >= attempts:
                    raise HhApiError("HH API вернул HTTP {} для {}".format(exc.code, path)) from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = self._retry_delay(attempt, retry_after)
                self._sleep(delay)
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                self._emit(
                    {
                        "path": path,
                        "params": dict(params or {}),
                        "status_code": None,
                        "attempt": attempt,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        "error": str(exc),
                    }
                )
                if attempt >= attempts:
                    raise HhApiError("Не удалось получить корректный ответ {}".format(path)) from exc
                self._sleep(self._retry_delay(attempt, None))
        raise AssertionError("Недостижимая ветка")

    def _retry_delay(self, attempt: int, retry_after: Optional[str]) -> float:
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return self.settings.retry_base_seconds * (2 ** (attempt - 1))

    def search(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        return self.request_json("/vacancies", params)

    def count(self, params: Mapping[str, Any]) -> int:
        count_params = dict(params)
        count_params.update({"page": 0, "per_page": 1})
        return int(self.search(count_params).get("found", 0))

    def iter_search_pages(self, params: Mapping[str, Any]) -> Iterator[Dict[str, Any]]:
        page = 0
        while True:
            page_params = dict(params)
            page_params.update({"page": page, "per_page": 100})
            payload = self.search(page_params)
            yield payload
            pages = int(payload.get("pages", 0))
            if page + 1 >= pages:
                break
            page += 1

    def get_vacancy(self, vacancy_id: str) -> Dict[str, Any]:
        return self.request_json("/vacancies/{}".format(vacancy_id))

    def get_professional_roles(self) -> Dict[str, Any]:
        return self.request_json("/professional_roles")
