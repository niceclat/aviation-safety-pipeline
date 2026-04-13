-- Silver layer: normalized aircraft with canonical make/model families.
-- Resolves the messy free-text aircraft naming into standardized families.

DROP TABLE IF EXISTS silver.aircraft_normalized CASCADE;

CREATE TABLE silver.aircraft_normalized AS
WITH make_normalized AS (
    SELECT
        a.*,
        -- Canonical manufacturer name
        CASE
            WHEN UPPER(TRIM(a.acft_make)) IN ('BOEING')
                OR UPPER(TRIM(a.acft_make)) LIKE 'BOEING%'
                THEN 'BOEING'
            WHEN UPPER(TRIM(a.acft_make)) IN ('AIRBUS', 'AIRBUS INDUSTRIE')
                OR UPPER(TRIM(a.acft_make)) LIKE 'AIRBUS%'
                THEN 'AIRBUS'
            WHEN UPPER(TRIM(a.acft_make)) IN (
                'BOMBARDIER', 'BOMBARDIER INC', 'CANADAIR',
                'DE HAVILLAND CANADA'
            ) OR UPPER(TRIM(a.acft_make)) LIKE 'BOMBARDIER%'
              OR UPPER(TRIM(a.acft_make)) LIKE 'CANADAIR%'
                THEN 'BOMBARDIER'
            WHEN UPPER(TRIM(a.acft_make)) LIKE 'EMBRAER%'
                THEN 'EMBRAER'
            WHEN UPPER(TRIM(a.acft_make)) IN ('CESSNA')
                OR UPPER(TRIM(a.acft_make)) LIKE 'CESSNA%'
                OR UPPER(TRIM(a.acft_make)) LIKE 'TEXTRON%'
                THEN 'CESSNA'
            WHEN UPPER(TRIM(a.acft_make)) IN ('BEECH', 'BEECHCRAFT')
                OR UPPER(TRIM(a.acft_make)) LIKE 'BEECH%'
                OR UPPER(TRIM(a.acft_make)) LIKE 'HAWKER BEECH%'
                THEN 'BEECHCRAFT'
            WHEN UPPER(TRIM(a.acft_make)) IN ('PIPER')
                OR UPPER(TRIM(a.acft_make)) LIKE 'PIPER%'
                THEN 'PIPER'
            WHEN UPPER(TRIM(a.acft_make)) IN ('BELL')
                OR UPPER(TRIM(a.acft_make)) LIKE 'BELL%'
                THEN 'BELL'
            WHEN UPPER(TRIM(a.acft_make)) IN (
                'MCDONNELL DOUGLAS', 'DOUGLAS', 'MCDONNELL'
            ) OR UPPER(TRIM(a.acft_make)) LIKE 'MCDONNELL%'
              OR UPPER(TRIM(a.acft_make)) LIKE 'DOUGLAS%'
                THEN 'MCDONNELL DOUGLAS'
            WHEN UPPER(TRIM(a.acft_make)) IN ('LOCKHEED', 'LOCKHEED MARTIN')
                OR UPPER(TRIM(a.acft_make)) LIKE 'LOCKHEED%'
                THEN 'LOCKHEED'
            WHEN UPPER(TRIM(a.acft_make)) LIKE 'DEHAVILLAND%'
                OR UPPER(TRIM(a.acft_make)) LIKE 'DE HAVILLAND%'
                THEN 'DEHAVILLAND'
            WHEN UPPER(TRIM(a.acft_make)) LIKE 'SIKORSKY%'
                THEN 'SIKORSKY'
            WHEN UPPER(TRIM(a.acft_make)) LIKE 'EUROCOPTER%'
                THEN 'EUROCOPTER'
            WHEN UPPER(TRIM(a.acft_make)) LIKE 'ROBINSON%'
                THEN 'ROBINSON'
            ELSE UPPER(TRIM(COALESCE(a.acft_make, 'UNKNOWN')))
        END AS manufacturer
    FROM bronze.aircraft a
    WHERE a.far_part IN ('121', '135')
),
model_extracted AS (
    SELECT
        m.*,
        -- Extract base model family using regex
        CASE
            -- Boeing: 3-digit base (707-787)
            WHEN m.manufacturer = 'BOEING'
                THEN COALESCE(
                    (regexp_match(UPPER(TRIM(m.acft_model)), '(7[0-9]7)'))[1],
                    (regexp_match(UPPER(TRIM(m.acft_model)), '(MD-\d+)'))[1],
                    UPPER(TRIM(m.acft_model))
                )
            -- Airbus: A3XX
            WHEN m.manufacturer = 'AIRBUS'
                THEN COALESCE(
                    (regexp_match(UPPER(TRIM(m.acft_model)), '(A\d{3})'))[1],
                    UPPER(TRIM(m.acft_model))
                )
            -- McDonnell Douglas: DC-X or MD-XX
            WHEN m.manufacturer = 'MCDONNELL DOUGLAS'
                THEN COALESCE(
                    (regexp_match(UPPER(TRIM(m.acft_model)), '(DC-\d+|MD-\d+)'))[1],
                    UPPER(TRIM(m.acft_model))
                )
            -- Bombardier: CL-600 / CRJ / DHC
            WHEN m.manufacturer = 'BOMBARDIER'
                THEN COALESCE(
                    (regexp_match(UPPER(TRIM(m.acft_model)), '(CL-\d+|CRJ|DHC-\d+)'))[1],
                    UPPER(TRIM(m.acft_model))
                )
            -- Embraer: EMB-XXX / ERJ-XXX / EXXX
            WHEN m.manufacturer = 'EMBRAER'
                THEN COALESCE(
                    (regexp_match(UPPER(TRIM(m.acft_model)), '(EMB-\d+|ERJ\s*\d+|E\d{3})'))[1],
                    UPPER(TRIM(m.acft_model))
                )
            -- Cessna: numeric model
            WHEN m.manufacturer = 'CESSNA'
                THEN COALESCE(
                    (regexp_match(UPPER(TRIM(m.acft_model)), '([A-Z]?\d{3})'))[1],
                    UPPER(TRIM(m.acft_model))
                )
            -- Piper: PA-XX
            WHEN m.manufacturer = 'PIPER'
                THEN COALESCE(
                    (regexp_match(UPPER(TRIM(m.acft_model)), '(PA[\s-]?\d+)'))[1],
                    UPPER(TRIM(m.acft_model))
                )
            -- Bell: 3-digit model
            WHEN m.manufacturer = 'BELL'
                THEN COALESCE(
                    (regexp_match(UPPER(TRIM(m.acft_model)), '(\d{3})'))[1],
                    UPPER(TRIM(m.acft_model))
                )
            -- Lockheed: L-XXXX
            WHEN m.manufacturer = 'LOCKHEED'
                THEN COALESCE(
                    (regexp_match(UPPER(TRIM(m.acft_model)), '(L-\d+)'))[1],
                    UPPER(TRIM(m.acft_model))
                )
            -- Generic fallback: first alphanumeric chunk
            ELSE COALESCE(
                (regexp_match(UPPER(TRIM(m.acft_model)), '([A-Z]*\d+[A-Z]?)'))[1],
                UPPER(TRIM(COALESCE(m.acft_model, 'UNKNOWN')))
            )
        END AS model_family
    FROM make_normalized m
)
SELECT
    me.ev_id,
    me.aircraft_key,
    me.regis_no,
    me.far_part,
    me.damage,
    me.acft_make           AS raw_make,
    me.acft_model          AS raw_model,
    me.acft_series,
    me.manufacturer,
    me.model_family,
    me.manufacturer || ' ' || me.model_family  AS model_full,
    me.acft_category,
    me.num_eng,
    me.total_seats,
    me.cert_max_gr_wt,
    me.acft_year,
    me.oper_name,
    me.oper_sched,
    me.oper_pax_cargo,
    me.type_fly,
    me.afm_hrs,
    me.second_pilot,

    -- Damage severity score
    CASE me.damage
        WHEN 'DEST' THEN 4
        WHEN 'SUBS' THEN 3
        WHEN 'MINR' THEN 2
        WHEN 'NONE' THEN 1
        ELSE 0
    END AS damage_score,

    me._source_file
FROM model_extracted me;

-- Indexes
CREATE INDEX idx_silver_aircraft_ev_id ON silver.aircraft_normalized (ev_id);
CREATE INDEX idx_silver_aircraft_model ON silver.aircraft_normalized (model_full);
CREATE INDEX idx_silver_aircraft_mfr ON silver.aircraft_normalized (manufacturer);
