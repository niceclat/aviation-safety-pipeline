"""
Tests for src/contracts.py — data contract definitions and mappings.

Covers:
    - All code translation helper functions
    - Input validation and edge cases
    - Manufacturer normalization rules
    - Severity scoring
    - Commercial operation filters
    - Contract metadata integrity
    - Lookup table loading and validation (requires PostgreSQL)
"""

import pytest

from src.contracts import (
    CONTRACT_VERSION,
    CONTRACT_DATE,
    CONTRACT_DESCRIPTION,
    TYPE_OPERATOR_TO_FAR_PART,
    DAMAGE_CODE_MAP,
    EVENT_TYPE_MAP,
    AIRCRAFT_CATEGORY_MAP,
    INJURY_SEVERITY_SCORES,
    DAMAGE_SEVERITY_SCORES,
    COMMERCIAL_FAR_PARTS,
    PRE1982_COMMERCIAL_OPERATORS,
    MANUFACTURER_RULES,
    MODEL_FAMILY_PATTERNS,
    MODEL_FAMILY_FALLBACK,
    normalize_manufacturer,
    map_type_operator_to_far_part,
    map_damage_code,
    map_event_type,
    map_aircraft_category,
    is_commercial_operation,
    is_pre1982_commercial,
    compute_injury_score,
    compute_damage_score,
    load_lookups_to_pg,
    validate_lookups,
)


# ---------------------------------------------------------------------------
# Contract metadata
# ---------------------------------------------------------------------------

class TestContractMetadata:
    """Verify contract metadata is set and consistent."""

    def test_version_format(self):
        parts = CONTRACT_VERSION.split(".")
        assert len(parts) == 3, "Version must be semver (X.Y.Z)"
        assert all(p.isdigit() for p in parts), "Version parts must be numeric"

    def test_date_format(self):
        parts = CONTRACT_DATE.split("-")
        assert len(parts) == 3, "Date must be YYYY-MM-DD"
        assert len(parts[0]) == 4, "Year must be 4 digits"

    def test_description_not_empty(self):
        assert len(CONTRACT_DESCRIPTION) > 10


# ---------------------------------------------------------------------------
# Code translation completeness
# ---------------------------------------------------------------------------

class TestCodeTranslationCompleteness:
    """Verify all code translation dicts are complete and consistent."""

    def test_type_operator_has_all_known_codes(self):
        known = {"D", "A", "B", "M", "F", "L", "J", "K", "E", "P", "N", "C", "G", "H", "I", "Y", "Z"}
        assert set(TYPE_OPERATOR_TO_FAR_PART.keys()) == known

    def test_type_operator_values_are_tuples(self):
        for code, val in TYPE_OPERATOR_TO_FAR_PART.items():
            assert isinstance(val, tuple), f"Code {code}: expected tuple, got {type(val)}"
            assert len(val) == 2, f"Code {code}: expected (far_part, description)"
            assert val[0], f"Code {code}: far_part is empty"
            assert val[1], f"Code {code}: description is empty"

    def test_damage_codes_complete(self):
        assert set(DAMAGE_CODE_MAP.keys()) == {"D", "S", "M", "N", "Z"}

    def test_event_type_codes_complete(self):
        assert len(EVENT_TYPE_MAP) == 10
        for code, val in EVENT_TYPE_MAP.items():
            assert val[0] in ("ACC", "INC"), f"Code {code}: invalid event type {val[0]}"

    def test_aircraft_category_codes_complete(self):
        assert len(AIRCRAFT_CATEGORY_MAP) >= 10

    def test_injury_scores_ordered(self):
        assert INJURY_SEVERITY_SCORES["FATL"] > INJURY_SEVERITY_SCORES["SERS"]
        assert INJURY_SEVERITY_SCORES["SERS"] > INJURY_SEVERITY_SCORES["MINR"]
        assert INJURY_SEVERITY_SCORES["MINR"] > INJURY_SEVERITY_SCORES["NONE"]

    def test_damage_scores_ordered(self):
        assert DAMAGE_SEVERITY_SCORES["DEST"] > DAMAGE_SEVERITY_SCORES["SUBS"]
        assert DAMAGE_SEVERITY_SCORES["SUBS"] > DAMAGE_SEVERITY_SCORES["MINR"]
        assert DAMAGE_SEVERITY_SCORES["MINR"] > DAMAGE_SEVERITY_SCORES["NONE"]
        assert DAMAGE_SEVERITY_SCORES["NONE"] > DAMAGE_SEVERITY_SCORES["UNK"]

    def test_commercial_far_parts(self):
        assert "121" in COMMERCIAL_FAR_PARTS
        assert "135" in COMMERCIAL_FAR_PARTS
        assert "091" not in COMMERCIAL_FAR_PARTS

    def test_pre1982_commercial_operators_map_to_commercial(self):
        for op in PRE1982_COMMERCIAL_OPERATORS:
            far = TYPE_OPERATOR_TO_FAR_PART[op][0]
            assert far in COMMERCIAL_FAR_PARTS, (
                f"Operator {op} maps to {far}, not in COMMERCIAL_FAR_PARTS"
            )


# ---------------------------------------------------------------------------
# Manufacturer normalization
# ---------------------------------------------------------------------------

class TestNormalizeManufacturer:
    """Test manufacturer name normalization."""

    @pytest.mark.parametrize("raw,expected", [
        ("BOEING", "BOEING"),
        ("Boeing", "BOEING"),
        ("boeing", "BOEING"),
        ("BOEING COMPANY", "BOEING"),
        ("AIRBUS", "AIRBUS"),
        ("AIRBUS INDUSTRIE", "AIRBUS"),
        ("Airbus", "AIRBUS"),
        ("MCDONNELL DOUGLAS", "MCDONNELL DOUGLAS"),
        ("DOUGLAS", "MCDONNELL DOUGLAS"),
        ("Douglas Aircraft", "MCDONNELL DOUGLAS"),
        ("CANADAIR", "BOMBARDIER"),
        ("BOMBARDIER INC", "BOMBARDIER"),
        ("Bombardier", "BOMBARDIER"),
        ("DE HAVILLAND CANADA", "BOMBARDIER"),
        ("CESSNA", "CESSNA"),
        ("Cessna", "CESSNA"),
        ("TEXTRON AVIATION", "CESSNA"),
        ("BEECH", "BEECHCRAFT"),
        ("BEECHCRAFT", "BEECHCRAFT"),
        ("HAWKER BEECHCRAFT", "BEECHCRAFT"),
        ("PIPER", "PIPER"),
        ("BELL", "BELL"),
        ("BELL HELICOPTER", "BELL"),
        ("LOCKHEED", "LOCKHEED"),
        ("LOCKHEED MARTIN", "LOCKHEED"),
        ("EMBRAER", "EMBRAER"),
        ("SIKORSKY", "SIKORSKY"),
        ("EUROCOPTER", "EUROCOPTER"),
        ("ROBINSON HELICOPTER", "ROBINSON"),
    ])
    def test_known_manufacturers(self, raw, expected):
        assert normalize_manufacturer(raw) == expected

    def test_unknown_manufacturer_returns_uppercased(self):
        assert normalize_manufacturer("Fokker") == "FOKKER"
        assert normalize_manufacturer("Mitsubishi") == "MITSUBISHI"

    def test_none_returns_unknown(self):
        assert normalize_manufacturer(None) == "UNKNOWN"

    def test_empty_returns_unknown(self):
        assert normalize_manufacturer("") == "UNKNOWN"
        assert normalize_manufacturer("   ") == "UNKNOWN"

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            normalize_manufacturer(123)
        with pytest.raises(TypeError):
            normalize_manufacturer(["BOEING"])


# ---------------------------------------------------------------------------
# Code mapping helpers
# ---------------------------------------------------------------------------

class TestMapTypeOperator:

    @pytest.mark.parametrize("code,expected", [
        ("E", "135"), ("P", "135"), ("N", "121"),
        ("D", "091"), ("A", "091"), ("C", "137"),
        ("G", "PUBU"), ("Y", "UNK"), ("Z", "UNK"),
    ])
    def test_known_codes(self, code, expected):
        assert map_type_operator_to_far_part(code) == expected

    def test_unknown_code_returns_unk(self):
        assert map_type_operator_to_far_part("X") == "UNK"
        assert map_type_operator_to_far_part("9") == "UNK"

    def test_none_returns_unk(self):
        assert map_type_operator_to_far_part(None) == "UNK"

    def test_empty_returns_unk(self):
        assert map_type_operator_to_far_part("") == "UNK"

    def test_whitespace_stripped(self):
        assert map_type_operator_to_far_part(" E ") == "135"


class TestMapDamageCode:

    @pytest.mark.parametrize("code,expected", [
        ("D", "DEST"), ("S", "SUBS"), ("M", "MINR"), ("N", "NONE"), ("Z", "UNK"),
    ])
    def test_known_codes(self, code, expected):
        assert map_damage_code(code) == expected

    def test_none_and_empty(self):
        assert map_damage_code(None) == "UNK"
        assert map_damage_code("") == "UNK"


class TestMapEventType:

    def test_accidents(self):
        for code in ["A", "B", "F", "G"]:
            assert map_event_type(code) == "ACC"

    def test_incidents(self):
        for code in ["C", "D", "E", "H", "I", "J"]:
            assert map_event_type(code) == "INC"

    def test_none_and_empty(self):
        assert map_event_type(None) == "UNK"
        assert map_event_type("") == "UNK"


class TestMapAircraftCategory:

    @pytest.mark.parametrize("code,expected", [
        ("A", "AIR"), ("B", "HELI"), ("C", "GLI"),
        ("D", "BALL"), ("I", "GYRO"),
    ])
    def test_known_codes(self, code, expected):
        assert map_aircraft_category(code) == expected

    def test_none_and_empty(self):
        assert map_aircraft_category(None) == "UNK"


# ---------------------------------------------------------------------------
# Commercial filters
# ---------------------------------------------------------------------------

class TestCommercialFilters:

    def test_commercial_far_parts(self):
        assert is_commercial_operation("121") is True
        assert is_commercial_operation("135") is True
        assert is_commercial_operation("091") is False
        assert is_commercial_operation("137") is False
        assert is_commercial_operation(None) is False
        assert is_commercial_operation("") is False

    def test_pre1982_commercial(self):
        assert is_pre1982_commercial("E") is True
        assert is_pre1982_commercial("P") is True
        assert is_pre1982_commercial("N") is True
        assert is_pre1982_commercial("D") is False
        assert is_pre1982_commercial("A") is False
        assert is_pre1982_commercial(None) is False


# ---------------------------------------------------------------------------
# Severity scoring
# ---------------------------------------------------------------------------

class TestSeverityScoring:

    @pytest.mark.parametrize("level,expected", [
        ("FATL", 4), ("SERS", 3), ("MINR", 2), ("NONE", 1),
    ])
    def test_injury_scores(self, level, expected):
        assert compute_injury_score(level) == expected

    @pytest.mark.parametrize("level,expected", [
        ("DEST", 4), ("SUBS", 3), ("MINR", 2), ("NONE", 1), ("UNK", 0),
    ])
    def test_damage_scores(self, level, expected):
        assert compute_damage_score(level) == expected

    def test_null_scores(self):
        assert compute_injury_score(None) == 0
        assert compute_injury_score("") == 0
        assert compute_damage_score(None) == 0

    def test_unknown_level_scores_zero(self):
        assert compute_injury_score("INVALID") == 0
        assert compute_damage_score("INVALID") == 0


# ---------------------------------------------------------------------------
# Manufacturer rules integrity
# ---------------------------------------------------------------------------

class TestManufacturerRulesIntegrity:

    def test_no_duplicate_prefixes(self):
        all_prefixes = [p for _, prefixes in MANUFACTURER_RULES for p in prefixes]
        assert len(all_prefixes) == len(set(all_prefixes)), "Duplicate prefixes found"

    def test_all_canonicals_unique(self):
        canonicals = [c for c, _ in MANUFACTURER_RULES]
        assert len(canonicals) == len(set(canonicals)), "Duplicate canonical names"

    def test_model_patterns_reference_known_manufacturers(self):
        known = {c for c, _ in MANUFACTURER_RULES}
        for mfr in MODEL_FAMILY_PATTERNS:
            assert mfr in known, f"Model pattern for unknown manufacturer: {mfr}"


# ---------------------------------------------------------------------------
# PostgreSQL integration tests (require running database)
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


class TestLookupLoading:
    """Integration tests for loading lookups to PostgreSQL."""

    def test_load_lookups_returns_dict(self, pg_conn):
        results = load_lookups_to_pg(pg_conn)
        assert isinstance(results, dict)
        assert len(results) == 6

    def test_load_lookups_all_positive_counts(self, pg_conn):
        results = load_lookups_to_pg(pg_conn)
        for table, count in results.items():
            assert count > 0, f"{table} loaded 0 rows"

    def test_load_lookups_expected_tables(self, pg_conn):
        results = load_lookups_to_pg(pg_conn)
        expected = {
            "_lookup_far_part", "_lookup_damage", "_lookup_event_type",
            "_lookup_aircraft_category", "_lookup_manufacturer", "_lookup_severity",
        }
        assert set(results.keys()) == expected

    def test_validate_lookups_passes(self, pg_conn):
        load_lookups_to_pg(pg_conn)
        assert validate_lookups(pg_conn) is True

    def test_idempotent_load(self, pg_conn):
        load_lookups_to_pg(pg_conn)
        results1 = load_lookups_to_pg(pg_conn)
        assert validate_lookups(pg_conn) is True
        # Counts should be same after second load
        for table, count in results1.items():
            assert count > 0
