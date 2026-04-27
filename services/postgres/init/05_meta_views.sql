CREATE OR REPLACE VIEW meta.v_pipeline_runs_recent AS
SELECT
  run_id,
  dag_id,
  task_id,
  source,
  layer,
  status,
  started_at,
  finished_at,
  EXTRACT(EPOCH FROM (COALESCE(finished_at, NOW()) - started_at))::BIGINT AS duration_seconds,
  rows_in,
  rows_out,
  rows_quarantined,
  error_message
FROM meta.pipeline_runs
WHERE started_at >= NOW() - INTERVAL '7 days'
ORDER BY started_at DESC;

CREATE OR REPLACE VIEW meta.v_pipeline_runs_summary AS
SELECT
  dag_id,
  layer,
  COUNT(*) FILTER (WHERE status = 'success') AS runs_success,
  COUNT(*) FILTER (WHERE status = 'failed') AS runs_failed,
  COALESCE(SUM(rows_in), 0) AS total_rows_in,
  COALESCE(SUM(rows_out), 0) AS total_rows_out,
  MAX(finished_at) AS last_finished_at
FROM meta.pipeline_runs
WHERE started_at >= NOW() - INTERVAL '7 days'
GROUP BY dag_id, layer
ORDER BY layer, dag_id;

CREATE OR REPLACE VIEW meta.v_dq_recent AS
SELECT
  id,
  dag_id,
  table_name,
  check_name,
  severity,
  passed,
  observed_value,
  expected_value,
  checked_at
FROM meta.dq_results
WHERE checked_at >= NOW() - INTERVAL '7 days'
ORDER BY checked_at DESC;
