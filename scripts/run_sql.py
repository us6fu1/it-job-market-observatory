#!/usr/bin/env python3
"""Применяет DDL, загрузку DWH или SQL-проверки качества."""

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def _files(mode: str):
    if mode == "ddl":
        return sorted((ROOT / "sql" / "ddl").glob("*.sql"))
    if mode == "load":
        return sorted((ROOT / "sql" / "staging").glob("*.sql"))
    return sorted((ROOT / "tests" / "data_quality").glob("*.sql"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("ddl", "load", "quality"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("Задайте DATABASE_URL или передайте --database-url")
    try:
        import psycopg
    except ImportError:
        parser.error("Не установлен psycopg. Выполните: python3 -m pip install .")

    failed = []
    with psycopg.connect(args.database_url, autocommit=True) as connection:
        for path in _files(args.mode):
            sql = path.read_text(encoding="utf-8")
            with connection.cursor() as cursor:
                cursor.execute(sql)
                if args.mode == "quality":
                    rows = cursor.fetchall()
                    for check_name, failed_rows in rows:
                        print("{}: {}".format(check_name, failed_rows))
                        if failed_rows:
                            failed.append((check_name, failed_rows))
                else:
                    print("Применён {}".format(path.relative_to(ROOT)))
    if failed:
        print("Проверки качества не пройдены", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
