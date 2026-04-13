"""
EDA Script 2: Aircraft model normalization analysis.

Analyzes the inconsistency in aircraft make/model naming across all three
databases and develops normalization rules for grouping variants into
model families relevant to commercial underwriting.

Usage:
    python src/eda/explore_models.py [--data-dir D:/honeywell/ntsb_data]
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


def normalize_make(raw: str) -> str:
    """Normalize aircraft manufacturer name."""
    if not raw:
        return "UNKNOWN"
    s = raw.strip().upper()

    # Canonical manufacturer mappings
    mappings = {
        "BOEING": ["BOEING"],
        "AIRBUS": ["AIRBUS", "AIRBUS INDUSTRIE"],
        "BOMBARDIER": ["BOMBARDIER", "BOMBARDIER INC", "CANADAIR", "DE HAVILLAND CANADA"],
        "EMBRAER": ["EMBRAER", "EMBRAER-EMPRESA BRASILEIRA DE"],
        "CESSNA": ["CESSNA", "TEXTRON AVIATION"],
        "BEECHCRAFT": ["BEECH", "BEECHCRAFT", "HAWKER BEECHCRAFT"],
        "PIPER": ["PIPER"],
        "BELL": ["BELL", "BELL HELICOPTER"],
        "MCDONNELL DOUGLAS": ["MCDONNELL DOUGLAS", "DOUGLAS", "MCDONNELL"],
        "LOCKHEED": ["LOCKHEED", "LOCKHEED MARTIN"],
        "DEHAVILLAND": ["DEHAVILLAND", "DE HAVILLAND"],
        "ROBINSON": ["ROBINSON HELICOPTER"],
        "SIKORSKY": ["SIKORSKY"],
        "EUROCOPTER": ["EUROCOPTER", "EUROCOPTER FRANCE", "EUROCOPTER DEUTSCHLAND"],
        "CIRRUS": ["CIRRUS DESIGN", "CIRRUS"],
        "MOONEY": ["MOONEY"],
        "GRUMMAN": ["GRUMMAN", "GRUMMAN AMERICAN"],
    }

    for canonical, variants in mappings.items():
        for v in variants:
            if s == v or s.startswith(v):
                return canonical
    return s


def extract_model_family(raw_model: str, make: str) -> str:
    """Extract base model family from a raw model string.

    Examples:
        737-7H4 -> 737
        737 7H4 -> 737
        737-823 -> 737
        A320-232 -> A320
        CL-600-2B19 -> CL-600
        PA-31-350 -> PA-31
        208B -> 208
    """
    if not raw_model:
        return "UNKNOWN"
    s = raw_model.strip().upper()

    # Boeing: extract 3-digit base (707, 717, 727, 737, 747, 757, 767, 777, 787)
    if make in ("BOEING",):
        m = re.match(r"(7[0-9]7)", s)
        if m:
            return m.group(1)
        # Also handle MD- models Boeing inherited
        m = re.match(r"(MD-\d+)", s)
        if m:
            return m.group(1)

    # Airbus: A3XX pattern
    if make in ("AIRBUS",):
        m = re.match(r"(A\d{3})", s)
        if m:
            return m.group(1)

    # McDonnell Douglas: DC-X or MD-XX
    if make in ("MCDONNELL DOUGLAS",):
        m = re.match(r"(DC-\d+|MD-\d+)", s)
        if m:
            return m.group(1)

    # Bombardier/Canadair: CL-600 family (CRJ), DHC, etc.
    if make in ("BOMBARDIER",):
        m = re.match(r"(CL-\d+|CRJ|DHC-\d+|BD-\d+)", s)
        if m:
            return m.group(1)

    # Embraer: EMB-XXX or ERJ-XXX or E1XX/E1XX
    if make in ("EMBRAER",):
        m = re.match(r"(EMB-\d+|ERJ\s*\d+|E\d{3})", s)
        if m:
            return m.group(1).replace(" ", "")

    # Cessna: numeric model (150, 172, 182, 206, 208, 402, etc.)
    if make in ("CESSNA",):
        m = re.match(r"([A-Z]?\d{3})", s)
        if m:
            return m.group(1)

    # Beechcraft: model name or number (1900, 99, 58, A36, etc.)
    if make in ("BEECHCRAFT",):
        m = re.match(r"([A-Z]?\d+[A-Z]?)", s)
        if m:
            return m.group(1)

    # Piper: PA-XX pattern
    if make in ("PIPER",):
        m = re.match(r"(PA[\s-]?\d+)", s)
        if m:
            return m.group(1).replace(" ", "-")

    # Bell: 3-digit model (206, 407, 412, etc.)
    if make in ("BELL",):
        m = re.match(r"(\d{3})", s)
        if m:
            return m.group(1)

    # Lockheed: L-XXXX
    if make in ("LOCKHEED",):
        m = re.match(r"(L-\d+)", s)
        if m:
            return m.group(1)

    # Generic: take everything before the first dash or space after initial model
    m = re.match(r"([A-Z]*\d+[A-Z]?)", s)
    if m:
        return m.group(1)

    return s


def analyze_models(mdb_path: str, name: str, far_parts=None, make_col="acft_make",
                   model_col="acft_model", table="aircraft", far_col="far_part"):
    """Analyze model naming for a given database and operation filter."""
    conn = get_connection(mdb_path)
    cursor = conn.cursor()

    if far_parts:
        placeholders = ",".join(f"'{p}'" for p in far_parts)
        query = f"SELECT [{make_col}], [{model_col}] FROM [{table}] WHERE [{far_col}] IN ({placeholders})"
    else:
        query = f"SELECT [{make_col}], [{model_col}] FROM [{table}]"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    print(f"\nTotal records: {len(rows):,}")

    # Raw make distribution
    raw_makes = Counter(r[0] for r in rows)
    print(f"\nRaw distinct makes: {len(raw_makes)}")
    print("Top 20 raw makes:")
    for k, v in raw_makes.most_common(20):
        print(f"  '{k}': {v}")

    # Normalized make distribution
    norm_makes = Counter(normalize_make(r[0]) for r in rows)
    print(f"\nNormalized distinct makes: {len(norm_makes)}")
    print("Top 20 normalized makes:")
    for k, v in norm_makes.most_common(20):
        print(f"  {k}: {v}")

    # Model family extraction
    families = Counter()
    family_detail = {}
    for raw_make, raw_model in rows:
        nm = normalize_make(raw_make)
        fam = extract_model_family(raw_model, nm)
        key = f"{nm} {fam}"
        families[key] += 1
        if key not in family_detail:
            family_detail[key] = Counter()
        family_detail[key][raw_model] += 1

    print(f"\nDistinct model families: {len(families)}")
    print("Top 30 model families:")
    for key, count in families.most_common(30):
        variants = family_detail[key]
        n_variants = len(variants)
        top3 = ", ".join(f"'{m}'({c})" for m, c in variants.most_common(3))
        print(f"  {key}: {count} incidents ({n_variants} variants: {top3})")

    return families


def analyze_pre1982_models(mdb_path: str):
    """Analyze PRE1982 models which use different columns."""
    print_header("PRE1982 Model Analysis (Commercial: TYPE_OPERATOR E/N/P)")

    conn = get_connection(mdb_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ACFT_MAKE, ACFT_MODEL FROM tblFirstHalf "
        "WHERE TYPE_OPERATOR IN ('E','N','P')"
    )
    rows = cursor.fetchall()
    conn.close()

    print(f"Total commercial records: {len(rows):,}")

    families = Counter()
    for raw_make, raw_model in rows:
        nm = normalize_make(raw_make)
        fam = extract_model_family(raw_model, nm)
        families[f"{nm} {fam}"] += 1

    print("\nTop 20 model families (PRE1982 commercial):")
    for key, count in families.most_common(20):
        print(f"  {key}: {count}")

    return families


def main():
    parser = argparse.ArgumentParser(description="Analyze aircraft model naming")
    parser.add_argument(
        "--data-dir",
        default="D:/honeywell/ntsb_data",
        help="Root directory containing extracted MDB files",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    avall = str(data_dir / "avall" / "avall.mdb")
    pre2008 = str(data_dir / "Pre2008" / "Pre2008.mdb")
    pre1982 = str(data_dir / "PRE1982" / "PRE1982.MDB")

    # Part 121 + 135 from avall (2008-present)
    print_header("avall: Part 121 (Scheduled Airlines)")
    analyze_models(avall, "avall_121", far_parts=["121"])

    print_header("avall: Part 135 (Commuter/Charter)")
    analyze_models(avall, "avall_135", far_parts=["135"])

    # Part 121 + 135 from Pre2008 (1982-2007)
    print_header("Pre2008: Part 121 (Scheduled Airlines)")
    analyze_models(pre2008, "pre2008_121", far_parts=["121"])

    print_header("Pre2008: Part 135 (Commuter/Charter)")
    analyze_models(pre2008, "pre2008_135", far_parts=["135"])

    # PRE1982 commercial
    analyze_pre1982_models(pre1982)

    # All commercial across Pre2008 + avall
    print_header("COMBINED Pre2008+avall: Part 121+135")
    conn1 = get_connection(pre2008)
    conn2 = get_connection(avall)
    c1, c2 = conn1.cursor(), conn2.cursor()

    c1.execute("SELECT acft_make, acft_model FROM aircraft WHERE far_part IN ('121','135')")
    rows1 = c1.fetchall()
    c2.execute("SELECT acft_make, acft_model FROM aircraft WHERE far_part IN ('121','135')")
    rows2 = c2.fetchall()
    conn1.close()
    conn2.close()

    all_rows = list(rows1) + list(rows2)
    print(f"Total combined commercial records: {len(all_rows):,}")

    families = Counter()
    for raw_make, raw_model in all_rows:
        nm = normalize_make(raw_make)
        fam = extract_model_family(raw_model, nm)
        families[f"{nm} {fam}"] += 1

    print("\nTop 30 combined commercial model families:")
    for key, count in families.most_common(30):
        print(f"  {key}: {count}")

    # Summary for assignment scoping
    print_header("SCOPING RECOMMENDATION")
    print("\nModels with 50+ incidents (sufficient for statistical analysis):")
    sufficient = [(k, v) for k, v in families.most_common() if v >= 50]
    for k, v in sufficient:
        print(f"  {k}: {v}")
    print(f"\n{len(sufficient)} model families with 50+ incidents")
    print("These are candidates for the gold-layer risk profile table.")


if __name__ == "__main__":
    main()
