"""Data quality check endpoints."""

from fastapi import APIRouter, Depends
from src.api.deps import get_db

router = APIRouter()


@router.get("/bronze")
def bronze_quality(conn=Depends(get_db)):
    """Check bronze layer row counts per schema."""
    results = {}
    schemas = [
        ("bronze_avall", ["events", "aircraft", "narratives", "findings", "engines"]),
        ("bronze_pre2008", ["events", "aircraft", "narratives", "findings", "engines"]),
        ("bronze_pre1982", ["tbl_first_half", "tbl_second_half", "tbl_occurrences"]),
    ]
    for schema, tables in schemas:
        schema_result = {}
        for table in tables:
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
                    schema_result[table] = cur.fetchone()[0]
            except Exception:
                conn.rollback()
                schema_result[table] = "ERROR"
        results[schema] = schema_result
    return results


@router.get("/silver")
def silver_quality(conn=Depends(get_db)):
    """Check silver layer row counts and key metrics."""
    results = {}
    tables = [
        "events_enriched", "aircraft_normalized",
        "findings_enriched", "narrative_analysis",
    ]
    for table in tables:
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM silver.{table}")
                results[table] = cur.fetchone()[0]
        except Exception:
            conn.rollback()
            results[table] = "ERROR"

    # NLP coverage
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM silver.narrative_analysis WHERE n_categories > 0"
            )
            results["nlp_categorized"] = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM silver.narrative_analysis WHERE embedding IS NOT NULL"
            )
            results["has_embeddings"] = cur.fetchone()[0]
    except Exception:
        conn.rollback()

    return results


@router.get("/contracts")
def contract_quality(conn=Depends(get_db)):
    """Validate data contract lookup tables."""
    try:
        from src.contracts import validate_lookups, CONTRACT_VERSION
        passed = validate_lookups(conn)
        return {
            "contract_version": CONTRACT_VERSION,
            "validation": "PASS" if passed else "FAIL",
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/gold")
def gold_quality(conn=Depends(get_db)):
    """Check gold layer completeness."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM gold.aircraft_risk_profile")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT risk_tier, COUNT(*) FROM gold.aircraft_risk_profile "
                "GROUP BY risk_tier ORDER BY risk_tier"
            )
            tiers = dict(cur.fetchall())
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE severity_trend IS NOT NULL"
            )
            has_trend = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE top_failure_1 IS NOT NULL"
            )
            has_failure = cur.fetchone()[0]
        return {
            "total_models": total,
            "risk_tiers": tiers,
            "with_trends": has_trend,
            "with_failures": has_failure,
        }
    except Exception as e:
        return {"error": str(e)}
