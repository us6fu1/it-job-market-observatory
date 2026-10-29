PYTHON ?= python3

.PHONY: test verify sample live db-up db-down db-init db-sample db-load db-quality db-verify dashboard dashboard-check

test:
	$(PYTHON) -m unittest discover -s tests/unit -v

verify: test sample

sample:
	$(PYTHON) -m ingestion sample --input data/sample --output build/sample

live:
	$(PYTHON) -m ingestion collect-trudvsem --config config/trudvsem_segments.json --raw-dir data/raw-trudvsem --database-url "$(DATABASE_URL)"

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-init:
	$(PYTHON) scripts/run_sql.py ddl

db-sample:
	$(PYTHON) scripts/load_sample_to_postgres.py

db-load:
	$(PYTHON) scripts/run_sql.py load

db-quality:
	$(PYTHON) scripts/run_sql.py quality

db-verify: db-init db-sample db-load db-quality dashboard-check

dashboard-check:
	$(PYTHON) scripts/smoke_dashboard.py

dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py
