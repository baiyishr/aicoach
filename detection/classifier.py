"""Classify stroke segments by stroke type.

Delegates to sport-specific classification rules.
"""

from dataclasses import dataclass

from detection.segmenter import StrokeSegment
from sport.tennis.classifier_rules import classify_tennis_stroke


@dataclass
class ClassifiedStroke:
    """A stroke segment with its classified type."""
    segment: StrokeSegment
    stroke_type: str  # e.g. "serve", "forehand", "backhand_1h", "backhand_2h", "volley"
    confidence: float
    sport: str = "tennis"

    @property
    def start_frame(self) -> int:
        return self.segment.start_frame

    @property
    def end_frame(self) -> int:
        return self.segment.end_frame

    @property
    def mid_frame(self) -> int:
        return self.segment.mid_frame


def classify_segment(
    segment: StrokeSegment,
    sport: str = "tennis",
    dominant_side: str = "right",
) -> ClassifiedStroke:
    """Classify a single stroke segment.

    Args:
        segment: The detected motion segment.
        sport: Sport type for selecting rules.
        dominant_side: Player's dominant hand.

    Returns:
        ClassifiedStroke with type and confidence.
    """
    if sport == "tennis":
        stroke_type, confidence = classify_tennis_stroke(
            segment.landmarks, segment.angles, dominant_side
        )
    else:
        stroke_type, confidence = "unknown", 0.0

    return ClassifiedStroke(
        segment=segment,
        stroke_type=stroke_type,
        confidence=confidence,
        sport=sport,
    )


def classify_all_segments(
    segments: list[StrokeSegment],
    sport: str = "tennis",
    dominant_side: str = "right",
) -> list[ClassifiedStroke]:
    """Classify all detected stroke segments.

    Args:
        segments: List of motion segments.
        sport: Sport type.
        dominant_side: Player's dominant hand.

    Returns:
        List of ClassifiedStroke objects.
    """
    return [classify_segment(s, sport, dominant_side) for s in segments]
