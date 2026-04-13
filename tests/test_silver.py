"""
Tests for silver layer — unified canonical model and NLP analysis.

Covers:
    - Silver table existence and row counts
    - Source era tags (all 3 sources represented)
    - Canonical field types and values
    - Manufacturer normalization results
    - Severity scoring consistency
    - NLP regex categorizer (unit tests)
    - NLP embedding analyzer (unit tests)
    - Narrative analysis output (integration)
"""

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# NLP regex categorizer unit tests
# ---------------------------------------------------------------------------

class TestRegexCategorizer:

    def test_import(self):
        from src.nlp.regex_categorizer import categorize, get_categories, get_pattern_count
        assert callable(categorize)

    def test_categories_list(self):
        from src.nlp.regex_categorizer import get_categories
        cats = get_categories()
        assert len(cats) == 11
        assert "engine_failure" in cats
        assert "weather" in cats
        assert "human_factors" in cats
        assert "fire" in cats

    def test_pattern_count(self):
        from src.nlp.regex_categorizer import get_pattern_count
        assert get_pattern_count() > 30

    def test_engine_failure_detected(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Total loss of engine power due to mechanical failure")
        assert "engine_failure" in result.categories
        assert result.has_engine_failure is True

    def test_weather_detected(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Flight into instrument meteorological conditions")
        assert "weather" in result.categories
        assert result.has_weather_factor is True

    def test_human_factors_detected(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Pilot's failure to maintain adequate airspeed resulting in loss of control")
        assert "human_factors" in result.categories
        assert result.has_human_factors is True

    def test_multiple_categories(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Engine failure followed by in-flight fire and pilot disorientation")
        assert result.n_categories >= 3
        assert "engine_failure" in result.categories
        assert "fire" in result.categories
        assert "human_factors" in result.categories

    def test_no_match(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Normal landing at airport")
        assert result.n_categories == 0
        assert result.primary_category is None

    def test_empty_text(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("")
        assert result.n_categories == 0
        assert result.severity_score == 0

    def test_none_text(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize(None)
        assert result.n_categories == 0

    def test_severity_fatal(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("The pilot was fatally injured")
        assert result.severity_score == 5

    def test_severity_destroyed(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("The aircraft was destroyed on impact")
        assert result.severity_score == 4

    def test_severity_serious(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("One passenger sustained serious injuries")
        assert result.severity_score == 3

    def test_severity_minor(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Minor damage to the left wing")
        assert result.severity_score == 2

    def test_severity_baseline(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Normal approach and landing at the airport")
        assert result.severity_score == 1

    def test_result_is_frozen(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Engine failure")
        with pytest.raises(AttributeError):
            result.severity_score = 99

    def test_fuel_related(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Fuel exhaustion due to improper fuel management")
        assert "fuel_related" in result.categories

    def test_bird_strike(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("The aircraft struck a bird during initial climb")
        assert "bird_strike" in result.categories

    def test_structural(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Structural fatigue crack in the wing spar")
        assert "structural" in result.categories
        assert result.has_structural is True

    def test_maintenance(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Improper maintenance of the fuel system")
        assert "maintenance" in result.categories
        assert result.has_maintenance is True

    def test_landing_gear(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("The nose gear collapsed on landing")
        assert "landing_gear" in result.categories

    def test_hydraulic(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Complete hydraulic system failure")
        assert "hydraulic" in result.categories

    def test_electrical(self):
        from src.nlp.regex_categorizer import categorize
        result = categorize("Electrical system failure causing battery fire")
        assert "electrical" in result.categories


# ---------------------------------------------------------------------------
# NLP embedding analyzer unit tests
# ---------------------------------------------------------------------------

class TestEmbeddingAnalyzer:

    def test_import(self):
        from src.nlp.embedding_analyzer import generate_embeddings, cluster_embeddings
        assert callable(generate_embeddings)
        assert callable(cluster_embeddings)

    def test_embedding_dim_constant(self):
        from src.nlp.embedding_analyzer import EMBEDDING_DIM
        assert EMBEDDING_DIM == 384

    @pytest.mark.slow
    def test_generate_embeddings_shape(self):
        from src.nlp.embedding_analyzer import generate_embeddings, EMBEDDING_DIM
        texts = ["engine failure", "bird strike", "pilot error"]
        emb = generate_embeddings(texts)
        assert emb.shape == (3, EMBEDDING_DIM)

    @pytest.mark.slow
    def test_embeddings_normalized(self):
        import numpy as np
        from src.nlp.embedding_analyzer import generate_embeddings
        emb = generate_embeddings(["test sentence"])
        norm = np.linalg.norm(emb[0])
        assert abs(norm - 1.0) < 0.01, f"Embedding not normalized: norm={norm}"

    @pytest.mark.slow
    def test_cluster_embeddings(self):
        import numpy as np
        from src.nlp.embedding_analyzer import generate_embeddings, cluster_embeddings
        texts = ["engine failure"] * 10 + ["bird strike"] * 10 + ["pilot error"] * 10
        emb = generate_embeddings(texts)
        result = cluster_embeddings(emb, n_clusters=3)
        assert result.n_clusters == 3
        assert len(result.cluster_ids) == 30
        assert len(result.anomaly_scores) == 30
        assert result.centroids.shape == (3, 384)

    @pytest.mark.slow
    def test_faiss_index_search(self):
        import numpy as np
        from src.nlp.embedding_analyzer import generate_embeddings, build_faiss_index, search_similar
        texts = ["engine failure during cruise", "bird strike on takeoff", "hydraulic leak"]
        emb = generate_embeddings(texts)
        index = build_faiss_index(emb)
        scores, indices = search_similar(index, emb[0], k=2)
        assert indices[0] == 0  # most similar to itself
        assert len(scores) == 2


# ---------------------------------------------------------------------------
# NLP pipeline module
# ---------------------------------------------------------------------------

class TestNLPPipeline:

    def test_import(self):
        from src.nlp.pipeline import run_narrative_analysis
        assert callable(run_narrative_analysis)

    def test_combine_text(self):
        from src.nlp.pipeline import _combine_text
        assert _combine_text("factual", "cause") == "cause factual"
        assert _combine_text(None, "cause") == "cause"
        assert _combine_text("factual", None) == "factual"
        assert _combine_text(None, None) == ""
        assert _combine_text("import", None) == ""
        assert _combine_text("None", "None") == ""


# ---------------------------------------------------------------------------
# SQL file integrity
# ---------------------------------------------------------------------------

class TestSilverSQLFiles:

    def test_all_silver_sql_files_exist(self):
        sql_dir = Path(__file__).resolve().parent.parent / "sql" / "silver"
        expected = [
            "000_canonical_schema.sql",
            "000_validate_lookups.sql",
            "001_events_enriched.sql",
            "002_aircraft_normalized.sql",
            "003_findings_enriched.sql",
            "004_narrative_analysis_schema.sql",
            "005_narrative_select.sql",
        ]
        for f in expected:
            assert (sql_dir / f).exists(), f"Missing: {f}"

    def test_sql_files_not_empty(self):
        sql_dir = Path(__file__).resolve().parent.parent / "sql" / "silver"
        for sql_file in sql_dir.glob("*.sql"):
            content = sql_file.read_text(encoding="utf-8")
            assert len(content) > 10, f"{sql_file.name} is empty"

    def test_narrative_schema_has_vector(self):
        sql_dir = Path(__file__).resolve().parent.parent / "sql" / "silver"
        content = (sql_dir / "004_narrative_analysis_schema.sql").read_text()
        assert "vector(384)" in content
        assert "cluster_id" in content
        assert "anomaly_score" in content
        assert "pgvector" in content.lower() or "vector" in content.lower()


# ---------------------------------------------------------------------------
# PostgreSQL integration tests (require running database + silver data)
# ---------------------------------------------------------------------------

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


class TestSilverEventsIntegration:

    def test_events_table_exists(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM silver.events_enriched")
            assert cur.fetchone()[0] > 0

    def test_all_three_eras_present(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT DISTINCT source_era FROM silver.events_enriched ORDER BY source_era")
            eras = [r[0] for r in cur.fetchall()]
        assert "avall" in eras
        assert "pre2008" in eras
        assert "pre1982" in eras

    def test_event_count_reasonable(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM silver.events_enriched")
            total = cur.fetchone()[0]
        assert total > 150000, f"Expected 150K+ events, got {total}"

    def test_injury_scores_valid(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT DISTINCT injury_score FROM silver.events_enriched ORDER BY injury_score")
            scores = [r[0] for r in cur.fetchall()]
        assert all(s in (0, 1, 2, 3, 4) for s in scores)


class TestSilverAircraftIntegration:

    def test_aircraft_table_exists(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM silver.aircraft_normalized")
            assert cur.fetchone()[0] > 0

    def test_commercial_only(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT DISTINCT far_part FROM silver.aircraft_normalized")
            parts = [r[0] for r in cur.fetchall()]
        assert all(p in ("121", "135") for p in parts)

    def test_manufacturer_normalized(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT DISTINCT manufacturer FROM silver.aircraft_normalized")
            mfrs = [r[0] for r in cur.fetchall()]
        assert "BOEING" in mfrs
        # No raw variants should appear
        assert "Boeing" not in mfrs
        assert "boeing" not in mfrs
        assert "MCDONNELL DOUGLAS" in mfrs
        assert "DOUGLAS" not in mfrs

    def test_all_three_eras(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT DISTINCT source_era FROM silver.aircraft_normalized ORDER BY source_era")
            eras = [r[0] for r in cur.fetchall()]
        assert len(eras) == 3


class TestSilverFindingsIntegration:

    def test_findings_table_exists(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM silver.findings_enriched")
            assert cur.fetchone()[0] > 0

    def test_three_code_systems(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT DISTINCT findings_system FROM silver.findings_enriched ORDER BY findings_system")
            systems = [r[0] for r in cur.fetchall()]
        assert len(systems) == 3


class TestSilverNarrativeIntegration:

    def test_narrative_table_exists(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis")
            assert cur.fetchone()[0] > 0

    def test_has_clusters(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT cluster_id) FROM silver.narrative_analysis WHERE cluster_id IS NOT NULL")
            n_clusters = cur.fetchone()[0]
        assert n_clusters > 5, f"Expected multiple clusters, got {n_clusters}"

    def test_has_embeddings(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis WHERE embedding IS NOT NULL")
            count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis")
            total = cur.fetchone()[0]
        assert count == total, f"Missing embeddings: {count}/{total}"

    def test_anomaly_scores_range(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT MIN(anomaly_score), MAX(anomaly_score) FROM silver.narrative_analysis")
            mn, mx = cur.fetchone()
        assert mn >= 0.0
        assert mx <= 1.0

    def test_regex_categories_populated(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis WHERE n_categories > 0")
            categorized = cur.fetchone()[0]
        assert categorized > 0
