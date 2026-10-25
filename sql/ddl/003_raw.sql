BEGIN;

CREATE TABLE IF NOT EXISTS raw.search_response (
    search_response_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL,
    segment_id text NOT NULL,
    page_number integer NOT NULL CHECK (page_number >= 0),
    vacancy_id text NOT NULL,
    payload jsonb NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_search_segment
        FOREIGN KEY (run_id, segment_id)
        REFERENCES audit.search_segment(run_id, segment_id),
    CONSTRAINT uq_search_vacancy_segment
        UNIQUE (run_id, segment_id, vacancy_id)
);

CREATE TABLE IF NOT EXISTS raw.vacancy_detail (
    vacancy_detail_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES audit.etl_run(run_id),
    vacancy_id text NOT NULL,
    source_updated_at timestamptz,
    payload_hash char(64) NOT NULL,
    payload jsonb NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_vacancy_detail_version UNIQUE (vacancy_id, payload_hash)
);

CREATE TABLE IF NOT EXISTS raw.vacancy_status_response (
    status_response_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES audit.etl_run(run_id),
    vacancy_id text NOT NULL,
    http_status integer NOT NULL,
    is_available boolean,
    payload jsonb,
    checked_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_search_response_run_vacancy
    ON raw.search_response (run_id, vacancy_id);

CREATE INDEX IF NOT EXISTS ix_vacancy_detail_latest
    ON raw.vacancy_detail (vacancy_id, loaded_at DESC);

CREATE INDEX IF NOT EXISTS ix_search_response_payload_gin
    ON raw.search_response USING gin (payload);

COMMIT;
