WITH checks AS (
    SELECT
        'duplicate_vacancy_in_snapshot'::text AS check_name,
        count(*)::bigint AS failed_rows
    FROM (
        SELECT run_id, vacancy_sk
        FROM dwh.fact_vacancy_snapshot
        GROUP BY run_id, vacancy_sk
        HAVING count(*) > 1
    ) AS duplicates

    UNION ALL

    SELECT
        'invalid_salary_bounds',
        count(*)
    FROM dwh.fact_vacancy_snapshot
    WHERE salary_from < 0
       OR salary_to < 0
       OR (salary_from IS NOT NULL AND salary_to IS NOT NULL AND salary_from > salary_to)

    UNION ALL

    SELECT
        'orphan_snapshot_vacancy',
        count(*)
    FROM dwh.fact_vacancy_snapshot AS fact
    LEFT JOIN dwh.dim_vacancy AS vacancy ON vacancy.vacancy_sk = fact.vacancy_sk
    WHERE vacancy.vacancy_sk IS NULL

    UNION ALL

    SELECT
        'segment_over_2000',
        count(*)
    FROM audit.search_segment
    WHERE found > 2000
      AND status <> 'over_limit'

    UNION ALL

    SELECT
        'missing_required_vacancy_fields',
        count(*)
    FROM stg.v_vacancy_normalized
    WHERE vacancy_id IS NULL OR vacancy_name IS NULL

    UNION ALL

    SELECT
        'rejected_rows',
        COALESCE(sum(rejected_rows), 0)::bigint
    FROM audit.etl_run
    WHERE status IN ('success', 'partial')
)
SELECT check_name, failed_rows
FROM checks
ORDER BY check_name;
