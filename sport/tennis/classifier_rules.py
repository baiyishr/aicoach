"""Tennis-specific stroke classification rules.

Classifies a StrokeSegment as serve, forehand, backhand (1H/2H), or volley
based on landmark positions and motion patterns.
"""

import numpy as np

from pose.landmarks import (
    LEFT_WRIST, RIGHT_WRIST,
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_ELBOW, RIGHT_ELBOW,
    LEFT_HIP, RIGHT_HIP,
    NOSE,
)


def classify_tennis_stroke(
    landmarks: list[np.ndarray],
    angles: list[dict[str, float]],
    dominant_side: str = "right",
) -> tuple[str, float]:
    """Classify a stroke segment into a tennis stroke type.

    Args:
        landmarks: Per-frame landmarks within the segment.
        angles: Per-frame joint angles within the segment.
        dominant_side: "right" or "left" for handedness.

    Returns:
        (stroke_type, confidence) where stroke_type is one of:
        "serve", "forehand", "backhand_1h", "backhand_2h", "volley"
    """
    if len(landmarks) < 5:
        return "unknown", 0.0

    # Determine dominant/non-dominant indices
    if dominant_side == "right":
        dom_wrist = RIGHT_WRIST
        dom_shoulder = RIGHT_SHOULDER
        dom_elbow = RIGHT_ELBOW
        non_dom_wrist = LEFT_WRIST
    else:
        dom_wrist = LEFT_WRIST
        dom_shoulder = LEFT_SHOULDER
        dom_elbow = LEFT_ELBOW
        non_dom_wrist = RIGHT_WRIST

    # Extract key features
    n = len(landmarks)

    # Feature 1: Max wrist height (relative to nose)
    max_wrist_height = 0.0
    for lm in landmarks:
        nose_y = lm[NOSE][1]
        wrist_y = lm[dom_wrist][1]
        # In normalized coords, y=0 is top, y=1 is bottom
        height_above_nose = nose_y - wrist_y
        max_wrist_height = max(max_wrist_height, height_above_nose)

    # Feature 2: Non-dominant wrist goes up (toss arm for serve)
    max_non_dom_height = 0.0
    for lm in landmarks:
        nose_y = lm[NOSE][1]
        height = nose_y - lm[non_dom_wrist][1]
        max_non_dom_height = max(max_non_dom_height, height)

    # Feature 3: Segment duration (short = volley)
    duration = n

    # Feature 4: Wrist distance between hands (close = 2H backhand)
    min_wrist_dist = float("inf")
    for lm in landmarks:
        dist = np.linalg.norm(lm[dom_wrist][:2] - lm[non_dom_wrist][:2])
        min_wrist_dist = min(min_wrist_dist, dist)

    # Feature 5: Dominant wrist swing direction
    # Positive x_delta means swing goes left-to-right (for right-hander: forehand)
    # Negative x_delta means swing goes right-to-left (for right-hander: backhand)
    contact_idx = n // 2  # Approximate contact point at middle of segment
    start_x = landmarks[0][dom_wrist][0]
    end_x = landmarks[min(contact_idx + 5, n - 1)][dom_wrist][0]
    x_delta = end_x - start_x

    # Feature 6: Hip rotation magnitude
    max_hip_rotation = 0.0
    for a in angles:
        if a and "hip_shoulder_separation" in a:
            max_hip_rotation = max(max_hip_rotation, abs(a["hip_shoulder_separation"]))

    # Feature 7: Max shoulder angle (arm extension)
    max_shoulder_angle = 0.0
    for a in angles:
        if a:
            key = f"{dominant_side}_shoulder"
            if key in a:
                max_shoulder_angle = max(max_shoulder_angle, a[key])

    # Classification logic
    scores = {
        "serve": 0.0,
        "forehand": 0.0,
        "backhand_1h": 0.0,
        "backhand_2h": 0.0,
        "volley": 0.0,
    }

    # Serve: dominant wrist goes high above head + non-dominant arm rises (toss)
    if max_wrist_height > 0.1:
        scores["serve"] += 0.4
    if max_wrist_height > 0.15:
        scores["serve"] += 0.2
    if max_non_dom_height > 0.05:
        scores["serve"] += 0.2
    if max_shoulder_angle > 140:
        scores["serve"] += 0.2

    # Volley: short duration, small hip rotation, compact motion
    if duration < 25:
        scores["volley"] += 0.3
    if max_hip_rotation < 15:
        scores["volley"] += 0.3
    if max_shoulder_angle < 90:
        scores["volley"] += 0.2

    # Forehand vs backhand: swing direction
    if dominant_side == "right":
        # Right-hander forehand: wrist moves left-to-right (positive x in normalized)
        if x_delta > 0.02:
            scores["forehand"] += 0.4
        elif x_delta < -0.02:
            scores["backhand_1h"] += 0.3
            scores["backhand_2h"] += 0.3
    else:
        if x_delta < -0.02:
            scores["forehand"] += 0.4
        elif x_delta > 0.02:
            scores["backhand_1h"] += 0.3
            scores["backhand_2h"] += 0.3

    # Hip rotation indicates groundstroke, not volley
    if max_hip_rotation > 20:
        scores["forehand"] += 0.2
        scores["backhand_1h"] += 0.1
        scores["backhand_2h"] += 0.1
        scores["volley"] -= 0.2

    # 2H backhand: both wrists close together during swing
    if min_wrist_dist < 0.05:
        scores["backhand_2h"] += 0.3
        scores["backhand_1h"] -= 0.2
    else:
        scores["backhand_1h"] += 0.1
        scores["backhand_2h"] -= 0.1

    # Suppress serve if wrist doesn't go above head
    if max_wrist_height < 0.05:
        scores["serve"] = 0.0

    # Pick highest score
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    # Normalize confidence to [0, 1]
    total = sum(max(0, s) for s in scores.values())
    confidence = best_score / total if total > 0 else 0.0

    return best_type, confidence
