"""
EDA Script 1: Explore and compare all three NTSB data sources.

Outputs a structured report of:
- Table inventories and row counts per database
- Schema differences between Pre2008 and avall
- PRE1982 flat structure analysis
- Field value distributions for key columns
- Date ranges and coverage gaps

Usage:
    python src/eda/explore_sources.py [--data-dir D:/honeywell/ntsb_data]
"""

import argparse
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

# mdbtools is Linux-only; on Windows we fall back to pyodbc
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False


def get_connection(mdb_path: str):
    """Connect to an MDB file. Uses pyodbc on Windows, mdbtools on Linux."""
    if HAS_PYODBC:
        drv = "Microsoft Access Driver (*.mdb, *.accdb)"
        return pyodbc.connect(f"DRIVER={{{drv}}};DBQ={mdb_path};")
    raise RuntimeError(
        "pyodbc not available. On Linux, use mdbtools via subprocess instead."
    )


def list_tables(cursor):
    """Return list of user table names."""
    return [t.table_name for t in cursor.tables(tableType="TABLE")]


def table_summary(cursor, table: str):
    """Return (row_count, column_names) for a table."""
    cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
    count = cursor.fetchone()[0]
    cols = [c.column_name for c in cursor.columns(table=table)]
    return count, cols


def distinct_values(cursor, table: str, column: str, limit: int = 50):
    """Return Counter of distinct values for a column."""
    cursor.execute(f"SELECT [{column}] FROM [{table}]")
    return Counter(r[0] for r in cursor.fetchall())


def sample_rows(cursor, table: str, n: int = 5):
    """Return first n rows and column names."""
    cursor.execute(f"SELECT TOP {n} * FROM [{table}]")
    cols = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    return cols, rows


def print_header(title: str):
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)


def explore_database(name: str, mdb_path: str):
    """Full exploration of a single MDB file."""
    print_header(f"{name} — {mdb_path}")

    conn = get_connection(mdb_path)
    cursor = conn.cursor()

    tables = list_tables(cursor)
    print(f"\nTables ({len(tables)}): {tables}")

    for t in tables:
        try:
            count, cols = table_summary(cursor, t)
            print(f"\n  {t} ({count:,} rows, {len(cols)} cols)")
            print(f"    Columns: {cols}")
        except Exception as e:
            print(f"\n  {t} — ERROR: {e}")

    conn.close()
    return tables


def explore_avall(mdb_path: str):
    """Deep dive into avall.mdb field distributions."""
    print_header("avall.mdb — Field Distributions")

    conn = get_connection(mdb_path)
    cursor = conn.cursor()

    # Date range
    cursor.execute("SELECT MIN(ev_date), MAX(ev_date) FROM events")
    r = cursor.fetchone()
    print(f"\nDate range: {r[0]} to {r[1]}")

    # Event type
    dist = distinct_values(cursor, "events", "ev_type")
    print(f"\nev_type: {dict(dist.most_common())}")

    # Highest injury
    dist = distinct_values(cursor, "events", "ev_highest_injury")
    print(f"\nev_highest_injury: {dict(dist.most_common())}")

    # Aircraft damage
    dist = distinct_values(cursor, "aircraft", "damage")
    print(f"\ndamage: {dict(dist.most_common())}")

    # FAR part
    dist = distinct_values(cursor, "aircraft", "far_part")
    print(f"\nfar_part (operation type):")
    for k, v in dist.most_common():
        print(f"  {k}: {v:,}")

    # Aircraft category
    dist = distinct_values(cursor, "aircraft", "acft_category")
    print(f"\nacft_category: {dict(dist.most_common())}")

    # Type of flying
    dist = distinct_values(cursor, "aircraft", "type_fly")
    print(f"\ntype_fly: {dict(dist.most_common())}")

    # Top aircraft makes (Part 121)
    cursor.execute(
        "SELECT acft_make, acft_model FROM aircraft WHERE far_part='121'"
    )
    rows = cursor.fetchall()
    mc = Counter((r[0], r[1]) for r in rows)
    print(f"\nTop Part 121 aircraft (make, model) — {len(rows)} total:")
    for k, v in mc.most_common(20):
        print(f"  {k[0]} | {k[1]}: {v}")

    # Top aircraft makes (Part 135)
    cursor.execute(
        "SELECT acft_make, acft_model FROM aircraft WHERE far_part='135'"
    )
    rows = cursor.fetchall()
    mc = Counter((r[0], r[1]) for r in rows)
    print(f"\nTop Part 135 aircraft (make, model) — {len(rows)} total:")
    for k, v in mc.most_common(15):
        print(f"  {k[0]} | {k[1]}: {v}")

    # Narrative field coverage
    cursor.execute(
        "SELECT COUNT(*) FROM narratives WHERE narr_accp IS NOT NULL"
    )
    n_accp = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM narratives WHERE narr_cause IS NOT NULL"
    )
    n_cause = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM narratives WHERE narr_accf IS NOT NULL"
    )
    n_accf = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM narratives")
    n_total = cursor.fetchone()[0]
    print(f"\nNarrative coverage ({n_total:,} total):")
    print(f"  narr_accp (factual): {n_accp:,}")
    print(f"  narr_accf (final):   {n_accf:,}")
    print(f"  narr_cause:          {n_cause:,}")

    # Events_Sequence vs Occurrences
    cursor.execute("SELECT COUNT(*) FROM Events_Sequence")
    es = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Occurrences")
    occ = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Findings")
    fin = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM seq_of_events")
    soe = cursor.fetchone()[0]
    print(f"\nFindings system:")
    print(f"  Events_Sequence (new): {es:,}")
    print(f"  Findings (new):        {fin:,}")
    print(f"  Occurrences (old):     {occ:,}")
    print(f"  seq_of_events (old):   {soe:,}")

    conn.close()


def explore_pre2008(mdb_path: str):
    """Deep dive into Pre2008.mdb — focus on differences from avall."""
    print_header("Pre2008.mdb — Field Distributions & Differences")

    conn = get_connection(mdb_path)
    cursor = conn.cursor()

    cursor.execute("SELECT MIN(ev_date), MAX(ev_date) FROM events")
    r = cursor.fetchone()
    print(f"\nDate range: {r[0]} to {r[1]}")

    dist = distinct_values(cursor, "aircraft", "far_part")
    print(f"\nfar_part distribution:")
    for k, v in dist.most_common():
        print(f"  {k}: {v:,}")

    # Events_Sequence vs Occurrences (Pre2008 uses old system)
    cursor.execute("SELECT COUNT(*) FROM Events_Sequence")
    es = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Occurrences")
    occ = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Findings")
    fin = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM seq_of_events")
    soe = cursor.fetchone()[0]
    print(f"\nFindings system (Pre2008 uses OLD):")
    print(f"  Events_Sequence (new): {es:,}")
    print(f"  Findings (new):        {fin:,}")
    print(f"  Occurrences (old):     {occ:,}")
    print(f"  seq_of_events (old):   {soe:,}")

    # Narrative coverage
    cursor.execute("SELECT COUNT(*) FROM narratives")
    n_total = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM narratives WHERE narr_cause IS NOT NULL"
    )
    n_cause = cursor.fetchone()[0]
    print(f"\nNarratives: {n_total:,} total, {n_cause:,} with probable cause")

    # Top Part 121 models
    cursor.execute(
        "SELECT acft_make, acft_model FROM aircraft WHERE far_part='121'"
    )
    rows = cursor.fetchall()
    mc = Counter((r[0], r[1]) for r in rows)
    print(f"\nTop Part 121 aircraft — {len(rows)} total:")
    for k, v in mc.most_common(15):
        print(f"  {k[0]} | {k[1]}: {v}")

    conn.close()


def explore_pre1982(mdb_path: str):
    """Explore the completely different PRE1982 schema."""
    print_header("PRE1982.MDB — Legacy Flat Structure")

    conn = get_connection(mdb_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT MIN(DATE_OCCURRENCE), MAX(DATE_OCCURRENCE) FROM tblFirstHalf"
    )
    r = cursor.fetchone()
    print(f"\nDate range: {r[0]} to {r[1]}")

    # TYPE_OPERATOR distribution
    dist = distinct_values(cursor, "tblFirstHalf", "TYPE_OPERATOR")
    print(f"\nTYPE_OPERATOR distribution:")
    for k, v in dist.most_common():
        print(f"  {k}: {v:,}")

    # Decode TYPE_OPERATOR via ct_Pre1982
    cursor.execute(
        "SELECT Code, Meang FROM ct_Pre1982 WHERE Name='TYPE_OPERATOR'"
    )
    print(f"\nTYPE_OPERATOR code meanings:")
    for r in cursor.fetchall():
        print(f"  {r[0]}: {r[1]}")

    # TYPE_CRAFT
    dist = distinct_values(cursor, "tblFirstHalf", "TYPE_CRAFT")
    print(f"\nTYPE_CRAFT distribution: {dict(dist.most_common())}")

    cursor.execute(
        "SELECT Code, Meang FROM ct_Pre1982 WHERE Name='TYPE_CRAFT'"
    )
    print(f"\nTYPE_CRAFT code meanings:")
    for r in cursor.fetchall():
        print(f"  {r[0]}: {r[1]}")

    # ACC_INC_CLASS
    dist = distinct_values(cursor, "tblFirstHalf", "ACC_INC_CLASS")
    print(f"\nACC_INC_CLASS: {dict(dist.most_common())}")

    # Sample aircraft makes
    cursor.execute(
        "SELECT ACFT_MAKE, ACFT_MODEL FROM tblFirstHalf "
        "WHERE TYPE_OPERATOR IN ('E','N','P')"
    )
    rows = cursor.fetchall()
    mc = Counter((r[0], r[1]) for r in rows)
    print(f"\nCommercial ops (Air Taxi/Intrastate/Contract) aircraft — {len(rows)} total:")
    for k, v in mc.most_common(15):
        print(f"  {k[0]} | {k[1]}: {v}")

    # CAUSE fields
    cursor.execute(
        "SELECT TOP 5 CAUSE_FACTOR_1P, CAUSE_FACTOR_1M, CAUSE_FACTOR_1S "
        "FROM tblFirstHalf"
    )
    print(f"\nSample cause factor codes (1P/1M/1S):")
    for r in cursor.fetchall():
        print(f"  {r}")

    conn.close()


def compare_schemas(mdb1_path: str, mdb2_path: str):
    """Compare column-level differences between Pre2008 and avall."""
    print_header("Schema Comparison: Pre2008 vs avall")

    conn1 = get_connection(mdb1_path)
    conn2 = get_connection(mdb2_path)

    tables = [
        "events", "aircraft", "narratives", "Findings", "Events_Sequence",
        "Occurrences", "seq_of_events", "engines", "injury", "Flight_Crew",
    ]

    for t in tables:
        cols1 = [c.column_name for c in conn1.cursor().columns(table=t)]
        cols2 = [c.column_name for c in conn2.cursor().columns(table=t)]

        only_pre2008 = set(cols1) - set(cols2)
        only_avall = set(cols2) - set(cols1)

        if only_pre2008 or only_avall:
            print(f"\n*** {t} — DIFFERENCES ***")
            if only_pre2008:
                print(f"  Only in Pre2008: {only_pre2008}")
            if only_avall:
                print(f"  Only in avall:   {only_avall}")
        else:
            print(f"{t} — schemas MATCH ({len(cols1)} cols)")

    conn1.close()
    conn2.close()


def main():
    parser = argparse.ArgumentParser(description="Explore NTSB data sources")
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

    # Phase 1: Table inventory for all three databases
    print_header("PHASE 1: Table Inventory")
    for name, path in [("PRE1982", pre1982), ("Pre2008", pre2008), ("avall", avall)]:
        explore_database(name, path)

    # Phase 2: Schema comparison (Pre2008 vs avall)
    compare_schemas(pre2008, avall)

    # Phase 3: Deep dives
    explore_avall(avall)
    explore_pre2008(pre2008)
    explore_pre1982(pre1982)

    print_header("EXPLORATION COMPLETE")
    print("\nKey findings to document in EDA.md:")
    print("1. PRE1982 has completely different flat schema (5 tables, 400+ cols)")
    print("2. Pre2008 and avall share 20-table schema but use different findings systems")
    print("3. Pre2008 uses Occurrences/seq_of_events (old numeric codes)")
    print("4. avall uses Events_Sequence/Findings (new CAST/ICAO taxonomy)")
    print("5. Only avall.Findings has cm_inPc field (added March 2024)")
    print("6. Aircraft model naming is inconsistent across all databases")
    print("7. Combined Pre2008 + avall = ~93K events (matching ~90K cited in assignment)")


if __name__ == "__main__":
    main()
