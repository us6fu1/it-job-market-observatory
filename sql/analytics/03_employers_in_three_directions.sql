SELECT
    e.employer_name,
    count(DISTINCT g.job_group_sk) AS direction_count,
    array_agg(DISTINCT g.job_group_name ORDER BY g.job_group_name) AS directions,
    count(DISTINCT current.vacancy_sk) AS vacancy_count
FROM mart.v_current_vacancies AS current
JOIN dwh.dim_employer AS e ON e.employer_sk = current.employer_sk
JOIN dwh.bridge_vacancy_job_group AS vg ON vg.vacancy_sk = current.vacancy_sk
JOIN dwh.dim_job_group AS g ON g.job_group_sk = vg.job_group_sk
GROUP BY e.employer_id, e.employer_name
HAVING count(DISTINCT g.job_group_sk) >= 3
ORDER BY vacancy_count DESC, e.employer_name;
