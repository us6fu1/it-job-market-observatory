-- Запускайте на копии базы и сохраните фактические планы в docs/benchmarks/.
-- Первый запрос показывает план до добавления составного индекса.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT run_id, vacancy_sk, observed_at
FROM dwh.fact_vacancy_snapshot
WHERE observed_at >= now() - interval '30 days'
  AND is_available = true
ORDER BY observed_at DESC;

CREATE INDEX IF NOT EXISTS ix_snapshot_available_observed
    ON dwh.fact_vacancy_snapshot (is_available, observed_at DESC)
    INCLUDE (run_id, vacancy_sk);

ANALYZE dwh.fact_vacancy_snapshot;

-- Второй план можно сравнить по Execution Time, Buffers и типу сканирования.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT run_id, vacancy_sk, observed_at
FROM dwh.fact_vacancy_snapshot
WHERE observed_at >= now() - interval '30 days'
  AND is_available = true
ORDER BY observed_at DESC;
