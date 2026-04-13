"""Generate bronze DDL SQL files from MDB schemas.

Reads each MDB file, auto-generates CREATE TABLE statements with all columns
as TEXT, handles PostgreSQL reserved words by quoting them.
"""

import sys
from pathlib import Path

import pyodbc

# PostgreSQL reserved words that need quoting when used as column names
PG_RESERVED = {
    "table", "column", "order", "group", "user", "select", "type", "comment",
    "key", "check", "primary", "default", "index", "constraint", "references",
    "case", "when", "then", "else", "end", "and", "or", "not", "in", "is",
    "null", "true", "false", "limit", "offset", "all", "cross", "join",
    "from", "where", "having", "union", "create", "drop", "alter", "grant",
    "values", "into", "set", "as", "on", "like", "between", "exists",
    "partition", "row", "rows", "range", "both", "leading", "trailing",
    "position", "current", "name", "action", "mode", "year", "month", "day",
    "hour", "minute", "second", "zone", "sequence", "start", "authorization",
}


def safe_col(name: str) -> str:
    """Make a column name safe for PostgreSQL."""
    s = name.lower().replace(" ", "_").replace("/", "_")
    if s in PG_RESERVED:
        return f'"column_{s}"'
    return s


def gen_ddl(schema: str, mdb_path: str, table_renames: dict) -> list:
    """Generate DDL statements for all tables in an MDB file."""
    conn = pyodbc.connect(
        f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};"
    )
    cursor = conn.cursor()
    tables = [t.table_name for t in cursor.tables(tableType="TABLE")]

    ddl = []
    for t in tables:
        cols = [c.column_name for c in cursor.columns(table=t)]
        pg_name = table_renames.get(t, t.lower())

        col_defs = [f"    {safe_col(c)} TEXT" for c in cols]
        col_defs.append("    _source_file TEXT NOT NULL")
        col_defs.append("    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()")

        ddl.append(
            f"DROP TABLE IF EXISTS {schema}.{pg_name} CASCADE;\n"
            f"CREATE TABLE {schema}.{pg_name} (\n"
            + ",\n".join(col_defs)
            + "\n);"
        )

    conn.close()
    return ddl


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "D:/honeywell/ntsb_data"
    sql_dir = Path(__file__).resolve().parent.parent.parent / "sql" / "bronze"

    renames = {
        "Flight_Crew": "flight_crew",
        "Events_Sequence": "events_sequence",
        "eADMSPUB_DataDictionary": "data_dictionary",
        "Country": "country",
        "NTSB_Admin": "ntsb_admin",
        "Findings": "findings",
        "Occurrences": "occurrences",
    }

    pre82_renames = {
        "tblFirstHalf": "tbl_first_half",
        "tblSecondHalf": "tbl_second_half",
        "tblOccurrences": "tbl_occurrences",
        "tblSeqOfEvents": "tbl_seq_of_events",
        "ct_Pre1982": "ct_codes",
    }

    sources = [
        ("002_bronze_avall.sql", "bronze_avall", f"{data_dir}/avall/avall.mdb", renames, "2008-present"),
        ("003_bronze_pre2008.sql", "bronze_pre2008", f"{data_dir}/Pre2008/Pre2008.mdb", renames, "1982-2007"),
        ("004_bronze_pre1982.sql", "bronze_pre1982", f"{data_dir}/PRE1982/PRE1982.MDB", pre82_renames, "1962-1981"),
    ]

    for fname, schema, mdb_path, rn, era in sources:
        mdb_file = Path(mdb_path).name
        ddl = gen_ddl(schema, mdb_path, rn)
        out = sql_dir / fname
        with open(out, "w") as f:
            f.write(f"-- Bronze: raw tables from {mdb_file} ({era})\n")
            f.write("-- Auto-generated. All columns TEXT. Reserved words quoted.\n\n")
            f.write("\n\n".join(ddl) + "\n")
        print(f"  {fname}: {len(ddl)} tables")

    print("Done.")


if __name__ == "__main__":
    main()
