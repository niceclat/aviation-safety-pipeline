"""Pipeline execution endpoints."""

import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from src.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

_running = False


@router.post("/run")
def trigger_full_pipeline(background_tasks: BackgroundTasks):
    """Trigger a full pipeline run in the background."""
    global _running
    if _running:
        return {"status": "already_running"}

    background_tasks.add_task(_run_pipeline)
    return {"status": "started", "message": "Pipeline running in background"}


@router.post("/run/{step}")
def trigger_step(step: str, conn=Depends(get_db)):
    """Run a single pipeline step: bronze, contracts, silver, gold, export."""
    valid = {"bronze", "contracts", "silver", "gold", "export"}
    if step not in valid:
        return {"error": f"Invalid step. Choose from: {valid}"}

    try:
        if step == "bronze":
            from src.download import download_ntsb_data
            from src.ingest import run_bronze_ingestion, detect_backend
            from src.config import DATA_DIR
            mdb_paths = download_ntsb_data(DATA_DIR)
            backend = detect_backend()
            results = run_bronze_ingestion(conn, DATA_DIR, backend, mdb_paths)
            total = sum(v for r in results.values() for v in r.values() if v > 0)
            return {"status": "success", "step": step, "rows": total}

        elif step == "contracts":
            from src.contracts import load_lookups_to_pg, validate_lookups
            results = load_lookups_to_pg(conn)
            valid = validate_lookups(conn)
            return {"status": "success", "step": step, "lookups": results, "valid": valid}

        elif step == "silver":
            from src.transform import run_silver
            from src.nlp.pipeline import run_narrative_analysis
            run_silver(conn)
            nlp_count = run_narrative_analysis(conn, enable_embeddings=True)
            return {"status": "success", "step": step, "nlp_narratives": nlp_count}

        elif step == "gold":
            from src.transform import run_gold
            run_gold(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM gold.aircraft_risk_profile")
                count = cur.fetchone()[0]
            return {"status": "success", "step": step, "models": count}

        elif step == "export":
            return {"status": "success", "step": step, "message": "Use /gold endpoints instead"}

    except Exception as e:
        logger.error(f"Step {step} failed: {e}")
        return {"status": "error", "step": step, "error": str(e)}


def _run_pipeline():
    """Background task for full pipeline."""
    global _running
    _running = True
    try:
        import psycopg2
        from src.config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD, DATA_DIR
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASSWORD,
        )
        from src.download import download_ntsb_data
        from src.ingest import run_bronze_ingestion, detect_backend
        from src.contracts import load_lookups_to_pg
        from src.transform import run_silver, run_gold
        from src.nlp.pipeline import run_narrative_analysis

        mdb_paths = download_ntsb_data(DATA_DIR)
        backend = detect_backend()
        run_bronze_ingestion(conn, DATA_DIR, backend, mdb_paths)
        load_lookups_to_pg(conn)
        run_silver(conn)
        run_narrative_analysis(conn, enable_embeddings=True)
        run_gold(conn)
        conn.close()
        logger.info("Background pipeline complete")
    except Exception as e:
        logger.error(f"Background pipeline failed: {e}")
    finally:
        _running = False
