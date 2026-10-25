CREATE OR REPLACE VIEW stg.v_vacancy_detail_latest AS
SELECT DISTINCT ON (vacancy_id)
    vacancy_id,
    source_updated_at,
    payload_hash,
    payload,
    loaded_at
FROM raw.vacancy_detail
ORDER BY vacancy_id, source_updated_at DESC NULLS LAST, loaded_at DESC;

CREATE OR REPLACE VIEW stg.v_vacancy_normalized AS
SELECT
    d.vacancy_id,
    NULLIF(d.payload ->> 'name', '') AS vacancy_name,
    NULLIF(d.payload #>> '{employer,id}', '') AS employer_id,
    NULLIF(d.payload #>> '{employer,name}', '') AS employer_name,
    CASE WHEN d.payload #>> '{employer,trusted}' IN ('true', 'false')
         THEN (d.payload #>> '{employer,trusted}')::boolean END AS employer_trusted,
    NULLIF(d.payload #>> '{area,id}', '') AS area_id,
    NULLIF(d.payload #>> '{area,name}', '') AS area_name,
    NULLIF(d.payload ->> 'published_at', '')::timestamptz AS published_at,
    NULLIF(d.payload ->> 'created_at', '')::timestamptz AS created_at,
    COALESCE(
        NULLIF(d.payload ->> 'updated_at', '')::timestamptz,
        d.source_updated_at
    ) AS source_updated_at,
    NULLIF(d.payload ->> 'alternate_url', '') AS alternate_url,
    NULLIF(d.payload #>> '{experience,id}', '') AS experience_id,
    NULLIF(d.payload #>> '{employment,id}', '') AS employment_id,
    NULLIF(d.payload #>> '{schedule,id}', '') AS schedule_id,
    NULLIF(COALESCE(
        NULLIF(d.payload -> 'salary_range', 'null'::jsonb),
        NULLIF(d.payload -> 'salary', 'null'::jsonb)
    ) ->> 'from', '')::numeric
        AS salary_from,
    NULLIF(COALESCE(
        NULLIF(d.payload -> 'salary_range', 'null'::jsonb),
        NULLIF(d.payload -> 'salary', 'null'::jsonb)
    ) ->> 'to', '')::numeric
        AS salary_to,
    NULLIF(COALESCE(
        NULLIF(d.payload -> 'salary_range', 'null'::jsonb),
        NULLIF(d.payload -> 'salary', 'null'::jsonb)
    ) ->> 'currency', '')
        AS salary_currency,
    CASE
        WHEN COALESCE(
            NULLIF(d.payload -> 'salary_range', 'null'::jsonb),
            NULLIF(d.payload -> 'salary', 'null'::jsonb)
        ) ->> 'gross' IN ('true', 'false')
        THEN (COALESCE(
            NULLIF(d.payload -> 'salary_range', 'null'::jsonb),
            NULLIF(d.payload -> 'salary', 'null'::jsonb)
        ) ->> 'gross')::boolean
    END AS salary_gross,
    COALESCE(
        NULLIF(COALESCE(
            NULLIF(d.payload -> 'salary_range', 'null'::jsonb),
            NULLIF(d.payload -> 'salary', 'null'::jsonb)
        ) #>> '{frequency,id}', ''),
        NULLIF(COALESCE(
            NULLIF(d.payload -> 'salary_range', 'null'::jsonb),
            NULLIF(d.payload -> 'salary', 'null'::jsonb)
        ) #>> '{mode,id}', ''),
        NULLIF(COALESCE(
            NULLIF(d.payload -> 'salary_range', 'null'::jsonb),
            NULLIF(d.payload -> 'salary', 'null'::jsonb)
        ) ->> 'period', '')
    ) AS salary_period,
    ARRAY(
        SELECT DISTINCT COALESCE(item ->> 'id', item ->> 'name')
        FROM jsonb_array_elements(
            CASE
                WHEN jsonb_typeof(COALESCE(
                    NULLIF(d.payload -> 'work_format', 'null'::jsonb),
                    NULLIF(d.payload -> 'work_formats', 'null'::jsonb)
                )) = 'array'
                THEN COALESCE(
                    NULLIF(d.payload -> 'work_format', 'null'::jsonb),
                    NULLIF(d.payload -> 'work_formats', 'null'::jsonb)
                )
                ELSE '[]'::jsonb
            END
        ) AS item
        WHERE COALESCE(item ->> 'id', item ->> 'name') IS NOT NULL
    ) AS work_formats,
    d.payload_hash,
    d.loaded_at
FROM stg.v_vacancy_detail_latest AS d;

CREATE OR REPLACE VIEW stg.v_vacancy_skill AS
SELECT
    d.vacancy_id,
    NULLIF(trim(skill ->> 'name'), '') AS skill_name,
    lower(NULLIF(trim(skill ->> 'name'), '')) AS normalized_name,
    d.source_updated_at
FROM stg.v_vacancy_detail_latest AS d
CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(d.payload -> 'key_skills') = 'array'
         THEN d.payload -> 'key_skills' ELSE '[]'::jsonb END
) AS skill
WHERE NULLIF(trim(skill ->> 'name'), '') IS NOT NULL;

CREATE OR REPLACE VIEW stg.v_vacancy_professional_role AS
SELECT
    d.vacancy_id,
    role ->> 'id' AS role_id,
    role ->> 'name' AS role_name
FROM stg.v_vacancy_detail_latest AS d
CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(d.payload -> 'professional_roles') = 'array'
         THEN d.payload -> 'professional_roles' ELSE '[]'::jsonb END
) AS role
WHERE role ->> 'id' IS NOT NULL;

CREATE OR REPLACE VIEW stg.v_vacancy_job_group AS
SELECT DISTINCT
    s.vacancy_id,
    a.job_group_code
FROM raw.search_response AS s
JOIN audit.search_segment AS a
  ON a.run_id = s.run_id
 AND a.segment_id = s.segment_id;
