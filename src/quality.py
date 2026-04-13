"""
Data quality checks for bronze layer ingestion.

Validates that:
1. All expected tables exist in PostgreSQL
2. Row counts match between source MDB and target PostgreSQL
3. Column counts match between source MDB and target PostgreSQL
4. No tables were silently dropped

Reusable — can be called after any bronze ingestion run.
SQL templates loaded from sql/bronze/005_quality_checks.sql.
See docs/DATA_CONTRACT.md for expected table counts.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


# ---------------------------------------------------------------------------
# SQL template loading
# ---------------------------------------------------------------------------

def _load_quality_sql() -> dict[str, str]:
    """Load quality check SQL templates from file."""
    sql_path = SQL_DIR / "bronze" / "005_quality_checks.sql"
    content = sql_path.read_text(encoding="utf-8")

    templates = {}
    current_tag = None
    current_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- TAG:"):
            if current_tag and current_lines:
                templates[current_tag] = "\n".join(current_lines).strip()
            current_tag = stripped.replace("-- TAG:", "").strip()
            current_lines = []
        elif stripped and not stripped.startswith("--"):
            current_lines.append(line)

    if current_tag and current_lines:
        templates[current_tag] = "\n".join(current_lines).strip()

    return templates


# ---------------------------------------------------------------------------
# Quality result model
# ---------------------------------------------------------------------------

@dataclass
class QualityResult:
    """Result of a single table quality check."""
    source: str
    table: str
    pg_table: str
    source_rows: int
    pg_rows: int
    source_cols: int
    pg_cols: int
    rows_match: bool
    cols_match: bool
    status: str  # PASS, FAIL, MISSING


# ---------------------------------------------------------------------------
# PostgreSQL row/column counting (via SQL templates)
# ---------------------------------------------------------------------------

def _count_pg_rows(pg_conn, schema: str, table: str,
                   sql_templates: dict) -> Optional[int]:
    """Count rows in a PostgreSQL table using SQL template."""
    try:
        query = sql_templates["count_pg_rows"].format(schema=schema, table=table)
        with pg_conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchone()[0]
    except Exception:
        pg_conn.rollback()
        return None


def _count_pg_cols(pg_conn, schema: str, table: str,
                   sql_templates: dict) -> int:
    """Count columns in a PostgreSQL table using SQL template."""
    try:
        query = sql_templates["count_pg_columns"]
        query = query.replace(":schema", f"'{schema}'").replace(":table", f"'{table}'")
        with pg_conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchone()[0]
    except Exception:
        pg_conn.rollback()
        return 0


# ---------------------------------------------------------------------------
# MDB row/column counting
# ---------------------------------------------------------------------------

def _count_mdb_rows(mdb_path: str, table: str, backend: str) -> int:
    """Count rows in an MDB table."""
    if backend == "pyodbc":
        import pyodbc
        with pyodbc.connect(
            f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};"
        ) as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM [{table}]")
            return cur.fetchone()[0]
    else:
        import subprocess
        result = subprocess.run(
            ["mdb-count", mdb_path, table],
            capture_output=True, text=True,
        )
        return int(result.stdout.strip()) if result.returncode == 0 else -1


def _count_mdb_cols(mdb_path: str, table: str, backend: str) -> int:
    """Count columns in an MDB table."""
    if backend == "pyodbc":
        import pyodbc
        with pyodbc.connect(
            f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};"
        ) as conn:
            return len([c for c in conn.cursor().columns(table=table)])
    else:
        import subprocess
        result = subprocess.run(
            ["mdb-export", "-H", "-d", "|", mdb_path, table],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return 0
        first_line = result.stdout.split("\n")[0]
        return len([c for c in first_line.split("|") if c.strip()])


# ---------------------------------------------------------------------------
# Validation per source
# ---------------------------------------------------------------------------

def validate_bronze_source(pg_conn, mdb_path: str, schema: str,
                           table_renames: dict, backend: str,
                           source_label: str) -> list[QualityResult]:
    """Validate all tables for a single bronze source.

    Args:
        pg_conn: PostgreSQL connection.
        mdb_path: Path to source MDB file.
        schema: Target PostgreSQL schema.
        table_renames: MDB name -> PG name mapping.
        backend: 'pyodbc' or 'mdbtools'.
        source_label: Human-readable source name.

    Returns:
        List of QualityResult for each table.
    """
    from src.ingest import _get_mdb_tables

    sql_templates = _load_quality_sql()
    results = []
    mdb_tables = _get_mdb_tables(mdb_path, backend)

    for mdb_table in mdb_tables:
        pg_table = table_renames.get(mdb_table, mdb_table.lower())

        try:
            source_rows = _count_mdb_rows(mdb_path, mdb_table, backend)
            source_cols = _count_mdb_cols(mdb_path, mdb_table, backend)
            pg_rows = _count_pg_rows(pg_conn, schema, pg_table, sql_templates)
            pg_cols = _count_pg_cols(pg_conn, schema, pg_table, sql_templates)

            if pg_rows is None:
                status = "MISSING"
                rows_match = False
                cols_match = False
                pg_rows = 0
            else:
                rows_match = source_rows == pg_rows
                cols_match = source_cols == pg_cols
                status = "PASS" if (rows_match and cols_match) else "FAIL"

            results.append(QualityResult(
                source=source_label, table=mdb_table,
                pg_table=f"{schema}.{pg_table}",
                source_rows=source_rows, pg_rows=pg_rows,
                source_cols=source_cols, pg_cols=pg_cols,
                rows_match=rows_match, cols_match=cols_match,
                status=status,
            ))

        except Exception as e:
            logger.error(f"  Quality check failed for {mdb_table}: {e}")
            pg_conn.rollback()
            results.append(QualityResult(
                source=source_label, table=mdb_table,
                pg_table=f"{schema}.{pg_table}",
                source_rows=-1, pg_rows=-1,
                source_cols=-1, pg_cols=-1,
                rows_match=False, cols_match=False,
                status="ERROR",
            ))

    return results


# ---------------------------------------------------------------------------
# Full bronze quality report
# ---------------------------------------------------------------------------

def run_bronze_quality_checks(pg_conn, data_dir: Path, backend: str,
                              mdb_paths: Optional[dict] = None) -> bool:
    """Run quality checks on all 3 bronze sources.

    Args:
        pg_conn: PostgreSQL connection.
        data_dir: Directory containing MDB files.
        backend: 'pyodbc' or 'mdbtools'.
        mdb_paths: Optional {filename: Path} from download module.

    Returns:
        True if all checks pass, False otherwise.
    """
    from src.ingest import SOURCES

    if mdb_paths is None:
        mdb_paths = {}

    logger.info("=" * 70)
    logger.info("  BRONZE DATA QUALITY CHECKS")
    logger.info("=" * 70)

    all_pass = True
    total_tables = 0
    total_pass = 0
    total_fail = 0
    total_missing = 0

    for source in SOURCES:
        mdb_path = mdb_paths.get(source.mdb_filename, data_dir / source.mdb_filename)
        if not mdb_path.exists():
            logger.warning(f"  SKIP: {source.mdb_filename} not found")
            continue

        results = validate_bronze_source(
            pg_conn, str(mdb_path), source.schema,
            source.table_renames, backend, source.mdb_filename,
        )

        logger.info(f"\n  {source.mdb_filename} -> {source.schema}")
        logger.info(
            f"  {'MDB Table':<30s} {'PG Table':<35s} "
            f"{'Src Rows':>10s} {'PG Rows':>10s} {'Cols':>7s} {'Status'}"
        )
        logger.info(f"  {'-'*30} {'-'*35} {'-'*10} {'-'*10} {'-'*7} {'-'*7}")

        for r in results:
            col_note = f"{r.source_cols}/{r.pg_cols}"
            logger.info(
                f"  {r.table:<30s} {r.pg_table:<35s} "
                f"{r.source_rows:>10,} {r.pg_rows:>10,} {col_note:>7s} {r.status}"
            )
            total_tables += 1
            if r.status == "PASS":
                total_pass += 1
            elif r.status in ("FAIL", "ERROR"):
                total_fail += 1
                all_pass = False
                if not r.rows_match and r.status != "ERROR":
                    logger.warning(
                        f"    ROW MISMATCH: source={r.source_rows:,} "
                        f"pg={r.pg_rows:,} (diff={r.source_rows - r.pg_rows:,})"
                    )
                if not r.cols_match and r.status != "ERROR":
                    logger.warning(
                        f"    COL MISMATCH: source={r.source_cols} pg={r.pg_cols}"
                    )
            elif r.status == "MISSING":
                total_missing += 1
                all_pass = False

    logger.info(f"\n  SUMMARY: {total_tables} tables checked")
    logger.info(f"    PASS:    {total_pass}")
    logger.info(f"    FAIL:    {total_fail}")
    logger.info(f"    MISSING: {total_missing}")
    logger.info(f"    RESULT:  {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")

    return all_pass
