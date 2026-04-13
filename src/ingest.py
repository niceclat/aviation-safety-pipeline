"""
Bronze layer ingestion: download, extract, and load NTSB MDB files.

Pipeline: download zip → extract MDB → auto-discover schema → bulk COPY to PostgreSQL.

Each data source gets its own isolated bronze schema:
    avall.mdb     → bronze_avall.*      (2008-present,  20 tables)
    Pre2008.mdb   → bronze_pre2008.*    (1982-2007,     20 tables)
    PRE1982.MDB   → bronze_pre1982.*    (1962-1981,      5 tables)

No transformation — raw mirror with lineage metadata (_source_file, _ingested_at).
See docs/DATA_CONTRACT.md for the full source-to-bronze mapping.
"""

import csv
import io
import logging
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration: source definitions
# ---------------------------------------------------------------------------

@dataclass
class BronzeSource:
    """Definition of a single MDB data source for bronze ingestion."""
    mdb_filename: str       # e.g. "avall.mdb"
    schema: str             # e.g. "bronze_avall"
    ddl_file: str           # e.g. "002_bronze_avall.sql"
    table_renames: dict     # MDB table name → PG table name overrides


SOURCES = [
    BronzeSource(
        mdb_filename="avall.mdb",
        schema="bronze_avall",
        ddl_file="002_bronze_avall.sql",
        table_renames={
            "Flight_Crew": "flight_crew",
            "Events_Sequence": "events_sequence",
            "eADMSPUB_DataDictionary": "data_dictionary",
            "Country": "country",
            "NTSB_Admin": "ntsb_admin",
            "Findings": "findings",
            "Occurrences": "occurrences",
        },
    ),
    BronzeSource(
        mdb_filename="Pre2008.mdb",
        schema="bronze_pre2008",
        ddl_file="003_bronze_pre2008.sql",
        table_renames={
            "Flight_Crew": "flight_crew",
            "Events_Sequence": "events_sequence",
            "eADMSPUB_DataDictionary": "data_dictionary",
            "Country": "country",
            "NTSB_Admin": "ntsb_admin",
            "Findings": "findings",
            "Occurrences": "occurrences",
        },
    ),
    BronzeSource(
        mdb_filename="PRE1982.MDB",
        schema="bronze_pre1982",
        ddl_file="004_bronze_pre1982.sql",
        table_renames={
            "tblFirstHalf": "tbl_first_half",
            "tblSecondHalf": "tbl_second_half",
            "tblOccurrences": "tbl_occurrences",
            "tblSeqOfEvents": "tbl_seq_of_events",
            "ct_Pre1982": "ct_codes",
        },
    ),
]


# ---------------------------------------------------------------------------
# PostgreSQL reserved word handling
# ---------------------------------------------------------------------------

_PG_RESERVED = {
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


def _safe_col(name: str) -> str:
    """Make a column name safe for PostgreSQL. Must match DDL generator logic."""
    s = name.lower().replace(" ", "_").replace("/", "_")
    if s in _PG_RESERVED:
        return f'"column_{s}"'
    return s


# ---------------------------------------------------------------------------
# MDB backend detection
# ---------------------------------------------------------------------------

def detect_backend() -> str:
    """Detect available MDB reader: pyodbc (Windows) or mdbtools (Linux/Docker).

    Raises:
        RuntimeError: If neither backend is available.
    """
    if platform.system() == "Windows":
        try:
            import pyodbc  # noqa: F401
            return "pyodbc"
        except ImportError:
            pass
    try:
        subprocess.run(["mdb-ver"], capture_output=True, check=True)
        return "mdbtools"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    raise RuntimeError(
        "No MDB reader available. Install pyodbc (Windows) or mdbtools (Linux)."
    )


# ---------------------------------------------------------------------------
# MDB reading functions
# ---------------------------------------------------------------------------

def _get_mdb_tables(mdb_path: str, backend: str) -> list[str]:
    """List all user tables in an MDB file."""
    if backend == "pyodbc":
        import pyodbc
        with pyodbc.connect(
            f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};"
        ) as conn:
            return [t.table_name for t in conn.cursor().tables(tableType="TABLE")]
    else:
        result = subprocess.run(
            ["mdb-tables", "-1", mdb_path],
            capture_output=True, text=True, check=True,
        )
        return [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]


def _get_mdb_columns(mdb_path: str, table_name: str, backend: str) -> list[str]:
    """Get column names for a table in an MDB file."""
    if backend == "pyodbc":
        import pyodbc
        with pyodbc.connect(
            f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};"
        ) as conn:
            return [c.column_name for c in conn.cursor().columns(table=table_name)]
    else:
        result = subprocess.run(
            ["mdb-export", "-H", "-d", "|", mdb_path, table_name],
            capture_output=True, text=True, check=True,
        )
        first_line = result.stdout.split("\n")[0]
        return [c.strip() for c in first_line.split("|")]


def _extract_rows(mdb_path: str, table_name: str, columns: list[str],
                  backend: str) -> list:
    """Extract all rows from an MDB table.

    Args:
        mdb_path: Path to the MDB file.
        table_name: MDB table name.
        columns: Column names to extract.
        backend: 'pyodbc' or 'mdbtools'.

    Returns:
        List of row tuples/lists.
    """
    if backend == "pyodbc":
        import pyodbc
        with pyodbc.connect(
            f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};"
        ) as conn:
            col_list = ", ".join(f"[{c}]" for c in columns)
            cursor = conn.cursor()
            cursor.execute(f"SELECT {col_list} FROM [{table_name}]")
            return cursor.fetchall()
    else:
        result = subprocess.run(
            ["mdb-export", mdb_path, table_name],
            capture_output=True, text=True, check=True,
        )
        reader = csv.DictReader(io.StringIO(result.stdout))
        return [[row.get(c, "") for c in columns] for row in reader]


# ---------------------------------------------------------------------------
# PostgreSQL loading
# ---------------------------------------------------------------------------

def _clean_value(val) -> str:
    """Convert a value to a clean string for PostgreSQL COPY TSV format.

    - None → empty string (treated as NULL by COPY)
    - Escapes backslashes, tabs, newlines (PostgreSQL COPY special chars)
    """
    if val is None:
        return ""
    s = str(val)
    if s in ("None", ""):
        return ""
    return (
        s.replace("\\", "\\\\")
        .replace("\t", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


def _load_rows_to_pg(pg_conn, schema: str, pg_table: str, columns: list[str],
                     rows: list, source_file: str) -> int:
    """Bulk load rows into a PostgreSQL table using COPY.

    Args:
        pg_conn: PostgreSQL connection.
        schema: Target schema (e.g. 'bronze_avall').
        pg_table: Target table name (e.g. 'events').
        columns: MDB column names (will be converted to safe PG names).
        rows: Row data from MDB.
        source_file: Lineage label (e.g. 'avall.mdb').

    Returns:
        Number of rows loaded.

    Raises:
        Exception: On COPY failure (caller handles rollback).
    """
    if not rows:
        return 0

    buf = io.StringIO()
    for row in rows:
        cleaned = [_clean_value(v) for v in row]
        cleaned.append(source_file)
        buf.write("\t".join(cleaned) + "\n")
    buf.seek(0)

    pg_cols = [_safe_col(c) for c in columns] + ["_source_file"]
    col_list = ", ".join(pg_cols)
    full_table = f"{schema}.{pg_table}"

    with pg_conn.cursor() as cursor:
        cursor.copy_expert(
            f"COPY {full_table} ({col_list}) FROM STDIN "
            f"WITH (FORMAT text, DELIMITER E'\\t', NULL '')",
            buf,
        )
    pg_conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Single-source ingestion
# ---------------------------------------------------------------------------

def ingest_mdb(pg_conn, mdb_path: str, source: BronzeSource,
               backend: str) -> dict[str, int]:
    """Ingest all tables from one MDB file into its bronze schema.

    Args:
        pg_conn: PostgreSQL connection.
        mdb_path: Path to the MDB file.
        source: BronzeSource configuration.
        backend: 'pyodbc' or 'mdbtools'.

    Returns:
        Dict of {pg_table_name: rows_loaded} for reporting.
    """
    mdb_tables = _get_mdb_tables(mdb_path, backend)
    logger.info(
        f"Ingesting {source.mdb_filename} → {source.schema}.* "
        f"({len(mdb_tables)} tables)"
    )

    results = {}
    for mdb_table in mdb_tables:
        pg_table = source.table_renames.get(mdb_table, mdb_table.lower())

        try:
            columns = _get_mdb_columns(mdb_path, mdb_table, backend)
            rows = _extract_rows(mdb_path, mdb_table, columns, backend)

            if not rows:
                logger.info(
                    f"  {mdb_table:30s} → {pg_table:30s}   0 rows (empty)"
                )
                results[pg_table] = 0
                continue

            n = _load_rows_to_pg(
                pg_conn, source.schema, pg_table, columns, rows,
                source.mdb_filename,
            )
            results[pg_table] = n
            logger.info(
                f"  {mdb_table:30s} → {pg_table:30s}   {n:>10,} rows"
            )

        except Exception as e:
            logger.error(
                f"  {mdb_table:30s} → {pg_table:30s}   ERROR: {e}"
            )
            pg_conn.rollback()
            results[pg_table] = -1  # -1 signals error

    return results


# ---------------------------------------------------------------------------
# SQL file execution
# ---------------------------------------------------------------------------

def _run_sql_file(pg_conn, sql_path: Path):
    """Execute a SQL file against PostgreSQL."""
    logger.info(f"Executing {sql_path.name}")
    sql = sql_path.read_text(encoding="utf-8")
    with pg_conn.cursor() as cursor:
        cursor.execute(sql)
    pg_conn.commit()


# ---------------------------------------------------------------------------
# Full bronze pipeline
# ---------------------------------------------------------------------------

def run_bronze_ingestion(pg_conn, data_dir: Path, backend: str,
                         mdb_paths: Optional[dict] = None) -> dict:
    """Full bronze layer: create schemas, create tables, ingest all 3 sources.

    Args:
        pg_conn: PostgreSQL connection.
        data_dir: Directory containing MDB files.
        backend: 'pyodbc' or 'mdbtools'.
        mdb_paths: Optional {filename: Path} from download module.

    Returns:
        Dict of {source_label: {table: row_count}} for full audit trail.
    """
    sql_dir = Path(__file__).resolve().parent.parent / "sql" / "bronze"
    if mdb_paths is None:
        mdb_paths = {}

    # Step 1: Create all schemas (bronze_avall, bronze_pre2008, bronze_pre1982, silver, gold)
    _run_sql_file(pg_conn, sql_dir / "001_create_schemas.sql")

    # Step 2-4: Create tables for each source
    all_results = {}
    for source in SOURCES:
        _run_sql_file(pg_conn, sql_dir / source.ddl_file)

    # Step 5-7: Ingest each source
    for source in SOURCES:
        mdb_path = mdb_paths.get(source.mdb_filename, data_dir / source.mdb_filename)

        if not mdb_path.exists():
            logger.warning(f"{source.mdb_filename} not found at {mdb_path}")
            all_results[source.mdb_filename] = {}
            continue

        results = ingest_mdb(pg_conn, str(mdb_path), source, backend)
        all_results[source.mdb_filename] = results

        total = sum(v for v in results.values() if v > 0)
        errors = sum(1 for v in results.values() if v < 0)
        logger.info(f"{source.mdb_filename} total: {total:,} rows ({errors} errors)")

    # Summary
    grand_total = sum(
        v for source_results in all_results.values()
        for v in source_results.values() if v > 0
    )
    total_errors = sum(
        1 for source_results in all_results.values()
        for v in source_results.values() if v < 0
    )
    logger.info(
        f"Bronze ingestion complete: {grand_total:,} rows, "
        f"{total_errors} errors across {len(SOURCES)} sources"
    )

    return all_results
