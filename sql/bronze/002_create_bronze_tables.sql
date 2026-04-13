-- Bronze layer: raw ingestion tables with lineage metadata.
-- Mirror the source MDB schemas with added ingestion tracking columns.
-- Pre2008 and avall share the same schema; PRE1982 is mapped to match.

DROP TABLE IF EXISTS bronze.events CASCADE;
CREATE TABLE bronze.events (
    ev_id               VARCHAR(14),
    ntsb_no             VARCHAR(11),
    ev_type             VARCHAR(3),
    ev_date             TIMESTAMP,
    ev_dow              VARCHAR(2),
    ev_time             SMALLINT,
    ev_tmzn             VARCHAR(3),
    ev_city             VARCHAR(15),
    ev_state            VARCHAR(2),
    ev_country          VARCHAR(4),
    ev_site_zipcode     VARCHAR(10),
    ev_year             SMALLINT,
    ev_month            SMALLINT,
    mid_air             VARCHAR(1),
    on_ground_collision VARCHAR(1),
    latitude            VARCHAR(7),
    longitude           VARCHAR(8),
    latlong_acq         VARCHAR(4),
    apt_name            VARCHAR(30),
    ev_nr_apt_id        VARCHAR(4),
    ev_nr_apt_loc       VARCHAR(4),
    apt_dist            REAL,
    apt_dir             SMALLINT,
    apt_elev            SMALLINT,
    wx_brief_comp       VARCHAR(4),
    wx_src_iic          VARCHAR(4),
    wx_obs_time         SMALLINT,
    wx_obs_dir          SMALLINT,
    wx_obs_fac_id       VARCHAR(4),
    wx_obs_elev         INTEGER,
    wx_obs_dist         SMALLINT,
    wx_obs_tmzn         VARCHAR(3),
    light_cond          VARCHAR(4),
    sky_cond_nonceil    VARCHAR(4),
    sky_nonceil_ht      INTEGER,
    sky_ceil_ht         INTEGER,
    sky_cond_ceil       VARCHAR(4),
    vis_rvr             REAL,
    vis_rvv             SMALLINT,
    vis_sm              REAL,
    wx_temp             SMALLINT,
    wx_dew_pt           SMALLINT,
    wind_dir_deg        SMALLINT,
    wind_dir_ind        VARCHAR(1),
    wind_vel_kts        SMALLINT,
    wind_vel_ind        VARCHAR(4),
    gust_ind            VARCHAR(1),
    gust_kts            SMALLINT,
    altimeter           REAL,
    wx_dens_alt         INTEGER,
    wx_int_precip       VARCHAR(3),
    metar               TEXT,
    ev_highest_injury   VARCHAR(4),
    inj_f_grnd          SMALLINT,
    inj_m_grnd          SMALLINT,
    inj_s_grnd          SMALLINT,
    inj_tot_f           SMALLINT,
    inj_tot_m           SMALLINT,
    inj_tot_n           SMALLINT,
    inj_tot_s           SMALLINT,
    inj_tot_t           SMALLINT,
    invest_agy          VARCHAR(1),
    ntsb_docket         INTEGER,
    ntsb_notf_from      VARCHAR(30),
    ntsb_notf_date      TIMESTAMP,
    ntsb_notf_tm        SMALLINT,
    fiche_number        VARCHAR(5),
    lchg_date           TIMESTAMP,
    lchg_userid         VARCHAR(18),
    wx_cond_basic       VARCHAR(3),
    faa_dist_office     VARCHAR(50),
    dec_latitude        DOUBLE PRECISION,
    dec_longitude       DOUBLE PRECISION,
    -- Lineage metadata
    _source_file        VARCHAR(50) NOT NULL,
    _ingested_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.aircraft CASCADE;
CREATE TABLE bronze.aircraft (
    ev_id                   VARCHAR(14),
    aircraft_key            INTEGER,
    regis_no                VARCHAR(11),
    ntsb_no                 VARCHAR(11),
    acft_missing            VARCHAR(1),
    far_part                VARCHAR(4),
    flt_plan_filed          VARCHAR(4),
    flight_plan_activated   VARCHAR(1),
    damage                  VARCHAR(4),
    acft_fire               VARCHAR(4),
    acft_expl               VARCHAR(4),
    acft_make               VARCHAR(30),
    acft_model              VARCHAR(20),
    acft_series             VARCHAR(10),
    acft_serial_no          VARCHAR(20),
    cert_max_gr_wt          INTEGER,
    acft_category           VARCHAR(4),
    acft_reg_cls            VARCHAR(4),
    homebuilt               VARCHAR(3),
    fc_seats                INTEGER,
    cc_seats                INTEGER,
    pax_seats               INTEGER,
    total_seats             SMALLINT,
    num_eng                 SMALLINT,
    fixed_retractable       VARCHAR(4),
    type_last_insp          VARCHAR(4),
    date_last_insp          TIMESTAMP,
    afm_hrs_last_insp       REAL,
    afm_hrs                 REAL,
    elt_install             VARCHAR(1),
    elt_oper                VARCHAR(1),
    elt_aided_loc_ev        VARCHAR(1),
    elt_type                VARCHAR(4),
    owner_acft              VARCHAR(50),
    owner_city              VARCHAR(50),
    owner_state             VARCHAR(2),
    owner_country           VARCHAR(4),
    oper_name               VARCHAR(50),
    oper_code               VARCHAR(4),
    certs_held              VARCHAR(1),
    oper_cert               VARCHAR(4),
    oper_cert_num           VARCHAR(11),
    oper_sched              VARCHAR(4),
    oper_dom_int            VARCHAR(3),
    oper_pax_cargo          VARCHAR(4),
    type_fly                VARCHAR(4),
    second_pilot            VARCHAR(1),
    dprt_apt_id             VARCHAR(4),
    dprt_city               VARCHAR(15),
    dprt_state              VARCHAR(2),
    dprt_country            VARCHAR(3),
    dprt_time               SMALLINT,
    dprt_timezn             VARCHAR(3),
    dest_apt_id             VARCHAR(4),
    dest_city               VARCHAR(15),
    dest_state              VARCHAR(2),
    dest_country            VARCHAR(3),
    phase_flt_spec          INTEGER,
    evacuation              VARCHAR(1),
    acft_year               INTEGER,
    num_eng_orig            SMALLINT,
    -- Lineage metadata
    _source_file            VARCHAR(50) NOT NULL,
    _ingested_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.narratives CASCADE;
CREATE TABLE bronze.narratives (
    ev_id           VARCHAR(14),
    aircraft_key    INTEGER,
    narr_accp       TEXT,
    narr_accf       TEXT,
    narr_cause      TEXT,
    narr_inc        TEXT,
    lchg_date       TIMESTAMP,
    lchg_userid     VARCHAR(18),
    -- Lineage metadata
    _source_file    VARCHAR(50) NOT NULL,
    _ingested_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.findings CASCADE;
CREATE TABLE bronze.findings (
    ev_id                   VARCHAR(14),
    aircraft_key            INTEGER,
    finding_no              INTEGER,
    finding_code            VARCHAR(10),
    finding_description     VARCHAR(255),
    category_no             VARCHAR(2),
    subcategory_no          VARCHAR(2),
    section_no              VARCHAR(2),
    subsection_no           VARCHAR(2),
    modifier_no             VARCHAR(2),
    cause_factor            VARCHAR(1),
    cm_inpc                 VARCHAR(5),
    lchg_date               TIMESTAMP,
    lchg_userid             VARCHAR(50),
    -- Lineage metadata
    _source_file            VARCHAR(50) NOT NULL,
    _ingested_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.events_sequence CASCADE;
CREATE TABLE bronze.events_sequence (
    ev_id                   VARCHAR(14),
    aircraft_key            INTEGER,
    occurrence_no           INTEGER,
    occurrence_code         VARCHAR(6),
    occurrence_description  VARCHAR(100),
    phase_no                VARCHAR(3),
    eventsoe_no             VARCHAR(3),
    defining_ev             BOOLEAN,
    lchg_date               TIMESTAMP,
    lchg_userid             VARCHAR(18),
    -- Lineage metadata
    _source_file            VARCHAR(50) NOT NULL,
    _ingested_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.occurrences CASCADE;
CREATE TABLE bronze.occurrences (
    ev_id               VARCHAR(14),
    aircraft_key        INTEGER,
    occurrence_no       INTEGER,
    occurrence_code     INTEGER,
    phase_of_flight     INTEGER,
    altitude            INTEGER,
    lchg_date           TIMESTAMP,
    lchg_userid         VARCHAR(18),
    -- Lineage metadata
    _source_file        VARCHAR(50) NOT NULL,
    _ingested_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.seq_of_events CASCADE;
CREATE TABLE bronze.seq_of_events (
    ev_id               VARCHAR(14),
    aircraft_key        INTEGER,
    occurrence_no       INTEGER,
    seq_event_no        INTEGER,
    group_code          SMALLINT,
    subj_code           INTEGER,
    cause_factor        VARCHAR(1),
    modifier_code       INTEGER,
    person_code         INTEGER,
    lchg_date           TIMESTAMP,
    lchg_userid         VARCHAR(18),
    -- Lineage metadata
    _source_file        VARCHAR(50) NOT NULL,
    _ingested_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.engines CASCADE;
CREATE TABLE bronze.engines (
    ev_id               VARCHAR(14),
    aircraft_key        INTEGER,
    eng_no              SMALLINT,
    eng_type            VARCHAR(4),
    eng_mfgr            VARCHAR(30),
    eng_model           VARCHAR(13),
    power_units         INTEGER,
    hp_or_lbs           VARCHAR(4),
    carb_fuel_injection VARCHAR(4),
    propeller_type      VARCHAR(4),
    propeller_make      VARCHAR(50),
    propeller_model     VARCHAR(50),
    eng_time_total      REAL,
    eng_time_last_insp  REAL,
    eng_time_overhaul   REAL,
    lchg_date           TIMESTAMP,
    lchg_userid         VARCHAR(18),
    -- Lineage metadata
    _source_file        VARCHAR(50) NOT NULL,
    _ingested_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.injury CASCADE;
CREATE TABLE bronze.injury (
    ev_id                   VARCHAR(14),
    aircraft_key            INTEGER,
    inj_person_category     VARCHAR(4),
    injury_level            VARCHAR(4),
    inj_person_count        SMALLINT,
    lchg_date               TIMESTAMP,
    lchg_userid             VARCHAR(18),
    -- Lineage metadata
    _source_file            VARCHAR(50) NOT NULL,
    _ingested_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.flight_crew CASCADE;
CREATE TABLE bronze.flight_crew (
    ev_id               VARCHAR(14),
    aircraft_key        INTEGER,
    crew_no             SMALLINT,
    crew_category       VARCHAR(5),
    crew_age            SMALLINT,
    crew_sex            VARCHAR(1),
    med_certf           VARCHAR(4),
    med_crtf_vldty      VARCHAR(4),
    date_lst_med        TIMESTAMP,
    crew_rat_endorse    VARCHAR(1),
    crew_inj_level      VARCHAR(4),
    seatbelts_used      VARCHAR(1),
    shldr_harn_used     VARCHAR(1),
    crew_tox_perf       VARCHAR(1),
    seat_occ_pic        VARCHAR(4),
    pc_profession       VARCHAR(4),
    bfr                 VARCHAR(1),
    bfr_date            TIMESTAMP,
    lchg_date           TIMESTAMP,
    lchg_userid         VARCHAR(18),
    -- Lineage metadata
    _source_file        VARCHAR(50) NOT NULL,
    _ingested_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.flight_time CASCADE;
CREATE TABLE bronze.flight_time (
    ev_id           VARCHAR(14),
    aircraft_key    INTEGER,
    crew_no         SMALLINT,
    flight_type     VARCHAR(4),
    flight_craft    VARCHAR(4),
    flight_hours    REAL,
    lchg_date       TIMESTAMP,
    lchg_userid     VARCHAR(18),
    -- Lineage metadata
    _source_file    VARCHAR(50) NOT NULL,
    _ingested_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Lookup/reference tables
DROP TABLE IF EXISTS bronze.ct_seqevt CASCADE;
CREATE TABLE bronze.ct_seqevt (
    code        INTEGER,
    meaning     VARCHAR(100),
    _source_file VARCHAR(50) NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.ct_iaids CASCADE;
CREATE TABLE bronze.ct_iaids (
    ct_name     VARCHAR(50),
    code_iaids  VARCHAR(10),
    meaning     VARCHAR(100),
    _source_file VARCHAR(50) NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze.states CASCADE;
CREATE TABLE bronze.states (
    state       VARCHAR(2),
    name        VARCHAR(50),
    faa_region  VARCHAR(3),
    _source_file VARCHAR(50) NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);
