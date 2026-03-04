"""Sport/stroke registry — maps sport names to stroke definitions and detectors."""

from sport.base import StrokeDefinition, PhaseDetector
from sport.tennis.strokes import TENNIS_STROKES
from sport.tennis.phases import TennisPhaseDetector


# Registry of stroke definitions per sport
_STROKE_DEFS: dict[str, dict[str, StrokeDefinition]] = {
    "tennis": TENNIS_STROKES,
}

# Registry of phase detectors per sport
_PHASE_DETECTORS: dict[str, PhaseDetector] = {
    "tennis": TennisPhaseDetector(),
}


def get_stroke_definitions(sport: str) -> dict[str, StrokeDefinition]:
    """Get all stroke definitions for a sport."""
    return _STROKE_DEFS.get(sport, {})


def get_stroke_definition(sport: str, stroke_type: str) -> StrokeDefinition | None:
    """Get a specific stroke definition."""
    return _STROKE_DEFS.get(sport, {}).get(stroke_type)


def get_phase_detector(sport: str) -> PhaseDetector | None:
    """Get the phase detector for a sport."""
    return _PHASE_DETECTORS.get(sport)


def get_supported_sports() -> list[str]:
    """Get list of supported sports."""
    return list(_STROKE_DEFS.keys())
