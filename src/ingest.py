"""
Bronze layer ingestion: MDB files → PostgreSQL bronze schema.

Reads MDB files using mdbtools (Linux/Docker) or pyodbc (Windows),
then bulk-loads into bronze tables via PostgreSQL COPY.

All SQL lives in sql/bronze/ — this module only handles data extraction
and loading mechanics.
"""

import csv
import io
import logging
import platform
import subprocess
from pathlib import Path

import psycopg2

logger = logging.getLogger(__name__)

# Table-to-MDB-table mapping for Pre2008/avall (same schema)
MODERN_TABLES = {
    "bronze.events":          "events",
    "bronze.aircraft":        "aircraft",
    "bronze.narratives":      "narratives",
    "bronze.findings":        "Findings",
    "bronze.events_sequence": "Events_Sequence",
    "bronze.occurrences":     "Occurrences",
    "bronze.seq_of_events":   "seq_of_events",
    "bronze.engines":         "engines",
    "bronze.injury":          "injury",
    "bronze.flight_crew":     "Flight_Crew",
    "bronze.flight_time":     "flight_time",
    "bronze.ct_seqevt":       "ct_seqevt",
    "bronze.ct_iaids":        "ct_iaids",
    "bronze.states":          "states",
}

# Column mappings: bronze table → list of MDB columns to extract
# (ordered to match the bronze table DDL, excluding lineage columns)
COLUMN_MAP = {
    "bronze.events": [
        "ev_id", "ntsb_no", "ev_type", "ev_date", "ev_dow", "ev_time",
        "ev_tmzn", "ev_city", "ev_state", "ev_country", "ev_site_zipcode",
        "ev_year", "ev_month", "mid_air", "on_ground_collision", "latitude",
        "longitude", "latlong_acq", "apt_name", "ev_nr_apt_id", "ev_nr_apt_loc",
        "apt_dist", "apt_dir", "apt_elev", "wx_brief_comp", "wx_src_iic",
        "wx_obs_time", "wx_obs_dir", "wx_obs_fac_id", "wx_obs_elev",
        "wx_obs_dist", "wx_obs_tmzn", "light_cond", "sky_cond_nonceil",
        "sky_nonceil_ht", "sky_ceil_ht", "sky_cond_ceil", "vis_rvr", "vis_rvv",
        "vis_sm", "wx_temp", "wx_dew_pt", "wind_dir_deg", "wind_dir_ind",
        "wind_vel_kts", "wind_vel_ind", "gust_ind", "gust_kts", "altimeter",
        "wx_dens_alt", "wx_int_precip", "metar", "ev_highest_injury",
        "inj_f_grnd", "inj_m_grnd", "inj_s_grnd", "inj_tot_f", "inj_tot_m",
        "inj_tot_n", "inj_tot_s", "inj_tot_t", "invest_agy", "ntsb_docket",
        "ntsb_notf_from", "ntsb_notf_date", "ntsb_notf_tm", "fiche_number",
        "lchg_date", "lchg_userid", "wx_cond_basic", "faa_dist_office",
        "dec_latitude", "dec_longitude",
    ],
    "bronze.aircraft": [
        "ev_id", "Aircraft_Key", "regis_no", "ntsb_no", "acft_missing",
        "far_part", "flt_plan_filed", "flight_plan_activated", "damage",
        "acft_fire", "acft_expl", "acft_make", "acft_model", "acft_series",
        "acft_serial_no", "cert_max_gr_wt", "acft_category", "acft_reg_cls",
        "homebuilt", "fc_seats", "cc_seats", "pax_seats", "total_seats",
        "num_eng", "fixed_retractable", "type_last_insp", "date_last_insp",
        "afm_hrs_last_insp", "afm_hrs", "elt_install", "elt_oper",
        "elt_aided_loc_ev", "elt_type", "owner_acft", "owner_city",
        "owner_state", "owner_country", "oper_name", "oper_code",
        "certs_held", "oper_cert", "oper_cert_num", "oper_sched",
        "oper_dom_int", "oper_pax_cargo", "type_fly", "second_pilot",
        "dprt_apt_id", "dprt_city", "dprt_state", "dprt_country",
        "dprt_time", "dprt_timezn", "dest_apt_id", "dest_city", "dest_state",
        "dest_country", "phase_flt_spec", "evacuation", "acft_year", "num_eng",
    ],
    "bronze.narratives": [
        "ev_id", "Aircraft_Key", "narr_accp", "narr_accf", "narr_cause",
        "narr_inc", "lchg_date", "lchg_userid",
    ],
    "bronze.findings": [
        "ev_id", "Aircraft_Key", "finding_no", "finding_code",
        "finding_description", "category_no", "subcategory_no", "section_no",
        "subsection_no", "modifier_no", "Cause_Factor", "cm_inPc",
        "lchg_date", "lchg_userid",
    ],
    "bronze.events_sequence": [
        "ev_id", "Aircraft_Key", "Occurrence_No", "Occurrence_Code",
        "Occurrence_Description", "phase_no", "eventsoe_no", "Defining_ev",
        "lchg_date", "lchg_userid",
    ],
    "bronze.occurrences": [
        "ev_id", "Aircraft_Key", "Occurrence_No", "Occurrence_Code",
        "Phase_of_Flight", "Altitude", "lchg_date", "lchg_userid",
    ],
    "bronze.seq_of_events": [
        "ev_id", "Aircraft_Key", "Occurrence_No", "seq_event_no",
        "group_code", "Subj_Code", "Cause_Factor", "Modifier_Code",
        "Person_Code", "lchg_date", "lchg_userid",
    ],
    "bronze.engines": [
        "ev_id", "Aircraft_Key", "eng_no", "eng_type", "eng_mfgr",
        "eng_model", "power_units", "hp_or_lbs", "carb_fuel_injection",
        "propeller_type", "propeller_make", "propeller_model",
        "eng_time_total", "eng_time_last_insp", "eng_time_overhaul",
        "lchg_date", "lchg_userid",
    ],
    "bronze.injury": [
        "ev_id", "Aircraft_Key", "inj_person_category", "injury_level",
        "inj_person_count", "lchg_date", "lchg_userid",
    ],
    "bronze.flight_crew": [
        "ev_id", "Aircraft_Key", "crew_no", "crew_category", "crew_age",
        "crew_sex", "med_certf", "med_crtf_vldty", "date_lst_med",
        "crew_rat_endorse", "crew_inj_level", "seatbelts_used",
        "shldr_harn_used", "crew_tox_perf", "seat_occ_pic", "pc_profession",
        "bfr", "bfr_date", "lchg_date", "lchg_userid",
    ],
    "bronze.flight_time": [
        "ev_id", "Aircraft_Key", "crew_no", "flight_type", "flight_craft",
        "flight_hours", "lchg_date", "lchg_userid",
    ],
    "bronze.ct_seqevt": ["code", "meaning"],
    "bronze.ct_iaids": ["ct_name", "code_iaids", "meaning"],
    "bronze.states": ["state", "name", "faa_region"],
}


def _export_mdb_table_mdbtools(mdb_path: str, table_name: str) -> str:
    """Export a table from MDB to CSV string using mdbtools (Linux)."""
    result = subprocess.run(
        ["mdb-export", mdb_path, table_name],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def _export_mdb_table_pyodbc(mdb_path: str, table_name: str,
                             columns: list) -> list:
    """Export a table from MDB using pyodbc (Windows)."""
    import pyodbc
    drv = "Microsoft Access Driver (*.mdb, *.accdb)"
    conn = pyodbc.connect(f"DRIVER={{{drv}}};DBQ={mdb_path};")
    cursor = conn.cursor()

    col_list = ", ".join(f"[{c}]" for c in columns)
    cursor.execute(f"SELECT {col_list} FROM [{table_name}]")
    rows = cursor.fetchall()
    conn.close()
    return rows


def _clean_value(val) -> str:
    """Convert a value to a clean string for COPY, handling NULLs."""
    if val is None:
        return ""
    s = str(val).strip()
    if s in ("None", ""):
        return ""
    # Escape tabs and newlines for TSV
    s = s.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    return s


def load_table_pyodbc(pg_conn, mdb_path: str, mdb_table: str,
                      bronze_table: str, columns: list, source_file: str):
    """Load a single MDB table into bronze via pyodbc + COPY."""
    logger.info(f"Loading {mdb_table} from {source_file} → {bronze_table}")

    rows = _export_mdb_table_pyodbc(mdb_path, mdb_table, columns)
    if not rows:
        logger.warning(f"  No rows in {mdb_table}, skipping")
        return 0

    # Build TSV buffer with source_file appended
    buf = io.StringIO()
    for row in rows:
        cleaned = [_clean_value(v) for v in row]
        cleaned.append(source_file)  # _source_file
        buf.write("\t".join(cleaned) + "\n")

    buf.seek(0)

    # Bronze column names (lowercase) + _source_file
    bronze_cols = [c.lower() for c in columns] + ["_source_file"]
    col_list = ", ".join(bronze_cols)

    cursor = pg_conn.cursor()
    cursor.copy_expert(
        f"COPY {bronze_table} ({col_list}) FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '')",
        buf,
    )
    pg_conn.commit()
    logger.info(f"  Loaded {len(rows):,} rows into {bronze_table}")
    return len(rows)


def load_table_mdbtools(pg_conn, mdb_path: str, mdb_table: str,
                        bronze_table: str, columns: list, source_file: str):
    """Load a single MDB table into bronze via mdbtools + COPY."""
    logger.info(f"Loading {mdb_table} from {source_file} → {bronze_table}")

    csv_data = _export_mdb_table_mdbtools(mdb_path, mdb_table)
    if not csv_data.strip():
        logger.warning(f"  No data in {mdb_table}, skipping")
        return 0

    reader = csv.DictReader(io.StringIO(csv_data))
    buf = io.StringIO()
    count = 0
    for row in reader:
        vals = [_clean_value(row.get(c, "")) for c in columns]
        vals.append(source_file)
        buf.write("\t".join(vals) + "\n")
        count += 1

    buf.seek(0)
    bronze_cols = [c.lower() for c in columns] + ["_source_file"]
    col_list = ", ".join(bronze_cols)

    cursor = pg_conn.cursor()
    cursor.copy_expert(
        f"COPY {bronze_table} ({col_list}) FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '')",
        buf,
    )
    pg_conn.commit()
    logger.info(f"  Loaded {count:,} rows into {bronze_table}")
    return count


def detect_backend():
    """Detect whether to use mdbtools or pyodbc."""
    if platform.system() == "Windows":
        try:
            import pyodbc
            return "pyodbc"
        except ImportError:
            pass
    # Try mdbtools
    try:
        subprocess.run(["mdb-ver"], capture_output=True, check=True)
        return "mdbtools"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    raise RuntimeError("Neither pyodbc nor mdbtools available")


def ingest_modern_mdb(pg_conn, mdb_path: str, source_label: str,
                      backend: str, tables: dict = None):
    """Ingest a Pre2008 or avall MDB file into bronze tables."""
    if tables is None:
        tables = MODERN_TABLES

    total = 0
    for bronze_table, mdb_table in tables.items():
        columns = COLUMN_MAP.get(bronze_table)
        if not columns:
            logger.warning(f"No column map for {bronze_table}, skipping")
            continue

        # For Pre2008, Findings doesn't have cm_inPc column
        if bronze_table == "bronze.findings" and source_label == "Pre2008.mdb":
            columns = [c for c in columns if c != "cm_inPc"]

        try:
            if backend == "pyodbc":
                n = load_table_pyodbc(
                    pg_conn, mdb_path, mdb_table, bronze_table,
                    columns, source_label,
                )
            else:
                n = load_table_mdbtools(
                    pg_conn, mdb_path, mdb_table, bronze_table,
                    columns, source_label,
                )
            total += n
        except Exception as e:
            logger.error(f"  Error loading {mdb_table}: {e}")

    return total


def run_sql_file(pg_conn, sql_path: Path):
    """Execute a SQL file against PostgreSQL."""
    logger.info(f"Executing {sql_path.name}")
    sql = sql_path.read_text(encoding="utf-8")
    cursor = pg_conn.cursor()
    cursor.execute(sql)
    pg_conn.commit()


def run_bronze_ingestion(pg_conn, data_dir: Path, backend: str,
                         mdb_paths: dict = None):
    """Full bronze layer ingestion pipeline.

    Args:
        pg_conn: PostgreSQL connection
        data_dir: directory containing MDB files
        backend: 'pyodbc' or 'mdbtools'
        mdb_paths: optional dict of {label: Path} from download module
    """
    sql_dir = Path(__file__).resolve().parent.parent / "sql" / "bronze"

    # Step 1: Create schemas
    run_sql_file(pg_conn, sql_dir / "001_create_schemas.sql")

    # Step 2: Create bronze tables
    run_sql_file(pg_conn, sql_dir / "002_create_bronze_tables.sql")

    # Resolve MDB paths
    if mdb_paths is None:
        mdb_paths = {}

    # Step 3: Ingest Pre2008
    pre2008_path = mdb_paths.get("Pre2008.mdb", data_dir / "Pre2008.mdb")
    if pre2008_path.exists():
        n = ingest_modern_mdb(pg_conn, str(pre2008_path), "Pre2008.mdb", backend)
        logger.info(f"Pre2008 total: {n:,} rows")
    else:
        logger.warning(f"Pre2008.mdb not found at {pre2008_path}")

    # Step 4: Ingest avall
    avall_path = mdb_paths.get("avall.mdb", data_dir / "avall.mdb")
    if avall_path.exists():
        n = ingest_modern_mdb(pg_conn, str(avall_path), "avall.mdb", backend)
        logger.info(f"avall total: {n:,} rows")
    else:
        logger.warning(f"avall.mdb not found at {avall_path}")

    logger.info("Bronze ingestion complete")
