-- Silver layer: enriched events table
-- Combines event metadata with computed severity scores and weather categorization.

DROP TABLE IF EXISTS silver.events_enriched CASCADE;

CREATE TABLE silver.events_enriched AS
WITH severity_scored AS (
    SELECT
        e.ev_id,
        e.ev_type,
        e.ev_date,
        EXTRACT(YEAR FROM e.ev_date)::INT                  AS event_year,
        EXTRACT(MONTH FROM e.ev_date)::INT                 AS event_month,
        e.ev_city,
        e.ev_state,
        e.ev_country,
        e.ev_highest_injury,
        e.light_cond,
        e.wx_cond_basic,
        e.vis_sm,
        e.wind_vel_kts,

        -- Injury totals
        COALESCE(e.inj_tot_f, 0)                           AS fatalities,
        COALESCE(e.inj_tot_s, 0)                           AS serious_injuries,
        COALESCE(e.inj_tot_m, 0)                           AS minor_injuries,
        COALESCE(e.inj_tot_n, 0)                           AS uninjured,

        -- Numeric severity scores
        CASE e.ev_highest_injury
            WHEN 'FATL' THEN 4
            WHEN 'SERS' THEN 3
            WHEN 'MINR' THEN 2
            WHEN 'NONE' THEN 1
            ELSE 0
        END                                                 AS injury_score,

        -- Weather categorization
        CASE
            WHEN e.wx_cond_basic = 'IMC' THEN 'IMC'
            WHEN e.wx_cond_basic = 'VMC' THEN 'VMC'
            ELSE 'UNKNOWN'
        END                                                 AS weather_category,

        -- Latitude/longitude as numeric
        e.dec_latitude,
        e.dec_longitude,

        e._source_file
    FROM bronze.events e
)
SELECT
    s.*,
    -- Combined severity = 60% injury + 40% damage (joined in aircraft table)
    -- This field computed at event level using injury score only
    s.injury_score                                          AS event_severity_score,

    -- Time-based features
    CASE
        WHEN s.event_year >= 2018 THEN 'recent_5yr'
        WHEN s.event_year >= 2008 THEN 'modern'
        WHEN s.event_year >= 1998 THEN 'mid_era'
        ELSE 'historical'
    END                                                     AS time_era
FROM severity_scored s;

-- Indexes for join performance
CREATE INDEX idx_silver_events_ev_id ON silver.events_enriched (ev_id);
CREATE INDEX idx_silver_events_year ON silver.events_enriched (event_year);
