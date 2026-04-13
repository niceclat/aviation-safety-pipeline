-- Silver layer: select narratives for NLP processing.
-- Used by src/nlp.py to read commercial narratives from bronze.

SELECT n.ev_id, n.aircraft_key, n.narr_accp, n.narr_cause
FROM bronze.narratives n
INNER JOIN bronze.aircraft a
    ON n.ev_id = a.ev_id AND n.aircraft_key = a.aircraft_key
WHERE a.far_part IN ('121', '135');
