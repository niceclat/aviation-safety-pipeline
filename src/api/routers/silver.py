"""Silver layer inspection and NLP endpoints."""

from fastapi import APIRouter, Depends, Query
from src.api.deps import get_db

router = APIRouter()


@router.get("/events")
def list_events(
    source_era: str = None,
    min_year: int = None,
    max_year: int = None,
    injury: str = None,
    limit: int = 20,
    conn=Depends(get_db),
):
    """Query unified events with filters."""
    conditions = ["1=1"]
    params = []

    if source_era:
        conditions.append("source_era = %s")
        params.append(source_era)
    if min_year:
        conditions.append("event_year >= %s")
        params.append(min_year)
    if max_year:
        conditions.append("event_year <= %s")
        params.append(max_year)
    if injury:
        conditions.append("ev_highest_injury = %s")
        params.append(injury.upper())

    where = " AND ".join(conditions)
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT ev_id, ev_type, ev_date, event_year, ev_city, ev_state, "
            f"ev_highest_injury, fatalities, serious_injuries, injury_score, "
            f"weather_category, source_era "
            f"FROM silver.events_enriched WHERE {where} "
            f"ORDER BY ev_date DESC LIMIT %s",
            params,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/aircraft")
def list_aircraft(
    manufacturer: str = None,
    model_family: str = None,
    far_part: str = None,
    limit: int = 20,
    conn=Depends(get_db),
):
    """Query normalized aircraft with filters."""
    conditions = ["1=1"]
    params = []

    if manufacturer:
        conditions.append("UPPER(manufacturer) = %s")
        params.append(manufacturer.upper())
    if model_family:
        conditions.append("UPPER(model_family) = %s")
        params.append(model_family.upper())
    if far_part:
        conditions.append("far_part = %s")
        params.append(far_part)

    where = " AND ".join(conditions)
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT ev_id, manufacturer, model_family, model_full, far_part, "
            f"damage, damage_score, make_raw, model_raw, source_era "
            f"FROM silver.aircraft_normalized WHERE {where} "
            f"ORDER BY ev_id LIMIT %s",
            params,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/manufacturers")
def list_manufacturers(conn=Depends(get_db)):
    """List all canonical manufacturers with counts."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT manufacturer, COUNT(*) as incidents "
            "FROM silver.aircraft_normalized "
            "GROUP BY manufacturer ORDER BY incidents DESC"
        )
        return [{"manufacturer": r[0], "incidents": r[1]} for r in cur.fetchall()]


@router.get("/narratives/{event_id}")
def get_narrative(event_id: str, conn=Depends(get_db)):
    """Get NLP analysis for a specific event."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ev_id, failure_categories, primary_category, n_categories, "
            "text_severity_score, has_engine_failure, has_weather_factor, "
            "has_human_factors, has_fire, has_structural, has_maintenance, "
            "narrative_length, cluster_id, anomaly_score "
            "FROM silver.narrative_analysis WHERE ev_id = %s",
            (event_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"error": f"Event '{event_id}' not found"}
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


@router.get("/nlp/stats")
def nlp_stats(conn=Depends(get_db)):
    """NLP analysis summary statistics."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis WHERE n_categories > 0")
        categorized = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT cluster_id) FROM silver.narrative_analysis")
        clusters = cur.fetchone()[0]
        cur.execute(
            "SELECT primary_category, COUNT(*) "
            "FROM silver.narrative_analysis "
            "WHERE primary_category IS NOT NULL "
            "GROUP BY primary_category ORDER BY COUNT(*) DESC"
        )
        categories = [{"category": r[0], "count": r[1]} for r in cur.fetchall()]
    return {
        "total_narratives": total,
        "categorized": categorized,
        "categorization_rate": round(100 * categorized / total, 1) if total else 0,
        "clusters": clusters,
        "top_categories": categories,
    }
