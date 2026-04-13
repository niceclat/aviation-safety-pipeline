-- Silver layer: enriched findings with decoded categories.
-- Combines old (Occurrences/seq_of_events) and new (Events_Sequence/Findings) systems.

DROP TABLE IF EXISTS silver.findings_enriched CASCADE;

CREATE TABLE silver.findings_enriched AS

-- New system findings (avall, 2008+)
SELECT
    f.ev_id,
    f.aircraft_key,
    f.finding_no,
    f.finding_description,
    f.category_no,
    f.cause_factor,
    COALESCE(f.cm_inpc, 'FALSE')                       AS in_probable_cause,
    -- Decode top-level category
    CASE f.category_no
        WHEN '01' THEN 'Aircraft'
        WHEN '02' THEN 'Personnel'
        WHEN '03' THEN 'Environmental'
        WHEN '04' THEN 'Organizational'
        WHEN '05' THEN 'Not determined'
        ELSE 'Other'
    END                                                 AS finding_category,
    -- Extract the first three levels as a readable label
    CASE
        WHEN f.finding_description IS NOT NULL
        THEN SPLIT_PART(f.finding_description, '-', 1)
             || '-' || SPLIT_PART(f.finding_description, '-', 2)
             || '-' || SPLIT_PART(f.finding_description, '-', 3)
        ELSE 'Unknown'
    END                                                 AS finding_summary,
    'new_taxonomy'                                      AS findings_system,
    f._source_file
FROM bronze.findings f
WHERE f.finding_code IS NOT NULL

UNION ALL

-- Old system findings (Pre2008): map from seq_of_events + ct_seqevt
SELECT
    soe.ev_id,
    soe.aircraft_key,
    soe.seq_event_no                                    AS finding_no,
    ct.meaning                                          AS finding_description,
    CASE
        WHEN soe.group_code = 1 THEN '01'
        WHEN soe.group_code = 2 THEN '02'
        WHEN soe.group_code = 3 THEN '03'
        ELSE '99'
    END                                                 AS category_no,
    soe.cause_factor,
    CASE
        WHEN soe.cause_factor IN ('C', 'F') THEN 'TRUE'
        ELSE 'FALSE'
    END                                                 AS in_probable_cause,
    CASE soe.group_code
        WHEN 1 THEN 'Aircraft/Environment'
        WHEN 2 THEN 'Personnel/Operations'
        WHEN 3 THEN 'Underlying'
        ELSE 'Other'
    END                                                 AS finding_category,
    COALESCE(ct.meaning, 'Code ' || soe.subj_code::TEXT) AS finding_summary,
    'old_taxonomy'                                      AS findings_system,
    soe._source_file
FROM bronze.seq_of_events soe
LEFT JOIN bronze.ct_seqevt ct ON soe.subj_code = ct.code;

-- Indexes
CREATE INDEX idx_silver_findings_ev_id ON silver.findings_enriched (ev_id);
CREATE INDEX idx_silver_findings_category ON silver.findings_enriched (finding_category);
