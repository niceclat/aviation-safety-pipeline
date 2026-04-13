-- Silver layer: unified, normalized aircraft from all 3 bronze sources.
-- Resolves messy free-text naming into canonical make/model families.
-- Filters to commercial operations (Part 121 + 135 or PRE1982 equivalents).
-- See docs/DATA_CONTRACT.md for PRE1982 code mappings.

DROP TABLE IF EXISTS silver.aircraft_normalized CASCADE;

CREATE TABLE silver.aircraft_normalized AS

WITH raw_aircraft AS (
    -- avall (2008-present)
    SELECT
        a.ev_id,
        NULLIF(a.aircraft_key, '')::INT                 AS aircraft_key,
        a.regis_no,
        TRIM(a.far_part)                                AS far_part,
        TRIM(a.damage)                                  AS damage,
        a.acft_make                                     AS make_raw,
        a.acft_model                                    AS model_raw,
        a.acft_series,
        a.acft_category,
        NULLIF(a.num_eng, '')::SMALLINT                 AS num_eng,
        NULLIF(a.total_seats, '')::SMALLINT             AS total_seats,
        NULLIF(a.cert_max_gr_wt, '')::INT               AS cert_max_gr_wt,
        NULLIF(a.acft_year, '')::INT                    AS acft_year,
        a.oper_name,
        a.oper_sched,
        a.oper_pax_cargo,
        a.type_fly,
        NULLIF(a.afm_hrs, '')::REAL                     AS afm_hrs,
        a.second_pilot,
        'avall'                                         AS source_era
    FROM bronze_avall.aircraft a
    WHERE TRIM(a.far_part) IN ('121', '135')

    UNION ALL

    -- Pre2008 (1982-2007)
    SELECT
        a.ev_id,
        NULLIF(a.aircraft_key, '')::INT,
        a.regis_no,
        TRIM(a.far_part),
        TRIM(a.damage),
        a.acft_make,
        a.acft_model,
        a.acft_series,
        a.acft_category,
        NULLIF(a.num_eng, '')::SMALLINT,
        NULLIF(a.total_seats, '')::SMALLINT,
        NULLIF(a.cert_max_gr_wt, '')::INT,
        NULLIF(a.acft_year, '')::INT,
        a.oper_name,
        a.oper_sched,
        a.oper_pax_cargo,
        a.type_fly,
        NULLIF(a.afm_hrs, '')::REAL,
        a.second_pilot,
        'pre2008'
    FROM bronze_pre2008.aircraft a
    WHERE TRIM(a.far_part) IN ('121', '135')

    UNION ALL

    -- PRE1982 (1962-1981) — mapped from flat schema
    SELECT
        'PRE1982_' || f.recnum                          AS ev_id,
        1                                               AS aircraft_key,
        f.regist_no                                     AS regis_no,
        -- TYPE_OPERATOR → far_part mapping (DATA_CONTRACT.md)
        CASE f.type_operator
            WHEN 'E' THEN '135'   -- Air Taxi
            WHEN 'P' THEN '135'   -- Contract Carrier
            WHEN 'N' THEN '121'   -- Intrastate Carrier
            ELSE '091'
        END                                             AS far_part,
        -- ACFT_ADAMG → damage mapping
        CASE f.acft_adamg
            WHEN 'D' THEN 'DEST'
            WHEN 'S' THEN 'SUBS'
            WHEN 'M' THEN 'MINR'
            WHEN 'N' THEN 'NONE'
            ELSE 'UNK'
        END                                             AS damage,
        f.acft_make                                     AS make_raw,
        f.acft_model                                    AS model_raw,
        NULL                                            AS acft_series,
        -- TYPE_CRAFT → acft_category mapping
        CASE f.type_craft
            WHEN 'A' THEN 'AIR'
            WHEN 'B' THEN 'HELI'
            WHEN 'C' THEN 'GLI'
            WHEN 'D' THEN 'BALL'
            WHEN 'E' THEN 'BLIM'
            WHEN 'I' THEN 'GYRO'
            ELSE 'UNK'
        END                                             AS acft_category,
        NULLIF(f.no_engines, '')::SMALLINT              AS num_eng,
        NULL::SMALLINT                                  AS total_seats,
        NULL::INT                                       AS cert_max_gr_wt,
        NULL::INT                                       AS acft_year,
        f.operator                                      AS oper_name,
        NULL                                            AS oper_sched,
        NULL                                            AS oper_pax_cargo,
        f.kind_fly_gena                                 AS type_fly,
        NULL::REAL                                      AS afm_hrs,
        NULL                                            AS second_pilot,
        'pre1982'                                       AS source_era
    FROM bronze_pre1982.tbl_first_half f
    WHERE f.type_operator IN ('E', 'P', 'N')  -- commercial ops only
),

make_normalized AS (
    SELECT
        r.*,
        CASE
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'BOEING%' THEN 'BOEING'
            WHEN UPPER(TRIM(r.make_raw)) IN ('AIRBUS','AIRBUS INDUSTRIE')
                OR UPPER(TRIM(r.make_raw)) LIKE 'AIRBUS%' THEN 'AIRBUS'
            WHEN UPPER(TRIM(r.make_raw)) IN ('BOMBARDIER','BOMBARDIER INC','CANADAIR','DE HAVILLAND CANADA')
                OR UPPER(TRIM(r.make_raw)) LIKE 'BOMBARDIER%'
                OR UPPER(TRIM(r.make_raw)) LIKE 'CANADAIR%' THEN 'BOMBARDIER'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'EMBRAER%' THEN 'EMBRAER'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'CESSNA%'
                OR UPPER(TRIM(r.make_raw)) LIKE 'TEXTRON%' THEN 'CESSNA'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'BEECH%'
                OR UPPER(TRIM(r.make_raw)) LIKE 'HAWKER BEECH%' THEN 'BEECHCRAFT'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'PIPER%' THEN 'PIPER'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'BELL%' THEN 'BELL'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'MCDONNELL%'
                OR UPPER(TRIM(r.make_raw)) LIKE 'DOUGLAS%' THEN 'MCDONNELL DOUGLAS'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'LOCKHEED%' THEN 'LOCKHEED'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'DEHAVILLAND%'
                OR UPPER(TRIM(r.make_raw)) LIKE 'DE HAVILLAND%' THEN 'DEHAVILLAND'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'SIKORSKY%' THEN 'SIKORSKY'
            WHEN UPPER(TRIM(r.make_raw)) LIKE 'EUROCOPTER%' THEN 'EUROCOPTER'
            ELSE UPPER(TRIM(COALESCE(r.make_raw, 'UNKNOWN')))
        END AS manufacturer
    FROM raw_aircraft r
),

model_extracted AS (
    SELECT
        m.*,
        CASE
            WHEN m.manufacturer = 'BOEING' THEN COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '(7[0-9]7)'))[1],
                (regexp_match(UPPER(TRIM(m.model_raw)), '(MD-\d+)'))[1],
                UPPER(TRIM(m.model_raw)))
            WHEN m.manufacturer = 'AIRBUS' THEN COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '(A\d{3})'))[1],
                UPPER(TRIM(m.model_raw)))
            WHEN m.manufacturer = 'MCDONNELL DOUGLAS' THEN COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '(DC-\d+|MD-\d+)'))[1],
                UPPER(TRIM(m.model_raw)))
            WHEN m.manufacturer = 'BOMBARDIER' THEN COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '(CL-\d+|CRJ|DHC-\d+)'))[1],
                UPPER(TRIM(m.model_raw)))
            WHEN m.manufacturer = 'EMBRAER' THEN COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '(EMB-\d+|ERJ\s*\d+|E\d{3})'))[1],
                UPPER(TRIM(m.model_raw)))
            WHEN m.manufacturer = 'CESSNA' THEN COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '([A-Z]?\d{3})'))[1],
                UPPER(TRIM(m.model_raw)))
            WHEN m.manufacturer = 'PIPER' THEN COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '(PA[\s-]?\d+)'))[1],
                UPPER(TRIM(m.model_raw)))
            WHEN m.manufacturer = 'BELL' THEN COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '(\d{3})'))[1],
                UPPER(TRIM(m.model_raw)))
            WHEN m.manufacturer = 'LOCKHEED' THEN COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '(L-\d+)'))[1],
                UPPER(TRIM(m.model_raw)))
            ELSE COALESCE(
                (regexp_match(UPPER(TRIM(m.model_raw)), '([A-Z]*\d+[A-Z]?)'))[1],
                UPPER(TRIM(COALESCE(m.model_raw, 'UNKNOWN'))))
        END AS model_family
    FROM make_normalized m
)

SELECT
    me.ev_id,
    me.aircraft_key,
    me.regis_no,
    me.far_part,
    me.damage,
    me.make_raw,
    me.model_raw,
    me.acft_series,
    me.manufacturer,
    me.model_family,
    me.manufacturer || ' ' || me.model_family           AS model_full,
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
    CASE me.damage
        WHEN 'DEST' THEN 4 WHEN 'SUBS' THEN 3
        WHEN 'MINR' THEN 2 WHEN 'NONE' THEN 1 ELSE 0
    END                                                 AS damage_score,
    me.source_era
FROM model_extracted me;

CREATE INDEX idx_silver_aircraft_ev_id ON silver.aircraft_normalized (ev_id);
CREATE INDEX idx_silver_aircraft_model ON silver.aircraft_normalized (model_full);
CREATE INDEX idx_silver_aircraft_era ON silver.aircraft_normalized (source_era);
