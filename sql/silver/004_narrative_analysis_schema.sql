-- Silver layer: narrative analysis table.
-- Populated by src/nlp/pipeline.py (regex + embeddings + FAISS).

-- Enable pgvector extension for embedding storage
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS silver.narrative_analysis CASCADE;

CREATE TABLE silver.narrative_analysis (
    ev_id               TEXT,
    aircraft_key        INTEGER,
    -- Regex categorization
    failure_categories  TEXT[],
    primary_category    TEXT,
    n_categories        INTEGER,
    text_severity_score INTEGER,
    has_engine_failure  BOOLEAN,
    has_weather_factor  BOOLEAN,
    has_human_factors   BOOLEAN,
    has_fire            BOOLEAN,
    has_structural      BOOLEAN,
    has_maintenance     BOOLEAN,
    narrative_length    INTEGER,
    -- FAISS clustering
    cluster_id          INTEGER,
    anomaly_score       REAL,
    -- Sentence embedding (pgvector)
    embedding           vector(384)
);

CREATE INDEX idx_narrative_ev_id ON silver.narrative_analysis (ev_id);
CREATE INDEX idx_narrative_cluster ON silver.narrative_analysis (cluster_id);
CREATE INDEX idx_narrative_anomaly ON silver.narrative_analysis (anomaly_score DESC);
