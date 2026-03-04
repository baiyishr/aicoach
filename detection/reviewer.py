"""Data structures for stroke review/correction workflow.

The user reviews auto-detected and classified strokes, can re-label or
discard them before building reference profiles.
"""

from dataclasses import dataclass, field

from detection.classifier import ClassifiedStroke


STROKE_TYPE_LABELS = {
    "serve": "Serve",
    "forehand": "Forehand",
    "backhand_1h": "Backhand (1H)",
    "backhand_2h": "Backhand (2H)",
    "volley": "Volley",
    "unknown": "Unknown",
}

STROKE_TYPES = list(STROKE_TYPE_LABELS.keys())


@dataclass
class ReviewableStroke:
    """A stroke ready for user review."""
    id: int
    classified: ClassifiedStroke
    user_label: str | None = None  # None = not yet reviewed
    discarded: bool = False

    @property
    def final_label(self) -> str:
        """The effective label (user override or auto-classified)."""
        if self.discarded:
            return "discarded"
        return self.user_label if self.user_label else self.classified.stroke_type

    @property
    def display_label(self) -> str:
        label = self.final_label
        return STROKE_TYPE_LABELS.get(label, label)

    def relabel(self, new_type: str):
        """Re-label this stroke."""
        self.user_label = new_type
        self.discarded = False

    def discard(self):
        """Mark this stroke as discarded."""
        self.discarded = True

    def restore(self):
        """Restore a discarded stroke."""
        self.discarded = False


@dataclass
class DetectionResult:
    """Collection of detected strokes for review."""
    video_path: str
    fps: float
    total_frames: int
    strokes: list[ReviewableStroke] = field(default_factory=list)

    @classmethod
    def from_classified(
        cls, video_path: str, fps: float, total_frames: int,
        classified: list[ClassifiedStroke],
    ) -> "DetectionResult":
        """Create from a list of classified strokes."""
        strokes = [
            ReviewableStroke(id=i, classified=c)
            for i, c in enumerate(classified)
        ]
        return cls(
            video_path=video_path,
            fps=fps,
            total_frames=total_frames,
            strokes=strokes,
        )

    @property
    def confirmed_strokes(self) -> list[ReviewableStroke]:
        """Get non-discarded strokes."""
        return [s for s in self.strokes if not s.discarded]

    def strokes_by_type(self, stroke_type: str) -> list[ReviewableStroke]:
        """Get confirmed strokes of a specific type."""
        return [
            s for s in self.confirmed_strokes
            if s.final_label == stroke_type
        ]

    def relabel(self, stroke_id: int, new_type: str):
        """Re-label a stroke by ID."""
        for s in self.strokes:
            if s.id == stroke_id:
                s.relabel(new_type)
                return

    def discard(self, stroke_id: int):
        """Discard a stroke by ID."""
        for s in self.strokes:
            if s.id == stroke_id:
                s.discard()
                return

    def restore(self, stroke_id: int):
        """Restore a discarded stroke by ID."""
        for s in self.strokes:
            if s.id == stroke_id:
                s.restore()
                return
