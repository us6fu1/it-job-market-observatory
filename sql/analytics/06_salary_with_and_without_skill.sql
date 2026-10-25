-- Замените значение в settings на нужный навык.
WITH settings AS (
    SELECT 'sql'::text AS normalized_skill
), vacancy_salary AS (
    SELECT
        current.vacancy_sk,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM dwh.bridge_vacancy_skill AS vs
                JOIN dwh.dim_skill AS s ON s.skill_sk = vs.skill_sk
                JOIN settings ON settings.normalized_skill = s.normalized_name
                WHERE vs.vacancy_sk = current.vacancy_sk
            ) THEN 'with_skill'
            ELSE 'without_skill'
        END AS skill_group,
        (current.salary_from + current.salary_to) / 2.0 AS two_bound_midpoint,
        current.salary_currency
    FROM mart.v_current_vacancies AS current
    WHERE current.salary_from IS NOT NULL
      AND current.salary_to IS NOT NULL
)
SELECT
    skill_group,
    salary_currency,
    count(*) AS vacancy_count,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY two_bound_midpoint) AS median_salary
FROM vacancy_salary
GROUP BY skill_group, salary_currency
ORDER BY salary_currency, skill_group;
