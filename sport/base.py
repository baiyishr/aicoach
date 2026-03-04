"""Base classes for sport-specific stroke analysis."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class PhaseDefinition:
    """Definition of a stroke phase."""
    name: str
    description: str


@dataclass
class StrokeDefinition:
    """Definition of a stroke type within a sport."""
    name: str  # e.g. "serve", "forehand"
    display_name: str  # e.g. "Serve", "Forehand"
    phases: list[PhaseDefinition]
    key_metrics: list[str]  # e.g. ["right_shoulder", "right_elbow", "right_knee"]


@dataclass
class DetectedPhase:
    """A detected phase within a stroke instance."""
    name: str
    start_idx: int  # Index within the stroke's landmark list
    end_idx: int

    @property
    def duration(self) -> int:
        return self.end_idx - self.start_idx


class PhaseDetector(ABC):
    """Base class for detecting phases within a stroke."""

    @abstractmethod
    def detect_phases(
        self,
        landmarks: list[np.ndarray],
        angles: list[dict[str, float]],
        stroke_type: str,
    ) -> list[DetectedPhase]:
        """Detect phases within a single stroke.

        Args:
            landmarks: Per-frame landmarks for the stroke.
            angles: Per-frame joint angles.
            stroke_type: Type of stroke.

        Returns:
            Ordered list of detected phases.
        """
        ...


@dataclass
class ReferenceProfile:
    """Averaged reference profile for a stroke type."""
    stroke_type: str
    sport: str
    num_samples: int
    phases: list[dict]  # [{name, normalized_angles: {joint: [values]}}]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            "stroke_type": self.stroke_type,
            "sport": self.sport,
            "num_samples": self.num_samples,
            "phases": self.phases,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReferenceProfile":
        """Deserialize from a dict."""
        return cls(
            stroke_type=data["stroke_type"],
            sport=data["sport"],
            num_samples=data["num_samples"],
            phases=data["phases"],
            metadata=data.get("metadata", {}),
        )
