"""Health check endpoints."""

from fastapi import APIRouter, Depends
from src.api.deps import get_db

router = APIRouter()


@router.get("/ready")
def readiness(conn=Depends(get_db)):
    """Check if database is reachable and has data."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.execute("SELECT COUNT(*) FROM gold.aircraft_risk_profile")
            gold_count = cur.fetchone()[0]
        return {
            "status": "ready",
            "database": "connected",
            "gold_models": gold_count,
        }
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}


@router.get("/live")
def liveness():
    """Simple liveness probe."""
    return {"status": "alive"}
