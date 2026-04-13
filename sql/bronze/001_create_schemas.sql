-- Create schemas for medallion architecture layers.
-- Bronze has one schema per data source — raw, isolated, no mixing.

CREATE SCHEMA IF NOT EXISTS bronze_avall;
CREATE SCHEMA IF NOT EXISTS bronze_pre2008;
CREATE SCHEMA IF NOT EXISTS bronze_pre1982;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
