"""
End-to-end pipeline orchestrator.

Usage:
    python src/pipeline.py              # Run full pipeline
    python src/pipeline.py --bronze     # Run bronze only
    python src/pipeline.py --silver     # Run silver only
    python src/pipeline.py --gold       # Run gold only
    python src/pipeline.py --export     # Export CSVs only
"""

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

import psycopg2

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD, DATA_DIR, OUTPUT_DIR
from src.download import download_ntsb_data
from src.ingest import run_bronze_ingestion, detect_backend
from src.transform import run_silver, run_gold
from src.nlp import run_narrative_analysis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pipeline")


def get_pg_connection():
    """Create PostgreSQL connection."""
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )


def _parse_export_sql() -> dict:
    """Parse sql/exports.sql into {filename: query} pairs."""
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "exports.sql"
    content = sql_path.read_text(encoding="utf-8")
    exports = {}
    current_file = None
    current_lines = []
    for line in content.splitlines():
        if line.strip().startswith("-- FILE:"):
            if current_file and current_lines:
                exports[current_file] = "\n".join(current_lines).strip()
            current_file = line.strip().replace("-- FILE:", "").strip()
            current_lines = []
        elif not line.strip().startswith("--") and line.strip():
            current_lines.append(line)
    if current_file and current_lines:
        exports[current_file] = "\n".join(current_lines).strip()
    return exports


def export_csvs(pg_conn):
    """Export sample outputs from each layer to CSV files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    exports = _parse_export_sql()

    for filename, query in exports.items():
        filepath = OUTPUT_DIR / filename
        try:
            cursor = pg_conn.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)

            logger.info(f"Exported {filepath.name}: {len(rows)} rows")
        except Exception as e:
            logger.error(f"Failed to export {filename}: {e}")
            pg_conn.rollback()


def main():
    parser = argparse.ArgumentParser(description="Aviation Safety Pipeline")
    parser.add_argument("--bronze", action="store_true", help="Run bronze layer only")
    parser.add_argument("--silver", action="store_true", help="Run silver layer only")
    parser.add_argument("--gold", action="store_true", help="Run gold layer only")
    parser.add_argument("--export", action="store_true", help="Export CSVs only")
    args = parser.parse_args()

    run_all = not (args.bronze or args.silver or args.gold or args.export)

    logger.info("=" * 60)
    logger.info("Aviation Safety Pipeline — Starting")
    logger.info("=" * 60)
    start = time.time()

    conn = get_pg_connection()
    logger.info(f"Connected to PostgreSQL at {PG_HOST}:{PG_PORT}/{PG_DB}")

    try:
        if run_all or args.bronze:
            # Step 1: Download data from NTSB (skips if already present)
            logger.info("--- DOWNLOADING NTSB DATA ---")
            t0 = time.time()
            mdb_paths = download_ntsb_data(DATA_DIR)
            logger.info(f"Download complete in {time.time()-t0:.1f}s")

            # Step 2: Ingest into bronze
            logger.info("--- BRONZE LAYER ---")
            t0 = time.time()
            backend = detect_backend()
            logger.info(f"MDB backend: {backend}")
            run_bronze_ingestion(conn, DATA_DIR, backend, mdb_paths)
            logger.info(f"Bronze complete in {time.time()-t0:.1f}s")

        if run_all or args.silver:
            logger.info("--- SILVER LAYER ---")
            t0 = time.time()
            run_silver(conn)
            run_narrative_analysis(conn)
            logger.info(f"Silver complete in {time.time()-t0:.1f}s")

        if run_all or args.gold:
            logger.info("--- GOLD LAYER ---")
            t0 = time.time()
            run_gold(conn)
            logger.info(f"Gold complete in {time.time()-t0:.1f}s")

        if run_all or args.export:
            logger.info("--- EXPORTING CSVs ---")
            export_csvs(conn)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"Pipeline complete in {elapsed:.1f}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
