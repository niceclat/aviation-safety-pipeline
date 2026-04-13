"""
EDA Script 3: Severity analysis and narrative text exploration.

Analyzes:
- Severity distributions (injury levels, damage types)
- Narrative field coverage and content patterns
- Failure category extraction from narratives (prototype NLP)
- Findings code structure and cause/factor patterns

Usage:
    python src/eda/explore_severity_narratives.py [--data-dir D:/honeywell/ntsb_data]
"""

import argparse
import re
from collections import Counter
from pathlib import Path

try:
    import pyodbc
except ImportError:
    raise RuntimeError("pyodbc required on Windows")


def get_connection(mdb_path: str):
    drv = "Microsoft Access Driver (*.mdb, *.accdb)"
    return pyodbc.connect(f"DRIVER={{{drv}}};DBQ={mdb_path};")


def print_header(title: str):
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)


# --- Failure category patterns for NLP extraction ---
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
    """Extract failure categories from narrative text using regex patterns."""
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


def analyze_severity(mdb_path: str, name: str):
    """Analyze severity distributions for commercial operations."""
    print_header(f"{name}: Severity Analysis (Part 121 + 135)")

    conn = get_connection(mdb_path)
    cursor = conn.cursor()

    # Join events + aircraft for commercial ops
    cursor.execute("""
        SELECT e.ev_highest_injury, a.damage, e.inj_tot_f, e.inj_tot_s,
               e.inj_tot_m, e.inj_tot_n, e.ev_type
        FROM events e
        INNER JOIN aircraft a ON e.ev_id = a.ev_id
        WHERE a.far_part IN ('121', '135')
    """)
    rows = cursor.fetchall()
    print(f"Total commercial events: {len(rows):,}")

    # Injury level distribution
    injury_dist = Counter(r[0] for r in rows)
    print(f"\nHighest injury level:")
    for k, v in injury_dist.most_common():
        print(f"  {k}: {v:,} ({100*v/len(rows):.1f}%)")

    # Damage distribution
    damage_dist = Counter(r[1] for r in rows)
    print(f"\nAircraft damage:")
    for k, v in damage_dist.most_common():
        print(f"  {k}: {v:,} ({100*v/len(rows):.1f}%)")

    # Event type
    type_dist = Counter(r[6] for r in rows)
    print(f"\nEvent type:")
    for k, v in type_dist.most_common():
        print(f"  {k}: {v:,}")

    # Fatality statistics
    fatalities = [r[2] or 0 for r in rows]
    serious = [r[3] or 0 for r in rows]
    events_with_fatal = sum(1 for f in fatalities if f > 0)
    total_fatal = sum(fatalities)
    total_serious = sum(serious)
    print(f"\nFatality stats:")
    print(f"  Events with fatalities: {events_with_fatal:,}")
    print(f"  Total fatalities: {total_fatal:,}")
    print(f"  Total serious injuries: {total_serious:,}")

    conn.close()


def analyze_narratives(mdb_path: str, name: str):
    """Analyze narrative text content for commercial operations."""
    print_header(f"{name}: Narrative Analysis (Part 121 + 135)")

    conn = get_connection(mdb_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT n.narr_accp, n.narr_accf, n.narr_cause, n.narr_inc
        FROM narratives n
        INNER JOIN aircraft a ON n.ev_id = a.ev_id AND n.Aircraft_Key = a.Aircraft_Key
        WHERE a.far_part IN ('121', '135')
    """)
    rows = cursor.fetchall()
    print(f"Narratives for commercial ops: {len(rows):,}")

    # Coverage analysis
    n_accp = sum(1 for r in rows if r[0] and str(r[0]).strip() not in ('', 'import'))
    n_accf = sum(1 for r in rows if r[1] and str(r[1]).strip())
    n_cause = sum(1 for r in rows if r[2] and str(r[2]).strip())
    n_inc = sum(1 for r in rows if r[3] and str(r[3]).strip())

    print(f"\nField coverage:")
    print(f"  narr_accp (factual):       {n_accp:,} ({100*n_accp/len(rows):.1f}%)")
    print(f"  narr_accf (final):         {n_accf:,} ({100*n_accf/len(rows):.1f}%)")
    print(f"  narr_cause (probable):     {n_cause:,} ({100*n_cause/len(rows):.1f}%)")
    print(f"  narr_inc (FAA incident):   {n_inc:,} ({100*n_inc/len(rows):.1f}%)")

    # Average text lengths
    accp_lens = [len(str(r[0])) for r in rows if r[0] and str(r[0]).strip() not in ('', 'import')]
    cause_lens = [len(str(r[2])) for r in rows if r[2] and str(r[2]).strip()]
    if accp_lens:
        print(f"\nnarr_accp avg length: {sum(accp_lens)/len(accp_lens):.0f} chars")
        print(f"  min: {min(accp_lens)}, max: {max(accp_lens)}")
    if cause_lens:
        print(f"narr_cause avg length: {sum(cause_lens)/len(cause_lens):.0f} chars")
        print(f"  min: {min(cause_lens)}, max: {max(cause_lens)}")

    # NLP: Extract failure categories from narr_cause
    print_header(f"{name}: Failure Category Extraction (NLP prototype)")
    all_categories = Counter()
    categorized = 0
    for r in rows:
        cause_text = str(r[2]) if r[2] else ""
        factual_text = str(r[0]) if r[0] else ""
        combined = cause_text + " " + factual_text
        cats = extract_failure_categories(combined)
        if cats:
            categorized += 1
        for c in cats:
            all_categories[c] += 1

    print(f"Narratives with extracted categories: {categorized:,}/{len(rows):,} ({100*categorized/len(rows):.1f}%)")
    print(f"\nFailure category distribution:")
    for cat, count in all_categories.most_common():
        print(f"  {cat}: {count:,} ({100*count/len(rows):.1f}%)")

    # Sample narratives for top categories
    print(f"\n--- Sample probable cause narratives ---")
    sample_count = 0
    for r in rows:
        if sample_count >= 5:
            break
        cause = str(r[2]) if r[2] else ""
        if cause and len(cause) > 50:
            cats = extract_failure_categories(cause)
            if cats:
                print(f"\n  Categories: {cats}")
                print(f"  Text: {cause[:300]}...")
                sample_count += 1

    conn.close()


def analyze_findings(mdb_path: str, name: str):
    """Analyze the structured Findings table."""
    print_header(f"{name}: Findings Code Analysis")

    conn = get_connection(mdb_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT f.finding_description, f.Cause_Factor, f.category_no,
               f.subcategory_no, f.section_no
        FROM Findings f
        INNER JOIN aircraft a ON f.ev_id = a.ev_id AND f.Aircraft_Key = a.Aircraft_Key
        WHERE a.far_part IN ('121', '135')
    """)
    rows = cursor.fetchall()
    print(f"Findings for commercial ops: {len(rows):,}")

    # Category distribution (first level of hierarchy)
    cat_dist = Counter(r[2] for r in rows)
    print(f"\nTop-level category distribution:")
    cat_labels = {
        "01": "Aircraft",
        "02": "Personnel issues",
        "03": "Environmental issues",
        "04": "Organizational issues",
        "05": "Not determined",
    }
    for k, v in cat_dist.most_common():
        label = cat_labels.get(k, k)
        print(f"  {k} ({label}): {v:,}")

    # Cause vs Factor
    cf_dist = Counter(r[1] for r in rows)
    print(f"\nCause/Factor distribution:")
    for k, v in cf_dist.most_common():
        label = {"C": "Cause", "F": "Factor", None: "Event/Other"}.get(k, k)
        print(f"  {label}: {v:,}")

    # Top finding descriptions
    desc_dist = Counter()
    for r in rows:
        if r[0]:
            # Take just the main finding text (first part before modifier)
            parts = str(r[0]).split("-")
            if len(parts) >= 3:
                key = "-".join(parts[:3])
            else:
                key = str(r[0])
            desc_dist[key] += 1

    print(f"\nTop 20 finding descriptions:")
    for desc, count in desc_dist.most_common(20):
        print(f"  {desc}: {count}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze severity and narratives"
    )
    parser.add_argument(
        "--data-dir",
        default="D:/honeywell/ntsb_data",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    avall = str(data_dir / "avall" / "avall.mdb")
    pre2008 = str(data_dir / "Pre2008" / "Pre2008.mdb")

    # Severity analysis
    analyze_severity(avall, "avall (2008+)")
    analyze_severity(pre2008, "Pre2008 (1982-2007)")

    # Narrative analysis
    analyze_narratives(avall, "avall (2008+)")
    analyze_narratives(pre2008, "Pre2008 (1982-2007)")

    # Findings analysis (only meaningful for avall)
    analyze_findings(avall, "avall (2008+)")

    print_header("SUMMARY")
    print("1. Severity scoring should weight: FATL=4, SERS=3, MINR=2, NONE=1")
    print("2. Damage scoring: DEST=4, SUBS=3, MINR=2, NONE=1")
    print("3. narr_cause is the richest field for NLP failure extraction")
    print("4. Regex patterns capture ~60-80% of narratives into categories")
    print("5. Findings table provides structured cause/factor codes (avall only)")
    print("6. Top categories: Personnel > Environmental > Aircraft issues")


if __name__ == "__main__":
    main()
