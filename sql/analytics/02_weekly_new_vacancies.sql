WITH weekly AS (
    SELECT
        g.job_group_name,
        date_trunc('week', v.published_at)::date AS week_start,
        count(DISTINCT v.vacancy_sk) AS new_vacancies
    FROM dwh.dim_vacancy AS v
    JOIN dwh.bridge_vacancy_job_group AS vg ON vg.vacancy_sk = v.vacancy_sk
    JOIN dwh.dim_job_group AS g ON g.job_group_sk = vg.job_group_sk
    WHERE v.published_at IS NOT NULL
    GROUP BY g.job_group_name, date_trunc('week', v.published_at)::date
)
SELECT
    *,
    lag(new_vacancies) OVER (
        PARTITION BY job_group_name ORDER BY week_start
    ) AS previous_week_vacancies,
    new_vacancies - lag(new_vacancies) OVER (
        PARTITION BY job_group_name ORDER BY week_start
    ) AS absolute_change
FROM weekly
ORDER BY job_group_name, week_start;
