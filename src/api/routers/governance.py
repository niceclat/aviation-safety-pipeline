"""Governance endpoints — run history, lineage, freshness."""

from fastapi import APIRouter, Depends
from src.api.deps import get_db

router = APIRouter()


@router.get("/runs")
def list_runs(limit: int = 10, conn=Depends(get_db)):
    """List recent pipeline runs."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT run_id, started_at, completed_at, status, duration_secs, "
            "bronze_rows, silver_rows, gold_rows, nlp_rows, contract_version "
            "FROM governance.pipeline_runs ORDER BY run_id DESC LIMIT %s",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/runs/{run_id}/steps")
def run_steps(run_id: int, conn=Depends(get_db)):
    """List steps for a specific pipeline run."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT step_name, status, duration_secs, rows_affected, error_message "
            "FROM governance.pipeline_steps WHERE run_id = %s ORDER BY step_id",
            (run_id,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/freshness")
def table_freshness(conn=Depends(get_db)):
    """Check when each table was last refreshed."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT schema_name, table_name, last_refreshed, row_count, run_id "
                "FROM governance.table_freshness ORDER BY last_refreshed DESC"
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        conn.rollback()
        return []


@router.get("/lineage/{event_id}")
def event_lineage(event_id: str, conn=Depends(get_db)):
    """Trace lineage for a specific event across all layers."""
    lineage = {"event_id": event_id}

    # Bronze
    for schema in ["bronze_avall", "bronze_pre2008"]:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT _source_file, _ingested_at FROM {schema}.events "
                    f"WHERE ev_id = %s LIMIT 1",
                    (event_id,),
                )
                row = cur.fetchone()
                if row:
                    lineage["bronze"] = {
                        "schema": schema,
                        "source_file": row[0],
                        "ingested_at": str(row[1]),
                    }
        except Exception:
            conn.rollback()

    # PRE1982
    if event_id.startswith("PRE1982_"):
        recnum = event_id.replace("PRE1982_", "")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT _source_file, _ingested_at FROM bronze_pre1982.tbl_first_half "
                    "WHERE recnum = %s LIMIT 1",
                    (recnum,),
                )
                row = cur.fetchone()
                if row:
                    lineage["bronze"] = {
                        "schema": "bronze_pre1982",
                        "source_file": row[0],
                        "ingested_at": str(row[1]),
                    }
        except Exception:
            conn.rollback()

    # Silver
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_era, event_year, ev_highest_injury, injury_score "
                "FROM silver.events_enriched WHERE ev_id = %s LIMIT 1",
                (event_id,),
            )
            row = cur.fetchone()
            if row:
                lineage["silver_event"] = {
                    "source_era": row[0], "year": row[1],
                    "highest_injury": row[2], "injury_score": row[3],
                }
    except Exception:
        conn.rollback()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT manufacturer, model_family, model_full, far_part "
                "FROM silver.aircraft_normalized WHERE ev_id = %s",
                (event_id,),
            )
            rows = cur.fetchall()
            if rows:
                lineage["silver_aircraft"] = [
                    {"manufacturer": r[0], "model_family": r[1],
                     "model_full": r[2], "far_part": r[3]}
                    for r in rows
                ]
    except Exception:
        conn.rollback()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT primary_category, cluster_id, anomaly_score, n_categories "
                "FROM silver.narrative_analysis WHERE ev_id = %s",
                (event_id,),
            )
            rows = cur.fetchall()
            if rows:
                lineage["silver_nlp"] = [
                    {"category": r[0], "cluster_id": r[1],
                     "anomaly_score": float(r[2]) if r[2] else None,
                     "n_categories": r[3]}
                    for r in rows
                ]
    except Exception:
        conn.rollback()

    return lineage
