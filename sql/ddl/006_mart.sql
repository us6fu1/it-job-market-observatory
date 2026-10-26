CREATE OR REPLACE VIEW mart.v_current_vacancies AS
WITH latest_run AS (
    SELECT run_id
    FROM audit.etl_run
    WHERE status IN ('success', 'partial')
    ORDER BY started_at DESC
    LIMIT 1
)
SELECT
    f.run_id,
    f.observed_at,
    v.vacancy_sk,
    v.vacancy_id,
    v.vacancy_name,
    v.published_at,
    v.employer_sk,
    v.area_sk,
    f.salary_from,
    f.salary_to,
    f.salary_currency,
    f.salary_gross,
    f.salary_period,
    f.work_formats
FROM dwh.fact_vacancy_snapshot AS f
JOIN latest_run AS r ON r.run_id = f.run_id
JOIN dwh.dim_vacancy AS v ON v.vacancy_sk = f.vacancy_sk
WHERE f.is_available;

CREATE OR REPLACE VIEW mart.v_market_overview AS
SELECT
    g.job_group_code,
    g.job_group_name,
    count(DISTINCT current.vacancy_sk) AS available_vacancies,
    count(DISTINCT current.vacancy_sk) FILTER (
        WHERE current.salary_from IS NOT NULL OR current.salary_to IS NOT NULL
    ) AS vacancies_with_salary,
    round(
        count(DISTINCT current.vacancy_sk) FILTER (
            WHERE current.salary_from IS NOT NULL OR current.salary_to IS NOT NULL
        )::numeric / NULLIF(count(DISTINCT current.vacancy_sk), 0),
        4
    ) AS salary_coverage
FROM mart.v_current_vacancies AS current
JOIN dwh.bridge_vacancy_job_group AS vg ON vg.vacancy_sk = current.vacancy_sk
JOIN dwh.dim_job_group AS g ON g.job_group_sk = vg.job_group_sk
GROUP BY g.job_group_code, g.job_group_name;

CREATE OR REPLACE VIEW mart.v_top_skills AS
WITH counts AS (
    SELECT
        g.job_group_code,
        g.job_group_name,
        s.skill_name,
        count(DISTINCT current.vacancy_sk) AS vacancy_count
    FROM mart.v_current_vacancies AS current
    JOIN dwh.bridge_vacancy_job_group AS vg ON vg.vacancy_sk = current.vacancy_sk
    JOIN dwh.dim_job_group AS g ON g.job_group_sk = vg.job_group_sk
    JOIN dwh.bridge_vacancy_skill AS vs ON vs.vacancy_sk = current.vacancy_sk
    JOIN dwh.dim_skill AS s ON s.skill_sk = vs.skill_sk
    GROUP BY g.job_group_code, g.job_group_name, s.skill_name
)
SELECT
    *,
    dense_rank() OVER (
        PARTITION BY job_group_code
        ORDER BY vacancy_count DESC
    ) AS skill_rank
FROM counts;

CREATE OR REPLACE VIEW mart.v_salary_by_group_region AS
SELECT
    g.job_group_code,
    g.job_group_name,
    a.area_id,
    a.area_name,
    current.salary_currency,
    count(DISTINCT current.vacancy_sk) AS total_vacancies,
    count(DISTINCT current.vacancy_sk) FILTER (
        WHERE current.salary_from IS NOT NULL OR current.salary_to IS NOT NULL
    ) AS vacancies_with_salary,
    count(DISTINCT current.vacancy_sk) FILTER (
        WHERE current.salary_from IS NOT NULL AND current.salary_to IS NOT NULL
    ) AS vacancies_with_two_bounds,
    percentile_cont(0.5) WITHIN GROUP (
        ORDER BY (current.salary_from + current.salary_to) / 2.0
    ) FILTER (
        WHERE current.salary_from IS NOT NULL AND current.salary_to IS NOT NULL
    ) AS median_two_bound_salary_midpoint
FROM mart.v_current_vacancies AS current
JOIN dwh.bridge_vacancy_job_group AS vg ON vg.vacancy_sk = current.vacancy_sk
JOIN dwh.dim_job_group AS g ON g.job_group_sk = vg.job_group_sk
LEFT JOIN dwh.dim_area AS a ON a.area_sk = current.area_sk
GROUP BY
    g.job_group_code,
    g.job_group_name,
    a.area_id,
    a.area_name,
    current.salary_currency;

CREATE OR REPLACE VIEW mart.v_weekly_new_vacancies AS
WITH latest_run AS (
    SELECT run_id, parameters
    FROM audit.etl_run
    WHERE status IN ('success', 'partial')
    ORDER BY started_at DESC
    LIMIT 1
), analysis_window AS (
    SELECT
        min((segment ->> 'date_from')::date) AS date_from,
        max((segment ->> 'date_to')::date) AS date_to
    FROM latest_run
    CROSS JOIN LATERAL jsonb_array_elements(
        COALESCE(parameters -> 'segments', '[]'::jsonb)
    ) AS segment
), first_publication AS (
    SELECT
        vg.job_group_sk,
        date_trunc('week', current.published_at)::date AS week_start,
        count(DISTINCT current.vacancy_sk) AS new_vacancies
    FROM mart.v_current_vacancies AS current
    JOIN dwh.bridge_vacancy_job_group AS vg
      ON vg.vacancy_sk = current.vacancy_sk
    CROSS JOIN analysis_window AS bounds
    WHERE current.published_at IS NOT NULL
      AND current.published_at::date BETWEEN bounds.date_from AND bounds.date_to
    GROUP BY vg.job_group_sk, date_trunc('week', current.published_at)::date
), with_previous AS (
    SELECT
        *,
        lag(new_vacancies) OVER (
            PARTITION BY job_group_sk ORDER BY week_start
        ) AS previous_week_vacancies
    FROM first_publication
)
SELECT
    g.job_group_code,
    g.job_group_name,
    p.week_start,
    p.new_vacancies,
    p.previous_week_vacancies,
    p.new_vacancies - p.previous_week_vacancies AS absolute_change
FROM with_previous AS p
JOIN dwh.dim_job_group AS g ON g.job_group_sk = p.job_group_sk;

CREATE OR REPLACE VIEW mart.v_employers_three_directions AS
SELECT
    e.employer_id,
    e.employer_name,
    count(DISTINCT vg.job_group_sk) AS job_group_count,
    array_agg(DISTINCT g.job_group_name ORDER BY g.job_group_name) AS job_groups
FROM mart.v_current_vacancies AS current
JOIN dwh.dim_employer AS e ON e.employer_sk = current.employer_sk
JOIN dwh.bridge_vacancy_job_group AS vg ON vg.vacancy_sk = current.vacancy_sk
JOIN dwh.dim_job_group AS g ON g.job_group_sk = vg.job_group_sk
GROUP BY e.employer_id, e.employer_name
HAVING count(DISTINCT vg.job_group_sk) >= 3;
