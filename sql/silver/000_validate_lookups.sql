-- Validation queries for contract lookup tables.
-- Returns all lookup data for Python-side comparison against contract dicts.

-- TAG: far_part
SELECT source_code, canonical_code FROM silver._lookup_far_part ORDER BY source_code;

-- TAG: damage
SELECT source_code, canonical_code FROM silver._lookup_damage ORDER BY source_code;

-- TAG: event_type
SELECT source_code, canonical_code FROM silver._lookup_event_type ORDER BY source_code;

-- TAG: aircraft_category
SELECT source_code, canonical_code FROM silver._lookup_aircraft_category ORDER BY source_code;

-- TAG: manufacturer
SELECT match_prefix, canonical_name FROM silver._lookup_manufacturer ORDER BY match_prefix;
