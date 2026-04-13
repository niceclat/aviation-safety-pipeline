"""
Regex-based failure categorization for narrative text.

Assigns one or more failure categories to each narrative using
compiled regex patterns. Explainable and auditable — each match
can be traced to a specific pattern.

Categories:
    engine_failure, landing_gear, fuel_related, weather, bird_strike,
    structural, hydraulic, electrical, fire, human_factors, maintenance
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Failure category patterns (compiled for performance)
# ---------------------------------------------------------------------------

_PATTERN_DEFS: dict[str, list[str]] = {
    "engine_failure": [
        r"engine\s*(failure|malfunction|power\s*loss|shutdown|flameout)",
        r"loss\s*of\s*engine\s*power",
        r"engine\s*seiz",
        r"total\s*loss\s*of\s*power",
    ],
    "landing_gear": [
        r"landing\s*gear",
        r"gear\s*(collapse|retract|fail|malfunction)",
        r"nose\s*gear",
        r"main\s*gear",
    ],
    "fuel_related": [
        r"fuel\s*(exhaust|starvat|contaminat|leak|mismanag|selector)",
        r"ran\s*out\s*of\s*fuel",
        r"fuel\s*system",
    ],
    "weather": [
        r"(thunderstorm|icing|turbulence|wind\s*shear|microburst)",
        r"instrument\s*meteorological\s*conditions",
        r"\bIMC\b",
        r"(fog|snow|rain|ice)\s*(encounter|accumulat|condit)",
        r"weather\s*(related|conditions|encounter)",
    ],
    "bird_strike": [
        r"bird\s*strike",
        r"struck?\s*(a\s*)?bird",
        r"wildlife\s*strike",
    ],
    "structural": [
        r"structural\s*(failure|fatigue|crack)",
        r"fuselage\s*(crack|fail|breach)",
        r"wing\s*(fail|separ|crack)",
        r"stabilizer\s*(fail|separ)",
    ],
    "hydraulic": [
        r"hydraulic\s*(failure|malfunction|leak|loss|system)",
    ],
    "electrical": [
        r"electrical\s*(failure|malfunction|fire|short|system)",
        r"battery\s*(fire|failure)",
        r"wiring\s*(failure|short|fire)",
    ],
    "fire": [
        r"(in-?flight|post-?crash|engine)\s*fire",
        r"fire\s*(erupted|broke\s*out|started|reported)",
        r"smoke\s*in\s*(the\s*)?(cabin|cockpit)",
    ],
    "human_factors": [
        r"pilot\s*(error|deviation|failure\s*to|inadequa)",
        r"(spatial\s*)?disorientation",
        r"controlled\s*flight\s*into\s*terrain",
        r"\bCFIT\b",
        r"loss\s*of\s*control",
        r"inadequate\s*(preflight|planning|decision)",
        r"crew\s*resource\s*management",
        r"fatigue",
    ],
    "maintenance": [
        r"maintenance\s*(error|inadequa|improper)",
        r"improper\s*maintenance",
        r"(inspect|overhaul)\s*(fail|inadequa|improper)",
    ],
}

# Pre-compile all patterns for performance
_COMPILED_PATTERNS: dict[str, list[re.Pattern]] = {
    cat: [re.compile(p, re.IGNORECASE) for p in patterns]
    for cat, patterns in _PATTERN_DEFS.items()
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegexResult:
    """Result of regex categorization for a single narrative."""
    categories: list[str]
    primary_category: Optional[str]
    n_categories: int
    severity_score: int
    has_engine_failure: bool
    has_weather_factor: bool
    has_human_factors: bool
    has_fire: bool
    has_structural: bool
    has_maintenance: bool


def categorize(text: Optional[str]) -> RegexResult:
    """Categorize a narrative text into failure categories.

    Args:
        text: Narrative text (narr_cause + narr_accp combined).

    Returns:
        RegexResult with all matched categories and flags.
    """
    if not text or not text.strip():
        return RegexResult(
            categories=[], primary_category=None, n_categories=0,
            severity_score=0, has_engine_failure=False,
            has_weather_factor=False, has_human_factors=False,
            has_fire=False, has_structural=False, has_maintenance=False,
        )

    text_lower = text.lower()
    matched = []
    for category, patterns in _COMPILED_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(text_lower):
                matched.append(category)
                break

    severity = _compute_text_severity(text_lower)

    return RegexResult(
        categories=matched,
        primary_category=matched[0] if matched else None,
        n_categories=len(matched),
        severity_score=severity,
        has_engine_failure="engine_failure" in matched,
        has_weather_factor="weather" in matched,
        has_human_factors="human_factors" in matched,
        has_fire="fire" in matched,
        has_structural="structural" in matched,
        has_maintenance="maintenance" in matched,
    )


def _compute_text_severity(text_lower: str) -> int:
    """Score severity from narrative language (1-5 scale)."""
    if re.search(r"fatal|killed|died|death", text_lower):
        return 5
    if re.search(r"destroyed|total\s*loss|not\s*recoverable", text_lower):
        return 4
    if re.search(r"serious\s*injur|hospitali|substantial\s*damage", text_lower):
        return 3
    if re.search(r"minor\s*injur|minor\s*damage", text_lower):
        return 2
    return 1


def get_categories() -> list[str]:
    """Return list of all available failure categories."""
    return list(_PATTERN_DEFS.keys())


def get_pattern_count() -> int:
    """Return total number of regex patterns across all categories."""
    return sum(len(p) for p in _PATTERN_DEFS.values())
