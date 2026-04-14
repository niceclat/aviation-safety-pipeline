# Design Decisions

## 1. Data Ingestion Strategy

### Source Selection: MDB Bulk Download

**Decision**: Use the three MDB bulk download files (`avall.zip`, `Pre2008.zip`, `PRE1982.zip`) as the primary data source rather than the NTSB Developer API or CAROL query tool.

**Rationale**:
- **Richest schema**: 20 normalized tables including engines, crew qualifications, flight time, and per-category injury breakdowns. The API and CAROL flatten these into denormalized records, losing granular detail critical for risk profiling.
- **Self-documenting**: The MDB contains `eADMSPUB_DataDictionary` (4,574 rows) with field descriptions, valid values, and code lookups — no external documentation needed.
- **Reproducible**: Static files with deterministic output. No API rate limits, authentication tokens, or pagination logic.
- **Full coverage**: Combined ~93,000 events spanning 1962–present.

**Trade-off**: MDB is a legacy Microsoft Access format requiring `mdbtools` on Linux. This adds a system dependency but is a one-line `apt-get install`.

### Scope: Pre2008 + avall (Part 121 + 135)

**Decision**: Ingest Pre2008 and avall databases. Exclude PRE1982 from the pipeline. Focus on FAR Part 121 (scheduled airlines) and Part 135 (commuter/charter).

**Rationale**:
- PRE1982 uses a completely different flat schema (5 tables, 400+ columns split across two tables) that would require extensive ETL mapping for marginal benefit.
- Pre2008 + avall provide ~93,000 events on a shared 20-table schema, covering 1982–present.
- Part 121 + 135 are the commercial operations relevant to Meridian Aero Underwriters' business (aircraft warranty and maintenance contract pricing). General aviation (Part 091) and agricultural (Part 137) are excluded.
- This yields **6,816 commercial aircraft records** across **26 model families** with 50+ incidents — sufficient statistical basis.

### MDB Reading: mdbtools (Docker) / pyodbc (Windows)

**Decision**: Dual-backend approach with runtime detection.

**Rationale**:
- Docker/Linux production: `mdbtools` is lightweight, widely available, and exports MDB tables to CSV for PostgreSQL COPY ingestion.
- Windows development: `pyodbc` with the Microsoft Access ODBC driver for interactive exploration and testing.
- The `detect_backend()` function auto-selects at runtime.

---

## 2. Medallion Architecture

### Bronze Layer

**Design**: Mirror source MDB tables in PostgreSQL with added lineage metadata (`_source_file`, `_ingested_at`).

**Key decisions**:
- Preserve raw data exactly as-is — no transformations, no type casting beyond what PostgreSQL accepts.
- Include `_source_file` to track whether each row came from `Pre2008.mdb` or `avall.mdb`. Critical for debugging and auditing.
- Load lookup tables (`ct_seqevt`, `ct_iaids`, `states`) into bronze for downstream joins.
- Use PostgreSQL `COPY` for bulk loading (10-100x faster than INSERT).

### Silver Layer

**Design**: Three enriched tables produced by SQL transformations.

1. **`silver.events_enriched`**: Severity scores, weather categorization, time-era bucketing. Computed from bronze.events.

2. **`silver.aircraft_normalized`**: The core normalization challenge. Canonical manufacturer names via CASE expressions. Model family extraction via `regexp_match()`. Filtered to Part 121 + 135 only.

3. **`silver.findings_enriched`**: Unifies old and new findings systems. Pre2008's `seq_of_events` (numeric codes, joined to `ct_seqevt` for descriptions) merged with avall's `Findings` (CAST/ICAO taxonomy with text descriptions). Tagged with `findings_system` to track provenance.

4. **`silver.narrative_analysis`**: NLP-derived failure categories from Python (see Section 4). Written by the Python NLP module, not SQL, because regex over large text fields is better suited to Python.

**Key SQL techniques**:
- CTEs for multi-step transformations
- `regexp_match()` for model family extraction
- CASE expressions for code decoding and make normalization
- UNION ALL to merge old/new findings systems

### Gold Layer

**Design**: Single denormalized `gold.aircraft_risk_profile` table — one row per model family.

**Key SQL techniques showcased**:
- **Window functions**: `NTILE(4)` for risk quartile assignment, `RANK()` for risk ranking
- **Aggregate FILTER**: PostgreSQL `COUNT(*) FILTER (WHERE ...)` for conditional aggregation
- **`REGR_SLOPE()`**: Linear regression in SQL for severity and frequency trend detection
- **`PERCENTILE_CONT()`**: Median calculation for model characteristics
- **`STRING_AGG()`**: Aggregating findings categories into readable strings
- **`LATERAL JOIN`**: For per-row annual incident count subquery
- **Conditional CASE on window results**: Trend classification (IMPROVING/STABLE/WORSENING)

**Risk tier methodology**:
- Composite score: `weighted_severity = injury_score * 0.6 + damage_score * 0.4`
- Quartile-based tier: CRITICAL / HIGH / MEDIUM / LOW using `NTILE(4)` over weighted severity, fatality rate, and destruction rate
- This is transparent and auditable — an underwriter can see exactly why a model is in a given tier

---

## 3. Schema Design Philosophy

### Why Not Normalize the Gold Table

The gold table is intentionally denormalized. The assignment specifies: "Gold table must be self-contained" and "Readable without querying other tables." An underwriter should open this one table and have everything needed to assess a model's risk.

### Why Separate Findings Systems

Pre2008 and avall use fundamentally different findings taxonomies. Rather than force-mapping between them (which would introduce inaccuracies), we preserve both in `silver.findings_enriched` with a `findings_system` tag. The gold layer aggregates across both systems at the category level where they're compatible.

---

## 4. NLP Approach

### Regex Pattern Matching (Not ML)

**Decision**: Use compiled regex patterns to extract 11 failure categories from narrative text.

**Rationale**:
- The assignment says "sound engineering judgment matters more than complexity"
- Insurance underwriting demands **explainability** — a regex rule that matches "engine failure" is auditable; a neural network classification is not
- Coverage is adequate: patterns classify 40-80% of narratives depending on the database era
- Categories map to underwriting risk factors: engine failure, weather, human factors, structural, etc.

**Trade-off**: Lower recall than ML approaches. Mitigated by also using the structured Findings table (avall) which provides NTSB-assigned categories.

### Text Severity Scoring

Simple keyword-based severity scoring (1-5 scale) from narrative language. Not a replacement for the structured severity fields, but adds a signal from unstructured text that can surface cases where structured data understates severity.

---

## 5. Docker Architecture

### Two-Service Compose

- **postgres**: PostgreSQL 15 with health check. Data persisted in a named volume.
- **pipeline**: Python 3.11-slim with mdbtools installed. Mounts `data/` (read-only) and `outputs/` (write). Runs `src/pipeline.py` as the entrypoint.

**Credential swap**: All connection parameters via `.env`. Reviewers clone, create `.env` from `.env.example`, and `docker-compose up`. No code changes needed.

---

## 6. Gold Table: How It Answers Each Question

### Q1: Severity trends — How has severity changed over time per model?

| Column | How it answers |
|---|---|
| `severity_trend` | IMPROVING / STABLE / WORSENING / INSUFFICIENT_DATA — plain label |
| `severity_slope` | Linear regression via `REGR_SLOPE()` — negative = improving, positive = worsening |
| `recent_severity` | Average weighted severity for last 10 years |
| `historical_severity` | Average weighted severity for prior years |

Trend classification: if recent is >0.2 higher than historical → WORSENING. >0.2 lower → IMPROVING. Otherwise STABLE. Threshold of 0.2 is configurable.

### Q2: Failure patterns — What failures appear most frequently?

| Column | Source | How it answers |
|---|---|---|
| `top_failure_1/2/3` | NLP regex on narratives | Top 3 failure categories per model |
| `pct_engine_failure`, `pct_weather_related`, etc. | NLP regex | Percentage breakdown by failure type |
| `causal_finding_categories` | NTSB structured Findings | Official cause categories |
| `aircraft_causes`, `personnel_causes`, `environmental_causes` | Findings table | Counts by cause type |

Patterns differ across models: BOEING 737 top failure = weather; BELL 206 = engine_failure.

### Q3: Narrative intelligence — What does NLP add beyond structured data?

| Column | Source | How it answers |
|---|---|---|
| `n_distinct_clusters` | FAISS k-means on sentence embeddings | How many semantic themes for this model |
| `avg_anomaly_score` | FAISS distance to centroid | How unusual this model's incidents are (0-1, higher = more atypical) |
| `high_anomaly_count` | FAISS anomaly > 0.7 | Count of outlier incidents worth investigating |
| `pct_nlp_categorized` | Regex hit rate | What percentage of narratives matched known failure patterns |
| `dominant_cluster_id` | FAISS mode cluster | Most common semantic group for this model |

Additionally, embeddings stored in pgvector enable SQL-level semantic search:
```sql
-- Find incidents most similar to a specific narrative
SELECT ev_id, 1 - (embedding <=> query_embedding) AS similarity
FROM silver.narrative_analysis
ORDER BY embedding <=> query_embedding
LIMIT 10;
```

### Q4: Risk comparison — quantified for non-technical stakeholders

| Column | How it answers |
|---|---|
| `risk_tier` | CRITICAL / HIGH / MEDIUM / LOW — plain labels anyone can act on |
| `risk_rank` | 1 = highest risk across all 163 models |
| `weighted_severity_score` | Composite: `injury_score * 0.6 + damage_score * 0.4` |
| `fatality_rate_pct` | Simple percentage: "X% of incidents had fatalities" |
| `destruction_rate_pct` | Simple percentage: "X% of incidents destroyed the aircraft" |
| `data_note` | "Based on 484 incidents (1962-2026)" — evidence context |

### Severity scoring rationale

```
weighted_severity = injury_score * INJURY_WEIGHT + damage_score * DAMAGE_WEIGHT
```

Where:
- `INJURY_WEIGHT = 0.6` — human harm is the primary underwriting concern
- `DAMAGE_WEIGHT = 0.4` — property damage is secondary
- Defined in `src/contracts.py` as tunable parameters

These weights are an **assumption**, not actuarial fact. In production, an actuary would calibrate them against historical loss data. The pipeline makes them configurable so they can be adjusted without code changes.

Risk tiers use `NTILE(4)` — quartile-based, so each tier contains roughly 25% of models. This ensures balanced distribution rather than arbitrary thresholds.

---

## 7. What I Would Add With More Time

1. **CAROL API supplementation**: Fetch Analysis narratives (not in MDB) for richer NLP input.
2. **spaCy NER**: Extract specific aircraft components and failure modes from narratives.
3. **Exposure normalization**: Incident counts per flight-hour or departure (requires fleet utilization data from FAA).
4. **Incremental loading**: Support weekly delta updates (`up[DD][MON].zip`) for production use.
5. **Graph analysis**: Apache AGE or NetworkX for visualizing relationships between aircraft models, failure modes, and operators.
6. **Actuarial calibration**: Replace assumed severity weights (0.6/0.4) with weights derived from historical loss data.
7. **PRE1982 full column mapping**: Currently maps ~30 of 403 columns. Extend to include crashworthiness, equipment, and detailed weather data.
