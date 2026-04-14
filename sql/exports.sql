-- Export queries for CSV output.
-- Each query is separated by a comment with the target filename.

-- FILE: bronze_avall_events_sample.csv
SELECT * FROM bronze_avall.events LIMIT 500;

-- FILE: bronze_pre2008_events_sample.csv
SELECT * FROM bronze_pre2008.events LIMIT 500;

-- FILE: bronze_pre1982_sample.csv
SELECT * FROM bronze_pre1982.tbl_first_half LIMIT 500;

-- FILE: silver_events_enriched_sample.csv
SELECT * FROM silver.events_enriched LIMIT 500;

-- FILE: silver_aircraft_normalized_sample.csv
SELECT * FROM silver.aircraft_normalized LIMIT 500;

-- FILE: silver_narrative_analysis_sample.csv
SELECT * FROM silver.narrative_analysis LIMIT 500;

-- FILE: gold_aircraft_risk_profile.csv
SELECT * FROM gold.aircraft_risk_profile;
