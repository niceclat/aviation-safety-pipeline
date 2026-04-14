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

# 3. Run
docker-compose up --build
```

No manual data download required. The pipeline automatically:
1. **Downloads** all 7 NTSB files from https://data.ntsb.gov/avdata (3 data + 4 docs, parallel, cached)
2. **Ingests** 3 MDB files into isolated bronze schemas (4.8M rows, 45 tables)
3. **Loads** data contract lookup tables (versioned canonical mappings)
4. **Transforms** to silver (unified events, normalized aircraft, enriched findings)
5. **Runs NLP** on 11K narratives (regex categorization + FAISS clustering + pgvector embeddings)
6. **Builds** gold risk profile table (175 aircraft models with risk tiers)
7. **Exports** CSV samples to `outputs/`

Total runtime: ~4 minutes from clean state.

## Project Structure

```
aviation-safety-pipeline/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── docker-compose.yml              # PostgreSQL (pgvector) + pipeline
├── Dockerfile
├── docs/
│   ├── EDA.md                      # Exploratory data analysis
│   ├── DESIGN_DECISIONS.md         # Architecture rationale + Q1-Q4 mapping
│   └── DATA_CONTRACT.md            # Source-to-canonical field mappings (v1.0.0)
├── sql/
│   ├── bronze/                     # Schema creation per source (3 DDL files)
│   ├── silver/                     # Canonical schema, lookups, transforms
│   ├── gold/                       # Risk profile aggregation (showcase SQL)
│   └── exports.sql                 # CSV export queries
├── src/
│   ├── config.py                   # .env-driven configuration
│   ├── pipeline.py                 # Modular orchestrator
│   ├── download.py                 # Parallel NTSB data download
│   ├── ingest.py                   # Bronze: MDB → PostgreSQL (auto-discovers schema)
│   ├── contracts.py                # Data contract v1.0.0 (canonical mappings)
│   ├── transform.py                # Silver/Gold: execute SQL files
│   ├── quality.py                  # Bronze data quality validation
│   ├── nlp/
│   │   ├── regex_categorizer.py    # Rule-based failure categorization
│   │   ├── embedding_analyzer.py   # Sentence embeddings + FAISS clustering
│   │   └── pipeline.py             # NLP orchestrator
│   └── eda/                        # Reproducible exploration scripts
├── tests/
│   ├── test_contracts.py           # 93 tests: mappings, normalization, lookups
│   ├── test_bronze.py              # 40 tests: ingestion, column safety, quality
│   ├── test_silver.py              # 45 tests: NLP, transforms, integration
│   ├── test_gold.py                # 24 tests: Q1-Q4 requirements, risk tiers
│   ├── test_download.py            # 9 tests: file definitions, URLs
│   └── validate_sql.py             # Cross-layer SQL validation
└── outputs/                        # CSV exports from each layer
```

## Architecture

### Medallion Layers

| Layer | Schemas | Purpose |
|-------|---------|---------|
| **Bronze** | `bronze_avall`, `bronze_pre2008`, `bronze_pre1982` | Raw mirror of each MDB source — all columns TEXT, lineage metadata |
| **Data Contract** | `silver._lookup_*` | Versioned canonical mappings loaded from `src/contracts.py` |
| **Silver** | `silver` | Unified canonical model, NLP analysis with regex + FAISS + pgvector |
| **Gold** | `gold` | Denormalized risk profile — one row per aircraft model, self-contained |

### Data Sources (all auto-downloaded)

| File | Period | Events | Tables | Bronze Schema |
|------|--------|--------|--------|---------------|
| `avall.mdb` | 2008–present | 30,358 | 20 | `bronze_avall` |
| `Pre2008.mdb` | 1982–2007 | 63,002 | 20 | `bronze_pre2008` |
| `PRE1982.MDB` | 1962–1981 | 87,039 | 5 (403 columns) | `bronze_pre1982` |

### NLP Pipeline

| Method | Purpose | Output |
|--------|---------|--------|
| Regex patterns (11 categories) | Explainable failure categorization | `primary_category`, `has_engine_failure`, etc. |
| Sentence embeddings (all-MiniLM-L6-v2) | Dense vector representation | `embedding` (pgvector, 384-dim) |
| FAISS k-means (50 clusters) | Semantic grouping + anomaly detection | `cluster_id`, `anomaly_score` |

### Key Technical Decisions

- **SQL in `.sql` files** — all transformation logic in `sql/`, zero SQL embedded in Python transforms
- **Data contract** — versioned lookup tables drive SQL JOINs, no hardcoded CASE statements
- **3 isolated bronze schemas** — raw mirror per source, no mixing
- **mdbtools** (Docker/Linux) / **pyodbc** (Windows) — dual backend with auto-detection
- **pgvector + FAISS** — embeddings stored in PostgreSQL for SQL-level semantic search, FAISS for clustering
- **97.6% manufacturer normalization** — 39 canonical names, 73 prefix rules, FAISS-validated

## Running Individual Steps

```bash
python src/pipeline.py                  # Full pipeline
python src/pipeline.py --bronze         # Download + ingest only
python src/pipeline.py --contracts      # Load contract lookups only
python src/pipeline.py --silver         # Silver transforms + NLP
python src/pipeline.py --gold           # Gold risk profile
python src/pipeline.py --export         # Export CSVs
python src/pipeline.py --quality        # Quality checks
```

## Querying the Gold Table

```sql
-- Compare risk across models
SELECT model_full, risk_tier, risk_rank,
       total_incidents, fatality_rate_pct,
       severity_trend, top_failure_1
FROM gold.aircraft_risk_profile
ORDER BY risk_rank;

-- Models with worsening severity
SELECT model_full, severity_trend, severity_slope,
       recent_severity, historical_severity
FROM gold.aircraft_risk_profile
WHERE severity_trend = 'WORSENING';

-- Semantic search: find incidents similar to a specific narrative
SELECT ev_id, 1 - (embedding <=> query.embedding) AS similarity
FROM silver.narrative_analysis,
     (SELECT embedding FROM silver.narrative_analysis WHERE ev_id = '20080213X00181') query
ORDER BY embedding <=> query.embedding
LIMIT 10;
```

## Testing

```bash
python -m pytest tests/ -v -k "not slow"    # 211 tests, ~2 seconds
python tests/validate_sql.py                 # Cross-layer SQL validation
```

## Documentation

- **[docs/EDA.md](docs/EDA.md)** — Data source investigation, schema comparison, field analysis
- **[docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md)** — Architecture rationale, Q1-Q4 column mapping, severity scoring
- **[docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md)** — Source-to-canonical field mappings (v1.0.0)
