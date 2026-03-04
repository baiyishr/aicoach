"""Joint angle calculation from pose landmarks."""

import numpy as np


def angle_between_points(
    a: np.ndarray, b: np.ndarray, c: np.ndarray
) -> float:
    """Calculate angle at point b formed by points a-b-c.

    Args:
        a: First point (x, y, z) or (x, y).
        b: Vertex point.
        c: Third point.

    Returns:
        Angle in degrees [0, 180].
    """
    ba = a - b
    bc = c - b
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def angle_2d(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Calculate angle using only x, y coordinates (ignoring depth)."""
    return angle_between_points(a[:2], b[:2], c[:2])


def landmarks_to_array(landmarks: list) -> np.ndarray:
    """Convert MediaPipe landmark list to numpy array (N, 3).

    Args:
        landmarks: List of landmarks with x, y, z attributes.

    Returns:
        Array of shape (num_landmarks, 3).
    """
    return np.array([[lm.x, lm.y, lm.z] for lm in landmarks])


def compute_joint_angles(landmarks: np.ndarray) -> dict[str, float]:
    """Compute key joint angles from landmark positions.

    Args:
        landmarks: Array of shape (33, 3) with normalized coordinates.

    Returns:
        Dict mapping angle name to value in degrees.
    """
    from pose.landmarks import (
        LEFT_SHOULDER, RIGHT_SHOULDER,
        LEFT_ELBOW, RIGHT_ELBOW,
        LEFT_WRIST, RIGHT_WRIST,
        LEFT_HIP, RIGHT_HIP,
        LEFT_KNEE, RIGHT_KNEE,
        LEFT_ANKLE, RIGHT_ANKLE,
    )

    angles = {}

    # Elbow angles
    angles["left_elbow"] = angle_between_points(
        landmarks[LEFT_SHOULDER], landmarks[LEFT_ELBOW], landmarks[LEFT_WRIST]
    )
    angles["right_elbow"] = angle_between_points(
        landmarks[RIGHT_SHOULDER], landmarks[RIGHT_ELBOW], landmarks[RIGHT_WRIST]
    )

    # Shoulder angles (arm raise)
    angles["left_shoulder"] = angle_between_points(
        landmarks[LEFT_HIP], landmarks[LEFT_SHOULDER], landmarks[LEFT_ELBOW]
    )
    angles["right_shoulder"] = angle_between_points(
        landmarks[RIGHT_HIP], landmarks[RIGHT_SHOULDER], landmarks[RIGHT_ELBOW]
    )

    # Hip angles
    angles["left_hip"] = angle_between_points(
        landmarks[LEFT_SHOULDER], landmarks[LEFT_HIP], landmarks[LEFT_KNEE]
    )
    angles["right_hip"] = angle_between_points(
        landmarks[RIGHT_SHOULDER], landmarks[RIGHT_HIP], landmarks[RIGHT_KNEE]
    )

    # Knee angles
    angles["left_knee"] = angle_between_points(
        landmarks[LEFT_HIP], landmarks[LEFT_KNEE], landmarks[LEFT_ANKLE]
    )
    angles["right_knee"] = angle_between_points(
        landmarks[RIGHT_HIP], landmarks[RIGHT_KNEE], landmarks[RIGHT_ANKLE]
    )

    # Shoulder rotation (hip-shoulder separation in horizontal plane)
    left_hip = landmarks[LEFT_HIP]
    right_hip = landmarks[RIGHT_HIP]
    left_shoulder = landmarks[LEFT_SHOULDER]
    right_shoulder = landmarks[RIGHT_SHOULDER]

    hip_vec = right_hip[:2] - left_hip[:2]
    shoulder_vec = right_shoulder[:2] - left_shoulder[:2]

    hip_angle = np.arctan2(hip_vec[1], hip_vec[0])
    shoulder_angle = np.arctan2(shoulder_vec[1], shoulder_vec[0])
    angles["hip_shoulder_separation"] = float(
        np.degrees(shoulder_angle - hip_angle)
    )

    return angles


def compute_velocity(
    landmarks_seq: list[np.ndarray], fps: float = 30.0
) -> list[dict[str, float]]:
    """Compute per-frame velocity of key landmarks.

    Args:
        landmarks_seq: List of landmark arrays, each (33, 3).
        fps: Video framerate.

    Returns:
        List of dicts mapping landmark index to velocity (normalized units/second).
    """
    from pose.landmarks import MOTION_LANDMARKS

    velocities = []
    dt = 1.0 / fps

    for i in range(len(landmarks_seq)):
        frame_vel = {}
        if i == 0:
            for idx in MOTION_LANDMARKS:
                frame_vel[idx] = 0.0
        else:
            for idx in MOTION_LANDMARKS:
                diff = landmarks_seq[i][idx] - landmarks_seq[i - 1][idx]
                speed = float(np.linalg.norm(diff[:2])) / dt  # 2D velocity
                frame_vel[idx] = speed
        velocities.append(frame_vel)

    return velocities
