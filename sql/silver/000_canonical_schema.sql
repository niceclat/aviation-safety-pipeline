-- Silver layer: canonical model schema.
-- Target tables for the unified data model.
-- Generated/driven by src/contracts.py — do not edit mappings here.

-- Lookup tables (populated by contracts.py from Python dicts)
DROP TABLE IF EXISTS silver._lookup_far_part CASCADE;
CREATE TABLE silver._lookup_far_part (
    source_code     TEXT PRIMARY KEY,
    canonical_code  TEXT NOT NULL,
    description     TEXT
);

DROP TABLE IF EXISTS silver._lookup_damage CASCADE;
CREATE TABLE silver._lookup_damage (
    source_code     TEXT PRIMARY KEY,
    canonical_code  TEXT NOT NULL,
    description     TEXT
);

DROP TABLE IF EXISTS silver._lookup_event_type CASCADE;
CREATE TABLE silver._lookup_event_type (
    source_code     TEXT PRIMARY KEY,
    canonical_code  TEXT NOT NULL,
    description     TEXT
);

DROP TABLE IF EXISTS silver._lookup_aircraft_category CASCADE;
CREATE TABLE silver._lookup_aircraft_category (
    source_code     TEXT PRIMARY KEY,
    canonical_code  TEXT NOT NULL,
    description     TEXT
);

DROP TABLE IF EXISTS silver._lookup_manufacturer CASCADE;
CREATE TABLE silver._lookup_manufacturer (
    match_prefix    TEXT PRIMARY KEY,
    canonical_name  TEXT NOT NULL
);

DROP TABLE IF EXISTS silver._lookup_severity CASCADE;
CREATE TABLE silver._lookup_severity (
    injury_level    TEXT,
    damage_level    TEXT,
    injury_score    INTEGER,
    damage_score    INTEGER
);
