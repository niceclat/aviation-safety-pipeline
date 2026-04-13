"""
NLP pipeline orchestrator: reads narratives from bronze, runs regex + embeddings,
writes results to silver.narrative_analysis.

Reads SQL from sql/silver/ files — no SQL embedded in Python.
"""

import io
import logging
from pathlib import Path

import numpy as np

from src.nlp.regex_categorizer import categorize
from src.nlp.embedding_analyzer import (
    generate_embeddings,
    cluster_embeddings,
    build_faiss_index,
    EMBEDDING_DIM,
)

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parent.parent.parent / "sql"


def _read_sql(relative_path: str) -> str:
    """Read a SQL file from the sql/ directory."""
    return (SQL_DIR / relative_path).read_text(encoding="utf-8")


def _fetch_narratives(pg_conn) -> list[tuple]:
    """Fetch commercial narratives from bronze using SQL file.

    Returns:
        List of (ev_id, aircraft_key, narr_accp, narr_cause) tuples.
    """
    sql = _read_sql("silver/005_narrative_select.sql")
    with pg_conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    logger.info(f"Fetched {len(rows):,} narratives from bronze")
    return rows


def _create_schema(pg_conn):
    """Create the narrative analysis table from SQL file."""
    sql = _read_sql("silver/004_narrative_analysis_schema.sql")
    with pg_conn.cursor() as cur:
        cur.execute(sql)
    pg_conn.commit()
    logger.info("Created silver.narrative_analysis table")


def _combine_text(narr_accp, narr_cause) -> str:
    """Combine narrative fields into a single text for analysis."""
    parts = []
    if narr_cause and str(narr_cause).strip() and str(narr_cause).strip() != "None":
        parts.append(str(narr_cause).strip())
    if narr_accp and str(narr_accp).strip() and str(narr_accp).strip() not in ("None", "import"):
        parts.append(str(narr_accp).strip())
    return " ".join(parts)


def run_narrative_analysis(pg_conn, enable_embeddings: bool = True) -> int:
    """Run full NLP pipeline on commercial narratives.

    Steps:
        1. Fetch narratives from bronze
        2. Run regex categorization
        3. Generate embeddings + FAISS clustering (if enabled)
        4. Write results to silver.narrative_analysis

    Args:
        pg_conn: PostgreSQL connection.
        enable_embeddings: If False, skip embedding/FAISS (faster for testing).

    Returns:
        Number of narratives processed.
    """
    # Step 1: Fetch
    rows = _fetch_narratives(pg_conn)
    if not rows:
        logger.warning("No narratives found — skipping NLP")
        return 0

    # Step 2: Regex categorization
    logger.info("Running regex categorization...")
    texts = []
    regex_results = []
    for ev_id, aircraft_key, narr_accp, narr_cause in rows:
        text = _combine_text(narr_accp, narr_cause)
        texts.append(text)
        regex_results.append(categorize(text))

    categorized = sum(1 for r in regex_results if r.n_categories > 0)
    logger.info(
        f"Regex: {categorized:,}/{len(rows):,} narratives categorized "
        f"({100*categorized/len(rows):.1f}%)"
    )

    # Step 3: Embeddings + FAISS (optional)
    cluster_ids = None
    anomaly_scores = None
    embeddings = None

    if enable_embeddings:
        try:
            embeddings = generate_embeddings(texts)
            result = cluster_embeddings(embeddings)
            cluster_ids = result.cluster_ids
            anomaly_scores = result.anomaly_scores

            # Build and save FAISS index
            index = build_faiss_index(embeddings)
            logger.info(f"FAISS index: {index.ntotal} vectors ready for search")

        except ImportError as e:
            logger.warning(f"Embeddings skipped (missing dependency): {e}")
        except Exception as e:
            logger.error(f"Embedding analysis failed: {e}")

    # Step 4: Write to PostgreSQL
    _create_schema(pg_conn)
    count = _write_results(
        pg_conn, rows, regex_results, texts,
        cluster_ids, anomaly_scores, embeddings,
    )

    logger.info(f"NLP pipeline complete: {count:,} rows written to silver.narrative_analysis")
    return count


def _write_results(pg_conn, rows, regex_results, texts,
                   cluster_ids, anomaly_scores, embeddings) -> int:
    """Bulk write NLP results to silver.narrative_analysis using COPY."""
    buf = io.StringIO()

    for i, (ev_id, aircraft_key, _, _) in enumerate(rows):
        rx = regex_results[i]
        cats_pg = "{" + ",".join(rx.categories) + "}" if rx.categories else "{}"
        cluster = str(cluster_ids[i]) if cluster_ids is not None else ""
        anomaly = f"{anomaly_scores[i]:.4f}" if anomaly_scores is not None else ""
        narr_len = str(len(texts[i]))

        # Format embedding as pgvector literal if available
        if embeddings is not None:
            emb_str = "[" + ",".join(f"{v:.6f}" for v in embeddings[i]) + "]"
        else:
            emb_str = ""

        fields = [
            ev_id or "",
            str(aircraft_key) if aircraft_key else "",
            cats_pg,
            rx.primary_category or "",
            str(rx.n_categories),
            str(rx.severity_score),
            str(rx.has_engine_failure),
            str(rx.has_weather_factor),
            str(rx.has_human_factors),
            str(rx.has_fire),
            str(rx.has_structural),
            str(rx.has_maintenance),
            narr_len,
            cluster,
            anomaly,
            emb_str,
        ]
        buf.write("\t".join(fields) + "\n")

    buf.seek(0)

    with pg_conn.cursor() as cur:
        cur.copy_expert(
            "COPY silver.narrative_analysis "
            "(ev_id, aircraft_key, failure_categories, primary_category, "
            "n_categories, text_severity_score, has_engine_failure, "
            "has_weather_factor, has_human_factors, has_fire, "
            "has_structural, has_maintenance, narrative_length, "
            "cluster_id, anomaly_score, embedding) "
            "FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '')",
            buf,
        )
    pg_conn.commit()
    return len(rows)
