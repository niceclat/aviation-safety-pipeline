"""Semantic search endpoints — powered by pgvector embeddings."""

import logging
from fastapi import APIRouter, Depends
from src.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/similar/{event_id}")
def find_similar(event_id: str, k: int = 10, conn=Depends(get_db)):
    """Find incidents most semantically similar to a given event."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT embedding FROM silver.narrative_analysis "
                "WHERE ev_id = %s AND embedding IS NOT NULL LIMIT 1",
                (event_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"error": f"Event '{event_id}' not found or has no embedding"}

            cur.execute(
                "SELECT na.ev_id, na.primary_category, na.cluster_id, "
                "na.anomaly_score, "
                "1 - (na.embedding <=> seed.embedding) AS similarity "
                "FROM silver.narrative_analysis na, "
                "(SELECT embedding FROM silver.narrative_analysis WHERE ev_id = %s) seed "
                "WHERE na.ev_id != %s AND na.embedding IS NOT NULL "
                "ORDER BY na.embedding <=> seed.embedding LIMIT %s",
                (event_id, event_id, k),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"error": str(e)}


@router.get("/cluster/{cluster_id}")
def cluster_members(cluster_id: int, limit: int = 20, conn=Depends(get_db)):
    """List incidents in a specific FAISS cluster."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT na.ev_id, na.primary_category, na.anomaly_score, "
            "na.text_severity_score, na.narrative_length "
            "FROM silver.narrative_analysis na "
            "WHERE na.cluster_id = %s "
            "ORDER BY na.anomaly_score LIMIT %s",
            (cluster_id, limit),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/anomalies")
def top_anomalies(min_score: float = 0.7, limit: int = 20, conn=Depends(get_db)):
    """Find most anomalous incidents (far from any cluster centroid)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT na.ev_id, na.primary_category, na.cluster_id, "
            "na.anomaly_score, na.text_severity_score "
            "FROM silver.narrative_analysis na "
            "WHERE na.anomaly_score >= %s "
            "ORDER BY na.anomaly_score DESC LIMIT %s",
            (min_score, limit),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/clusters/summary")
def cluster_summary(conn=Depends(get_db)):
    """Summary of all FAISS clusters — size, avg anomaly, top category."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT cluster_id, COUNT(*) as size,
                   ROUND(AVG(anomaly_score)::numeric, 3) as avg_anomaly,
                   MODE() WITHIN GROUP (ORDER BY primary_category) as top_category
            FROM silver.narrative_analysis
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
            ORDER BY size DESC
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
