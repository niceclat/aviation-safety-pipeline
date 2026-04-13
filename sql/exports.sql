-- Export queries for CSV output.
-- Each query is separated by a comment with the target filename.

-- FILE: bronze_events_sample.csv
SELECT * FROM bronze.events LIMIT 500;

-- FILE: bronze_aircraft_sample.csv
SELECT * FROM bronze.aircraft LIMIT 500;

-- FILE: silver_events_enriched_sample.csv
SELECT * FROM silver.events_enriched LIMIT 500;

-- FILE: silver_aircraft_normalized_sample.csv
SELECT * FROM silver.aircraft_normalized LIMIT 500;

-- FILE: silver_narrative_analysis_sample.csv
SELECT * FROM silver.narrative_analysis LIMIT 500;

-- FILE: gold_aircraft_risk_profile.csv
SELECT * FROM gold.aircraft_risk_profile;
