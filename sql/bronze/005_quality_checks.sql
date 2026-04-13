-- Bronze quality check query templates.
-- Used by src/quality.py — {schema} and {table} are replaced at runtime.

-- TAG: count_pg_rows
SELECT COUNT(*) FROM {schema}.{table};

-- TAG: count_pg_columns
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_schema = :schema
  AND table_name = :table
  AND column_name NOT IN ('_source_file', '_ingested_at');
