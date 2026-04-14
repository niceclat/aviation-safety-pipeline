"""Gold layer query endpoints — risk profiles for underwriters."""

from fastapi import APIRouter, Depends, Query
from src.api.deps import get_db

router = APIRouter()


@router.get("/risk-profiles")
def list_risk_profiles(
    tier: str = None,
    manufacturer: str = None,
    min_incidents: int = 10,
    limit: int = 50,
    conn=Depends(get_db),
):
    """List aircraft risk profiles with optional filters."""
    conditions = ["total_incidents >= %s"]
    params = [min_incidents]

    if tier:
        conditions.append("risk_tier = %s")
        params.append(tier.upper())
    if manufacturer:
        conditions.append("UPPER(manufacturer) = %s")
        params.append(manufacturer.upper())

    where = " AND ".join(conditions)
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT model_full, manufacturer, risk_tier, risk_rank, "
            f"total_incidents, fatality_rate_pct, destruction_rate_pct, "
            f"weighted_severity_score, severity_trend, top_failure_1, "
            f"avg_anomaly_score, data_note "
            f"FROM gold.aircraft_risk_profile "
            f"WHERE {where} "
            f"ORDER BY risk_rank LIMIT %s",
            params,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/risk-profiles/{model}")
def get_risk_profile(model: str, conn=Depends(get_db)):
    """Get full risk profile for a specific model."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM gold.aircraft_risk_profile WHERE model_full = %s",
            (model,),
        )
        row = cur.fetchone()
        if not row:
            return {"error": f"Model '{model}' not found"}
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


@router.get("/compare")
def compare_models(
    models: str = Query(..., description="Comma-separated model names"),
    conn=Depends(get_db),
):
    """Compare risk profiles for multiple models side by side."""
    model_list = [m.strip() for m in models.split(",")]
    placeholders = ",".join(["%s"] * len(model_list))

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT model_full, risk_tier, risk_rank, total_incidents, "
            f"fatality_rate_pct, weighted_severity_score, severity_trend, "
            f"top_failure_1, pct_engine_failure, pct_weather_related, pct_human_factor "
            f"FROM gold.aircraft_risk_profile "
            f"WHERE model_full IN ({placeholders}) "
            f"ORDER BY risk_rank",
            model_list,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/tiers")
def tier_summary(conn=Depends(get_db)):
    """Summary statistics per risk tier."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT risk_tier, COUNT(*) as models,
                   ROUND(AVG(total_incidents)) as avg_incidents,
                   ROUND(AVG(fatality_rate_pct)::numeric, 1) as avg_fatality_pct,
                   ROUND(AVG(weighted_severity_score)::numeric, 2) as avg_severity
            FROM gold.aircraft_risk_profile
            GROUP BY risk_tier ORDER BY avg_severity DESC
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
