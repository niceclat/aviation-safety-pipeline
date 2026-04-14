# Exploratory Data Analysis

## 1. Data Source Investigation

### Available Sources

The NTSB provides aviation incident data through three access methods:

| Source | URL | Format | Coverage |
|--------|-----|--------|----------|
| Bulk MDB Downloads | https://data.ntsb.gov/avdata | Microsoft Access `.mdb` | 1962–present |
| Developer API | https://developer.ntsb.gov | REST JSON (`cm_` prefixed fields) | Same underlying data |
| CAROL Query Tool | https://data.ntsb.gov/carol-main-public/basic-search | JSON/CSV download | Aviation from 1983–present |

### Bulk Download Files

From the MDB Release Notes page, the data files available are:

| File | Description | Size |
|------|-------------|------|
| `avall.zip` | Aviation data 2008–present (monthly updates) | ~94 MB |
| `Pre2008.zip` | Aviation data 1982–2007 | ~155 MB |
| `PRE1982.zip` | Aviation data 1962–1981 | ~39 MB |
| `eadmspub.pdf` | Database schema for `avall.zip` | 58 KB |
| `eadmspub_legacy.pdf` | Database schema for `Pre2008.zip` | 19 KB |
| `codman.pdf` | Coding manual for `PRE1982.zip` | 124 KB |
| `MDB_Release_Notes.pdf` | Release notes (schema changes) | 87 KB |
| `up[DD][MON].zip` | Weekly delta updates (incremental) | ~430–800 KB each |

The weekly update files (`up01APR.zip`, etc.) are incremental patches for production systems — not needed for initial pipeline load.

### Why MDB Bulk Download

We chose the MDB bulk download as the primary ingestion source because:

1. **Richest relational schema** — 20 normalized tables including engines, crew, flight time, and injury breakdowns that the API/CAROL flatten or omit
2. **Self-documenting** — contains `eADMSPUB_DataDictionary` (4,574 rows) and code lookup tables (`ct_iaids`, `ct_seqevt`)
3. **Deterministic/reproducible** — static file, no API rate limits or authentication
4. **Full historical depth** — three files cover 1962–present

The CAROL JSON download uses `cm_` prefixed field names and includes an Analysis narrative field not present in the MDB. The Developer API wraps the same data in a `{data, pagination, metadata}` JSON envelope. Both flatten the relational structure, losing granular tables (engines, flight_time, injury by category). For a pipeline focused on detailed risk profiling, the MDB's normalized schema is superior.

### Format Challenge: Legacy MDB on Linux/Docker

The `.mdb` format is Microsoft Access — a legacy government data standard. On the Docker/Linux target environment, the Access ODBC driver is unavailable. Solution: use `mdbtools` (`apt-get install mdbtools`), a Linux package that reads MDB files and exports to CSV. This is documented in the Dockerfile.

On Windows (development), we use `pyodbc` with the Microsoft Access Driver for exploration.

---

## 2. Database Schema Comparison

All three MDB files were downloaded, extracted, and analyzed. Reproducible scripts: `src/eda/explore_sources.py`.

### Three Eras, Three Structures

| | PRE1982 (1962–1981) | Pre2008 (1982–2007) | avall (2008–present) |
|---|---|---|---|
| **Events** | 87,039 (`tblFirstHalf` + `tblSecondHalf`) | 63,002 (`events`) | 30,358 (`events`) |
| **Total tables** | 5 | 20 | 20 |
| **Aircraft data** | Embedded columns in flat table | `aircraft` table (93 cols) | `aircraft` table (93 cols) |
| **Narratives** | `REMARKS` + `CAUSE` (short, ~1 sentence) | 4 fields: `narr_accp`, `narr_accf`, `narr_cause`, `narr_inc` | Same 4 fields |
| **Findings/Causes** | 30 columns (`CAUSE_FACTOR_1P..10S`) + `tblSeqOfEvents` (355K rows) | `Occurrences` (138K) + `seq_of_events` (264K) — old numeric codes | `Events_Sequence` (65K) + `Findings` (71K) — new CAST/ICAO taxonomy |
| **Injuries** | 60+ flat columns per person type | `injury` table (189K rows, normalized) | `injury` table (175K rows, normalized) |
| **Crew/Engines** | Embedded columns | Separate tables (`Flight_Crew`, `flight_time`, `engines`) | Same separate tables |
| **Operation type** | `TYPE_OPERATOR` (single char code) | `far_part` (091, 121, 135, etc.) | `far_part` (same codes) |
| **Schema docs** | `codman.pdf` | `eadmspub_legacy.pdf` | `eadmspub.pdf` |

### PRE1982: Completely Different Structure

The PRE1982 database uses a flat, denormalized layout:

- **`tblFirstHalf`** (87,039 rows, 203 columns): Event metadata, aircraft info, pilot details, cause factors, and injury counts all in one row
- **`tblSecondHalf`** (87,039 rows, 200 columns): Joined on `RecNum` — continuation of the same record (investigation details, weather, fire, equipment, crashworthiness)
- **`tblOccurrences`** (130,970 rows): Occurrence sequences linked by `RecNum`
- **`tblSeqOfEvents`** (355,681 rows): Cause/factor codes using the old coding manual format
- **`ct_Pre1982`** (2,910 rows): Code lookup table

The `TYPE_OPERATOR` field maps conceptually to `far_part`:

| PRE1982 Code | Meaning | Approximate far_part |
|---|---|---|
| D | Private Owner | 091 |
| E | Air Taxi Operator | 135 |
| N | Intrastate Carrier | 121/135 |
| P | Contract Carrier | 135 |
| F | Fixed Base Operator | 091/137 |
| C | Aerial Applicator | 137 |
| A | Flying School | 091 |
| B | Corporate/Executive | 091 |

### Pre2008 vs avall: Same Schema, Different Findings Systems

Pre2008 and avall share the same 20-table schema with one difference:

- **`Findings` table**: avall has an additional `cm_inPc` column (added March 2024 release) — a TRUE/FALSE flag indicating whether the finding was cited in the probable cause statement. Pre2008 uses the legacy `Cause_Factor` field ('C'/'F') instead.

The critical structural difference is **which tables contain data**:

| Table | Pre2008 | avall | System |
|---|---|---|---|
| `Occurrences` | **137,989 rows** | 0 rows | Old (numeric codes from `ct_seqevt`) |
| `seq_of_events` | **264,329 rows** | 0 rows | Old (numeric subject/modifier/person codes) |
| `Events_Sequence` | 25 rows | **64,907 rows** | New (CAST/ICAO taxonomy, text descriptions) |
| `Findings` | 14 rows | **71,114 rows** | New (hierarchical finding codes with descriptions) |

Pre2008 uses the **old** findings system (numeric codes requiring `ct_seqevt` lookup). avall uses the **new** CAST/ICAO taxonomy with human-readable descriptions. Only ~25 Pre2008 events were backfilled to the new system.

---

## 3. Operation Type and Scope

### FAR Part Codes

The Federal Aviation Regulations (FAR) part under which an aircraft operates determines its relevance to commercial underwriting:

| far_part | Meaning | Pre2008 Count | avall Count | Relevance |
|---|---|---|---|---|
| 091 | General Aviation | 52,693 | 21,871 | Low — private/recreational |
| 121 | Scheduled Airlines | 1,856 | 949 | **High — commercial fleet** |
| 135 | Commuter/Charter | 3,103 | 908 | **High — commercial ops** |
| 137 | Agricultural | 3,747 | 1,193 | Low — crop dusting |
| 129 | Foreign Carriers | 371 | 384 | Medium — foreign ops in US |
| NUSN/NUSC | Non-US registered | 1,154 | 3,895 | Low — outside US jurisdiction |

**Scope decision**: Focus on **Part 121 + Part 135** operations. These are the commercial operations that Meridian Aero Underwriters would price warranties and maintenance contracts for. Combined: **6,816 aircraft records** across both databases.

---

## 4. Aircraft Model Naming

Reproducible script: `src/eda/explore_models.py`.

### The Problem

Aircraft manufacturer and model names are entered as free text with no standardization:

**Make inconsistency:**
- `BOEING`, `Boeing`, `boeing` → all the same manufacturer
- `MCDONNELL DOUGLAS`, `DOUGLAS`, `McDonnell Douglas` → same (pre-merger/post-merger)
- `BOMBARDIER INC`, `Bombardier`, `CANADAIR` → same corporate family

**Model inconsistency (Boeing 737 example):**
- `737`, `737-200`, `737-300`, `737-7H4`, `737 7H4`, `737-823`, `737-8H4`, `737-832`
- These are all variants of the 737 family but appear as separate models

### Normalization Strategy

**Make normalization**: Map all variants to canonical manufacturer names using a lookup dictionary (17 canonical names cover >95% of commercial aircraft).

**Model family extraction**: Use regex patterns to extract the base model family:
- Boeing: 3-digit base → `737`, `747`, `757`, `767`, `777`, `787`
- Airbus: `A` + 3 digits → `A320`, `A319`, `A330`
- McDonnell Douglas: `DC-` or `MD-` prefix → `DC-9`, `DC-10`, `MD-80`
- Bombardier: `CL-600` family (covers CRJ series)
- Cessna/Piper/Bell: numeric model extraction

### Model Families with Sufficient Data

After normalization, **26 model families** have 50+ incidents in the combined dataset (Part 121 + 135):

| Model Family | Incidents | Primary Operation |
|---|---|---|
| BOEING 737 | 484 | Part 121 |
| BELL 206 | 281 | Part 135 |
| BOEING 727 | 234 | Part 121 |
| PIPER PA-32 | 203 | Part 135 |
| PIPER PA-31 | 200 | Part 135 |
| CESSNA 207 | 194 | Part 135 |
| CESSNA 402 | 181 | Part 135 |
| MCDONNELL DOUGLAS DC-9 | 172 | Part 121 |
| CESSNA 208 | 169 | Part 135 |
| BOEING 757 | 160 | Part 121 |
| BOEING 767 | 144 | Part 121 |
| BOEING 747 | 125 | Part 121 |
| BOMBARDIER CL-600 | 93 | Part 121 |
| MCDONNELL DOUGLAS DC-10 | 88 | Part 121 |
| AIRBUS A320 | 81 | Part 121 |
| BOEING 777 | 63 | Part 121 |
| ... | ... | ... |

The assignment requires "at least 2 aircraft models with sufficient incident volume" — we have 26.

---

## 5. Severity Analysis

Reproducible script: `src/eda/explore_severity_narratives.py`.

### Severity Fields

Severity is captured through multiple fields:

| Field | Values | Description |
|---|---|---|
| `ev_highest_injury` | FATL, SERS, MINR, NONE | Highest injury level in the event |
| `damage` | DEST, SUBS, MINR, NONE, UNK | Aircraft damage level |
| `inj_tot_f/s/m/n` | integers | Fatality/serious/minor/none counts |
| `ev_type` | ACC, INC | Accident vs. incident classification |

### Distribution (Commercial Operations, Part 121 + 135)

**avall (2008–present):**
- 54.6% no injuries, 19.9% serious, 9.5% fatal, 8.8% minor
- 50.6% substantial damage, 5.8% destroyed
- 175 events with fatalities, 616 total fatalities

**Pre2008 (1982–2007):**
- 58.1% no injuries, 15.5% fatal, 13.8% serious, 11.9% minor
- 45.8% substantial damage, 17.4% destroyed
- 743 events with fatalities, 5,075 total fatalities

Notable trend: fatality rate dropped from 15.5% (1982–2007) to 9.5% (2008+), and destruction rate from 17.4% to 5.8%. Aviation safety has materially improved.

### Severity Scoring Approach

Composite severity score combining injury and damage:

```
injury_score: FATL=4, SERS=3, MINR=2, NONE=1
damage_score: DEST=4, SUBS=3, MINR=2, NONE=1
severity_score = (injury_score * 0.6) + (damage_score * 0.4)
```

Injury weighted higher because human harm is the primary underwriting concern.

---

## 6. Narrative Text Analysis

### Coverage

| Field | avall (121+135) | Pre2008 (121+135) | Description |
|---|---|---|---|
| `narr_accp` | 75.0% | 47.8% | Factual narrative |
| `narr_accf` | 82.9% | 99.2% | Final report narrative |
| `narr_cause` | 47.9% | 65.1% | Probable cause statement |
| `narr_inc` | 0.6% | 0.0% | FAA incident narrative (rarely populated) |

The **probable cause narrative** (`narr_cause`) is the most valuable for NLP — it's a concise statement of what caused the incident. The factual narrative (`narr_accp`) provides supporting detail.

### NLP Failure Category Extraction

Using regex pattern matching against 11 failure categories, we can classify narratives:

| Category | Pre2008 (121+135) | Description |
|---|---|---|
| weather | 20.0% | IMC, icing, turbulence, wind shear |
| landing_gear | 18.7% | Gear collapse, retraction failures |
| human_factors | 10.4% | Pilot error, CFIT, loss of control |
| engine_failure | 6.4% | Power loss, mechanical failure |
| fuel_related | 4.6% | Exhaustion, starvation, contamination |
| fire | 4.0% | In-flight or post-crash fire |
| hydraulic | 2.1% | Hydraulic system failures |
| electrical | 1.3% | Electrical system failures |
| structural | 1.0% | Fatigue, cracks, separation |
| bird_strike | 0.7% | Wildlife strikes |
| maintenance | 0.7% | Maintenance errors |

This approach is intentionally practical — regex pattern matching is explainable, auditable, and appropriate for insurance underwriting where transparency matters more than model complexity.

### Where is failure information — structured or text?

**Both.** The structured `Findings` table provides NTSB-assigned cause categories, but only for avall (2008+). Pre2008 uses a different numeric code system (`seq_of_events`). PRE1982 has only short text in `REMARKS` and `CAUSE` fields. The NLP pipeline bridges this gap by extracting structured failure categories from narrative text across all 3 eras, providing consistent categorization regardless of which findings system the source uses.

---

## 7. Findings Code Structure (avall only)

The `Findings` table uses a hierarchical CAST/ICAO taxonomy with 5 levels:

```
category_no / subcategory_no / section_no / subsection_no / modifier_no
```

Top-level categories for commercial operations (4,341 findings):

| Code | Category | Count | % |
|---|---|---|---|
| 02 | Personnel issues | 1,706 | 39.3% |
| 01 | Aircraft | 1,228 | 28.3% |
| 03 | Environmental issues | 1,052 | 24.2% |
| 04 | Organizational issues | 292 | 6.7% |
| 05 | Not determined | 63 | 1.5% |

Of these findings, 1,966 are coded as **Causes** and 559 as **Factors**.

---

## 8. Aircraft Usage and Exposure

The NTSB data captures **incident counts** but not **exposure data** (flight hours, departures, fleet size). The `afm_hrs` (airframe hours) field exists in the `aircraft` table but is sparsely populated and reflects the individual aircraft at time of incident, not fleet-wide utilization.

**Why this matters for risk**: A model with 100 incidents from 10,000 flight hours is riskier than one with 100 incidents from 1,000,000 flight hours. Without exposure normalization, our risk profile measures **absolute** incident frequency, not **rate-based** risk.

**Mitigation**: The gold table includes `avg_incidents_per_year` and `years_with_incidents` as proxies for exposure. Models with longer operational histories naturally accumulate more incidents — the severity trend analysis (`REGR_SLOPE`) accounts for this by measuring change over time rather than absolute counts.

**Future work**: Supplement with FAA fleet utilization data (Operations and Activity reports) to compute incidents per 100,000 flight hours — the standard industry risk metric.

---

## 9. Incident Distribution

### By Time
- **Pre-1982**: 87,039 events — highest volume era (general aviation boom)
- **1982-2007**: 63,002 events — declining as safety improved
- **2008-present**: 30,358 events — lowest, reflecting modern safety standards

### By Geography
- Events concentrated in US states with high aviation activity: California, Texas, Florida, Alaska
- PRE1982 data is US-only; Pre2008 and avall include foreign-registered aircraft

### By Conditions
- **VMC** (visual conditions): majority of incidents across all eras
- **IMC** (instrument conditions): higher severity when they occur — higher fatality rate
- The gold table includes `pct_imc_conditions` per model to flag weather-sensitive aircraft

---

## 10. Data Quality Issues

1. **Aircraft naming inconsistency** — free text make/model requires normalization (see Section 4)
2. **Null values** — many fields have NULL or missing data, especially in older records
3. **narr_accp = 'import'** — some avall narratives contain only the string "import" (placeholder for incomplete imports)
4. **Findings system transition** — Pre2008 uses old numeric codes, avall uses new CAST/ICAO taxonomy. Cannot directly combine findings across databases without code mapping.
5. **PRE1982 completely different schema** — requires extensive mapping to align with modern tables
6. **Date overlap** — Pre2008 starts at 1948 (not 1982) for some records, suggesting data migration artifacts
7. **Duplicate event IDs** — some Pre2008 Events_Sequence/Findings rows have ev_ids that start with `2008` (likely backfill from avall)
