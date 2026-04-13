-- Silver layer: unified events from all 3 bronze sources.
-- Casts TEXT to proper types, computes severity scores, tags source era.
-- See docs/DATA_CONTRACT.md for field mappings.

DROP TABLE IF EXISTS silver.events_enriched CASCADE;

CREATE TABLE silver.events_enriched AS

-- avall (2008-present)
SELECT
    e.ev_id,
    e.ev_type,
    e.ev_date::TIMESTAMP                                AS ev_date,
    EXTRACT(YEAR FROM e.ev_date::TIMESTAMP)::INT        AS event_year,
    EXTRACT(MONTH FROM e.ev_date::TIMESTAMP)::INT       AS event_month,
    e.ev_city,
    e.ev_state,
    e.ev_country,
    TRIM(e.ev_highest_injury)                           AS ev_highest_injury,
    e.light_cond,
    e.wx_cond_basic,
    NULLIF(e.vis_sm, '')::REAL                          AS vis_sm,
    NULLIF(e.wind_vel_kts, '')::SMALLINT                AS wind_vel_kts,
    COALESCE(NULLIF(e.inj_tot_f, '')::INT, 0)          AS fatalities,
    COALESCE(NULLIF(e.inj_tot_s, '')::INT, 0)          AS serious_injuries,
    COALESCE(NULLIF(e.inj_tot_m, '')::INT, 0)          AS minor_injuries,
    COALESCE(NULLIF(e.inj_tot_n, '')::INT, 0)          AS uninjured,
    NULLIF(e.dec_latitude, '')::DOUBLE PRECISION        AS dec_latitude,
    NULLIF(e.dec_longitude, '')::DOUBLE PRECISION       AS dec_longitude,
    CASE TRIM(e.ev_highest_injury)
        WHEN 'FATL' THEN 4 WHEN 'SERS' THEN 3
        WHEN 'MINR' THEN 2 WHEN 'NONE' THEN 1 ELSE 0
    END                                                 AS injury_score,
    CASE
        WHEN e.wx_cond_basic = 'IMC' THEN 'IMC'
        WHEN e.wx_cond_basic = 'VMC' THEN 'VMC'
        ELSE 'UNKNOWN'
    END                                                 AS weather_category,
    'avall'                                             AS source_era
FROM bronze_avall.events e
WHERE e.ev_date IS NOT NULL AND e.ev_date != ''

UNION ALL

-- Pre2008 (1982-2007)
SELECT
    e.ev_id,
    e.ev_type,
    e.ev_date::TIMESTAMP,
    EXTRACT(YEAR FROM e.ev_date::TIMESTAMP)::INT,
    EXTRACT(MONTH FROM e.ev_date::TIMESTAMP)::INT,
    e.ev_city,
    e.ev_state,
    e.ev_country,
    TRIM(e.ev_highest_injury),
    e.light_cond,
    e.wx_cond_basic,
    NULLIF(e.vis_sm, '')::REAL,
    NULLIF(e.wind_vel_kts, '')::SMALLINT,
    COALESCE(NULLIF(e.inj_tot_f, '')::INT, 0),
    COALESCE(NULLIF(e.inj_tot_s, '')::INT, 0),
    COALESCE(NULLIF(e.inj_tot_m, '')::INT, 0),
    COALESCE(NULLIF(e.inj_tot_n, '')::INT, 0),
    NULLIF(e.dec_latitude, '')::DOUBLE PRECISION,
    NULLIF(e.dec_longitude, '')::DOUBLE PRECISION,
    CASE TRIM(e.ev_highest_injury)
        WHEN 'FATL' THEN 4 WHEN 'SERS' THEN 3
        WHEN 'MINR' THEN 2 WHEN 'NONE' THEN 1 ELSE 0
    END,
    CASE
        WHEN e.wx_cond_basic = 'IMC' THEN 'IMC'
        WHEN e.wx_cond_basic = 'VMC' THEN 'VMC'
        ELSE 'UNKNOWN'
    END,
    'pre2008'
FROM bronze_pre2008.events e
WHERE e.ev_date IS NOT NULL AND e.ev_date != ''

UNION ALL

-- PRE1982 (1962-1981) — mapped from flat schema per DATA_CONTRACT.md
SELECT
    'PRE1982_' || f.recnum                              AS ev_id,
    CASE
        WHEN f.acc_inc_class IN ('A','B','F','G') THEN 'ACC'
        ELSE 'INC'
    END                                                 AS ev_type,
    f.date_occurrence::TIMESTAMP,
    EXTRACT(YEAR FROM f.date_occurrence::TIMESTAMP)::INT,
    EXTRACT(MONTH FROM f.date_occurrence::TIMESTAMP)::INT,
    f.location                                          AS ev_city,
    f.locat_state_terr                                  AS ev_state,
    'US'                                                AS ev_country,
    CASE
        WHEN NULLIF(f.grand_total_fatal, '')::INT > 0 THEN 'FATL'
        WHEN NULLIF(f.grand_total_serious, '')::INT > 0 THEN 'SERS'
        WHEN NULLIF(f.grand_total_minor, '')::INT > 0 THEN 'MINR'
        ELSE 'NONE'
    END                                                 AS ev_highest_injury,
    f.light_cond,
    NULL                                                AS wx_cond_basic,
    NULL::REAL                                          AS vis_sm,
    NULL::SMALLINT                                      AS wind_vel_kts,
    COALESCE(NULLIF(f.grand_total_fatal, '')::INT, 0)   AS fatalities,
    COALESCE(NULLIF(f.grand_total_serious, '')::INT, 0) AS serious_injuries,
    COALESCE(NULLIF(f.grand_total_minor, '')::INT, 0)   AS minor_injuries,
    COALESCE(NULLIF(f.grand_total_none, '')::INT, 0)    AS uninjured,
    NULL::DOUBLE PRECISION                              AS dec_latitude,
    NULL::DOUBLE PRECISION                              AS dec_longitude,
    CASE
        WHEN NULLIF(f.grand_total_fatal, '')::INT > 0 THEN 4
        WHEN NULLIF(f.grand_total_serious, '')::INT > 0 THEN 3
        WHEN NULLIF(f.grand_total_minor, '')::INT > 0 THEN 2
        ELSE 1
    END                                                 AS injury_score,
    'UNKNOWN'                                           AS weather_category,
    'pre1982'                                           AS source_era
FROM bronze_pre1982.tbl_first_half f
WHERE f.date_occurrence IS NOT NULL AND f.date_occurrence != '';

CREATE INDEX idx_silver_events_ev_id ON silver.events_enriched (ev_id);
CREATE INDEX idx_silver_events_year ON silver.events_enriched (event_year);
CREATE INDEX idx_silver_events_era ON silver.events_enriched (source_era);
