"""
Tests for the REST API endpoints.

Covers:
    - Health checks
    - Gold layer queries (risk profiles, tiers, compare)
    - Silver layer queries (events, aircraft, NLP stats)
    - Bronze layer inspection (schemas, table stats)
    - Semantic search (similar, anomalies, clusters)
    - Governance (runs, lineage, freshness)
    - Quality checks via API
"""

import pytest
from fastapi.testclient import TestClient

try:
    from src.api.app import app
    client = TestClient(app)
    HAS_API = True
except Exception:
    HAS_API = False


@pytest.fixture(autouse=True)
def skip_if_no_api():
    if not HAS_API:
        pytest.skip("API not available")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:

    def test_liveness(self):
        r = client.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    def test_readiness(self):
        r = client.get("/health/ready")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ready"
        assert data["gold_models"] > 0


# ---------------------------------------------------------------------------
# Gold Layer
# ---------------------------------------------------------------------------

class TestGoldAPI:

    def test_list_risk_profiles(self):
        r = client.get("/gold/risk-profiles")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert "model_full" in data[0]
        assert "risk_tier" in data[0]

    def test_filter_by_tier(self):
        r = client.get("/gold/risk-profiles?tier=CRITICAL&limit=5")
        assert r.status_code == 200
        data = r.json()
        assert all(d["risk_tier"] == "CRITICAL" for d in data)

    def test_filter_by_manufacturer(self):
        r = client.get("/gold/risk-profiles?manufacturer=BOEING")
        assert r.status_code == 200
        data = r.json()
        assert all(d["manufacturer"] == "BOEING" for d in data)

    def test_get_single_model(self):
        r = client.get("/gold/risk-profiles/BOEING 737")
        assert r.status_code == 200
        data = r.json()
        assert data["model_full"] == "BOEING 737"
        assert "risk_tier" in data
        assert "severity_trend" in data

    def test_model_not_found(self):
        r = client.get("/gold/risk-profiles/NONEXISTENT 999")
        assert r.status_code == 200
        assert "error" in r.json()

    def test_compare_models(self):
        r = client.get("/gold/compare?models=BOEING 737,BOEING 747")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2

    def test_tier_summary(self):
        r = client.get("/gold/tiers")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 4
        tiers = {d["risk_tier"] for d in data}
        assert tiers == {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


# ---------------------------------------------------------------------------
# Silver Layer
# ---------------------------------------------------------------------------

class TestSilverAPI:

    def test_list_events(self):
        r = client.get("/silver/events?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 5
        assert "ev_id" in data[0]

    def test_filter_events_by_era(self):
        r = client.get("/silver/events?source_era=avall&limit=3")
        assert r.status_code == 200
        data = r.json()
        assert all(d["source_era"] == "avall" for d in data)

    def test_list_aircraft(self):
        r = client.get("/silver/aircraft?manufacturer=BOEING&limit=5")
        assert r.status_code == 200
        data = r.json()
        assert all(d["manufacturer"] == "BOEING" for d in data)

    def test_list_manufacturers(self):
        r = client.get("/silver/manufacturers")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 10
        names = [d["manufacturer"] for d in data]
        assert "BOEING" in names
        assert "CESSNA" in names

    def test_nlp_stats(self):
        r = client.get("/silver/nlp/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_narratives"] > 0
        assert data["clusters"] > 0
        assert len(data["top_categories"]) > 0


# ---------------------------------------------------------------------------
# Bronze Layer
# ---------------------------------------------------------------------------

class TestBronzeAPI:

    def test_list_schemas(self):
        r = client.get("/bronze/schemas")
        assert r.status_code == 200
        data = r.json()
        assert "bronze_avall" in data
        assert "bronze_pre2008" in data
        assert "bronze_pre1982" in data
        assert data["bronze_avall"]["tables"] == 20
        assert data["bronze_pre1982"]["tables"] == 5

    def test_table_stats(self):
        r = client.get("/bronze/bronze_avall/events/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["row_count"] > 25000
        assert data["column_count"] > 50

    def test_inspect_rows(self):
        r = client.get("/bronze/bronze_avall/events?limit=3")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0
        assert len(data["rows"]) == 3

    def test_invalid_schema(self):
        r = client.get("/bronze/invalid_schema/events")
        assert r.status_code == 200
        assert "error" in r.json()


# ---------------------------------------------------------------------------
# Semantic Search
# ---------------------------------------------------------------------------

class TestSearchAPI:

    def test_anomalies(self):
        r = client.get("/search/anomalies?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert all(d["anomaly_score"] >= 0.7 for d in data)

    def test_cluster_summary(self):
        r = client.get("/search/clusters/summary")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 5

    def test_cluster_members(self):
        # Get first cluster from summary
        summary = client.get("/search/clusters/summary").json()
        cluster_id = summary[0]["cluster_id"]
        r = client.get(f"/search/cluster/{cluster_id}?limit=5")
        assert r.status_code == 200
        assert len(r.json()) > 0


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

class TestGovernanceAPI:

    def test_list_runs(self):
        r = client.get("/governance/runs")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert "run_id" in data[0]
        assert "status" in data[0]

    def test_run_steps(self):
        runs = client.get("/governance/runs").json()
        run_id = runs[0]["run_id"]
        r = client.get(f"/governance/runs/{run_id}/steps")
        assert r.status_code == 200

    def test_lineage(self):
        # Get a real event_id from silver
        events = client.get("/silver/events?limit=1").json()
        ev_id = events[0]["ev_id"]
        r = client.get(f"/governance/lineage/{ev_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["event_id"] == ev_id


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

class TestQualityAPI:

    def test_bronze_quality(self):
        r = client.get("/quality/bronze")
        assert r.status_code == 200
        data = r.json()
        assert "bronze_avall" in data

    def test_silver_quality(self):
        r = client.get("/quality/silver")
        assert r.status_code == 200
        data = r.json()
        assert data["events_enriched"] > 0
        assert data["has_embeddings"] > 0

    def test_gold_quality(self):
        r = client.get("/quality/gold")
        assert r.status_code == 200
        data = r.json()
        assert data["total_models"] > 0
        assert "CRITICAL" in data["risk_tiers"]

    def test_contract_quality(self):
        r = client.get("/quality/contracts")
        assert r.status_code == 200
        data = r.json()
        assert data["validation"] == "PASS"


# ---------------------------------------------------------------------------
# Pipeline trigger
# ---------------------------------------------------------------------------

class TestPipelineAPI:

    def test_invalid_step(self):
        r = client.post("/pipeline/run/invalid")
        assert r.status_code == 200
        assert "error" in r.json()
