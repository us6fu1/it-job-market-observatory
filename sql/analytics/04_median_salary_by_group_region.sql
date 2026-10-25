SELECT
    g.job_group_name,
    a.area_name,
    current.salary_currency,
    count(*) AS vacancy_count,
    count(*) FILTER (
        WHERE current.salary_from IS NOT NULL OR current.salary_to IS NOT NULL
    ) AS salary_known_count,
    count(*) FILTER (
        WHERE current.salary_from IS NOT NULL AND current.salary_to IS NOT NULL
    ) AS two_bound_count,
    percentile_cont(0.5) WITHIN GROUP (
        ORDER BY (current.salary_from + current.salary_to) / 2.0
    ) FILTER (
        WHERE current.salary_from IS NOT NULL AND current.salary_to IS NOT NULL
    ) AS median_two_bound_midpoint
FROM mart.v_current_vacancies AS current
JOIN dwh.bridge_vacancy_job_group AS vg ON vg.vacancy_sk = current.vacancy_sk
JOIN dwh.dim_job_group AS g ON g.job_group_sk = vg.job_group_sk
LEFT JOIN dwh.dim_area AS a ON a.area_sk = current.area_sk
GROUP BY g.job_group_name, a.area_name, current.salary_currency
ORDER BY g.job_group_name, a.area_name, current.salary_currency;
