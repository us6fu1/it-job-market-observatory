-- Сравниваются два последних завершённых снимка.
-- "Пропала из поиска" не означает "закрыта". Закрытие проверяется отдельно.
WITH selected_runs AS (
    SELECT
        run_id,
        started_at,
        row_number() OVER (ORDER BY started_at DESC) AS position
    FROM audit.etl_run
    WHERE status IN ('success', 'partial')
), previous_snapshot AS (
    SELECT f.vacancy_sk
    FROM dwh.fact_vacancy_snapshot AS f
    JOIN selected_runs AS r ON r.run_id = f.run_id AND r.position = 2
    WHERE f.is_available
), current_snapshot AS (
    SELECT f.vacancy_sk
    FROM dwh.fact_vacancy_snapshot AS f
    JOIN selected_runs AS r ON r.run_id = f.run_id AND r.position = 1
    WHERE f.is_available
)
SELECT
    v.vacancy_id,
    v.vacancy_name,
    CASE
        WHEN previous_snapshot.vacancy_sk IS NULL THEN 'new_in_search'
        WHEN current_snapshot.vacancy_sk IS NULL THEN 'not_seen_in_latest_search'
        ELSE 'still_in_search'
    END AS search_state
FROM previous_snapshot
FULL OUTER JOIN current_snapshot
    ON current_snapshot.vacancy_sk = previous_snapshot.vacancy_sk
JOIN dwh.dim_vacancy AS v
    ON v.vacancy_sk = COALESCE(
        current_snapshot.vacancy_sk,
        previous_snapshot.vacancy_sk
    )
ORDER BY search_state, v.vacancy_id;
