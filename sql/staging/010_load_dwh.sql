BEGIN;

INSERT INTO dwh.dim_job_group (job_group_code, job_group_name)
SELECT DISTINCT
    job_group_code,
    initcap(replace(job_group_code, '_', ' '))
FROM audit.search_segment
ON CONFLICT (job_group_code) DO NOTHING;

INSERT INTO dwh.dim_employer (employer_id, employer_name, trusted)
SELECT DISTINCT ON (employer_id)
    employer_id,
    employer_name,
    employer_trusted
FROM stg.v_vacancy_normalized
WHERE employer_id IS NOT NULL
  AND employer_name IS NOT NULL
ORDER BY employer_id, loaded_at DESC
ON CONFLICT (employer_id) DO UPDATE
SET employer_name = EXCLUDED.employer_name,
    trusted = EXCLUDED.trusted,
    last_seen_at = now();

INSERT INTO dwh.dim_area (area_id, area_name)
SELECT DISTINCT ON (area_id)
    area_id,
    area_name
FROM stg.v_vacancy_normalized
WHERE area_id IS NOT NULL
  AND area_name IS NOT NULL
ORDER BY area_id, loaded_at DESC
ON CONFLICT (area_id) DO UPDATE
SET area_name = EXCLUDED.area_name,
    last_seen_at = now();

INSERT INTO dwh.dim_hh_professional_role (role_id, role_name)
SELECT DISTINCT ON (role_id)
    role_id,
    role_name
FROM stg.v_vacancy_professional_role
ORDER BY role_id, role_name NULLS LAST
ON CONFLICT (role_id) DO UPDATE
SET role_name = EXCLUDED.role_name,
    last_seen_at = now();

INSERT INTO dwh.dim_skill (skill_name, normalized_name)
SELECT DISTINCT ON (normalized_name)
    skill_name,
    normalized_name
FROM stg.v_vacancy_skill
ORDER BY normalized_name, skill_name
ON CONFLICT (normalized_name) DO UPDATE
SET skill_name = EXCLUDED.skill_name;

INSERT INTO dwh.dim_vacancy (
    vacancy_id,
    vacancy_name,
    employer_sk,
    area_sk,
    published_at,
    created_at,
    source_updated_at,
    alternate_url,
    experience_id,
    employment_id,
    schedule_id
)
SELECT
    v.vacancy_id,
    v.vacancy_name,
    e.employer_sk,
    a.area_sk,
    v.published_at,
    v.created_at,
    v.source_updated_at,
    v.alternate_url,
    v.experience_id,
    v.employment_id,
    v.schedule_id
FROM stg.v_vacancy_normalized AS v
LEFT JOIN dwh.dim_employer AS e ON e.employer_id = v.employer_id
LEFT JOIN dwh.dim_area AS a ON a.area_id = v.area_id
WHERE v.vacancy_name IS NOT NULL
ON CONFLICT (vacancy_id) DO UPDATE
SET vacancy_name = EXCLUDED.vacancy_name,
    employer_sk = EXCLUDED.employer_sk,
    area_sk = EXCLUDED.area_sk,
    published_at = EXCLUDED.published_at,
    created_at = EXCLUDED.created_at,
    source_updated_at = EXCLUDED.source_updated_at,
    alternate_url = EXCLUDED.alternate_url,
    experience_id = EXCLUDED.experience_id,
    employment_id = EXCLUDED.employment_id,
    schedule_id = EXCLUDED.schedule_id,
    last_seen_at = now();

DELETE FROM dwh.bridge_vacancy_skill AS bridge
USING dwh.dim_vacancy AS vacancy
WHERE bridge.vacancy_sk = vacancy.vacancy_sk
  AND EXISTS (
      SELECT 1 FROM stg.v_vacancy_skill AS source
      WHERE source.vacancy_id = vacancy.vacancy_id
  );

INSERT INTO dwh.bridge_vacancy_skill (vacancy_sk, skill_sk, source_updated_at)
SELECT DISTINCT
    v.vacancy_sk,
    s.skill_sk,
    source.source_updated_at
FROM stg.v_vacancy_skill AS source
JOIN dwh.dim_vacancy AS v ON v.vacancy_id = source.vacancy_id
JOIN dwh.dim_skill AS s ON s.normalized_name = source.normalized_name
ON CONFLICT (vacancy_sk, skill_sk) DO UPDATE
SET source_updated_at = EXCLUDED.source_updated_at;

DELETE FROM dwh.bridge_vacancy_professional_role AS bridge
USING dwh.dim_vacancy AS vacancy
WHERE bridge.vacancy_sk = vacancy.vacancy_sk
  AND EXISTS (
      SELECT 1 FROM stg.v_vacancy_professional_role AS source
      WHERE source.vacancy_id = vacancy.vacancy_id
  );

INSERT INTO dwh.bridge_vacancy_professional_role (vacancy_sk, role_sk)
SELECT DISTINCT
    v.vacancy_sk,
    r.role_sk
FROM stg.v_vacancy_professional_role AS source
JOIN dwh.dim_vacancy AS v ON v.vacancy_id = source.vacancy_id
JOIN dwh.dim_hh_professional_role AS r ON r.role_id = source.role_id
ON CONFLICT (vacancy_sk, role_sk) DO NOTHING;

INSERT INTO dwh.bridge_vacancy_job_group (
    vacancy_sk,
    job_group_sk,
    classification_source
)
SELECT DISTINCT
    v.vacancy_sk,
    g.job_group_sk,
    'search_segment'
FROM stg.v_vacancy_job_group AS source
JOIN dwh.dim_vacancy AS v ON v.vacancy_id = source.vacancy_id
JOIN dwh.dim_job_group AS g ON g.job_group_code = source.job_group_code
ON CONFLICT (vacancy_sk, job_group_sk) DO UPDATE
SET classification_source = EXCLUDED.classification_source;

INSERT INTO dwh.fact_vacancy_snapshot (
    run_id,
    vacancy_sk,
    observed_at,
    is_available,
    salary_from,
    salary_to,
    salary_currency,
    salary_gross,
    salary_period,
    work_formats,
    source_payload_hash
)
SELECT DISTINCT ON (s.run_id, v.vacancy_sk)
    s.run_id,
    v.vacancy_sk,
    run.started_at,
    true,
    n.salary_from,
    n.salary_to,
    n.salary_currency,
    n.salary_gross,
    n.salary_period,
    n.work_formats,
    n.payload_hash
FROM raw.search_response AS s
JOIN audit.etl_run AS run ON run.run_id = s.run_id
JOIN dwh.dim_vacancy AS v ON v.vacancy_id = s.vacancy_id
LEFT JOIN stg.v_vacancy_normalized AS n ON n.vacancy_id = s.vacancy_id
ORDER BY s.run_id, v.vacancy_sk, s.ingested_at DESC
ON CONFLICT (run_id, vacancy_sk) DO UPDATE
SET observed_at = EXCLUDED.observed_at,
    is_available = EXCLUDED.is_available,
    salary_from = EXCLUDED.salary_from,
    salary_to = EXCLUDED.salary_to,
    salary_currency = EXCLUDED.salary_currency,
    salary_gross = EXCLUDED.salary_gross,
    salary_period = EXCLUDED.salary_period,
    work_formats = EXCLUDED.work_formats,
    source_payload_hash = EXCLUDED.source_payload_hash;

COMMIT;
