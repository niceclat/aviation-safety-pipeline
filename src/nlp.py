"""
NLP module: extract failure categories and severity signals from narrative text.

Called by silver layer SQL via a PostgreSQL function, or run standalone to
populate the silver.narrative_analysis table.

Uses regex pattern matching — intentionally practical and auditable for
insurance underwriting context.
"""

import io
import logging
import re
from pathlib import Path

import psycopg2

logger = logging.getLogger(__name__)

FAILURE_PATTERNS = {
    "engine_failure": [
        r"engine\s*(failure|malfunction|power\s*loss|shutdown|flameout)",
        r"loss\s*of\s*engine\s*power",
        r"engine\s*seiz",
        r"total\s*loss\s*of\s*power",
    ],
    "landing_gear": [
        r"landing\s*gear",
        r"gear\s*(collapse|retract|fail|malfunction)",
        r"nose\s*gear",
        r"main\s*gear",
    ],
    "fuel_related": [
        r"fuel\s*(exhaust|starvat|contaminat|leak|mismanag|selector)",
        r"ran\s*out\s*of\s*fuel",
        r"fuel\s*system",
    ],
    "weather": [
        r"(thunderstorm|icing|turbulence|wind\s*shear|microburst)",
        r"instrument\s*meteorological\s*conditions",
        r"\bIMC\b",
        r"(fog|snow|rain|ice)\s*(encounter|accumulat|condit)",
        r"weather\s*(related|conditions|encounter)",
    ],
    "bird_strike": [
        r"bird\s*strike",
        r"struck?\s*(a\s*)?bird",
        r"wildlife\s*strike",
    ],
    "structural": [
        r"structural\s*(failure|fatigue|crack)",
        r"fuselage\s*(crack|fail|breach)",
        r"wing\s*(fail|separ|crack)",
        r"stabilizer\s*(fail|separ)",
    ],
    "hydraulic": [
        r"hydraulic\s*(failure|malfunction|leak|loss|system)",
    ],
    "electrical": [
        r"electrical\s*(failure|malfunction|fire|short|system)",
        r"battery\s*(fire|failure)",
        r"wiring\s*(failure|short|fire)",
    ],
    "fire": [
        r"(in-?flight|post-?crash|engine)\s*fire",
        r"fire\s*(erupted|broke\s*out|started|reported)",
        r"smoke\s*in\s*(the\s*)?(cabin|cockpit)",
    ],
    "human_factors": [
        r"pilot\s*(error|deviation|failure\s*to|inadequa)",
        r"(spatial\s*)?disorientation",
        r"controlled\s*flight\s*into\s*terrain",
        r"\bCFIT\b",
        r"loss\s*of\s*control",
        r"inadequate\s*(preflight|planning|decision)",
        r"crew\s*resource\s*management",
        r"fatigue",
    ],
    "maintenance": [
        r"maintenance\s*(error|inadequa|improper)",
        r"improper\s*maintenance",
        r"(inspect|overhaul)\s*(fail|inadequa|improper)",
    ],
}


def extract_failure_categories(text: str) -> list:
    """Extract failure categories from narrative text using regex."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for category, patterns in FAILURE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                found.append(category)
                break
    return found


def compute_text_severity(text: str) -> int:
    """Score narrative severity based on keyword presence (1-5 scale)."""
    if not text:
        return 0
    text_lower = text.lower()

    score = 1
    if re.search(r"fatal|killed|died|death", text_lower):
        score = max(score, 5)
    if re.search(r"destroyed|total\s*loss|not\s*recoverable", text_lower):
        score = max(score, 4)
    if re.search(r"serious\s*injur|hospitali|substantial\s*damage", text_lower):
        score = max(score, 3)
    if re.search(r"minor\s*injur|minor\s*damage", text_lower):
        score = max(score, 2)
    return score


def _read_sql(filename: str) -> str:
    """Read a SQL file from the sql/ directory."""
    sql_dir = Path(__file__).resolve().parent.parent / "sql"
    return (sql_dir / filename).read_text(encoding="utf-8")


def run_narrative_analysis(pg_conn):
    """Process narratives and write results to silver.narrative_analysis."""
    logger.info("Running NLP narrative analysis")

    cursor = pg_conn.cursor()

    # Create target table from SQL file
    cursor.execute(_read_sql("silver/004_narrative_analysis_schema.sql"))
    pg_conn.commit()

    # Read narratives using SQL file
    cursor.execute(_read_sql("silver/005_narrative_select.sql"))
    rows = cursor.fetchall()
    logger.info(f"Processing {len(rows):,} narratives")

    # Build all rows in memory, then bulk insert via COPY
    buf = io.StringIO()
    count = 0
    for ev_id, aircraft_key, narr_accp, narr_cause in rows:
        combined = (str(narr_cause) if narr_cause else "") + " " + (str(narr_accp) if narr_accp else "")
        categories = extract_failure_categories(combined)
        severity = compute_text_severity(combined)
        primary = categories[0] if categories else ""
        narr_len = len(combined.strip())

        cats_pg = "{" + ",".join(categories) + "}" if categories else "{}"
        fields = [
            ev_id or "",
            str(aircraft_key) if aircraft_key is not None else "",
            cats_pg,
            primary,
            str(len(categories)),
            str(severity),
            str("engine_failure" in categories),
            str("weather" in categories),
            str("human_factors" in categories),
            str("fire" in categories),
            str("structural" in categories),
            str("maintenance" in categories),
            str(narr_len),
        ]
        buf.write("\t".join(fields) + "\n")
        count += 1

    buf.seek(0)
    cursor.copy_expert(
        "COPY silver.narrative_analysis FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '')",
        buf,
    )
    pg_conn.commit()
    logger.info(f"Wrote {count:,} narrative analysis rows to silver.narrative_analysis")
    return count
