#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests/unit -v
python3 -m ingestion sample --input data/sample --output build/sample
