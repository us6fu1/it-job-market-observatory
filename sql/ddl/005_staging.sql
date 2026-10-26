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
WITH source_skills AS (
    SELECT
        d.vacancy_id,
        NULLIF(trim(skill ->> 'name'), '') AS source_skill_name,
        d.source_updated_at
    FROM stg.v_vacancy_detail_latest AS d
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(d.payload -> 'key_skills') = 'array'
             THEN d.payload -> 'key_skills' ELSE '[]'::jsonb END
    ) AS skill
    WHERE NULLIF(trim(skill ->> 'name'), '') IS NOT NULL
), canonical_skills AS (
    SELECT
        vacancy_id,
        CASE
            WHEN vacancy_id NOT LIKE 'trudvsem:%' THEN source_skill_name
            WHEN lower(source_skill_name) ~ 'python|питон' THEN 'Python'
            WHEN lower(source_skill_name) ~ 'postgres' THEN 'PostgreSQL'
            WHEN lower(source_skill_name) ~ 'greenplum' THEN 'Greenplum'
            WHEN lower(source_skill_name) ~ 'clickhouse' THEN 'ClickHouse'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])oracle([^a-z]|$)' THEN 'Oracle'
            WHEN lower(source_skill_name) ~ 'ms sql|sql server' THEN 'MS SQL Server'
            WHEN lower(source_skill_name) ~ 'mysql' THEN 'MySQL'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])sql([^a-z]|$)|запрос' THEN 'SQL'
            WHEN lower(source_skill_name) ~ 'hadoop' THEN 'Hadoop'
            WHEN lower(source_skill_name) ~ 'pyspark' THEN 'PySpark'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])spark([^a-z]|$)' THEN 'Spark'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])hive([^a-z]|$)' THEN 'Hive'
            WHEN lower(source_skill_name) ~ 'kafka' THEN 'Kafka'
            WHEN lower(source_skill_name) ~ 'rabbitmq' THEN 'RabbitMQ'
            WHEN lower(source_skill_name) ~ 'airflow' THEN 'Airflow'
            WHEN lower(source_skill_name) ~ 'power[[:space:]]*bi|microsoft power bi' THEN 'Power BI'
            WHEN lower(source_skill_name) ~ 'tableau' THEN 'Tableau'
            WHEN lower(source_skill_name) ~ 'qlik' THEN 'Qlik'
            WHEN lower(source_skill_name) ~ 'superset' THEN 'Superset'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])dax([^a-z]|$)' THEN 'DAX'
            WHEN lower(source_skill_name) ~ 'excel' THEN 'Excel'
            WHEN lower(source_skill_name) ~ 'pandas' THEN 'Pandas'
            WHEN lower(source_skill_name) ~ 'numpy' THEN 'NumPy'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])git([^a-z]|$)' THEN 'Git'
            WHEN lower(source_skill_name) ~ 'docker' THEN 'Docker'
            WHEN lower(source_skill_name) ~ 'kubernetes|k8s' THEN 'Kubernetes'
            WHEN lower(source_skill_name) ~ 'linux' THEN 'Linux'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])etl([^a-z]|$)' THEN 'ETL'
            WHEN lower(source_skill_name) ~ 'rest[[:space:]]*api' THEN 'REST API'
            WHEN lower(source_skill_name) ~ 'fastapi' THEN 'FastAPI'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])dwh([^a-z]|$)|data warehouse|хранилищ.*данных' THEN 'DWH'
            WHEN lower(source_skill_name) ~ 'data quality|качество данных' THEN 'Data Quality'
            WHEN lower(source_skill_name) ~ 'machine learning|машинн.*обучен' THEN 'Machine Learning'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])llm([^a-z]|$)|large language model|языков.*модел' THEN 'LLM'
            WHEN lower(source_skill_name) ~ '(^|[^a-z])nlp([^a-z]|$)|natural language processing|естественн.*язык' THEN 'NLP'
        END AS skill_name,
        source_updated_at
    FROM source_skills
)
SELECT DISTINCT
    vacancy_id,
    skill_name,
    lower(skill_name) AS normalized_name,
    source_updated_at
FROM canonical_skills
WHERE skill_name IS NOT NULL;

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
WITH latest_source_runs AS (
    SELECT DISTINCT ON (source)
        run_id,
        source
    FROM audit.etl_run
    WHERE status IN ('success', 'partial')
    ORDER BY source, started_at DESC
)
SELECT DISTINCT
    s.vacancy_id,
    a.job_group_code
FROM raw.search_response AS s
JOIN latest_source_runs AS latest ON latest.run_id = s.run_id
JOIN audit.search_segment AS a
  ON a.run_id = s.run_id
 AND a.segment_id = s.segment_id;
