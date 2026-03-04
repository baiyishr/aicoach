"""Compute angle/position deltas between student and pro reference."""

from dataclasses import dataclass, field

import numpy as np

from sport.base import ReferenceProfile
from comparison.alignment import align_student_stroke, align_phases
from config import SIGNIFICANT_ANGLE_DIFF


@dataclass
class AngleDiff:
    """Difference in a specific joint angle."""
    joint: str
    student_avg: float
    pro_avg: float
    diff: float  # student - pro (positive means student has larger angle)
    abs_diff: float
    significant: bool

    @property
    def description(self) -> str:
        direction = "more" if self.diff > 0 else "less"
        return f"{self.joint}: Student {self.student_avg:.0f}° vs Pro {self.pro_avg:.0f}° ({self.abs_diff:.0f}° {direction})"


@dataclass
class PhaseDiff:
    """Differences within a single phase."""
    phase_name: str
    angle_diffs: list[AngleDiff] = field(default_factory=list)

    @property
    def significant_diffs(self) -> list[AngleDiff]:
        return [d for d in self.angle_diffs if d.significant]

    @property
    def max_diff(self) -> float:
        if not self.angle_diffs:
            return 0.0
        return max(d.abs_diff for d in self.angle_diffs)


@dataclass
class StrokeDiff:
    """Full comparison result for a stroke."""
    stroke_type: str
    phase_diffs: list[PhaseDiff] = field(default_factory=list)

    @property
    def all_significant(self) -> list[tuple[str, AngleDiff]]:
        """All significant diffs across phases, sorted by severity."""
        result = []
        for pd in self.phase_diffs:
            for ad in pd.significant_diffs:
                result.append((pd.phase_name, ad))
        result.sort(key=lambda x: x[1].abs_diff, reverse=True)
        return result

    @property
    def top_issues(self) -> list[tuple[str, AngleDiff]]:
        """Top 5 most significant differences."""
        return self.all_significant[:5]


def compute_diff(
    student_landmarks: list[np.ndarray],
    student_angles: list[dict[str, float]],
    reference: ReferenceProfile,
    stroke_type: str,
    sport: str = "tennis",
    threshold: float = SIGNIFICANT_ANGLE_DIFF,
) -> StrokeDiff:
    """Compute differences between a student's stroke and a pro reference.

    Args:
        student_landmarks: Student's per-frame landmarks.
        student_angles: Student's per-frame angles.
        reference: Pro reference profile.
        stroke_type: Stroke type.
        sport: Sport name.
        threshold: Angle difference threshold for significance.

    Returns:
        StrokeDiff with per-phase angle differences.
    """
    # Align student's stroke
    student_phases = align_student_stroke(
        student_landmarks, student_angles, stroke_type, sport
    )

    # Match with reference phases
    aligned = align_phases(student_phases, reference)

    phase_diffs = []
    for student_phase, ref_phase in aligned:
        if ref_phase is None:
            continue

        student_angles_norm = student_phase["normalized_angles"]
        ref_angles_norm = ref_phase["normalized_angles"]

        # Find common joints
        common_joints = set(student_angles_norm.keys()) & set(ref_angles_norm.keys())

        angle_diffs = []
        for joint in sorted(common_joints):
            student_vals = np.array(student_angles_norm[joint])
            ref_vals = np.array(ref_angles_norm[joint])

            # Ensure same length
            min_len = min(len(student_vals), len(ref_vals))
            student_vals = student_vals[:min_len]
            ref_vals = ref_vals[:min_len]

            student_avg = float(np.mean(student_vals))
            ref_avg = float(np.mean(ref_vals))
            diff = student_avg - ref_avg
            abs_diff = abs(diff)

            angle_diffs.append(AngleDiff(
                joint=joint,
                student_avg=student_avg,
                pro_avg=ref_avg,
                diff=diff,
                abs_diff=abs_diff,
                significant=abs_diff > threshold,
            ))

        phase_diffs.append(PhaseDiff(
            phase_name=student_phase["name"],
            angle_diffs=angle_diffs,
        ))

    return StrokeDiff(stroke_type=stroke_type, phase_diffs=phase_diffs)
