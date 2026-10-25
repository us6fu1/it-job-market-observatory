BEGIN;

CREATE TABLE IF NOT EXISTS dwh.dim_employer (
    employer_sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employer_id text NOT NULL UNIQUE,
    employer_name text NOT NULL,
    trusted boolean,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dwh.dim_area (
    area_sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    area_id text NOT NULL UNIQUE,
    area_name text NOT NULL,
    parent_area_id text,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dwh.dim_hh_professional_role (
    role_sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_id text NOT NULL UNIQUE,
    role_name text,
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dwh.dim_job_group (
    job_group_sk smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_group_code text NOT NULL UNIQUE,
    job_group_name text NOT NULL
);

INSERT INTO dwh.dim_job_group (job_group_code, job_group_name)
VALUES
    ('data_analyst', 'Data Analyst'),
    ('bi_developer', 'BI Developer'),
    ('data_engineer', 'Data Engineer')
ON CONFLICT (job_group_code) DO UPDATE
SET job_group_name = EXCLUDED.job_group_name;

CREATE TABLE IF NOT EXISTS dwh.dim_skill (
    skill_sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    skill_name text NOT NULL,
    normalized_name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dwh.dim_vacancy (
    vacancy_sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vacancy_id text NOT NULL UNIQUE,
    vacancy_name text NOT NULL,
    employer_sk bigint REFERENCES dwh.dim_employer(employer_sk),
    area_sk bigint REFERENCES dwh.dim_area(area_sk),
    published_at timestamptz,
    created_at timestamptz,
    source_updated_at timestamptz,
    alternate_url text,
    experience_id text,
    employment_id text,
    schedule_id text,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dwh.bridge_role_job_group (
    role_sk bigint NOT NULL REFERENCES dwh.dim_hh_professional_role(role_sk),
    job_group_sk smallint NOT NULL REFERENCES dwh.dim_job_group(job_group_sk),
    mapping_rule text NOT NULL,
    valid_from date NOT NULL DEFAULT current_date,
    valid_to date,
    PRIMARY KEY (role_sk, job_group_sk, valid_from)
);

CREATE TABLE IF NOT EXISTS dwh.bridge_vacancy_professional_role (
    vacancy_sk bigint NOT NULL REFERENCES dwh.dim_vacancy(vacancy_sk) ON DELETE CASCADE,
    role_sk bigint NOT NULL REFERENCES dwh.dim_hh_professional_role(role_sk),
    PRIMARY KEY (vacancy_sk, role_sk)
);

CREATE TABLE IF NOT EXISTS dwh.bridge_vacancy_job_group (
    vacancy_sk bigint NOT NULL REFERENCES dwh.dim_vacancy(vacancy_sk) ON DELETE CASCADE,
    job_group_sk smallint NOT NULL REFERENCES dwh.dim_job_group(job_group_sk),
    classification_source text NOT NULL,
    PRIMARY KEY (vacancy_sk, job_group_sk)
);

CREATE TABLE IF NOT EXISTS dwh.bridge_vacancy_skill (
    vacancy_sk bigint NOT NULL REFERENCES dwh.dim_vacancy(vacancy_sk) ON DELETE CASCADE,
    skill_sk bigint NOT NULL REFERENCES dwh.dim_skill(skill_sk),
    source_updated_at timestamptz,
    PRIMARY KEY (vacancy_sk, skill_sk)
);

CREATE TABLE IF NOT EXISTS dwh.fact_vacancy_snapshot (
    run_id uuid NOT NULL REFERENCES audit.etl_run(run_id),
    vacancy_sk bigint NOT NULL REFERENCES dwh.dim_vacancy(vacancy_sk),
    observed_at timestamptz NOT NULL,
    is_available boolean NOT NULL DEFAULT true,
    salary_from numeric(14, 2),
    salary_to numeric(14, 2),
    salary_currency text,
    salary_gross boolean,
    salary_period text,
    work_formats text[] NOT NULL DEFAULT '{}',
    source_payload_hash char(64),
    PRIMARY KEY (run_id, vacancy_sk),
    CHECK (salary_from IS NULL OR salary_from >= 0),
    CHECK (salary_to IS NULL OR salary_to >= 0),
    CHECK (salary_from IS NULL OR salary_to IS NULL OR salary_from <= salary_to)
);

CREATE TABLE IF NOT EXISTS dwh.fact_vacancy_status_check (
    status_check_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vacancy_sk bigint NOT NULL REFERENCES dwh.dim_vacancy(vacancy_sk),
    run_id uuid REFERENCES audit.etl_run(run_id),
    checked_at timestamptz NOT NULL,
    http_status integer NOT NULL,
    is_available boolean,
    status_reason text
);

CREATE INDEX IF NOT EXISTS ix_vacancy_published_at
    ON dwh.dim_vacancy (published_at);

CREATE INDEX IF NOT EXISTS ix_snapshot_observed_available
    ON dwh.fact_vacancy_snapshot (observed_at, is_available);

CREATE INDEX IF NOT EXISTS ix_snapshot_salary_currency
    ON dwh.fact_vacancy_snapshot (salary_currency)
    WHERE salary_from IS NOT NULL OR salary_to IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_bridge_skill_skill_vacancy
    ON dwh.bridge_vacancy_skill (skill_sk, vacancy_sk);

CREATE INDEX IF NOT EXISTS ix_bridge_group_group_vacancy
    ON dwh.bridge_vacancy_job_group (job_group_sk, vacancy_sk);

COMMIT;
