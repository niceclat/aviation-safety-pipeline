-- Silver layer: select narratives for NLP processing.
-- Pulls from all bronze sources for commercial operations.

-- avall narratives
SELECT n.ev_id, n.aircraft_key, n.narr_accp, n.narr_cause
FROM bronze_avall.narratives n
INNER JOIN bronze_avall.aircraft a
    ON n.ev_id = a.ev_id AND n.aircraft_key = a.aircraft_key
WHERE TRIM(a.far_part) IN ('121', '135')

UNION ALL

-- Pre2008 narratives
SELECT n.ev_id, n.aircraft_key, n.narr_accp, n.narr_cause
FROM bronze_pre2008.narratives n
INNER JOIN bronze_pre2008.aircraft a
    ON n.ev_id = a.ev_id AND n.aircraft_key = a.aircraft_key
WHERE TRIM(a.far_part) IN ('121', '135')

UNION ALL

-- PRE1982 narratives (REMARKS + CAUSE from tblSecondHalf)
SELECT
    'PRE1982_' || s.recnum  AS ev_id,
    '1'                     AS aircraft_key,
    s.remarks               AS narr_accp,
    s.cause                 AS narr_cause
FROM bronze_pre1982.tbl_second_half s
INNER JOIN bronze_pre1982.tbl_first_half f ON s.recnum = f.recnum
WHERE f.type_operator IN ('E', 'P', 'N');
