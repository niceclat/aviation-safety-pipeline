-- Bronze: raw tables from Pre2008.mdb (1982-2007)
-- Auto-generated. All columns TEXT. Reserved words quoted.

DROP TABLE IF EXISTS bronze_pre2008.aircraft CASCADE;
CREATE TABLE bronze_pre2008.aircraft (
    ev_id TEXT,
    aircraft_key TEXT,
    regis_no TEXT,
    ntsb_no TEXT,
    acft_missing TEXT,
    far_part TEXT,
    flt_plan_filed TEXT,
    flight_plan_activated TEXT,
    damage TEXT,
    acft_fire TEXT,
    acft_expl TEXT,
    acft_make TEXT,
    acft_model TEXT,
    acft_series TEXT,
    acft_serial_no TEXT,
    cert_max_gr_wt TEXT,
    acft_category TEXT,
    acft_reg_cls TEXT,
    homebuilt TEXT,
    fc_seats TEXT,
    cc_seats TEXT,
    pax_seats TEXT,
    total_seats TEXT,
    num_eng TEXT,
    fixed_retractable TEXT,
    type_last_insp TEXT,
    date_last_insp TEXT,
    afm_hrs_last_insp TEXT,
    afm_hrs TEXT,
    elt_install TEXT,
    elt_oper TEXT,
    elt_aided_loc_ev TEXT,
    elt_type TEXT,
    owner_acft TEXT,
    owner_street TEXT,
    owner_city TEXT,
    owner_state TEXT,
    owner_country TEXT,
    owner_zip TEXT,
    oper_individual_name TEXT,
    oper_name TEXT,
    oper_same TEXT,
    oper_dba TEXT,
    oper_addr_same TEXT,
    oper_street TEXT,
    oper_city TEXT,
    oper_state TEXT,
    oper_country TEXT,
    oper_zip TEXT,
    oper_code TEXT,
    certs_held TEXT,
    oprtng_cert TEXT,
    oper_cert TEXT,
    oper_cert_num TEXT,
    oper_sched TEXT,
    oper_dom_int TEXT,
    oper_pax_cargo TEXT,
    type_fly TEXT,
    second_pilot TEXT,
    dprt_pt_same_ev TEXT,
    dprt_apt_id TEXT,
    dprt_city TEXT,
    dprt_state TEXT,
    dprt_country TEXT,
    dprt_time TEXT,
    dprt_timezn TEXT,
    dest_same_local TEXT,
    dest_apt_id TEXT,
    dest_city TEXT,
    dest_state TEXT,
    dest_country TEXT,
    phase_flt_spec TEXT,
    report_to_icao TEXT,
    evacuation TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    afm_hrs_since TEXT,
    rwy_num TEXT,
    rwy_len TEXT,
    rwy_width TEXT,
    site_seeing TEXT,
    air_medical TEXT,
    med_type_flight TEXT,
    acft_year TEXT,
    fuel_on_board TEXT,
    commercial_space_flight TEXT,
    unmanned TEXT,
    ifr_equipped_cert TEXT,
    elt_mounted_aircraft TEXT,
    elt_connected_antenna TEXT,
    elt_manufacturer TEXT,
    elt_model TEXT,
    elt_reason_other TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.country CASCADE;
CREATE TABLE bronze_pre2008.country (
    country_code TEXT,
    country_name TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.ct_iaids CASCADE;
CREATE TABLE bronze_pre2008.ct_iaids (
    ct_name TEXT,
    code_iaids TEXT,
    meaning TEXT,
    seq TEXT,
    ntsb_type TEXT,
    ntsb_code TEXT,
    avn_code TEXT,
    ntsb_codes_more TEXT,
    not_for_ntsb_use TEXT,
    eadms_use TEXT,
    notes TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.ct_seqevt CASCADE;
CREATE TABLE bronze_pre2008.ct_seqevt (
    code TEXT,
    meaning TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.dt_aircraft CASCADE;
CREATE TABLE bronze_pre2008.dt_aircraft (
    ev_id TEXT,
    aircraft_key TEXT,
    col_name TEXT,
    code TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.dt_events CASCADE;
CREATE TABLE bronze_pre2008.dt_events (
    ev_id TEXT,
    col_name TEXT,
    code TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.dt_flight_crew CASCADE;
CREATE TABLE bronze_pre2008.dt_flight_crew (
    ev_id TEXT,
    aircraft_key TEXT,
    crew_no TEXT,
    col_name TEXT,
    code TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.data_dictionary CASCADE;
CREATE TABLE bronze_pre2008.data_dictionary (
    category_of_data TEXT,
    "column_table" TEXT,
    "column_column" TEXT,
    ct_name TEXT,
    code_iaids TEXT,
    meaning TEXT,
    data_type_eadms TEXT,
    length_eadms TEXT,
    short_desc TEXT,
    question_def TEXT,
    code_meaning TEXT,
    typeofchange TEXT,
    change_notes TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.engines CASCADE;
CREATE TABLE bronze_pre2008.engines (
    ev_id TEXT,
    aircraft_key TEXT,
    eng_no TEXT,
    eng_type TEXT,
    eng_mfgr TEXT,
    eng_model TEXT,
    power_units TEXT,
    hp_or_lbs TEXT,
    lchg_userid TEXT,
    lchg_date TEXT,
    carb_fuel_injection TEXT,
    propeller_type TEXT,
    propeller_make TEXT,
    propeller_model TEXT,
    eng_time_total TEXT,
    eng_time_last_insp TEXT,
    eng_time_overhaul TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.events CASCADE;
CREATE TABLE bronze_pre2008.events (
    ev_id TEXT,
    ntsb_no TEXT,
    ev_type TEXT,
    ev_date TEXT,
    ev_dow TEXT,
    ev_time TEXT,
    ev_tmzn TEXT,
    ev_city TEXT,
    ev_state TEXT,
    ev_country TEXT,
    ev_site_zipcode TEXT,
    ev_year TEXT,
    ev_month TEXT,
    mid_air TEXT,
    on_ground_collision TEXT,
    latitude TEXT,
    longitude TEXT,
    latlong_acq TEXT,
    apt_name TEXT,
    ev_nr_apt_id TEXT,
    ev_nr_apt_loc TEXT,
    apt_dist TEXT,
    apt_dir TEXT,
    apt_elev TEXT,
    wx_brief_comp TEXT,
    wx_src_iic TEXT,
    wx_obs_time TEXT,
    wx_obs_dir TEXT,
    wx_obs_fac_id TEXT,
    wx_obs_elev TEXT,
    wx_obs_dist TEXT,
    wx_obs_tmzn TEXT,
    light_cond TEXT,
    sky_cond_nonceil TEXT,
    sky_nonceil_ht TEXT,
    sky_ceil_ht TEXT,
    sky_cond_ceil TEXT,
    vis_rvr TEXT,
    vis_rvv TEXT,
    vis_sm TEXT,
    wx_temp TEXT,
    wx_dew_pt TEXT,
    wind_dir_deg TEXT,
    wind_dir_ind TEXT,
    wind_vel_kts TEXT,
    wind_vel_ind TEXT,
    gust_ind TEXT,
    gust_kts TEXT,
    altimeter TEXT,
    wx_dens_alt TEXT,
    wx_int_precip TEXT,
    metar TEXT,
    ev_highest_injury TEXT,
    inj_f_grnd TEXT,
    inj_m_grnd TEXT,
    inj_s_grnd TEXT,
    inj_tot_f TEXT,
    inj_tot_m TEXT,
    inj_tot_n TEXT,
    inj_tot_s TEXT,
    inj_tot_t TEXT,
    invest_agy TEXT,
    ntsb_docket TEXT,
    ntsb_notf_from TEXT,
    ntsb_notf_date TEXT,
    ntsb_notf_tm TEXT,
    fiche_number TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    wx_cond_basic TEXT,
    faa_dist_office TEXT,
    dec_latitude TEXT,
    dec_longitude TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.events_sequence CASCADE;
CREATE TABLE bronze_pre2008.events_sequence (
    ev_id TEXT,
    aircraft_key TEXT,
    occurrence_no TEXT,
    occurrence_code TEXT,
    occurrence_description TEXT,
    phase_no TEXT,
    eventsoe_no TEXT,
    defining_ev TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.findings CASCADE;
CREATE TABLE bronze_pre2008.findings (
    ev_id TEXT,
    aircraft_key TEXT,
    finding_no TEXT,
    finding_code TEXT,
    finding_description TEXT,
    category_no TEXT,
    subcategory_no TEXT,
    section_no TEXT,
    subsection_no TEXT,
    modifier_no TEXT,
    cause_factor TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.flight_crew CASCADE;
CREATE TABLE bronze_pre2008.flight_crew (
    ev_id TEXT,
    aircraft_key TEXT,
    crew_no TEXT,
    crew_category TEXT,
    crew_age TEXT,
    crew_sex TEXT,
    crew_city TEXT,
    crew_res_state TEXT,
    crew_res_country TEXT,
    med_certf TEXT,
    med_crtf_vldty TEXT,
    date_lst_med TEXT,
    crew_rat_endorse TEXT,
    crew_inj_level TEXT,
    seatbelts_used TEXT,
    shldr_harn_used TEXT,
    crew_tox_perf TEXT,
    seat_occ_pic TEXT,
    pc_profession TEXT,
    bfr TEXT,
    bfr_date TEXT,
    ft_as_of TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    seat_occ_row TEXT,
    infl_rest_inst TEXT,
    infl_rest_depl TEXT,
    child_restraint TEXT,
    med_crtf_limit TEXT,
    mr_faa_med_certf TEXT,
    pilot_flying TEXT,
    available_restraint TEXT,
    restraint_used TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.flight_time CASCADE;
CREATE TABLE bronze_pre2008.flight_time (
    ev_id TEXT,
    aircraft_key TEXT,
    crew_no TEXT,
    flight_type TEXT,
    flight_craft TEXT,
    flight_hours TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.injury CASCADE;
CREATE TABLE bronze_pre2008.injury (
    ev_id TEXT,
    aircraft_key TEXT,
    inj_person_category TEXT,
    injury_level TEXT,
    inj_person_count TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.narratives CASCADE;
CREATE TABLE bronze_pre2008.narratives (
    ev_id TEXT,
    aircraft_key TEXT,
    narr_accp TEXT,
    narr_accf TEXT,
    narr_cause TEXT,
    narr_inc TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.ntsb_admin CASCADE;
CREATE TABLE bronze_pre2008.ntsb_admin (
    ev_id TEXT,
    rec_stat TEXT,
    approval_date TEXT,
    lchg_userid TEXT,
    lchg_date TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.occurrences CASCADE;
CREATE TABLE bronze_pre2008.occurrences (
    ev_id TEXT,
    aircraft_key TEXT,
    occurrence_no TEXT,
    occurrence_code TEXT,
    phase_of_flight TEXT,
    altitude TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.seq_of_events CASCADE;
CREATE TABLE bronze_pre2008.seq_of_events (
    ev_id TEXT,
    aircraft_key TEXT,
    occurrence_no TEXT,
    seq_event_no TEXT,
    group_code TEXT,
    subj_code TEXT,
    cause_factor TEXT,
    modifier_code TEXT,
    person_code TEXT,
    lchg_date TEXT,
    lchg_userid TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS bronze_pre2008.states CASCADE;
CREATE TABLE bronze_pre2008.states (
    state TEXT,
    "column_name" TEXT,
    faa_region TEXT,
    _source_file TEXT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL DEFAULT NOW()
);
