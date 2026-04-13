"""
Silver and Gold layer transformations.

Executes SQL files from sql/silver/ and sql/gold/ in order.
All transformation logic lives in SQL — this module only orchestrates execution.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def run_sql_file(pg_conn, sql_path: Path):
    """Execute a SQL file against PostgreSQL."""
    logger.info(f"Executing {sql_path.name}")
    sql = sql_path.read_text(encoding="utf-8")
    cursor = pg_conn.cursor()
    cursor.execute(sql)
    pg_conn.commit()


def run_layer(pg_conn, layer: str):
    """Run all SQL files for a layer (silver or gold) in sorted order."""
    sql_dir = Path(__file__).resolve().parent.parent / "sql" / layer
    if not sql_dir.exists():
        logger.warning(f"SQL directory not found: {sql_dir}")
        return

    sql_files = sorted(sql_dir.glob("*.sql"))
    if not sql_files:
        logger.warning(f"No SQL files found in {sql_dir}")
        return

    logger.info(f"Running {layer} layer: {len(sql_files)} SQL files")
    for sql_file in sql_files:
        run_sql_file(pg_conn, sql_file)

    logger.info(f"{layer} layer complete")


def run_silver(pg_conn):
    """Execute all silver layer transformations."""
    run_layer(pg_conn, "silver")


def run_gold(pg_conn):
    """Execute all gold layer transformations."""
    run_layer(pg_conn, "gold")
