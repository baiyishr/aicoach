"""Phase-based temporal alignment for stroke comparison.

Maps student's stroke phases to normalized time [0, 1] per phase,
enabling direct comparison with the pro reference profile.
"""

import numpy as np

from sport.base import DetectedPhase, ReferenceProfile
from sport.registry import get_phase_detector
from comparison.reference import normalize_phase_angles
from config import PHASE_NORMALIZATION_POINTS


def align_student_stroke(
    landmarks: list[np.ndarray],
    angles: list[dict[str, float]],
    stroke_type: str,
    sport: str = "tennis",
) -> list[dict]:
    """Align a student's stroke by detecting and normalizing phases.

    Args:
        landmarks: Per-frame landmarks for the stroke.
        angles: Per-frame joint angles.
        stroke_type: Type of stroke.
        sport: Sport name.

    Returns:
        List of dicts: [{name, normalized_angles: {joint: [values]}}]
    """
    phase_detector = get_phase_detector(sport)
    if not phase_detector:
        return []

    phases = phase_detector.detect_phases(landmarks, angles, stroke_type)

    result = []
    for phase in phases:
        normalized = normalize_phase_angles(
            angles, phase, num_points=PHASE_NORMALIZATION_POINTS
        )
        result.append({
            "name": phase.name,
            "normalized_angles": normalized,
        })

    return result


def align_phases(
    student_phases: list[dict],
    reference: ReferenceProfile,
) -> list[tuple[dict, dict | None]]:
    """Match student phases to reference phases by name.

    Args:
        student_phases: Student's normalized phase data.
        reference: Pro reference profile.

    Returns:
        List of (student_phase, reference_phase) tuples.
        reference_phase is None if no matching phase found.
    """
    ref_by_name = {p["name"]: p for p in reference.phases}

    aligned = []
    for sp in student_phases:
        rp = ref_by_name.get(sp["name"])
        aligned.append((sp, rp))

    return aligned
