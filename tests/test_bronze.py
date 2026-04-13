"""
Tests for bronze layer — ingestion and quality validation.

Covers:
    - Backend detection
    - MDB reading functions
    - Data cleaning
    - PostgreSQL loading
    - Quality check framework
    - End-to-end bronze ingestion verification (requires PostgreSQL + MDB data)
"""

import pytest
from pathlib import Path

from src.ingest import (
    detect_backend,
    _safe_col,
    _clean_value,
    _PG_RESERVED,
    SOURCES,
)


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

class TestDetectBackend:

    def test_returns_string(self):
        backend = detect_backend()
        assert backend in ("pyodbc", "mdbtools")

    def test_pyodbc_on_windows(self):
        import platform
        if platform.system() == "Windows":
            assert detect_backend() == "pyodbc"


# ---------------------------------------------------------------------------
# Column name safety
# ---------------------------------------------------------------------------

class TestSafeCol:

    def test_lowercase(self):
        assert _safe_col("MyColumn") == "mycolumn"

    def test_spaces_to_underscores(self):
        assert _safe_col("My Column") == "my_column"

    def test_slashes_to_underscores(self):
        assert _safe_col("Data/Type") == "data_type"

    def test_reserved_word_quoted(self):
        assert _safe_col("table") == '"column_table"'
        assert _safe_col("Table") == '"column_table"'
        assert _safe_col("column") == '"column_column"'
        assert _safe_col("name") == '"column_name"'
        assert _safe_col("order") == '"column_order"'
        assert _safe_col("type") == '"column_type"'

    def test_non_reserved_not_quoted(self):
        assert _safe_col("ev_id") == "ev_id"
        assert _safe_col("acft_make") == "acft_make"
        assert _safe_col("Aircraft_Key") == "aircraft_key"

    def test_all_reserved_words_are_handled(self):
        for word in _PG_RESERVED:
            result = _safe_col(word)
            assert result.startswith('"column_'), f"Reserved word '{word}' not quoted"


# ---------------------------------------------------------------------------
# Value cleaning
# ---------------------------------------------------------------------------

class TestCleanValue:

    def test_none_returns_empty(self):
        assert _clean_value(None) == ""

    def test_none_string_returns_empty(self):
        assert _clean_value("None") == ""

    def test_empty_returns_empty(self):
        assert _clean_value("") == ""

    def test_normal_string(self):
        assert _clean_value("hello") == "hello"

    def test_strips_whitespace(self):
        assert _clean_value("  hello  ") == "hello"

    def test_tabs_replaced(self):
        assert "\t" not in _clean_value("hello\tworld")

    def test_newlines_replaced(self):
        assert "\n" not in _clean_value("hello\nworld")
        assert "\r" not in _clean_value("hello\rworld")

    def test_backslashes_escaped(self):
        result = _clean_value("path\\to\\file")
        assert "\\\\" in result

    def test_numeric_values(self):
        assert _clean_value(42) == "42"
        assert _clean_value(3.14) == "3.14"

    def test_datetime_values(self):
        from datetime import datetime
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = _clean_value(dt)
        assert "2024" in result


# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------

class TestSourceDefinitions:

    def test_three_sources_defined(self):
        assert len(SOURCES) == 3

    def test_source_schemas_unique(self):
        schemas = [s.schema for s in SOURCES]
        assert len(schemas) == len(set(schemas))

    def test_source_filenames_unique(self):
        filenames = [s.mdb_filename for s in SOURCES]
        assert len(filenames) == len(set(filenames))

    def test_source_ddl_files_unique(self):
        ddl_files = [s.ddl_file for s in SOURCES]
        assert len(ddl_files) == len(set(ddl_files))

    def test_avall_source(self):
        avall = [s for s in SOURCES if s.mdb_filename == "avall.mdb"][0]
        assert avall.schema == "bronze_avall"
        assert "Flight_Crew" in avall.table_renames

    def test_pre2008_source(self):
        pre2008 = [s for s in SOURCES if s.mdb_filename == "Pre2008.mdb"][0]
        assert pre2008.schema == "bronze_pre2008"

    def test_pre1982_source(self):
        pre1982 = [s for s in SOURCES if s.mdb_filename == "PRE1982.MDB"][0]
        assert pre1982.schema == "bronze_pre1982"
        assert "tblFirstHalf" in pre1982.table_renames

    def test_ddl_files_exist(self):
        sql_dir = Path(__file__).resolve().parent.parent / "sql" / "bronze"
        for source in SOURCES:
            ddl_path = sql_dir / source.ddl_file
            assert ddl_path.exists(), f"DDL file missing: {ddl_path}"


# ---------------------------------------------------------------------------
# SQL file integrity
# ---------------------------------------------------------------------------

class TestSQLFileIntegrity:

    def test_bronze_ddl_files_not_empty(self):
        sql_dir = Path(__file__).resolve().parent.parent / "sql" / "bronze"
        for sql_file in sql_dir.glob("*.sql"):
            content = sql_file.read_text(encoding="utf-8")
            assert len(content) > 10, f"{sql_file.name} is empty or too short"

    def test_schema_creation_file_exists(self):
        sql_dir = Path(__file__).resolve().parent.parent / "sql" / "bronze"
        assert (sql_dir / "001_create_schemas.sql").exists()

    def test_schemas_created(self):
        sql_dir = Path(__file__).resolve().parent.parent / "sql" / "bronze"
        content = (sql_dir / "001_create_schemas.sql").read_text()
        assert "bronze_avall" in content
        assert "bronze_pre2008" in content
        assert "bronze_pre1982" in content
        assert "silver" in content
        assert "gold" in content

    def test_quality_check_sql_exists(self):
        sql_dir = Path(__file__).resolve().parent.parent / "sql" / "bronze"
        assert (sql_dir / "005_quality_checks.sql").exists()


# ---------------------------------------------------------------------------
# PostgreSQL integration tests (require running database + ingested data)
# ---------------------------------------------------------------------------

@pytest.fixture
def pg_conn():
    """PostgreSQL connection fixture. Skips if unavailable."""
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


class TestBronzeIngestionResults:
    """Verify bronze data is loaded correctly. Requires prior ingestion run."""

    def test_bronze_avall_events_not_empty(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bronze_avall.events")
            count = cur.fetchone()[0]
        assert count > 0, "bronze_avall.events is empty"

    def test_bronze_pre2008_events_not_empty(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bronze_pre2008.events")
            count = cur.fetchone()[0]
        assert count > 0, "bronze_pre2008.events is empty"

    def test_bronze_pre1982_tbl_first_half_not_empty(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bronze_pre1982.tbl_first_half")
            count = cur.fetchone()[0]
        assert count > 0, "bronze_pre1982.tbl_first_half is empty"

    def test_avall_event_count_matches_known(self, pg_conn):
        """avall.mdb has ~30K events."""
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bronze_avall.events")
            count = cur.fetchone()[0]
        assert 25000 < count < 40000, f"Unexpected avall event count: {count}"

    def test_pre2008_event_count_matches_known(self, pg_conn):
        """Pre2008.mdb has ~63K events."""
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bronze_pre2008.events")
            count = cur.fetchone()[0]
        assert 55000 < count < 70000, f"Unexpected Pre2008 event count: {count}"

    def test_pre1982_event_count_matches_known(self, pg_conn):
        """PRE1982.MDB has ~87K events."""
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bronze_pre1982.tbl_first_half")
            count = cur.fetchone()[0]
        assert 80000 < count < 95000, f"Unexpected PRE1982 event count: {count}"

    def test_lineage_columns_populated(self, pg_conn):
        """Every bronze table should have _source_file populated."""
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM bronze_avall.events "
                "WHERE _source_file IS NOT NULL AND _source_file != ''"
            )
            count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM bronze_avall.events")
            total = cur.fetchone()[0]
        assert count == total, "Some rows missing _source_file"

    def test_source_file_label_correct(self, pg_conn):
        with pg_conn.cursor() as cur:
            cur.execute("SELECT DISTINCT _source_file FROM bronze_avall.events")
            labels = [r[0] for r in cur.fetchall()]
        assert labels == ["avall.mdb"]


class TestBronzeQualityFramework:
    """Test the quality check framework itself."""

    def test_quality_module_imports(self):
        from src.quality import run_bronze_quality_checks, validate_bronze_source
        assert callable(run_bronze_quality_checks)
        assert callable(validate_bronze_source)

    def test_quality_result_dataclass(self):
        from src.quality import QualityResult
        qr = QualityResult(
            source="test", table="test_table", pg_table="schema.table",
            source_rows=100, pg_rows=100, source_cols=5, pg_cols=5,
            rows_match=True, cols_match=True, status="PASS",
        )
        assert qr.status == "PASS"
        assert qr.rows_match is True
