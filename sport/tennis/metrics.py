"""Tennis-specific metrics extraction from landmarks and angles."""

import numpy as np

from pose.landmarks import (
    RIGHT_WRIST, LEFT_WRIST, NOSE,
    RIGHT_SHOULDER, LEFT_SHOULDER,
    RIGHT_HIP, LEFT_HIP,
    RIGHT_KNEE, LEFT_KNEE,
    RIGHT_ELBOW,
)


def extract_serve_metrics(
    landmarks: list[np.ndarray],
    angles: list[dict[str, float]],
) -> dict[str, float]:
    """Extract serve-specific metrics.

    Returns:
        Dict of metric name to value.
    """
    metrics = {}

    # Contact height relative to body height
    nose_y_values = [lm[NOSE][1] for lm in landmarks]
    wrist_y_values = [lm[RIGHT_WRIST][1] for lm in landmarks]
    min_wrist_y = min(wrist_y_values)  # Highest point
    avg_nose_y = np.mean(nose_y_values)

    # Approximate body height using hip-to-nose distance
    hip_y = np.mean([lm[RIGHT_HIP][1] for lm in landmarks])
    body_height = abs(hip_y - avg_nose_y)
    if body_height > 0:
        metrics["contact_height_ratio"] = abs(avg_nose_y - min_wrist_y) / body_height

    # Max knee bend (lower angle = more bend)
    knee_angles = [a.get("right_knee", 180) for a in angles if a]
    if knee_angles:
        metrics["min_knee_angle"] = min(knee_angles)

    # Max shoulder rotation
    sep_values = [abs(a.get("hip_shoulder_separation", 0)) for a in angles if a]
    if sep_values:
        metrics["max_hip_shoulder_separation"] = max(sep_values)

    # Elbow angle at trophy (max shoulder angle frame)
    shoulder_angles = [a.get("right_shoulder", 0) for a in angles if a]
    if shoulder_angles:
        trophy_idx = int(np.argmax(shoulder_angles))
        if trophy_idx < len(angles) and angles[trophy_idx]:
            metrics["elbow_at_trophy"] = angles[trophy_idx].get("right_elbow", 0)

    return metrics


def extract_groundstroke_metrics(
    landmarks: list[np.ndarray],
    angles: list[dict[str, float]],
    stroke_type: str,
) -> dict[str, float]:
    """Extract forehand/backhand metrics."""
    metrics = {}

    # Hip rotation
    sep_values = [abs(a.get("hip_shoulder_separation", 0)) for a in angles if a]
    if sep_values:
        metrics["max_hip_shoulder_separation"] = max(sep_values)

    # Shoulder turn
    shoulder_angles = [a.get("right_shoulder", 0) for a in angles if a]
    if shoulder_angles:
        metrics["max_shoulder_angle"] = max(shoulder_angles)

    # Elbow angle at contact (peak wrist velocity frame)
    wrist_vel = []
    for i in range(1, len(landmarks)):
        diff = landmarks[i][RIGHT_WRIST][:2] - landmarks[i - 1][RIGHT_WRIST][:2]
        wrist_vel.append(np.linalg.norm(diff))

    if wrist_vel:
        contact_idx = int(np.argmax(wrist_vel)) + 1
        if contact_idx < len(angles) and angles[contact_idx]:
            metrics["elbow_at_contact"] = angles[contact_idx].get("right_elbow", 0)

    # Knee bend during stroke
    knee_angles = [a.get("right_knee", 180) for a in angles if a]
    if knee_angles:
        metrics["min_knee_angle"] = min(knee_angles)

    return metrics


def extract_metrics(
    landmarks: list[np.ndarray],
    angles: list[dict[str, float]],
    stroke_type: str,
) -> dict[str, float]:
    """Extract metrics based on stroke type."""
    if stroke_type == "serve":
        return extract_serve_metrics(landmarks, angles)
    elif stroke_type in ("forehand", "backhand_1h", "backhand_2h"):
        return extract_groundstroke_metrics(landmarks, angles, stroke_type)
    elif stroke_type == "volley":
        return extract_groundstroke_metrics(landmarks, angles, stroke_type)
    return {}
