"""Skeleton overlay drawing on video frames."""

import cv2
import numpy as np

from pose.landmarks import POSE_CONNECTIONS, NUM_LANDMARKS


# Colors (BGR)
LANDMARK_COLOR = (0, 255, 0)  # Green
CONNECTION_COLOR = (0, 200, 200)  # Yellow-ish
HIGHLIGHT_COLOR = (0, 0, 255)  # Red
LANDMARK_RADIUS = 4
CONNECTION_THICKNESS = 2


def draw_skeleton(
    frame: np.ndarray,
    landmarks: np.ndarray,
    color: tuple[int, int, int] = CONNECTION_COLOR,
    landmark_color: tuple[int, int, int] = LANDMARK_COLOR,
    highlight_indices: list[int] | None = None,
) -> np.ndarray:
    """Draw pose skeleton overlay on a frame.

    Args:
        frame: BGR image (H, W, 3).
        landmarks: Normalized landmark positions (33, 3) in [0, 1].
        color: Connection line color.
        landmark_color: Joint dot color.
        highlight_indices: Landmark indices to highlight in red.

    Returns:
        Frame with skeleton drawn.
    """
    h, w = frame.shape[:2]
    overlay = frame.copy()

    # Convert normalized coords to pixel coords
    points = {}
    for i in range(min(NUM_LANDMARKS, len(landmarks))):
        x = int(landmarks[i][0] * w)
        y = int(landmarks[i][1] * h)
        points[i] = (x, y)

    # Draw connections
    for start, end in POSE_CONNECTIONS:
        if start in points and end in points:
            cv2.line(overlay, points[start], points[end], color, CONNECTION_THICKNESS)

    # Draw landmarks
    for i, pt in points.items():
        c = HIGHLIGHT_COLOR if (highlight_indices and i in highlight_indices) else landmark_color
        cv2.circle(overlay, pt, LANDMARK_RADIUS, c, -1)

    return overlay


def draw_side_by_side(
    frame_a: np.ndarray,
    landmarks_a: np.ndarray,
    frame_b: np.ndarray,
    landmarks_b: np.ndarray,
    label_a: str = "Pro",
    label_b: str = "Student",
) -> np.ndarray:
    """Draw two skeletons side by side for comparison.

    Args:
        frame_a: First video frame.
        landmarks_a: First set of landmarks.
        frame_b: Second video frame.
        landmarks_b: Second set of landmarks.
        label_a: Label for first frame.
        label_b: Label for second frame.

    Returns:
        Combined frame with both skeletons.
    """
    skel_a = draw_skeleton(frame_a, landmarks_a)
    skel_b = draw_skeleton(frame_b, landmarks_b, color=(200, 200, 0), landmark_color=(255, 0, 0))

    # Resize to same height
    h = max(skel_a.shape[0], skel_b.shape[0])
    if skel_a.shape[0] != h:
        scale = h / skel_a.shape[0]
        skel_a = cv2.resize(skel_a, (int(skel_a.shape[1] * scale), h))
    if skel_b.shape[0] != h:
        scale = h / skel_b.shape[0]
        skel_b = cv2.resize(skel_b, (int(skel_b.shape[1] * scale), h))

    # Add labels
    cv2.putText(skel_a, label_a, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(skel_b, label_b, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    return np.hstack([skel_a, skel_b])


def create_thumbnail(
    frame: np.ndarray,
    landmarks: np.ndarray | None = None,
    size: tuple[int, int] = (160, 120),
) -> np.ndarray:
    """Create a small thumbnail of a frame with optional skeleton.

    Args:
        frame: BGR image.
        landmarks: Optional landmarks to draw.
        size: Output size (width, height).

    Returns:
        Thumbnail image.
    """
    if landmarks is not None:
        frame = draw_skeleton(frame, landmarks)
    return cv2.resize(frame, size)
