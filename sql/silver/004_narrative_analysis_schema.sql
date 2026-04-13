-- Silver layer: create narrative analysis table (populated by Python NLP module).

DROP TABLE IF EXISTS silver.narrative_analysis CASCADE;

CREATE TABLE silver.narrative_analysis (
    ev_id               VARCHAR(14),
    aircraft_key        INTEGER,
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
    narrative_length    INTEGER
);
