"""Build reference profiles from confirmed pro strokes.

Takes multiple confirmed strokes of the same type and builds an averaged
reference profile with per-phase normalized angle data.
"""

import numpy as np

from sport.base import ReferenceProfile, DetectedPhase
from sport.registry import get_phase_detector
from detection.reviewer import ReviewableStroke
from config import PHASE_NORMALIZATION_POINTS


def normalize_phase_angles(
    angles: list[dict[str, float]],
    phase: DetectedPhase,
    num_points: int = PHASE_NORMALIZATION_POINTS,
) -> dict[str, list[float]]:
    """Normalize angle data within a phase to a fixed number of points.

    Args:
        angles: Full stroke angle data.
        phase: The phase boundaries.
        num_points: Number of output points.

    Returns:
        Dict mapping joint name to list of interpolated angle values.
    """
    start = phase.start_idx
    end = phase.end_idx
    phase_angles = angles[start:end]

    if not phase_angles:
        return {}

    # Collect all joint names
    all_joints = set()
    for a in phase_angles:
        if a:
            all_joints.update(a.keys())

    result = {}
    for joint in all_joints:
        values = []
        for a in phase_angles:
            values.append(a.get(joint, 0.0) if a else 0.0)

        if len(values) < 2:
            result[joint] = values * num_points
            continue

        # Interpolate to num_points
        x_orig = np.linspace(0, 1, len(values))
        x_new = np.linspace(0, 1, num_points)
        result[joint] = np.interp(x_new, x_orig, values).tolist()

    return result


def build_reference_profile(
    strokes: list[ReviewableStroke],
    stroke_type: str,
    sport: str = "tennis",
) -> ReferenceProfile | None:
    """Build a reference profile by averaging multiple confirmed strokes.

    Args:
        strokes: Confirmed strokes of the same type.
        stroke_type: The stroke type.
        sport: Sport name.

    Returns:
        ReferenceProfile or None if insufficient data.
    """
    if not strokes:
        return None

    phase_detector = get_phase_detector(sport)
    if not phase_detector:
        return None

    # Detect phases for each stroke and normalize angles
    all_phase_data: dict[str, list[dict[str, list[float]]]] = {}

    for stroke in strokes:
        seg = stroke.classified.segment
        phases = phase_detector.detect_phases(seg.landmarks, seg.angles, stroke_type)

        for phase in phases:
            normalized = normalize_phase_angles(seg.angles, phase)
            if phase.name not in all_phase_data:
                all_phase_data[phase.name] = []
            all_phase_data[phase.name].append(normalized)

    # Average across all strokes for each phase
    averaged_phases = []
    for phase_name, samples in all_phase_data.items():
        if not samples:
            continue

        # Collect all joints across samples
        all_joints = set()
        for s in samples:
            all_joints.update(s.keys())

        averaged_angles = {}
        for joint in all_joints:
            joint_values = []
            for s in samples:
                if joint in s:
                    joint_values.append(s[joint])

            if joint_values:
                # Average the arrays element-wise
                averaged_angles[joint] = np.mean(joint_values, axis=0).tolist()

        averaged_phases.append({
            "name": phase_name,
            "normalized_angles": averaged_angles,
        })

    return ReferenceProfile(
        stroke_type=stroke_type,
        sport=sport,
        num_samples=len(strokes),
        phases=averaged_phases,
    )
