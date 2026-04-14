"""
End-to-end pipeline orchestrator.

Modular execution — each layer runs independently:
    python src/pipeline.py                  # Full pipeline
    python src/pipeline.py --bronze         # Download + ingest only
    python src/pipeline.py --contracts      # Load contract lookups only
    python src/pipeline.py --silver         # Silver transforms + NLP only
    python src/pipeline.py --gold           # Gold risk profile only
    python src/pipeline.py --export         # Export CSVs only
    python src/pipeline.py --quality        # Quality checks only
"""

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD, DATA_DIR, OUTPUT_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pipeline")

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def get_pg_connection():
    """Create PostgreSQL connection with retry."""
    retries = 3
    for attempt in range(retries):
        try:
            conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, dbname=PG_DB,
                user=PG_USER, password=PG_PASSWORD,
                connect_timeout=10,
            )
            return conn
        except psycopg2.OperationalError as e:
            if attempt < retries - 1:
                logger.warning(f"Connection attempt {attempt+1} failed, retrying...")
                time.sleep(2)
            else:
                raise


def _parse_export_sql() -> dict:
    """Parse sql/exports.sql into {filename: query} pairs."""
    sql_path = SQL_DIR / "exports.sql"
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


def run_bronze(conn):
    """Step 1: Download NTSB data and ingest into bronze schemas."""
    from src.download import download_ntsb_data
    from src.ingest import run_bronze_ingestion, detect_backend

    logger.info("--- STEP 1: DOWNLOAD ---")
    t0 = time.time()
    mdb_paths = download_ntsb_data(DATA_DIR)
    logger.info(f"Download complete in {time.time()-t0:.1f}s")

    logger.info("--- STEP 2: BRONZE INGESTION ---")
    t0 = time.time()
    backend = detect_backend()
    logger.info(f"MDB backend: {backend}")
    run_bronze_ingestion(conn, DATA_DIR, backend, mdb_paths)
    logger.info(f"Bronze complete in {time.time()-t0:.1f}s")


def run_contracts(conn):
    """Step 3: Load data contract lookup tables."""
    from src.contracts import load_lookups_to_pg, validate_lookups

    logger.info("--- STEP 3: DATA CONTRACTS ---")
    t0 = time.time()
    load_lookups_to_pg(conn)
    passed = validate_lookups(conn)
    if not passed:
        raise RuntimeError("Contract validation failed")
    logger.info(f"Contracts loaded and validated in {time.time()-t0:.1f}s")


def run_silver(conn):
    """Step 4: Silver transforms + NLP."""
    from src.transform import run_silver as _run_silver
    from src.nlp.pipeline import run_narrative_analysis

    logger.info("--- STEP 4: SILVER TRANSFORMS ---")
    t0 = time.time()
    _run_silver(conn)
    logger.info(f"Silver SQL complete in {time.time()-t0:.1f}s")

    logger.info("--- STEP 5: NLP ANALYSIS ---")
    t0 = time.time()
    run_narrative_analysis(conn, enable_embeddings=True)
    logger.info(f"NLP complete in {time.time()-t0:.1f}s")


def run_gold(conn):
    """Step 6: Gold risk profile table."""
    from src.transform import run_gold as _run_gold

    logger.info("--- STEP 6: GOLD LAYER ---")
    t0 = time.time()
    _run_gold(conn)
    logger.info(f"Gold complete in {time.time()-t0:.1f}s")


def run_quality(conn):
    """Step 7: Quality checks."""
    from src.quality import run_bronze_quality_checks
    from src.contracts import validate_lookups
    from src.ingest import detect_backend

    logger.info("--- STEP 7: QUALITY CHECKS ---")
    backend = detect_backend()

    logger.info("Bronze quality:")
    bronze_ok = run_bronze_quality_checks(conn, DATA_DIR, backend)

    logger.info("Contract quality:")
    contract_ok = validate_lookups(conn)

    if bronze_ok and contract_ok:
        logger.info("ALL QUALITY CHECKS PASSED")
    else:
        logger.error("QUALITY CHECKS FAILED")


def run_export(conn):
    """Step 8: Export CSVs."""
    logger.info("--- STEP 8: EXPORT CSVs ---")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    exports = _parse_export_sql()
    for filename, query in exports.items():
        filepath = OUTPUT_DIR / filename
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)

            logger.info(f"  {filepath.name}: {len(rows)} rows")
        except Exception as e:
            logger.error(f"  Failed {filename}: {e}")
            conn.rollback()


def main():
    parser = argparse.ArgumentParser(description="Aviation Safety Pipeline")
    parser.add_argument("--bronze", action="store_true", help="Download + bronze ingestion")
    parser.add_argument("--contracts", action="store_true", help="Load contract lookups")
    parser.add_argument("--silver", action="store_true", help="Silver transforms + NLP")
    parser.add_argument("--gold", action="store_true", help="Gold risk profile")
    parser.add_argument("--export", action="store_true", help="Export CSVs")
    parser.add_argument("--quality", action="store_true", help="Quality checks")
    args = parser.parse_args()

    run_all = not any([args.bronze, args.contracts, args.silver, args.gold, args.export, args.quality])

    logger.info("=" * 60)
    logger.info("  Aviation Safety Pipeline")
    logger.info("=" * 60)
    start = time.time()

    conn = get_pg_connection()
    logger.info(f"Connected to {PG_HOST}:{PG_PORT}/{PG_DB}")

    try:
        if run_all or args.bronze:
            run_bronze(conn)
        if run_all or args.contracts:
            run_contracts(conn)
        if run_all or args.silver:
            run_silver(conn)
        if run_all or args.gold:
            run_gold(conn)
        if run_all or args.export:
            run_export(conn)
        if args.quality:
            run_quality(conn)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"  Pipeline complete in {elapsed:.1f}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
