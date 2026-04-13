# Data Contract — Source to Bronze to Silver Mapping

| | |
|---|---|
| **Version** | 1.0.0 |
| **Date** | 2026-04-13 |
| **Owner** | Data Engineering |
| **Code** | `src/contracts.py` |

> When updating mappings, bump the version in both this file and `src/contracts.py`.

## Overview

Three NTSB data sources are ingested into isolated bronze schemas, then unified into a canonical silver model.

```
avall.mdb (2008-present)     →  bronze_avall.*      ─┐
Pre2008.mdb (1982-2007)      →  bronze_pre2008.*    ─┼→  silver.*  →  gold.*
PRE1982.MDB (1962-1981)      →  bronze_pre1982.*    ─┘
```

---

## Bronze Layer — Raw Mirror (No Transformation)

Each source gets its own schema. Tables mirror the MDB exactly — all columns, all rows, all TEXT. The only additions are lineage columns (`_source_file`, `_ingested_at`).

### bronze_avall (20 tables from avall.mdb)

| MDB Table | Bronze Table | Rows | Cols | Notes |
|---|---|---|---|---|
| events | bronze_avall.events | 30,358 | 73 | Core event metadata |
| aircraft | bronze_avall.aircraft | 30,877 | 93 | Aircraft details |
| narratives | bronze_avall.narratives | 27,877 | 8 | Free-text narratives |
| Findings | bronze_avall.findings | 71,114 | 14 | CAST/ICAO taxonomy (new system) |
| Events_Sequence | bronze_avall.events_sequence | 64,907 | 10 | Occurrence sequences (new system) |
| Occurrences | bronze_avall.occurrences | 0 | 8 | Empty — replaced by Events_Sequence |
| seq_of_events | bronze_avall.seq_of_events | 0 | 11 | Empty — replaced by Findings |
| engines | bronze_avall.engines | 27,848 | 17 | Engine details |
| injury | bronze_avall.injury | 174,550 | 7 | Injury counts by category |
| Flight_Crew | bronze_avall.flight_crew | 31,667 | 33 | Crew qualifications |
| flight_time | bronze_avall.flight_time | 398,263 | 8 | Pilot experience hours |
| NTSB_Admin | bronze_avall.ntsb_admin | 30,358 | 5 | Investigation status |
| dt_aircraft | bronze_avall.dt_aircraft | 262,723 | 6 | Multi-value aircraft fields |
| dt_events | bronze_avall.dt_events | 113,728 | 5 | Multi-value event fields |
| dt_Flight_Crew | bronze_avall.dt_flight_crew | 174,307 | 7 | Multi-value crew fields |
| eADMSPUB_DataDictionary | bronze_avall.data_dictionary | 4,574 | 13 | Schema documentation |
| ct_iaids | bronze_avall.ct_iaids | 955 | 11 | Code lookup table |
| ct_seqevt | bronze_avall.ct_seqevt | 2,224 | 2 | Sequence event code meanings |
| Country | bronze_avall.country | 262 | 2 | Country code lookup |
| states | bronze_avall.states | 51 | 3 | US state/region lookup |

### bronze_pre2008 (20 tables from Pre2008.mdb)

Same schema as bronze_avall. Key differences in data population:

| MDB Table | Bronze Table | Rows | Notes |
|---|---|---|---|
| events | bronze_pre2008.events | 63,002 | |
| aircraft | bronze_pre2008.aircraft | 63,914 | |
| narratives | bronze_pre2008.narratives | 61,783 | |
| Findings | bronze_pre2008.findings | 14 | **Nearly empty** — only backfilled records |
| Events_Sequence | bronze_pre2008.events_sequence | 25 | **Nearly empty** — only backfilled records |
| Occurrences | bronze_pre2008.occurrences | 137,989 | **Primary** — old system |
| seq_of_events | bronze_pre2008.seq_of_events | 264,329 | **Primary** — old system |
| engines | bronze_pre2008.engines | 62,727 | |
| injury | bronze_pre2008.injury | 189,314 | |
| Flight_Crew | bronze_pre2008.flight_crew | 64,079 | |
| flight_time | bronze_pre2008.flight_time | 886,796 | |
| NTSB_Admin | bronze_pre2008.ntsb_admin | 63,002 | |
| dt_aircraft | bronze_pre2008.dt_aircraft | 477,074 | |
| dt_events | bronze_pre2008.dt_events | 55,922 | |
| dt_Flight_Crew | bronze_pre2008.dt_flight_crew | 365,937 | |
| eADMSPUB_DataDictionary | bronze_pre2008.data_dictionary | 4,575 | |
| ct_iaids | bronze_pre2008.ct_iaids | 955 | |
| ct_seqevt | bronze_pre2008.ct_seqevt | 2,224 | |
| Country | bronze_pre2008.country | 259 | |
| states | bronze_pre2008.states | 51 | |

### bronze_pre1982 (5 tables from PRE1982.MDB)

Completely different schema — flat, denormalized.

| MDB Table | Bronze Table | Rows | Cols | Notes |
|---|---|---|---|---|
| tblFirstHalf | bronze_pre1982.tbl_first_half | 87,039 | 203 | Event + aircraft + pilot + injuries + causes |
| tblSecondHalf | bronze_pre1982.tbl_second_half | 87,039 | 200 | Continuation: weather, fire, equipment, investigation |
| tblOccurrences | bronze_pre1982.tbl_occurrences | 130,970 | 6 | Occurrence sequences |
| tblSeqOfEvents | bronze_pre1982.tbl_seq_of_events | 355,681 | 6 | Cause/factor codes |
| ct_Pre1982 | bronze_pre1982.ct_codes | 2,910 | 3 | Code lookup (Name, Code, Meaning) |

---

## Silver Layer — Canonical Model (Unified)

Silver unifies the three bronze schemas into a single canonical model.

### silver.events

| Canonical Column | avall Source | Pre2008 Source | PRE1982 Source |
|---|---|---|---|
| event_id | events.ev_id | events.ev_id | tblFirstHalf.RecNum (prefixed 'PRE1982_') |
| ntsb_no | events.ntsb_no | events.ntsb_no | tblFirstHalf.DOCKET_NO |
| event_type | events.ev_type | events.ev_type | tblFirstHalf.ACC_INC_CLASS → mapped |
| event_date | events.ev_date | events.ev_date | tblFirstHalf.DATE_OCCURRENCE |
| city | events.ev_city | events.ev_city | tblFirstHalf.LOCATION |
| state | events.ev_state | events.ev_state | tblFirstHalf.LOCAT_STATE_TERR |
| country | events.ev_country | events.ev_country | 'US' (domestic only) |
| highest_injury | events.ev_highest_injury | events.ev_highest_injury | Derived from GRAND_TOTAL_FATAL/SERIOUS |
| fatalities | events.inj_tot_f | events.inj_tot_f | tblFirstHalf.GRAND_TOTAL_FATAL |
| serious_injuries | events.inj_tot_s | events.inj_tot_s | tblFirstHalf.GRAND_TOTAL_SERIOUS |
| light_condition | events.light_cond | events.light_cond | tblFirstHalf.LIGHT_COND → mapped |
| weather_condition | events.wx_cond_basic | events.wx_cond_basic | tblSecondHalf.GENERAL_WEATHER → mapped |
| source_era | 'avall' | 'pre2008' | 'pre1982' |

### silver.aircraft

| Canonical Column | avall/Pre2008 Source | PRE1982 Source |
|---|---|---|
| event_id | aircraft.ev_id | tblFirstHalf.RecNum (prefixed) |
| aircraft_key | aircraft.Aircraft_Key | 1 (single aircraft per event) |
| registration_no | aircraft.regis_no | tblFirstHalf.REGIST_NO |
| far_part | aircraft.far_part | tblFirstHalf.TYPE_OPERATOR → mapped |
| damage | aircraft.damage | tblFirstHalf.ACFT_ADAMG → mapped |
| make_raw | aircraft.acft_make | tblFirstHalf.ACFT_MAKE |
| model_raw | aircraft.acft_model | tblFirstHalf.ACFT_MODEL |
| manufacturer | Normalized from make_raw | Normalized from make_raw |
| model_family | Extracted from model_raw | Extracted from model_raw |
| category | aircraft.acft_category | tblFirstHalf.TYPE_CRAFT → mapped |
| num_engines | aircraft.num_eng | tblFirstHalf.NO_ENGINES |
| total_seats | aircraft.total_seats | NULL |
| operator_name | aircraft.oper_name | tblFirstHalf.OPERATOR |
| source_era | 'avall' / 'pre2008' | 'pre1982' |

### PRE1982 Code Mappings

**TYPE_OPERATOR → far_part:**

| PRE1982 Code | Meaning | Canonical far_part |
|---|---|---|
| D | Private Owner | 091 |
| A | Flying School | 091 |
| B | Corporate/Executive | 091 |
| M | Flying Club | 091 |
| F | Fixed Base Operator | 091 |
| E | Air Taxi Operator | 135 |
| P | Contract Carrier | 135 |
| N | Intrastate Carrier | 121 |
| C | Aerial Applicator | 137 |
| G | Federal-Public Aircraft | PUBU |
| H | State-Public Aircraft | PUBU |
| I | Municipal-Public Aircraft | PUBU |

**ACFT_ADAMG → damage:**

| PRE1982 Code | Canonical |
|---|---|
| D | DEST |
| S | SUBS |
| M | MINR |
| N | NONE |
| Z | UNK |

**ACC_INC_CLASS → ev_type:**

| PRE1982 Code | Canonical |
|---|---|
| A, B, F, G | ACC (Accident) |
| C, D, E, H, I, J | INC (Incident) |

**TYPE_CRAFT → acft_category:**

| PRE1982 Code | Canonical |
|---|---|
| A | AIR |
| B | HELI |
| C | GLI |
| D | BALL |
| E | BLIM |
| I | GYRO |
