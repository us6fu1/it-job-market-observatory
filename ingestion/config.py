"""Настройки приложения без сторонних библиотек."""

from dataclasses import dataclass
import os
from typing import Mapping, Optional


DEFAULT_USER_AGENT = "IT-Job-Market-Observatory/0.1 (local-mvp)"


@dataclass(frozen=True)
class HhSettings:
    base_url: str = "https://api.hh.ru"
    user_agent: str = DEFAULT_USER_AGENT
    oauth_token: Optional[str] = None
    timeout_seconds: float = 30.0
    max_retries: int = 5
    retry_base_seconds: float = 1.0

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "HhSettings":
        values = os.environ if env is None else env
        access_token = (
            values.get("HH_ACCESS_TOKEN")
            or values.get("HH_OAUTH_TOKEN")
            or ""
        ).strip() or None
        return cls(
            base_url=values.get("HH_BASE_URL", cls.base_url).rstrip("/"),
            user_agent=values.get("HH_USER_AGENT", DEFAULT_USER_AGENT).strip(),
            oauth_token=access_token,
            timeout_seconds=float(values.get("HH_TIMEOUT_SECONDS", "30")),
            max_retries=int(values.get("HH_MAX_RETRIES", "5")),
            retry_base_seconds=float(values.get("HH_RETRY_BASE_SECONDS", "1")),
        )

    def validate_for_live_request(self) -> None:
        if not self.user_agent or self.user_agent == DEFAULT_USER_AGENT:
            raise ValueError(
                "Перед реальным запросом задайте HH_USER_AGENT с названием проекта "
                "и контактом. Пример есть в .env.example."
            )
        if self.max_retries < 0:
            raise ValueError("HH_MAX_RETRIES не может быть отрицательным")
        if self.timeout_seconds <= 0:
            raise ValueError("HH_TIMEOUT_SECONDS должен быть больше нуля")
