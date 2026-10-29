-- Сравниваются два последних завершённых снимка каждого источника.
-- "Пропала из поиска" не означает "закрыта". Закрытие проверяется отдельно.
WITH available_sources AS (
    SELECT DISTINCT source
    FROM audit.etl_run
    WHERE status IN ('success', 'partial')
), selected_sources AS (
    SELECT source FROM available_sources WHERE source <> 'synthetic_demo'
    UNION ALL
    SELECT source
    FROM available_sources
    WHERE source = 'synthetic_demo'
      AND NOT EXISTS (
          SELECT 1 FROM available_sources WHERE source <> 'synthetic_demo'
      )
), selected_runs AS (
    SELECT
        run.source,
        run.run_id,
        run.started_at,
        row_number() OVER (
            PARTITION BY run.source
            ORDER BY run.started_at DESC
        ) AS position
    FROM audit.etl_run AS run
    JOIN selected_sources AS source ON source.source = run.source
    WHERE run.status IN ('success', 'partial')
), previous_snapshot AS (
    SELECT r.source, f.vacancy_sk
    FROM dwh.fact_vacancy_snapshot AS f
    JOIN selected_runs AS r ON r.run_id = f.run_id AND r.position = 2
    WHERE f.is_available
), current_snapshot AS (
    SELECT r.source, f.vacancy_sk
    FROM dwh.fact_vacancy_snapshot AS f
    JOIN selected_runs AS r ON r.run_id = f.run_id AND r.position = 1
    WHERE f.is_available
)
SELECT
    COALESCE(current_snapshot.source, previous_snapshot.source) AS source,
    v.vacancy_id,
    v.vacancy_name,
    CASE
        WHEN previous_snapshot.vacancy_sk IS NULL THEN 'new_in_search'
        WHEN current_snapshot.vacancy_sk IS NULL THEN 'not_seen_in_latest_search'
        ELSE 'still_in_search'
    END AS search_state
FROM previous_snapshot
FULL OUTER JOIN current_snapshot
    ON current_snapshot.source = previous_snapshot.source
   AND current_snapshot.vacancy_sk = previous_snapshot.vacancy_sk
JOIN dwh.dim_vacancy AS v
    ON v.vacancy_sk = COALESCE(
        current_snapshot.vacancy_sk,
        previous_snapshot.vacancy_sk
    )
ORDER BY source, search_state, v.vacancy_id;
