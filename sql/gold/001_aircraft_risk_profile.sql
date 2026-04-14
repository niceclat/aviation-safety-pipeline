-- Gold layer: denormalized aircraft risk profile table.
-- One row per model family. Self-contained — readable without querying other tables.
--
-- Requirements (from PrincipalDE_External.md):
--   1. Compare models by risk          -> risk_tier, risk_rank, weighted_severity_score
--   2. Understand what drives risk      -> failure patterns, structured findings, NLP clusters
--   3. Spot improving/deteriorating     -> severity_trend, severity_slope, frequency_slope
--   4. Evidence to assign risk tier     -> all metrics + data_note
--   5. Self-contained                   -> no JOINs needed to read this table
--
-- Questions answered:
--   Q1 Severity trends per model       -> severity_trend, recent_severity, historical_severity
--   Q2 Failure patterns                -> top_failure_*, pct_*, causal_finding_categories
--   Q3 Narrative intelligence          -> NLP cluster insights, anomaly detection
--   Q4 Risk comparison                 -> risk_tier (CRITICAL/HIGH/MEDIUM/LOW), risk_rank

DROP TABLE IF EXISTS gold.aircraft_risk_profile CASCADE;

CREATE TABLE gold.aircraft_risk_profile AS

WITH commercial_events AS (
    SELECT
        a.ev_id,
        a.aircraft_key,
        a.manufacturer,
        a.model_family,
        a.model_full,
        a.acft_category,
        a.far_part,
        a.damage_score,
        a.model_raw,
        a.num_eng,
        a.total_seats,
        a.source_era,
        e.event_year,
        e.ev_date,
        e.ev_type,
        e.ev_highest_injury,
        e.injury_score,
        e.fatalities,
        e.serious_injuries,
        e.minor_injuries,
        e.uninjured,
        e.weather_category,
        e.light_cond
    FROM silver.aircraft_normalized a
    INNER JOIN silver.events_enriched e ON a.ev_id = e.ev_id
),

model_aggregates AS (
    SELECT
        ce.model_full,
        ce.manufacturer,
        ce.model_family,
        MAX(ce.acft_category)                               AS aircraft_category,
        STRING_AGG(DISTINCT ce.far_part, ', ' ORDER BY ce.far_part)
                                                            AS operation_types,
        STRING_AGG(DISTINCT ce.source_era, ', ' ORDER BY ce.source_era)
                                                            AS data_eras,
        -- Volume
        COUNT(*)                                            AS total_incidents,
        COUNT(*) FILTER (WHERE ce.ev_type = 'ACC')          AS total_accidents,
        COUNT(*) FILTER (WHERE ce.ev_type = 'INC')          AS total_incidents_only,
        MIN(ce.ev_date)                                     AS first_incident_date,
        MAX(ce.ev_date)                                     AS last_incident_date,
        COUNT(DISTINCT ce.event_year)                       AS years_with_incidents,

        -- Severity counts
        COUNT(*) FILTER (WHERE ce.ev_highest_injury = 'FATL')
                                                            AS fatal_event_count,
        COUNT(*) FILTER (WHERE ce.ev_highest_injury = 'SERS')
                                                            AS serious_event_count,
        SUM(ce.fatalities)                                  AS total_fatalities,
        SUM(ce.serious_injuries)                            AS total_serious_injuries,
        COUNT(*) FILTER (WHERE ce.damage_score = 4)         AS destroyed_count,

        -- Rates
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE ce.ev_highest_injury = 'FATL')
            / NULLIF(COUNT(*), 0), 2
        )                                                   AS fatality_rate_pct,
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE ce.damage_score = 4)
            / NULLIF(COUNT(*), 0), 2
        )                                                   AS destruction_rate_pct,

        -- Average severity
        ROUND(AVG(ce.injury_score), 2)                      AS avg_injury_score,
        ROUND(AVG(ce.damage_score), 2)                      AS avg_damage_score,
        ROUND(
            AVG(ce.injury_score * 0.6 + ce.damage_score * 0.4), 2
        )                                                   AS weighted_severity_score,

        -- Weather breakdown
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE ce.weather_category = 'IMC')
            / NULLIF(COUNT(*), 0), 2
        )                                                   AS pct_imc_conditions,

        -- Incident distribution by era
        COUNT(*) FILTER (WHERE ce.source_era = 'pre1982')   AS incidents_pre1982,
        COUNT(*) FILTER (WHERE ce.source_era = 'pre2008')   AS incidents_pre2008,
        COUNT(*) FILTER (WHERE ce.source_era = 'avall')     AS incidents_avall,

        -- Model characteristics
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ce.num_eng)
                                                            AS median_engines,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ce.total_seats)
                                                            AS median_seats
    FROM commercial_events ce
    GROUP BY ce.model_full, ce.manufacturer, ce.model_family
    HAVING COUNT(*) >= 10
),

-- Q1: Severity trend per model
severity_trend AS (
    SELECT
        ce.model_full,
        ROUND(
            AVG(ce.injury_score * 0.6 + ce.damage_score * 0.4)
            FILTER (WHERE ce.event_year >= EXTRACT(YEAR FROM NOW()) - 10), 2
        )                                                   AS recent_severity,
        ROUND(
            AVG(ce.injury_score * 0.6 + ce.damage_score * 0.4)
            FILTER (WHERE ce.event_year < EXTRACT(YEAR FROM NOW()) - 10), 2
        )                                                   AS historical_severity,
        ROUND(REGR_SLOPE(
            ce.injury_score * 0.6 + ce.damage_score * 0.4,
            ce.event_year
        )::NUMERIC, 4)                                      AS severity_slope
    FROM commercial_events ce
    GROUP BY ce.model_full
),

-- Q2: Failure patterns from NLP regex (exclude NULL = uncategorized)
failure_patterns AS (
    SELECT
        a.model_full,
        na.primary_category,
        COUNT(*) AS cat_count,
        ROW_NUMBER() OVER (
            PARTITION BY a.model_full
            ORDER BY COUNT(*) DESC
        ) AS rank,
        ROUND(100.0 * COUNT(*) FILTER (WHERE na.has_engine_failure)
            / NULLIF(COUNT(*), 0), 1)                       AS pct_engine,
        ROUND(100.0 * COUNT(*) FILTER (WHERE na.has_weather_factor)
            / NULLIF(COUNT(*), 0), 1)                       AS pct_weather,
        ROUND(100.0 * COUNT(*) FILTER (WHERE na.has_human_factors)
            / NULLIF(COUNT(*), 0), 1)                       AS pct_human,
        ROUND(100.0 * COUNT(*) FILTER (WHERE na.has_fire)
            / NULLIF(COUNT(*), 0), 1)                       AS pct_fire,
        ROUND(100.0 * COUNT(*) FILTER (WHERE na.has_structural)
            / NULLIF(COUNT(*), 0), 1)                       AS pct_structural,
        ROUND(100.0 * COUNT(*) FILTER (WHERE na.has_maintenance)
            / NULLIF(COUNT(*), 0), 1)                       AS pct_maintenance
    FROM silver.aircraft_normalized a
    LEFT JOIN silver.narrative_analysis na
        ON a.ev_id = na.ev_id AND a.aircraft_key = na.aircraft_key
    WHERE na.primary_category IS NOT NULL
    GROUP BY a.model_full, na.primary_category
),

top_failures AS (
    SELECT
        fp.model_full,
        MAX(fp.primary_category) FILTER (WHERE fp.rank = 1) AS top_failure_1,
        MAX(fp.cat_count) FILTER (WHERE fp.rank = 1)        AS top_failure_1_count,
        MAX(fp.primary_category) FILTER (WHERE fp.rank = 2) AS top_failure_2,
        MAX(fp.cat_count) FILTER (WHERE fp.rank = 2)        AS top_failure_2_count,
        MAX(fp.primary_category) FILTER (WHERE fp.rank = 3) AS top_failure_3,
        MAX(fp.cat_count) FILTER (WHERE fp.rank = 3)        AS top_failure_3_count,
        MAX(fp.pct_engine)                                  AS pct_engine_failure,
        MAX(fp.pct_weather)                                 AS pct_weather_related,
        MAX(fp.pct_human)                                   AS pct_human_factor,
        MAX(fp.pct_fire)                                    AS pct_fire_related,
        MAX(fp.pct_structural)                              AS pct_structural_failure,
        MAX(fp.pct_maintenance)                             AS pct_maintenance_related
    FROM failure_patterns fp
    WHERE fp.rank <= 3
    GROUP BY fp.model_full
),

-- Q2 continued: Structured findings from NTSB
structured_findings AS (
    SELECT
        a.model_full,
        STRING_AGG(
            DISTINCT fe.finding_category, ', '
            ORDER BY fe.finding_category
        ) FILTER (WHERE fe.cause_factor = 'C')              AS causal_finding_categories,
        COUNT(*) FILTER (WHERE fe.finding_category = 'Aircraft'
                         AND fe.cause_factor = 'C')         AS aircraft_causes,
        COUNT(*) FILTER (WHERE fe.finding_category = 'Personnel'
                         AND fe.cause_factor = 'C')         AS personnel_causes,
        COUNT(*) FILTER (WHERE fe.finding_category = 'Environmental'
                         AND fe.cause_factor = 'C')         AS environmental_causes
    FROM silver.aircraft_normalized a
    LEFT JOIN silver.findings_enriched fe
        ON a.ev_id = fe.ev_id AND a.aircraft_key = fe.aircraft_key
    GROUP BY a.model_full
),

-- Q3: Narrative intelligence from FAISS clustering
narrative_intelligence AS (
    SELECT
        a.model_full,
        COUNT(DISTINCT na.cluster_id)                       AS n_distinct_clusters,
        ROUND(AVG(na.anomaly_score)::NUMERIC, 4)            AS avg_anomaly_score,
        COUNT(*) FILTER (WHERE na.anomaly_score > 0.7)      AS high_anomaly_count,
        ROUND(100.0 * COUNT(*) FILTER (WHERE na.n_categories > 0)
            / NULLIF(COUNT(*), 0), 1)                       AS pct_nlp_categorized,
        MODE() WITHIN GROUP (ORDER BY na.cluster_id)        AS dominant_cluster_id
    FROM silver.aircraft_normalized a
    LEFT JOIN silver.narrative_analysis na
        ON a.ev_id = na.ev_id AND a.aircraft_key = na.aircraft_key
    GROUP BY a.model_full
)

-- Final assembly: self-contained risk profile
SELECT
    -- Identity
    ma.manufacturer,
    ma.model_family,
    ma.model_full,
    ma.aircraft_category,
    ma.operation_types,
    ROUND(ma.median_engines)::INT                           AS typical_engines,
    ROUND(ma.median_seats)::INT                             AS typical_seats,

    -- Volume / Exposure
    ma.total_incidents,
    ma.total_accidents,
    ma.total_incidents_only,
    ma.years_with_incidents,
    ma.first_incident_date::DATE,
    ma.last_incident_date::DATE,
    ROUND(
        ma.total_incidents::NUMERIC
        / NULLIF(ma.years_with_incidents, 0), 1
    )                                                       AS avg_incidents_per_year,

    -- Data coverage
    ma.data_eras,
    ma.incidents_pre1982,
    ma.incidents_pre2008,
    ma.incidents_avall,

    -- Q1: Severity metrics
    ma.fatal_event_count,
    ma.serious_event_count,
    ma.total_fatalities,
    ma.total_serious_injuries,
    ma.destroyed_count,
    ma.fatality_rate_pct,
    ma.destruction_rate_pct,
    ma.avg_injury_score,
    ma.avg_damage_score,
    ma.weighted_severity_score,

    -- Q1: Trend analysis
    st.recent_severity,
    st.historical_severity,
    CASE
        WHEN st.recent_severity IS NULL OR st.historical_severity IS NULL
            THEN 'INSUFFICIENT_DATA'
        WHEN st.recent_severity < st.historical_severity - 0.2
            THEN 'IMPROVING'
        WHEN st.recent_severity > st.historical_severity + 0.2
            THEN 'WORSENING'
        ELSE 'STABLE'
    END                                                     AS severity_trend,
    st.severity_slope,

    -- Q2: Failure patterns (NLP regex-derived)
    tf.top_failure_1,
    tf.top_failure_1_count,
    tf.top_failure_2,
    tf.top_failure_2_count,
    tf.top_failure_3,
    tf.top_failure_3_count,
    tf.pct_engine_failure,
    tf.pct_weather_related,
    tf.pct_human_factor,
    tf.pct_fire_related,
    tf.pct_structural_failure,
    tf.pct_maintenance_related,

    -- Q2: Structured findings
    sf.causal_finding_categories,
    sf.aircraft_causes,
    sf.personnel_causes,
    sf.environmental_causes,

    -- Q3: Narrative intelligence (FAISS-derived)
    ni.n_distinct_clusters,
    ni.avg_anomaly_score,
    ni.high_anomaly_count,
    ni.pct_nlp_categorized,
    ni.dominant_cluster_id,

    -- Weather
    ma.pct_imc_conditions,

    -- Q4: Risk tier (quartile-based composite)
    NTILE(4) OVER (
        ORDER BY ma.weighted_severity_score DESC,
                 ma.fatality_rate_pct DESC,
                 ma.destruction_rate_pct DESC
    )                                                       AS risk_quartile,
    CASE NTILE(4) OVER (
        ORDER BY ma.weighted_severity_score DESC,
                 ma.fatality_rate_pct DESC,
                 ma.destruction_rate_pct DESC
    )
        WHEN 1 THEN 'CRITICAL'
        WHEN 2 THEN 'HIGH'
        WHEN 3 THEN 'MEDIUM'
        WHEN 4 THEN 'LOW'
    END                                                     AS risk_tier,

    RANK() OVER (
        ORDER BY ma.weighted_severity_score DESC,
                 ma.fatality_rate_pct DESC
    )                                                       AS risk_rank,

    -- Metadata
    NOW()::DATE                                             AS data_as_of,
    'Based on ' || ma.total_incidents || ' incidents ('
        || EXTRACT(YEAR FROM ma.first_incident_date)::INT || '-'
        || EXTRACT(YEAR FROM ma.last_incident_date)::INT || ')'
                                                            AS data_note

FROM model_aggregates ma
LEFT JOIN severity_trend st ON ma.model_full = st.model_full
LEFT JOIN top_failures tf ON ma.model_full = tf.model_full
LEFT JOIN structured_findings sf ON ma.model_full = sf.model_full
LEFT JOIN narrative_intelligence ni ON ma.model_full = ni.model_full
ORDER BY ma.weighted_severity_score DESC, ma.total_incidents DESC;
