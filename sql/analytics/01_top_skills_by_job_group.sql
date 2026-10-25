WITH skill_counts AS (
    SELECT
        g.job_group_name,
        s.skill_name,
        count(DISTINCT current.vacancy_sk) AS vacancy_count
    FROM mart.v_current_vacancies AS current
    JOIN dwh.bridge_vacancy_job_group AS vg ON vg.vacancy_sk = current.vacancy_sk
    JOIN dwh.dim_job_group AS g ON g.job_group_sk = vg.job_group_sk
    JOIN dwh.bridge_vacancy_skill AS vs ON vs.vacancy_sk = current.vacancy_sk
    JOIN dwh.dim_skill AS s ON s.skill_sk = vs.skill_sk
    GROUP BY g.job_group_name, s.skill_name
)
SELECT
    job_group_name,
    skill_name,
    vacancy_count,
    dense_rank() OVER (
        PARTITION BY job_group_name
        ORDER BY vacancy_count DESC
    ) AS skill_rank
FROM skill_counts
ORDER BY job_group_name, skill_rank, skill_name;
