-- Silver layer: unified findings from all bronze sources.
-- Merges 3 different cause/factor systems into one canonical structure.
-- See docs/DATA_CONTRACT.md for code system differences.

DROP TABLE IF EXISTS silver.findings_enriched CASCADE;

CREATE TABLE silver.findings_enriched AS

-- avall: new CAST/ICAO taxonomy (Findings table)
SELECT
    f.ev_id,
    NULLIF(f.aircraft_key, '')::INT                     AS aircraft_key,
    f.finding_no,
    f.finding_description,
    f.category_no,
    f.cause_factor,
    COALESCE(f.cm_inpc, 'FALSE')                        AS in_probable_cause,
    CASE f.category_no
        WHEN '01' THEN 'Aircraft'
        WHEN '02' THEN 'Personnel'
        WHEN '03' THEN 'Environmental'
        WHEN '04' THEN 'Organizational'
        WHEN '05' THEN 'Not determined'
        ELSE 'Other'
    END                                                 AS finding_category,
    CASE
        WHEN f.finding_description IS NOT NULL
        THEN SPLIT_PART(f.finding_description, '-', 1)
             || '-' || SPLIT_PART(f.finding_description, '-', 2)
             || '-' || SPLIT_PART(f.finding_description, '-', 3)
        ELSE 'Unknown'
    END                                                 AS finding_summary,
    'avall_cast_icao'                                   AS findings_system,
    'avall'                                             AS source_era
FROM bronze_avall.findings f
WHERE f.finding_code IS NOT NULL AND f.finding_code != ''

UNION ALL

-- Pre2008: old numeric code system (seq_of_events + ct_seqevt)
SELECT
    soe.ev_id,
    NULLIF(soe.aircraft_key, '')::INT                   AS aircraft_key,
    soe.seq_event_no                                    AS finding_no,
    ct.meaning                                          AS finding_description,
    CASE NULLIF(soe.group_code, '')::INT
        WHEN 1 THEN '01' WHEN 2 THEN '02'
        WHEN 3 THEN '03' ELSE '99'
    END                                                 AS category_no,
    soe.cause_factor,
    CASE WHEN soe.cause_factor IN ('C', 'F') THEN 'TRUE' ELSE 'FALSE'
    END                                                 AS in_probable_cause,
    CASE NULLIF(soe.group_code, '')::INT
        WHEN 1 THEN 'Aircraft/Environment'
        WHEN 2 THEN 'Personnel/Operations'
        WHEN 3 THEN 'Underlying'
        ELSE 'Other'
    END                                                 AS finding_category,
    COALESCE(ct.meaning, 'Code ' || soe.subj_code)     AS finding_summary,
    'pre2008_numeric'                                   AS findings_system,
    'pre2008'                                           AS source_era
FROM bronze_pre2008.seq_of_events soe
LEFT JOIN bronze_pre2008.ct_seqevt ct ON soe.subj_code = ct.code
WHERE soe.ev_id IS NOT NULL AND soe.ev_id != ''

UNION ALL

-- PRE1982: flat cause factor columns (tblSeqOfEvents)
SELECT
    'PRE1982_' || soe.recnum                            AS ev_id,
    1                                                   AS aircraft_key,
    soe.cfnum                                           AS finding_no,
    ct.meang                                            AS finding_description,
    '99'                                                AS category_no,
    soe.corf                                            AS cause_factor,
    CASE WHEN soe.corf IN ('C', 'F') THEN 'TRUE' ELSE 'FALSE'
    END                                                 AS in_probable_cause,
    'Legacy'                                            AS finding_category,
    COALESCE(ct.meang, 'Code ' || soe.cfcode)           AS finding_summary,
    'pre1982_legacy'                                    AS findings_system,
    'pre1982'                                           AS source_era
FROM bronze_pre1982.tbl_seq_of_events soe
LEFT JOIN bronze_pre1982.ct_codes ct ON soe.cfcode = ct.code
WHERE soe.recnum IS NOT NULL AND soe.recnum != '';

CREATE INDEX idx_silver_findings_ev_id ON silver.findings_enriched (ev_id);
CREATE INDEX idx_silver_findings_category ON silver.findings_enriched (finding_category);
CREATE INDEX idx_silver_findings_era ON silver.findings_enriched (source_era);
