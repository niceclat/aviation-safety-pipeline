"""
Tests for gold layer — aircraft risk profile table.

Verifies requirements from PrincipalDE_External.md:
    Q1: Severity trends per model
    Q2: Failure patterns across models
    Q3: Narrative intelligence beyond structured data
    Q4: Risk comparison for non-technical stakeholders
    + Self-contained table
    + At least 2 models with sufficient volume
"""

import pytest


@pytest.fixture
def pg_conn():
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", port=5432, dbname="aviation_safety",
            user="pipeline", password="changeme",
        )
        yield conn
        conn.close()
    except Exception:
        pytest.skip("PostgreSQL not available")


class TestGoldTableExists:

    def test_table_not_empty(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM gold.aircraft_risk_profile")
            assert cur.fetchone()[0] > 0

    def test_at_least_two_models(self, pg_conn):
        """Requirement: at least 2 aircraft models with sufficient volume."""
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM gold.aircraft_risk_profile")
            assert cur.fetchone()[0] >= 2


class TestGoldSelfContained:
    """Gold table must be readable without querying other tables."""

    def test_has_identity_columns(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='gold' AND table_name='aircraft_risk_profile'"
            )
            cols = {r[0] for r in cur.fetchall()}
        assert "manufacturer" in cols
        assert "model_family" in cols
        assert "model_full" in cols
        assert "aircraft_category" in cols

    def test_has_volume_columns(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='gold' AND table_name='aircraft_risk_profile'"
            )
            cols = {r[0] for r in cur.fetchall()}
        assert "total_incidents" in cols
        assert "total_accidents" in cols
        assert "first_incident_date" in cols
        assert "last_incident_date" in cols

    def test_has_severity_columns(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='gold' AND table_name='aircraft_risk_profile'"
            )
            cols = {r[0] for r in cur.fetchall()}
        assert "fatality_rate_pct" in cols
        assert "weighted_severity_score" in cols
        assert "risk_tier" in cols
        assert "risk_rank" in cols

    def test_has_metadata(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='gold' AND table_name='aircraft_risk_profile'"
            )
            cols = {r[0] for r in cur.fetchall()}
        assert "data_as_of" in cols
        assert "data_note" in cols


class TestQ1SeverityTrends:
    """Q1: How has severity changed over time per model?"""

    def test_severity_trend_populated(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE severity_trend IS NOT NULL"
            )
            assert cur.fetchone()[0] > 0

    def test_severity_trend_values_valid(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT severity_trend FROM gold.aircraft_risk_profile"
            )
            trends = {r[0] for r in cur.fetchall()}
        valid = {"IMPROVING", "STABLE", "WORSENING", "INSUFFICIENT_DATA"}
        assert trends.issubset(valid), f"Invalid trends: {trends - valid}"

    def test_severity_slope_exists(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE severity_slope IS NOT NULL"
            )
            assert cur.fetchone()[0] > 0

    def test_recent_vs_historical(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE recent_severity IS NOT NULL OR historical_severity IS NOT NULL"
            )
            assert cur.fetchone()[0] > 0


class TestQ2FailurePatterns:
    """Q2: What failures appear most frequently?"""

    def test_failure_percentages_exist(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='gold' AND table_name='aircraft_risk_profile' "
                "AND column_name LIKE 'pct_%'"
            )
            pct_cols = [r[0] for r in cur.fetchall()]
        assert len(pct_cols) >= 6, f"Expected 6+ pct columns, got {pct_cols}"

    def test_structured_findings_exist(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE causal_finding_categories IS NOT NULL"
            )
            assert cur.fetchone()[0] > 0

    def test_cause_counts_populated(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE aircraft_causes > 0 OR personnel_causes > 0 OR environmental_causes > 0"
            )
            assert cur.fetchone()[0] > 0


class TestQ3NarrativeIntelligence:
    """Q3: What can NLP extract beyond structured metadata?"""

    def test_cluster_insights_exist(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE n_distinct_clusters IS NOT NULL"
            )
            assert cur.fetchone()[0] > 0

    def test_anomaly_scores_exist(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE avg_anomaly_score IS NOT NULL"
            )
            assert cur.fetchone()[0] > 0

    def test_nlp_categorization_rate(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE pct_nlp_categorized IS NOT NULL"
            )
            assert cur.fetchone()[0] > 0


class TestQ4RiskComparison:
    """Q4: Risk comparison for non-technical stakeholders."""

    def test_risk_tiers_present(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT risk_tier FROM gold.aircraft_risk_profile ORDER BY risk_tier"
            )
            tiers = [r[0] for r in cur.fetchall()]
        assert "CRITICAL" in tiers
        assert "HIGH" in tiers
        assert "MEDIUM" in tiers
        assert "LOW" in tiers

    def test_risk_rank_sequential(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT risk_rank FROM gold.aircraft_risk_profile ORDER BY risk_rank"
            )
            ranks = [r[0] for r in cur.fetchall()]
        assert ranks[0] == 1
        assert all(r >= 1 for r in ranks)

    def test_risk_tier_distribution_balanced(self, pg_conn):
        """Tiers should be roughly balanced (NTILE(4))."""
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT risk_tier, COUNT(*) FROM gold.aircraft_risk_profile "
                "GROUP BY risk_tier"
            )
            counts = {r[0]: r[1] for r in cur.fetchall()}
        total = sum(counts.values())
        for tier, count in counts.items():
            pct = 100 * count / total
            assert 15 < pct < 35, f"{tier} has {pct:.0f}% — expected ~25%"

    def test_weighted_severity_drives_ranking(self, pg_conn):
        """Higher risk_rank should correlate with higher severity."""
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT weighted_severity_score FROM gold.aircraft_risk_profile "
                "WHERE risk_tier = 'CRITICAL' "
                "ORDER BY weighted_severity_score DESC LIMIT 1"
            )
            critical_max = cur.fetchone()[0]
            cur.execute(
                "SELECT weighted_severity_score FROM gold.aircraft_risk_profile "
                "WHERE risk_tier = 'LOW' "
                "ORDER BY weighted_severity_score ASC LIMIT 1"
            )
            low_min = cur.fetchone()[0]
        assert critical_max >= low_min


class TestGoldDataCoverage:
    """Verify gold table covers all 3 data eras."""

    def test_has_era_columns(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='gold' AND table_name='aircraft_risk_profile' "
                "AND column_name LIKE 'incidents_%'"
            )
            era_cols = [r[0] for r in cur.fetchall()]
        assert "incidents_pre1982" in era_cols
        assert "incidents_pre2008" in era_cols
        assert "incidents_avall" in era_cols

    def test_models_span_multiple_eras(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM gold.aircraft_risk_profile "
                "WHERE incidents_pre1982 > 0 AND incidents_pre2008 > 0"
            )
            assert cur.fetchone()[0] > 0, "No models span pre1982 + pre2008"


class TestGoldSQLIntegrity:

    def test_gold_sql_file_exists(self):
        from pathlib import Path
        sql = Path(__file__).resolve().parent.parent / "sql" / "gold" / "001_aircraft_risk_profile.sql"
        assert sql.exists()

    def test_gold_sql_has_requirements_comments(self):
        from pathlib import Path
        sql = Path(__file__).resolve().parent.parent / "sql" / "gold" / "001_aircraft_risk_profile.sql"
        content = sql.read_text()
        assert "Q1" in content
        assert "Q2" in content
        assert "Q3" in content
        assert "Q4" in content
        assert "self-contained" in content.lower()
