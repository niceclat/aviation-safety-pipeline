"""
Data contract definitions: source-to-canonical mappings.

This module is the single source of truth for how the 3 bronze schemas
map to the unified silver canonical model. Every code translation,
field mapping, and business rule lives here.

Used by:
    - sql/silver/000_canonical_schema.sql (lookup table DDL)
    - load_lookups_to_pg() (populates lookup tables from these dicts)
    - Silver SQL transforms (JOIN against lookup tables)
    - Quality checks (validation rules)
    - docs/DATA_CONTRACT.md (human-readable version)

See docs/DATA_CONTRACT.md for the human-readable version.
"""

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Contract metadata
# ---------------------------------------------------------------------------

CONTRACT_VERSION = "1.0.0"
CONTRACT_DATE = "2026-04-13"
CONTRACT_DESCRIPTION = (
    "Canonical mapping for NTSB aviation data: "
    "3 bronze sources (avall, Pre2008, PRE1982) -> unified silver model"
)

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


# ---------------------------------------------------------------------------
# Code translation tables
# ---------------------------------------------------------------------------

# PRE1982 TYPE_OPERATOR -> canonical far_part
TYPE_OPERATOR_TO_FAR_PART = {
    "D": ("091",  "Private Owner"),
    "A": ("091",  "Flying School"),
    "B": ("091",  "Corporate/Executive"),
    "M": ("091",  "Flying Club"),
    "F": ("091",  "Fixed Base Operator"),
    "L": ("091",  "Flying Club (Military)"),
    "J": ("091",  "Civil Air Patrol"),
    "K": ("091",  "Aircraft Manufacturer"),
    "E": ("135",  "Air Taxi Operator"),
    "P": ("135",  "Contract Carrier"),
    "N": ("121",  "Intrastate Carrier"),
    "C": ("137",  "Aerial Applicator"),
    "G": ("PUBU", "Federal-Public Aircraft"),
    "H": ("PUBU", "State-Public Aircraft"),
    "I": ("PUBU", "Municipal-Public Aircraft"),
    "Y": ("UNK",  "Other"),
    "Z": ("UNK",  "Unknown/Not Reported"),
}

# PRE1982 ACFT_ADAMG -> canonical damage code
DAMAGE_CODE_MAP = {
    "D": ("DEST", "Destroyed"),
    "S": ("SUBS", "Substantial"),
    "M": ("MINR", "Minor"),
    "N": ("NONE", "None"),
    "Z": ("UNK",  "Unknown/Not Reported"),
}

# PRE1982 ACC_INC_CLASS -> canonical event type
EVENT_TYPE_MAP = {
    "A": ("ACC", "Accident - US Registered Aircraft"),
    "B": ("ACC", "Accident - No Flight, US Reg"),
    "F": ("ACC", "Accident - Foreign Registered"),
    "G": ("ACC", "Accident - No Flight, Foreign Reg"),
    "C": ("INC", "Incident - US Registered"),
    "D": ("INC", "Incident - No Flight, US Reg"),
    "E": ("INC", "Incident - Closed Receipt Message, US"),
    "H": ("INC", "Incident - Foreign Registered"),
    "I": ("INC", "Incident - No Flight, Foreign Reg"),
    "J": ("INC", "Incident - Closed Receipt Message, Foreign"),
}

# PRE1982 TYPE_CRAFT -> canonical aircraft category
AIRCRAFT_CATEGORY_MAP = {
    "A": ("AIR",  "Fixed-Wing"),
    "B": ("HELI", "Helicopter"),
    "C": ("GLI",  "Glider"),
    "D": ("BALL", "Balloon"),
    "E": ("BLIM", "Blimp"),
    "F": ("BLIM", "Dirigible"),
    "G": ("RCKT", "Rocket"),
    "H": ("AIR",  "Convertiplane"),
    "I": ("GYRO", "Gyroplane"),
    "Y": ("UNK",  "Other"),
}

# Severity scoring weights
# Composite: weighted_severity = injury_score * INJURY_WEIGHT + damage_score * DAMAGE_WEIGHT
# Rationale: human harm weighted higher than property damage for insurance underwriting.
# These are tunable parameters — adjust based on actuarial guidance.
INJURY_WEIGHT = 0.6
DAMAGE_WEIGHT = 0.4

INJURY_SEVERITY_SCORES = {
    "FATL": 4,
    "SERS": 3,
    "MINR": 2,
    "NONE": 1,
}

DAMAGE_SEVERITY_SCORES = {
    "DEST": 4,
    "SUBS": 3,
    "MINR": 2,
    "NONE": 1,
    "UNK": 0,
}

# Commercial operation filters
COMMERCIAL_FAR_PARTS = frozenset({"121", "135"})
PRE1982_COMMERCIAL_OPERATORS = frozenset({"E", "P", "N"})


# ---------------------------------------------------------------------------
# Canonical manufacturer normalization
# ---------------------------------------------------------------------------

MANUFACTURER_RULES = [
    ("BOEING", ["BOEING"]),
    ("AIRBUS", ["AIRBUS", "AIRBUS INDUSTRIE"]),
    ("BOMBARDIER", ["BOMBARDIER", "BOMBARDIER INC", "CANADAIR", "DE HAVILLAND CANADA"]),
    ("EMBRAER", ["EMBRAER"]),
    ("CESSNA", ["CESSNA", "TEXTRON"]),
    ("BEECHCRAFT", ["BEECH", "HAWKER BEECH"]),
    ("PIPER", ["PIPER"]),
    ("BELL", ["BELL"]),
    ("MCDONNELL DOUGLAS", ["MCDONNELL", "DOUGLAS"]),
    ("LOCKHEED", ["LOCKHEED"]),
    ("DEHAVILLAND", ["DEHAVILLAND", "DE HAVILLAND"]),
    ("SIKORSKY", ["SIKORSKY"]),
    ("EUROCOPTER", ["EUROCOPTER"]),
    ("ROBINSON", ["ROBINSON"]),
]

MODEL_FAMILY_PATTERNS = {
    "BOEING": [r"(7[0-9]7)", r"(MD-\d+)"],
    "AIRBUS": [r"(A\d{3})"],
    "MCDONNELL DOUGLAS": [r"(DC-\d+)", r"(MD-\d+)"],
    "BOMBARDIER": [r"(CL-\d+)", r"(CRJ)", r"(DHC-\d+)"],
    "EMBRAER": [r"(EMB-\d+)", r"(ERJ\s*\d+)", r"(E\d{3})"],
    "CESSNA": [r"([A-Z]?\d{3})"],
    "PIPER": [r"(PA[\s-]?\d+)"],
    "BELL": [r"(\d{3})"],
    "LOCKHEED": [r"(L-\d+)"],
}

MODEL_FAMILY_FALLBACK = r"([A-Z]*\d+[A-Z]?)"


# ---------------------------------------------------------------------------
# Field mapping contracts per entity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldMapping:
    """Maps a canonical silver field to its source in each bronze schema."""
    canonical_name: str
    canonical_type: str
    avall_source: str
    pre2008_source: str
    pre1982_source: str
    description: str = ""
    nullable: bool = True


EVENTS_MAPPINGS = [
    FieldMapping("event_id", "TEXT", "e.ev_id", "e.ev_id",
                 "'PRE1982_' || f.recnum", "Unique event identifier"),
    FieldMapping("event_type", "TEXT", "e.ev_type", "e.ev_type",
                 "JOIN silver._lookup_event_type", "ACC or INC"),
    FieldMapping("event_date", "TIMESTAMP", "e.ev_date::TIMESTAMP",
                 "e.ev_date::TIMESTAMP", "f.date_occurrence::TIMESTAMP",
                 "Date of event"),
    FieldMapping("city", "TEXT", "e.ev_city", "e.ev_city",
                 "f.location", "City/location"),
    FieldMapping("state", "TEXT", "e.ev_state", "e.ev_state",
                 "f.locat_state_terr", "US state code"),
    FieldMapping("country", "TEXT", "e.ev_country", "e.ev_country",
                 "'US'", "Country code"),
    FieldMapping("highest_injury", "TEXT", "TRIM(e.ev_highest_injury)",
                 "TRIM(e.ev_highest_injury)",
                 "Derived from GRAND_TOTAL columns", "FATL/SERS/MINR/NONE"),
    FieldMapping("fatalities", "INTEGER",
                 "COALESCE(NULLIF(e.inj_tot_f,'')::INT,0)",
                 "COALESCE(NULLIF(e.inj_tot_f,'')::INT,0)",
                 "COALESCE(NULLIF(f.grand_total_fatal,'')::INT,0)",
                 "Total fatalities"),
    FieldMapping("source_era", "TEXT", "'avall'", "'pre2008'", "'pre1982'",
                 "Which bronze source"),
]

AIRCRAFT_MAPPINGS = [
    FieldMapping("event_id", "TEXT", "a.ev_id", "a.ev_id",
                 "'PRE1982_' || f.recnum", "FK to events"),
    FieldMapping("far_part", "TEXT", "TRIM(a.far_part)", "TRIM(a.far_part)",
                 "JOIN silver._lookup_far_part", "FAR regulation part"),
    FieldMapping("damage", "TEXT", "TRIM(a.damage)", "TRIM(a.damage)",
                 "JOIN silver._lookup_damage", "DEST/SUBS/MINR/NONE"),
    FieldMapping("make_raw", "TEXT", "a.acft_make", "a.acft_make",
                 "f.acft_make", "Original manufacturer name"),
    FieldMapping("model_raw", "TEXT", "a.acft_model", "a.acft_model",
                 "f.acft_model", "Original model name"),
    FieldMapping("manufacturer", "TEXT", "JOIN silver._lookup_manufacturer",
                 "JOIN silver._lookup_manufacturer",
                 "JOIN silver._lookup_manufacturer",
                 "Canonical manufacturer"),
    FieldMapping("category", "TEXT", "a.acft_category", "a.acft_category",
                 "JOIN silver._lookup_aircraft_category", "AIR/HELI etc."),
    FieldMapping("source_era", "TEXT", "'avall'", "'pre2008'", "'pre1982'",
                 "Source era tag"),
]


# ---------------------------------------------------------------------------
# Helper functions — input-validated, null-safe
# ---------------------------------------------------------------------------

def _validate_str(value: Optional[str], param_name: str) -> Optional[str]:
    """Validate and clean a string input."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{param_name} must be str or None, got {type(value).__name__}")
    stripped = value.strip()
    return stripped if stripped else None


def normalize_manufacturer(raw_make: Optional[str]) -> str:
    """Apply manufacturer normalization rules.

    Args:
        raw_make: Raw aircraft make string from any source.

    Returns:
        Canonical manufacturer name (e.g. 'BOEING').

    Raises:
        TypeError: If raw_make is not str or None.
    """
    cleaned = _validate_str(raw_make, "raw_make")
    if not cleaned:
        return "UNKNOWN"
    upper = cleaned.upper()
    for canonical, prefixes in MANUFACTURER_RULES:
        for prefix in prefixes:
            if upper == prefix or upper.startswith(prefix):
                return canonical
    return upper


def map_type_operator_to_far_part(code: Optional[str]) -> str:
    """Map PRE1982 TYPE_OPERATOR code to canonical far_part.

    Args:
        code: Single-character operator type code.

    Returns:
        Canonical far_part code (e.g. '121', '135', '091').
    """
    cleaned = _validate_str(code, "code")
    if not cleaned:
        return "UNK"
    result = TYPE_OPERATOR_TO_FAR_PART.get(cleaned)
    return result[0] if result else "UNK"


def map_damage_code(code: Optional[str]) -> str:
    """Map PRE1982 ACFT_ADAMG code to canonical damage."""
    cleaned = _validate_str(code, "code")
    if not cleaned:
        return "UNK"
    result = DAMAGE_CODE_MAP.get(cleaned)
    return result[0] if result else "UNK"


def map_event_type(code: Optional[str]) -> str:
    """Map PRE1982 ACC_INC_CLASS code to canonical event type."""
    cleaned = _validate_str(code, "code")
    if not cleaned:
        return "UNK"
    result = EVENT_TYPE_MAP.get(cleaned)
    return result[0] if result else "UNK"


def map_aircraft_category(code: Optional[str]) -> str:
    """Map PRE1982 TYPE_CRAFT code to canonical category."""
    cleaned = _validate_str(code, "code")
    if not cleaned:
        return "UNK"
    result = AIRCRAFT_CATEGORY_MAP.get(cleaned)
    return result[0] if result else "UNK"


def is_commercial_operation(far_part: Optional[str]) -> bool:
    """Check if a far_part code represents commercial operations."""
    cleaned = _validate_str(far_part, "far_part")
    return cleaned in COMMERCIAL_FAR_PARTS if cleaned else False


def is_pre1982_commercial(type_operator: Optional[str]) -> bool:
    """Check if a PRE1982 TYPE_OPERATOR is a commercial operation."""
    cleaned = _validate_str(type_operator, "type_operator")
    return cleaned in PRE1982_COMMERCIAL_OPERATORS if cleaned else False


def compute_injury_score(highest_injury: Optional[str]) -> int:
    """Compute numeric severity score from injury level."""
    cleaned = _validate_str(highest_injury, "highest_injury")
    if not cleaned:
        return 0
    return INJURY_SEVERITY_SCORES.get(cleaned, 0)


def compute_damage_score(damage: Optional[str]) -> int:
    """Compute numeric severity score from damage level."""
    cleaned = _validate_str(damage, "damage")
    if not cleaned:
        return 0
    return DAMAGE_SEVERITY_SCORES.get(cleaned, 0)


# ---------------------------------------------------------------------------
# Load contracts into PostgreSQL lookup tables
# ---------------------------------------------------------------------------

def _load_lookup_table(pg_conn, table: str, rows: list[tuple],
                       columns: list[str]) -> int:
    """Bulk load a lookup table using COPY for performance.

    Args:
        pg_conn: PostgreSQL connection.
        table: Full table name (e.g. 'silver._lookup_far_part').
        rows: List of tuples matching column order.
        columns: Column names.

    Returns:
        Number of rows loaded.

    Raises:
        psycopg2.Error: On database errors.
    """
    buf = io.StringIO()
    for row in rows:
        cleaned = [str(v).replace("\t", " ").replace("\n", " ") if v else ""
                   for v in row]
        buf.write("\t".join(cleaned) + "\n")
    buf.seek(0)

    col_list = ", ".join(columns)
    with pg_conn.cursor() as cur:
        cur.copy_expert(
            f"COPY {table} ({col_list}) FROM STDIN "
            f"WITH (FORMAT text, DELIMITER E'\\t', NULL '')",
            buf,
        )
    pg_conn.commit()
    return len(rows)


def load_lookups_to_pg(pg_conn) -> dict[str, int]:
    """Load all contract lookup tables into PostgreSQL silver schema.

    Creates the lookup table schema (from SQL file), then bulk-loads
    all mapping data from the Python dicts defined in this module.

    Args:
        pg_conn: PostgreSQL connection.

    Returns:
        Dict of {table_name: rows_loaded} for audit.

    Raises:
        FileNotFoundError: If the SQL DDL file is missing.
        psycopg2.Error: On database errors.
    """
    results = {}
    errors = []

    # Step 1: Create lookup table schema from SQL file
    ddl_path = SQL_DIR / "silver" / "000_canonical_schema.sql"
    if not ddl_path.exists():
        raise FileNotFoundError(f"Canonical schema DDL not found: {ddl_path}")

    try:
        with pg_conn.cursor() as cur:
            cur.execute(ddl_path.read_text(encoding="utf-8"))
        pg_conn.commit()
        logger.info(f"Created silver lookup tables (contract v{CONTRACT_VERSION})")
    except Exception as e:
        logger.error(f"Failed to create lookup schema: {e}")
        pg_conn.rollback()
        raise

    # Step 2: Load each lookup table
    lookups = [
        (
            "silver._lookup_far_part",
            ["source_code", "canonical_code", "description"],
            [(code, val[0], val[1]) for code, val in TYPE_OPERATOR_TO_FAR_PART.items()],
        ),
        (
            "silver._lookup_damage",
            ["source_code", "canonical_code", "description"],
            [(code, val[0], val[1]) for code, val in DAMAGE_CODE_MAP.items()],
        ),
        (
            "silver._lookup_event_type",
            ["source_code", "canonical_code", "description"],
            [(code, val[0], val[1]) for code, val in EVENT_TYPE_MAP.items()],
        ),
        (
            "silver._lookup_aircraft_category",
            ["source_code", "canonical_code", "description"],
            [(code, val[0], val[1]) for code, val in AIRCRAFT_CATEGORY_MAP.items()],
        ),
        (
            "silver._lookup_manufacturer",
            ["match_prefix", "canonical_name"],
            [(prefix, canonical)
             for canonical, prefixes in MANUFACTURER_RULES
             for prefix in prefixes],
        ),
        (
            "silver._lookup_severity",
            ["injury_level", "damage_level", "injury_score", "damage_score"],
            [(level, None, score, None) for level, score in INJURY_SEVERITY_SCORES.items()]
            + [(None, level, None, score) for level, score in DAMAGE_SEVERITY_SCORES.items()],
        ),
    ]

    for table, columns, rows in lookups:
        short_name = table.split(".")[-1]
        try:
            n = _load_lookup_table(pg_conn, table, rows, columns)
            results[short_name] = n
            logger.info(f"  {short_name}: {n} rows loaded")
        except Exception as e:
            logger.error(f"  {short_name}: FAILED - {e}")
            pg_conn.rollback()
            errors.append(short_name)
            results[short_name] = -1

    total_loaded = sum(v for v in results.values() if v > 0)
    logger.info(
        f"Loaded {total_loaded} lookup rows across {len(results)} tables "
        f"({len(errors)} errors)"
    )

    if errors:
        raise RuntimeError(f"Failed to load lookup tables: {errors}")

    return results


# ---------------------------------------------------------------------------
# Quality validation for loaded lookups
# ---------------------------------------------------------------------------

def _parse_validation_sql() -> dict[str, str]:
    """Parse the validation SQL file into {tag: query} pairs.

    Reads sql/silver/000_validate_lookups.sql and splits by TAG comments.
    """
    sql_path = SQL_DIR / "silver" / "000_validate_lookups.sql"
    content = sql_path.read_text(encoding="utf-8")

    queries = {}
    current_tag = None
    current_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- TAG:"):
            if current_tag and current_lines:
                queries[current_tag] = "\n".join(current_lines).strip()
            current_tag = stripped.replace("-- TAG:", "").strip()
            current_lines = []
        elif stripped and not stripped.startswith("--"):
            current_lines.append(line)

    if current_tag and current_lines:
        queries[current_tag] = "\n".join(current_lines).strip()

    return queries


def validate_lookups(pg_conn) -> bool:
    """Validate that all lookup tables match the Python contract definitions.

    Reads validation queries from sql/silver/000_validate_lookups.sql.
    Compares PostgreSQL data against the Python dicts in this module.

    Checks:
        - Row counts match expected
        - Every Python dict entry exists in PostgreSQL
        - No orphaned rows in PostgreSQL

    Args:
        pg_conn: PostgreSQL connection.

    Returns:
        True if all checks pass, False otherwise.
    """
    all_pass = True
    queries = _parse_validation_sql()

    # Expected data from Python contract dicts
    expected_data = {
        "far_part": {k: v[0] for k, v in TYPE_OPERATOR_TO_FAR_PART.items()},
        "damage": {k: v[0] for k, v in DAMAGE_CODE_MAP.items()},
        "event_type": {k: v[0] for k, v in EVENT_TYPE_MAP.items()},
        "aircraft_category": {k: v[0] for k, v in AIRCRAFT_CATEGORY_MAP.items()},
        "manufacturer": {
            prefix: canonical
            for canonical, prefixes in MANUFACTURER_RULES
            for prefix in prefixes
        },
    }

    for tag, expected in expected_data.items():
        query = queries.get(tag)
        if not query:
            logger.error(f"  _lookup_{tag}: no validation query found in SQL file")
            all_pass = False
            continue

        try:
            with pg_conn.cursor() as cur:
                cur.execute(query)
                pg_data = {r[0]: r[1] for r in cur.fetchall()}

            if len(pg_data) != len(expected):
                logger.error(
                    f"  _lookup_{tag}: row count mismatch "
                    f"(expected={len(expected)} actual={len(pg_data)})"
                )
                all_pass = False
                continue

            mismatches = [
                f"{code}: expected={exp} got={pg_data.get(code)}"
                for code, exp in expected.items()
                if pg_data.get(code) != exp
            ]

            if mismatches:
                for m in mismatches:
                    logger.error(f"  _lookup_{tag}: MISMATCH {m}")
                all_pass = False
            else:
                logger.info(f"  _lookup_{tag}: {len(expected)} entries verified - PASS")

        except Exception as e:
            logger.error(f"  _lookup_{tag}: validation error - {e}")
            pg_conn.rollback()
            all_pass = False

    status = "ALL PASS" if all_pass else "FAILURES DETECTED"
    logger.info(f"  Contract validation: {status} (v{CONTRACT_VERSION})")
    return all_pass
