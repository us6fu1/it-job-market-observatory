.PHONY: test sample db-up db-down db-init db-sample db-load db-quality dashboard

test:
	python3 -m unittest discover -s tests/unit -v

sample:
	python3 -m ingestion sample --input data/sample --output build/sample

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-init:
	python3 scripts/run_sql.py ddl

db-sample:
	python3 scripts/load_sample_to_postgres.py

db-load:
	python3 scripts/run_sql.py load

db-quality:
	python3 scripts/run_sql.py quality

dashboard:
	streamlit run dashboard/app.py
