"""Командная строка проекта."""

import argparse
import json
import os
from pathlib import Path
from typing import Optional, Sequence

from ingestion.config import HhSettings
from ingestion.hh_client import HhClient
from ingestion.pipeline import CollectionPipeline, build_sample
from ingestion.postgres_store import CompositeStore, PostgresRawStore
from ingestion.raw_store import FileRawStore
from ingestion.segmentation import load_segments
from ingestion.trudvsem_client import TrudvsemClient, TrudvsemSettings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-market")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample = subparsers.add_parser("sample", help="Собрать офлайн-демо из data/sample")
    sample.add_argument("--input", type=Path, default=Path("data/sample"))
    sample.add_argument("--output", type=Path, default=Path("build/sample"))

    collect = subparsers.add_parser("collect", help="Загрузить вакансии из HH API")
    collect.add_argument("--config", type=Path, required=True)
    collect.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    collect.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    collect.add_argument("--refresh-details", action="store_true")

    trudvsem = subparsers.add_parser(
        "collect-trudvsem",
        help="Загрузить открытые вакансии из API «Работа России»",
    )
    trudvsem.add_argument("--config", type=Path, required=True)
    trudvsem.add_argument("--raw-dir", type=Path, default=Path("data/raw-trudvsem"))
    trudvsem.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    trudvsem.add_argument("--refresh-details", action="store_true")

    roles = subparsers.add_parser("roles", help="Сохранить актуальный справочник профролей HH")
    roles.add_argument("--output", type=Path, default=Path("build/hh_professional_roles.json"))
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parser().parse_args(argv)
    if args.command == "sample":
        result = build_sample(args.input, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "collect-trudvsem":
        file_store = FileRawStore(args.raw_dir)
        postgres_store = (
            PostgresRawStore(args.database_url, source="trudvsem_api")
            if args.database_url
            else None
        )
        store = CompositeStore(file_store, *([postgres_store] if postgres_store else []))
        client = TrudvsemClient(
            TrudvsemSettings.from_env(), request_hook=store.record_request
        )
        try:
            result = CollectionPipeline(
                client,
                store,
                refresh_details=args.refresh_details,
                result_limit=10000,
            ).collect(load_segments(args.config))
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        finally:
            if postgres_store is not None:
                postgres_store.close()
        return

    settings = HhSettings.from_env()
    settings.validate_for_live_request()
    if args.command == "roles":
        payload = HhClient(settings).get_professional_roles()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("Справочник сохранён: {}".format(args.output))
        return


    file_store = FileRawStore(args.raw_dir)
    postgres_store = PostgresRawStore(args.database_url) if args.database_url else None
    store = CompositeStore(file_store, *([postgres_store] if postgres_store else []))
    client = HhClient(settings, request_hook=store.record_request)
    try:
        result = CollectionPipeline(
            client,
            store,
            refresh_details=args.refresh_details,
        ).collect(load_segments(args.config))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        if postgres_store is not None:
            postgres_store.close()


if __name__ == "__main__":
    main()
