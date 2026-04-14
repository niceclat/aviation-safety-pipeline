"""
Pipeline governance: run tracking, lineage, monitoring, and freshness.

Provides context managers for tracking pipeline runs and individual steps.
All metadata stored in governance.* schema.

Usage:
    with PipelineRun(conn) as run:
        with run.step("bronze") as step:
            step.rows_affected = ingest_rows
        with run.step("silver") as step:
            step.rows_affected = silver_rows
"""

import logging
import platform
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def _ensure_governance_schema(pg_conn):
    """Create governance schema and tables if they don't exist."""
    sql_path = SQL_DIR / "governance" / "001_pipeline_metadata.sql"
    sql = sql_path.read_text(encoding="utf-8")
    with pg_conn.cursor() as cur:
        cur.execute(sql)
    pg_conn.commit()


class PipelineRun:
    """Context manager for tracking a full pipeline run.

    Creates a row in governance.pipeline_runs on entry,
    updates with final status on exit.
    """

    def __init__(self, pg_conn, contract_version: str = "", backend: str = ""):
        self.conn = pg_conn
        self.run_id: Optional[int] = None
        self.contract_version = contract_version
        self.backend = backend
        self.start_time: float = 0
        self.bronze_rows: int = 0
        self.silver_rows: int = 0
        self.gold_rows: int = 0
        self.nlp_rows: int = 0

    def __enter__(self):
        _ensure_governance_schema(self.conn)
        self.start_time = time.time()

        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO governance.pipeline_runs "
                "(status, contract_version, backend, hostname) "
                "VALUES ('RUNNING', %s, %s, %s) RETURNING run_id",
                (self.contract_version, self.backend, platform.node()),
            )
            self.run_id = cur.fetchone()[0]
        self.conn.commit()
        logger.info(f"Pipeline run #{self.run_id} started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        status = "FAILED" if exc_type else "SUCCESS"
        error_msg = str(exc_val) if exc_val else None

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE governance.pipeline_runs SET "
                    "completed_at = NOW(), status = %s, duration_secs = %s, "
                    "error_message = %s, bronze_rows = %s, silver_rows = %s, "
                    "gold_rows = %s, nlp_rows = %s "
                    "WHERE run_id = %s",
                    (status, duration, error_msg, self.bronze_rows,
                     self.silver_rows, self.gold_rows, self.nlp_rows,
                     self.run_id),
                )
            self.conn.commit()
            logger.info(
                f"Pipeline run #{self.run_id} {status} in {duration:.1f}s "
                f"(bronze={self.bronze_rows:,} silver={self.silver_rows:,} "
                f"gold={self.gold_rows:,} nlp={self.nlp_rows:,})"
            )
        except Exception as e:
            logger.error(f"Failed to update run status: {e}")
            self.conn.rollback()

        return False  # Don't suppress exceptions

    @contextmanager
    def step(self, step_name: str):
        """Track an individual pipeline step within this run."""
        step_id = None
        step_start = time.time()

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO governance.pipeline_steps "
                    "(run_id, step_name, status) "
                    "VALUES (%s, %s, 'RUNNING') RETURNING step_id",
                    (self.run_id, step_name),
                )
                step_id = cur.fetchone()[0]
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to create step record: {e}")
            self.conn.rollback()

        step_result = StepResult()
        try:
            yield step_result
            # Success
            duration = time.time() - step_start
            if step_id:
                try:
                    with self.conn.cursor() as cur:
                        cur.execute(
                            "UPDATE governance.pipeline_steps SET "
                            "completed_at = NOW(), status = 'SUCCESS', "
                            "duration_secs = %s, rows_affected = %s "
                            "WHERE step_id = %s",
                            (duration, step_result.rows_affected, step_id),
                        )
                    self.conn.commit()
                except Exception as e:
                    logger.error(f"Failed to update step: {e}")
                    self.conn.rollback()

            logger.info(
                f"  Step [{step_name}] completed in {duration:.1f}s "
                f"({step_result.rows_affected:,} rows)"
            )

        except Exception as e:
            duration = time.time() - step_start
            if step_id:
                try:
                    with self.conn.cursor() as cur:
                        cur.execute(
                            "UPDATE governance.pipeline_steps SET "
                            "completed_at = NOW(), status = 'FAILED', "
                            "duration_secs = %s, error_message = %s "
                            "WHERE step_id = %s",
                            (duration, str(e), step_id),
                        )
                    self.conn.commit()
                except Exception:
                    self.conn.rollback()
            raise


class StepResult:
    """Mutable container for step-level metrics."""
    def __init__(self):
        self.rows_affected: int = 0


def update_table_freshness(pg_conn, run_id: int, schema: str, table: str):
    """Record when a table was last refreshed and its row count."""
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {schema}.{table}"
            )
            row_count = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO governance.table_freshness "
                "(schema_name, table_name, last_refreshed, row_count, run_id) "
                "VALUES (%s, %s, NOW(), %s, %s) "
                "ON CONFLICT (schema_name, table_name) DO UPDATE SET "
                "last_refreshed = NOW(), row_count = %s, run_id = %s",
                (schema, table, row_count, run_id, row_count, run_id),
            )
        pg_conn.commit()
    except Exception as e:
        logger.error(f"Failed to update freshness for {schema}.{table}: {e}")
        pg_conn.rollback()
