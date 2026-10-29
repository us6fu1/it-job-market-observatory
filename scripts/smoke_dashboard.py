#!/usr/bin/env python3
"""Проверяет запуск Streamlit и чтение витрин PostgreSQL без браузера."""

import os
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("Для проверки дашборда задайте DATABASE_URL")

    app = AppTest.from_file(str(ROOT / "dashboard" / "app.py")).run(timeout=30)
    if app.exception:
        messages = "\n".join(str(item.value) for item in app.exception)
        raise SystemExit("Дашборд завершился с ошибкой:\n{}".format(messages))

    expected_tabs = {"Обзор", "Зарплаты", "Навыки", "Вакансии", "Качество данных"}
    actual_tabs = {tab.label for tab in app.tabs}
    missing = expected_tabs - actual_tabs
    if missing:
        raise SystemExit(
            "В дашборде отсутствуют вкладки: {}".format(", ".join(sorted(missing)))
        )

    print("Дашборд прочитал PostgreSQL без ошибок: {} вкладок".format(len(app.tabs)))


if __name__ == "__main__":
    main()
