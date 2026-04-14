-- Governance: pipeline run metadata, lineage, and monitoring.
-- Tracks every pipeline execution for auditability.

CREATE SCHEMA IF NOT EXISTS governance;

-- Pipeline run log — one row per execution
DROP TABLE IF EXISTS governance.pipeline_runs CASCADE;
CREATE TABLE governance.pipeline_runs (
    run_id          SERIAL PRIMARY KEY,
    started_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'RUNNING',  -- RUNNING, SUCCESS, FAILED
    duration_secs   REAL,
    error_message   TEXT,
    -- Row counts per layer
    bronze_rows     BIGINT,
    silver_rows     BIGINT,
    gold_rows       BIGINT,
    nlp_rows        BIGINT,
    -- Contract version used
    contract_version TEXT,
    -- Environment
    backend         TEXT,
    hostname        TEXT
);

-- Step-level tracking within a run
DROP TABLE IF EXISTS governance.pipeline_steps CASCADE;
CREATE TABLE governance.pipeline_steps (
    step_id         SERIAL PRIMARY KEY,
    run_id          INTEGER REFERENCES governance.pipeline_runs(run_id),
    step_name       TEXT NOT NULL,
    started_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'RUNNING',
    duration_secs   REAL,
    rows_affected   BIGINT,
    error_message   TEXT
);

-- Data freshness — when was each table last refreshed?
DROP TABLE IF EXISTS governance.table_freshness CASCADE;
CREATE TABLE governance.table_freshness (
    schema_name     TEXT NOT NULL,
    table_name      TEXT NOT NULL,
    last_refreshed  TIMESTAMP NOT NULL DEFAULT NOW(),
    row_count       BIGINT,
    run_id          INTEGER REFERENCES governance.pipeline_runs(run_id),
    PRIMARY KEY (schema_name, table_name)
);
