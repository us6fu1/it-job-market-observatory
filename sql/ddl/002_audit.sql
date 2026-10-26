BEGIN;

CREATE TABLE IF NOT EXISTS audit.etl_run (
    run_id uuid PRIMARY KEY,
    source text NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    rows_received integer NOT NULL DEFAULT 0 CHECK (rows_received >= 0),
    unique_vacancies integer NOT NULL DEFAULT 0 CHECK (unique_vacancies >= 0),
    details_loaded integer NOT NULL DEFAULT 0 CHECK (details_loaded >= 0),
    filtered_out integer NOT NULL DEFAULT 0 CHECK (filtered_out >= 0),
    rejected_rows integer NOT NULL DEFAULT 0 CHECK (rejected_rows >= 0),
    error_message text
);

ALTER TABLE audit.etl_run
    ADD COLUMN IF NOT EXISTS filtered_out integer NOT NULL DEFAULT 0
    CHECK (filtered_out >= 0);

CREATE TABLE IF NOT EXISTS audit.api_request (
    request_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES audit.etl_run(run_id),
    endpoint text NOT NULL,
    query_params jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_code integer,
    attempt integer NOT NULL CHECK (attempt > 0),
    duration_ms integer CHECK (duration_ms >= 0),
    requested_at timestamptz NOT NULL DEFAULT now(),
    error_message text
);

CREATE TABLE IF NOT EXISTS audit.search_segment (
    run_id uuid NOT NULL REFERENCES audit.etl_run(run_id),
    segment_id text NOT NULL,
    parent_segment_id text,
    job_group_code text NOT NULL,
    query_params jsonb NOT NULL,
    found integer NOT NULL CHECK (found >= 0),
    received integer NOT NULL DEFAULT 0 CHECK (received >= 0),
    status text NOT NULL CHECK (status IN ('ready', 'running', 'success', 'over_limit', 'error')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    error_message text,
    PRIMARY KEY (run_id, segment_id)
);

CREATE INDEX IF NOT EXISTS ix_api_request_run_status
    ON audit.api_request (run_id, status_code);

CREATE INDEX IF NOT EXISTS ix_search_segment_status
    ON audit.search_segment (run_id, status);

COMMIT;
