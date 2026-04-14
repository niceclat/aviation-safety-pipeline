"""Validate EDA.md claims against the actual database.

Checks every numeric claim in EDA.md to ensure no stale or incorrect data.
Run after any pipeline rebuild to confirm documentation accuracy.

Usage:
    python tests/validate_eda.py
"""

import logging
import psycopg2

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("validate_eda")


def main():
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="aviation_safety",
        user="pipeline", password="changeme",
    )
    cur = conn.cursor()
    all_pass = True

    logger.info("=" * 60)
    logger.info("  VALIDATING EDA.md CLAIMS AGAINST DATABASE")
    logger.info("=" * 60)

    def check(label, query, expected, tolerance=0):
        nonlocal all_pass
        cur.execute(query)
        actual = cur.fetchone()[0]
        diff = abs(actual - expected)
        ok = diff <= tolerance
        status = "OK" if ok else f"WRONG (actual={actual:,})"
        if not ok:
            all_pass = False
        logger.info(f"  {label}: expected={expected:,} actual={actual:,} {status}")

    # Section 2: Event counts
    logger.info("\nSection 2: Event counts")
    check("avall events", "SELECT COUNT(*) FROM bronze_avall.events", 30358)
    check("pre2008 events", "SELECT COUNT(*) FROM bronze_pre2008.events", 63002)
    check("pre1982 events", "SELECT COUNT(*) FROM bronze_pre1982.tbl_first_half", 87039)

    # Section 2: Table counts
    logger.info("\nSection 2: Table counts")
    check("avall tables",
          "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='bronze_avall'", 20)
    check("pre2008 tables",
          "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='bronze_pre2008'", 20)
    check("pre1982 tables",
          "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='bronze_pre1982'", 5)

    # Section 2: PRE1982 column counts
    logger.info("\nSection 2: PRE1982 structure")
    check("tblFirstHalf cols",
          "SELECT COUNT(*) FROM information_schema.columns "
          "WHERE table_schema='bronze_pre1982' AND table_name='tbl_first_half' "
          "AND column_name NOT IN ('_source_file','_ingested_at')", 203)
    check("tblSecondHalf cols",
          "SELECT COUNT(*) FROM information_schema.columns "
          "WHERE table_schema='bronze_pre1982' AND table_name='tbl_second_half' "
          "AND column_name NOT IN ('_source_file','_ingested_at')", 200)
    check("tblOccurrences rows",
          "SELECT COUNT(*) FROM bronze_pre1982.tbl_occurrences", 130970)
    check("tblSeqOfEvents rows",
          "SELECT COUNT(*) FROM bronze_pre1982.tbl_seq_of_events", 355681)
    check("ct_Pre1982 rows",
          "SELECT COUNT(*) FROM bronze_pre1982.ct_codes", 2910)

    # Section 2: Findings system split
    logger.info("\nSection 2: Findings system split")
    check("avall Occurrences (should be 0)",
          "SELECT COUNT(*) FROM bronze_avall.occurrences", 0)
    check("pre2008 Occurrences",
          "SELECT COUNT(*) FROM bronze_pre2008.occurrences", 137989)
    check("avall Events_Sequence",
          "SELECT COUNT(*) FROM bronze_avall.events_sequence", 64907)
    check("avall Findings",
          "SELECT COUNT(*) FROM bronze_avall.findings", 71114)
    check("pre2008 seq_of_events",
          "SELECT COUNT(*) FROM bronze_pre2008.seq_of_events", 264329)

    # Section 3: FAR part counts
    logger.info("\nSection 3: FAR part counts")
    check("pre2008 Part 091",
          "SELECT COUNT(*) FROM bronze_pre2008.aircraft WHERE TRIM(far_part)='091'", 52693)
    check("pre2008 Part 121",
          "SELECT COUNT(*) FROM bronze_pre2008.aircraft WHERE TRIM(far_part)='121'", 1856)
    check("pre2008 Part 135",
          "SELECT COUNT(*) FROM bronze_pre2008.aircraft WHERE TRIM(far_part)='135'", 3103)
    check("avall Part 091",
          "SELECT COUNT(*) FROM bronze_avall.aircraft WHERE TRIM(far_part)='091'", 21871)
    check("avall Part 121",
          "SELECT COUNT(*) FROM bronze_avall.aircraft WHERE TRIM(far_part)='121'", 949)
    check("avall Part 135",
          "SELECT COUNT(*) FROM bronze_avall.aircraft WHERE TRIM(far_part)='135'", 908)
    check("Total commercial aircraft (all 3 eras)",
          "SELECT COUNT(*) FROM silver.aircraft_normalized", 11386, tolerance=100)

    # Section 4: Model families
    logger.info("\nSection 4: Model families")
    check("Gold risk profile models",
          "SELECT COUNT(*) FROM gold.aircraft_risk_profile", 173, tolerance=5)

    # Section 5: Severity (avall commercial)
    logger.info("\nSection 5: Severity (avall commercial)")
    check("avall fatal events",
          "SELECT COUNT(*) FROM silver.events_enriched e "
          "INNER JOIN silver.aircraft_normalized a ON e.ev_id = a.ev_id "
          "WHERE a.source_era='avall' AND e.ev_highest_injury='FATL'", 177, tolerance=5)
    check("avall total fatalities",
          "SELECT SUM(e.fatalities) FROM silver.events_enriched e "
          "INNER JOIN silver.aircraft_normalized a ON e.ev_id = a.ev_id "
          "WHERE a.source_era='avall'", 616, tolerance=20)
    check("pre2008 fatal events",
          "SELECT COUNT(*) FROM silver.events_enriched e "
          "INNER JOIN silver.aircraft_normalized a ON e.ev_id = a.ev_id "
          "WHERE a.source_era='pre2008' AND e.ev_highest_injury='FATL'", 770, tolerance=10)
    check("pre2008 total fatalities",
          "SELECT SUM(e.fatalities) FROM silver.events_enriched e "
          "INNER JOIN silver.aircraft_normalized a ON e.ev_id = a.ev_id "
          "WHERE a.source_era='pre2008'", 5075, tolerance=50)

    # Section 7: Findings (avall commercial)
    logger.info("\nSection 7: Findings (avall commercial)")
    check("avall commercial findings total",
          "SELECT COUNT(*) FROM silver.findings_enriched fe "
          "INNER JOIN silver.aircraft_normalized a ON fe.ev_id = a.ev_id "
          "WHERE fe.source_era='avall'", 4721, tolerance=100)

    # DataDictionary
    logger.info("\nOther claims")
    check("DataDictionary rows",
          "SELECT COUNT(*) FROM bronze_avall.data_dictionary", 4574)

    # Summary
    logger.info("")
    logger.info("=" * 60)
    if all_pass:
        logger.info("  EDA.md VALIDATION: ALL CLAIMS VERIFIED")
    else:
        logger.info("  EDA.md VALIDATION: SOME CLAIMS INCORRECT")
    logger.info("=" * 60)

    conn.close()
    return all_pass


if __name__ == "__main__":
    import sys
    passed = main()
    sys.exit(0 if passed else 1)
