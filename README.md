# Aviation Safety Pipeline

A medallion architecture data pipeline that ingests NTSB aviation incident data into PostgreSQL, transforms it through bronze → silver → gold layers, and produces an aircraft risk profile table for insurance underwriting decisions.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/niceclat/aviation-safety-pipeline.git
cd aviation-safety-pipeline

# 2. Configure
cp .env.example .env
# Edit .env if needed (defaults work with docker-compose)

# 3. Run — that's it
docker-compose up --build
```

No manual data download required. The pipeline automatically:
1. **Downloads** NTSB MDB files from https://data.ntsb.gov/avdata (parallel, cached)
2. **Extracts** zip archives and validates MDB files
3. **Ingests** into bronze tables (raw + lineage metadata)
4. **Transforms** to silver (normalized aircraft, enriched events, NLP analysis)
5. **Builds** gold risk profile table
6. **Exports** CSV samples to `outputs/`

Subsequent runs skip already-downloaded files (idempotent).

## Project Structure

```
aviation-safety-pipeline/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── docs/
│   ├── EDA.md                  # Exploratory data analysis findings
│   └── DESIGN_DECISIONS.md     # Architecture rationale
├── sql/
│   ├── bronze/                 # Schema creation, raw table DDL
│   ├── silver/                 # Normalization, enrichment transforms
│   └── gold/                   # Risk profile aggregation
├── src/
│   ├── config.py               # .env-driven configuration
│   ├── pipeline.py             # Main orchestrator
│   ├── ingest.py               # Bronze: MDB → PostgreSQL
│   ├── transform.py            # Silver/Gold: execute SQL files
│   ├── nlp.py                  # Narrative text analysis
│   └── eda/                    # Reproducible exploration scripts
│       ├── explore_sources.py
│       ├── explore_models.py
│       └── explore_severity_narratives.py
├── tests/
└── outputs/                    # CSV exports from each layer
```

## Architecture

### Medallion Layers

| Layer | Purpose | Tables |
|-------|---------|--------|
| **Bronze** | Raw ingestion with lineage metadata | `bronze.events`, `bronze.aircraft`, `bronze.narratives`, `bronze.findings`, + 9 more |
| **Silver** | Cleansed, normalized, enriched | `silver.events_enriched`, `silver.aircraft_normalized`, `silver.findings_enriched`, `silver.narrative_analysis` |
| **Gold** | Business-ready risk profiles | `gold.aircraft_risk_profile` |

### Data Sources

Three NTSB bulk download MDB files covering 1962–present (~93K events):
- `avall.mdb` — 2008–present (30K events, 20 tables)
- `Pre2008.mdb` — 1982–2007 (63K events, 20 tables, same schema)
- `PRE1982.MDB` — 1962–1981 (87K events, different schema, not ingested)

Pipeline focuses on **Part 121 (scheduled airlines)** and **Part 135 (commuter/charter)** — the commercial operations relevant to underwriting.

### Key Technical Decisions

- **SQL in `.sql` files** — all transformation logic in `sql/`, never embedded in Python
- **mdbtools** for reading MDB files in Docker (Linux), pyodbc for Windows development
- **Regex NLP** for narrative analysis — practical, auditable, appropriate for underwriting
- **PostgreSQL-native analytics** — `REGR_SLOPE()`, `NTILE()`, `PERCENTILE_CONT()`, aggregate `FILTER`

## Running Individual Layers

```bash
python src/pipeline.py --bronze    # Ingest MDB files
python src/pipeline.py --silver    # Run silver transforms + NLP
python src/pipeline.py --gold      # Build risk profile table
python src/pipeline.py --export    # Export CSVs to outputs/
```

## Querying the Gold Table

```sql
-- Compare risk across models
SELECT model_full, risk_tier, risk_rank,
       total_incidents, fatality_rate_pct,
       severity_trend, top_failure_1
FROM gold.aircraft_risk_profile
ORDER BY risk_rank;

-- Models with worsening severity trends
SELECT model_full, severity_trend, severity_slope,
       recent_severity, historical_severity
FROM gold.aircraft_risk_profile
WHERE severity_trend = 'WORSENING';
```

## Documentation

- **[docs/EDA.md](docs/EDA.md)** — Data source investigation, schema comparison, field analysis
- **[docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md)** — Architecture rationale, trade-offs

## EDA Scripts

Reproducible exploration scripts that generated the EDA findings:

```bash
python src/eda/explore_sources.py           # Compare 3 MDB schemas
python src/eda/explore_models.py            # Aircraft model normalization
python src/eda/explore_severity_narratives.py  # Severity + NLP analysis
```

These require the NTSB MDB files and pyodbc (Windows) or mdbtools (Linux).
