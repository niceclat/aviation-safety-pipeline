"""Validate all SQL transformations, CTEs, and cross-layer joins."""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("validate")


def main():
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="aviation_safety",
        user="pipeline", password="changeme",
    )
    cur = conn.cursor()
    all_pass = True

    logger.info("=" * 70)
    logger.info("  SQL TRANSFORMATION VALIDATION")
    logger.info("=" * 70)

    # ======================
    # SILVER: events_enriched
    # ======================
    logger.info("\n=== silver.events_enriched ===")

    cur.execute(
        "SELECT source_era, COUNT(*) FROM silver.events_enriched "
        "GROUP BY source_era ORDER BY source_era"
    )
    eras = dict(cur.fetchall())
    for era, count in eras.items():
        logger.info(f"  {era}: {count:,}")

    # Verify vs bronze
    cur.execute(
        "SELECT COUNT(*) FROM bronze_avall.events "
        "WHERE ev_date IS NOT NULL AND ev_date != ''"
    )
    avall_src = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM bronze_pre2008.events "
        "WHERE ev_date IS NOT NULL AND ev_date != ''"
    )
    pre2008_src = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM bronze_pre1982.tbl_first_half "
        "WHERE date_occurrence IS NOT NULL AND date_occurrence != ''"
    )
    pre1982_src = cur.fetchone()[0]

    checks = [
        ("avall events", avall_src, eras.get("avall", 0)),
        ("pre2008 events", pre2008_src, eras.get("pre2008", 0)),
        ("pre1982 events", pre1982_src, eras.get("pre1982", 0)),
    ]
    for name, expected, actual in checks:
        ok = expected == actual
        if not ok:
            all_pass = False
        logger.info(f"  {name}: bronze={expected:,} silver={actual:,} {'MATCH' if ok else 'MISMATCH'}")

    # Injury score validity
    cur.execute(
        "SELECT DISTINCT injury_score FROM silver.events_enriched ORDER BY injury_score"
    )
    scores = [r[0] for r in cur.fetchall()]
    valid_scores = all(s in (0, 1, 2, 3, 4) for s in scores)
    logger.info(f"  Injury scores: {scores} {'VALID' if valid_scores else 'INVALID'}")
    if not valid_scores:
        all_pass = False

    # Null checks
    for col in ["ev_id", "event_year", "source_era"]:
        cur.execute(f"SELECT COUNT(*) FROM silver.events_enriched WHERE {col} IS NULL")
        n = cur.fetchone()[0]
        if n > 0:
            all_pass = False
        logger.info(f"  NULL {col}: {n} {'OK' if n == 0 else 'PROBLEM'}")

    # ======================
    # SILVER: aircraft_normalized
    # ======================
    logger.info("\n=== silver.aircraft_normalized ===")

    cur.execute(
        "SELECT source_era, COUNT(*) FROM silver.aircraft_normalized "
        "GROUP BY source_era ORDER BY source_era"
    )
    a_eras = dict(cur.fetchall())
    for era, count in a_eras.items():
        logger.info(f"  {era}: {count:,}")

    # Commercial filter
    cur.execute("SELECT DISTINCT far_part FROM silver.aircraft_normalized")
    parts = [r[0] for r in cur.fetchall()]
    commercial_ok = all(p in ("121", "135") for p in parts)
    logger.info(f"  far_parts: {parts} {'PASS' if commercial_ok else 'FAIL'}")
    if not commercial_ok:
        all_pass = False

    # Verify vs bronze
    cur.execute(
        "SELECT COUNT(*) FROM bronze_avall.aircraft "
        "WHERE TRIM(far_part) IN ('121', '135')"
    )
    avall_comm = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM bronze_pre2008.aircraft "
        "WHERE TRIM(far_part) IN ('121', '135')"
    )
    pre2008_comm = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM bronze_pre1982.tbl_first_half "
        "WHERE type_operator IN ('E', 'P', 'N')"
    )
    pre1982_comm = cur.fetchone()[0]

    checks = [
        ("avall aircraft", avall_comm, a_eras.get("avall", 0)),
        ("pre2008 aircraft", pre2008_comm, a_eras.get("pre2008", 0)),
        ("pre1982 aircraft", pre1982_comm, a_eras.get("pre1982", 0)),
    ]
    for name, expected, actual in checks:
        ok = expected == actual
        if not ok:
            all_pass = False
        logger.info(f"  {name}: bronze={expected:,} silver={actual:,} {'MATCH' if ok else 'MISMATCH'}")

    # Normalization reduction
    cur.execute("SELECT COUNT(DISTINCT manufacturer) FROM silver.aircraft_normalized")
    n_mfr = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT make_raw) FROM silver.aircraft_normalized")
    n_raw = cur.fetchone()[0]
    logger.info(f"  Make normalization: {n_raw} raw -> {n_mfr} canonical (reduced {n_raw - n_mfr})")

    # ======================
    # SILVER: findings_enriched
    # ======================
    logger.info("\n=== silver.findings_enriched ===")

    cur.execute(
        "SELECT source_era, findings_system, COUNT(*) "
        "FROM silver.findings_enriched "
        "GROUP BY source_era, findings_system ORDER BY source_era"
    )
    for era, system, count in cur.fetchall():
        logger.info(f"  {era} ({system}): {count:,}")

    # ======================
    # SILVER: narrative_analysis
    # ======================
    logger.info("\n=== silver.narrative_analysis ===")

    cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis")
    total_na = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis WHERE embedding IS NOT NULL")
    has_emb = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis WHERE cluster_id IS NOT NULL")
    has_cluster = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM silver.narrative_analysis WHERE n_categories > 0")
    has_regex = cur.fetchone()[0]

    logger.info(f"  Total: {total_na:,}")
    emb_ok = has_emb == total_na
    logger.info(f"  Embeddings: {has_emb:,}/{total_na:,} {'MATCH' if emb_ok else 'MISMATCH'}")
    cluster_ok = has_cluster == total_na
    logger.info(f"  Clusters: {has_cluster:,}/{total_na:,} {'MATCH' if cluster_ok else 'MISMATCH'}")
    logger.info(f"  Regex categorized: {has_regex:,} ({100*has_regex/total_na:.1f}%)")
    if not emb_ok or not cluster_ok:
        all_pass = False

    # ======================
    # GOLD: aircraft_risk_profile
    # ======================
    logger.info("\n=== gold.aircraft_risk_profile ===")

    cur.execute("SELECT COUNT(*) FROM gold.aircraft_risk_profile")
    total_gold = cur.fetchone()[0]
    logger.info(f"  Total models: {total_gold}")

    cur.execute(
        "SELECT risk_tier, COUNT(*) FROM gold.aircraft_risk_profile "
        "GROUP BY risk_tier ORDER BY risk_tier"
    )
    logger.info(f"  Risk tiers: {dict(cur.fetchall())}")

    cur.execute(
        "SELECT severity_trend, COUNT(*) FROM gold.aircraft_risk_profile "
        "GROUP BY severity_trend ORDER BY severity_trend"
    )
    logger.info(f"  Severity trends: {dict(cur.fetchall())}")

    # Critical NULL checks
    critical = [
        "manufacturer", "model_full", "total_incidents", "risk_tier",
        "risk_rank", "weighted_severity_score", "severity_trend",
        "data_as_of", "data_note",
    ]
    logger.info("  Critical column NULLs:")
    for col in critical:
        cur.execute(
            f"SELECT COUNT(*) FROM gold.aircraft_risk_profile WHERE {col} IS NULL"
        )
        n = cur.fetchone()[0]
        if n > 0:
            all_pass = False
        logger.info(f"    {col}: {n} {'OK' if n == 0 else 'NULLS FOUND'}")

    # Severity ordering by tier
    cur.execute("""
        SELECT
            AVG(weighted_severity_score) FILTER (WHERE risk_tier = 'CRITICAL'),
            AVG(weighted_severity_score) FILTER (WHERE risk_tier = 'HIGH'),
            AVG(weighted_severity_score) FILTER (WHERE risk_tier = 'MEDIUM'),
            AVG(weighted_severity_score) FILTER (WHERE risk_tier = 'LOW')
        FROM gold.aircraft_risk_profile
    """)
    c, h, m, l = cur.fetchone()
    ordering_ok = c >= h >= m
    logger.info(f"  Avg severity: CRITICAL={c:.2f} HIGH={h:.2f} MEDIUM={m:.2f} LOW={l:.2f}")
    logger.info(f"  Tier ordering correct: {'PASS' if ordering_ok else 'FAIL'}")
    if not ordering_ok:
        all_pass = False

    # ======================
    # CROSS-LAYER JOIN INTEGRITY
    # ======================
    logger.info("\n=== CROSS-LAYER JOIN INTEGRITY ===")

    cur.execute("""
        SELECT COUNT(DISTINCT a.ev_id)
        FROM silver.aircraft_normalized a
        INNER JOIN silver.events_enriched e ON a.ev_id = e.ev_id
    """)
    joined = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT ev_id) FROM silver.aircraft_normalized")
    total_acft = cur.fetchone()[0]
    join_ok = joined == total_acft
    logger.info(
        f"  Aircraft -> Events: {joined:,}/{total_acft:,} "
        f"{'PASS' if join_ok else 'ORPHANS FOUND'}"
    )
    if not join_ok:
        all_pass = False

    cur.execute("""
        SELECT COUNT(DISTINCT na.ev_id)
        FROM silver.narrative_analysis na
        INNER JOIN silver.aircraft_normalized a ON na.ev_id = a.ev_id
    """)
    na_joined = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT ev_id) FROM silver.narrative_analysis")
    na_total = cur.fetchone()[0]
    logger.info(f"  Narratives -> Aircraft: {na_joined:,}/{na_total:,}")

    # ======================
    # SUMMARY
    # ======================
    logger.info("")
    logger.info("=" * 70)
    if all_pass:
        logger.info("  ALL SQL VALIDATIONS PASSED")
    else:
        logger.info("  SOME VALIDATIONS FAILED - REVIEW ABOVE")
    logger.info("=" * 70)

    conn.close()
    return all_pass


if __name__ == "__main__":
    import sys
    passed = main()
    sys.exit(0 if passed else 1)
