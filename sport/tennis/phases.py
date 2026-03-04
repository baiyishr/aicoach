"""Tennis stroke phase detection.

Detects phases within individual strokes using angle thresholds and velocity.
"""

import numpy as np

from sport.base import PhaseDetector, DetectedPhase
from sport.tennis.strokes import TENNIS_STROKES
from pose.landmarks import (
    RIGHT_WRIST, LEFT_WRIST, RIGHT_SHOULDER, LEFT_SHOULDER,
    RIGHT_ELBOW, NOSE,
)
from config import PHASE_VELOCITY_SMOOTHING_WINDOW


class TennisPhaseDetector(PhaseDetector):
    """Detect phases within tennis strokes."""

    def detect_phases(
        self,
        landmarks: list[np.ndarray],
        angles: list[dict[str, float]],
        stroke_type: str,
    ) -> list[DetectedPhase]:
        n = len(landmarks)
        if n < 5:
            return []

        stroke_def = TENNIS_STROKES.get(stroke_type)
        if not stroke_def:
            return []

        if stroke_type == "serve":
            return self._detect_serve_phases(landmarks, angles, stroke_def)
        elif stroke_type in ("forehand", "backhand_1h", "backhand_2h"):
            return self._detect_groundstroke_phases(landmarks, angles, stroke_def, stroke_type)
        elif stroke_type == "volley":
            return self._detect_volley_phases(landmarks, angles, stroke_def)
        return []

    def _detect_serve_phases(
        self, landmarks, angles, stroke_def
    ) -> list[DetectedPhase]:
        n = len(landmarks)

        # Find trophy position: max shoulder angle (arm raised)
        shoulder_angles = []
        for a in angles:
            shoulder_angles.append(a.get("right_shoulder", 0) if a else 0)

        trophy_idx = int(np.argmax(shoulder_angles[:n * 3 // 4])) if n > 4 else n // 4

        # Find contact: highest wrist point (lowest y in normalized coords)
        wrist_y = [lm[RIGHT_WRIST][1] for lm in landmarks]
        # Search after trophy position
        search_start = max(trophy_idx, 1)
        contact_idx = search_start + int(np.argmin(wrist_y[search_start:]))

        # Racket drop: between trophy and contact
        racket_drop_idx = (trophy_idx + contact_idx) // 2

        # Build phases
        phase_names = [p.name for p in stroke_def.phases]
        boundaries = [0, trophy_idx, racket_drop_idx, contact_idx, n - 1]

        return self._build_phases(phase_names, boundaries)

    def _detect_groundstroke_phases(
        self, landmarks, angles, stroke_def, stroke_type
    ) -> list[DetectedPhase]:
        n = len(landmarks)

        # Determine dominant wrist
        dom_wrist = RIGHT_WRIST if stroke_type != "backhand_1h" else RIGHT_WRIST

        # Wrist velocity to find swing peak
        wrist_vel = self._compute_landmark_velocity(landmarks, dom_wrist)
        smoothed_vel = self._smooth(wrist_vel)

        # Backswing peak: max shoulder rotation (or max wrist displacement from center)
        hip_shoulder_sep = []
        for a in angles:
            hip_shoulder_sep.append(abs(a.get("hip_shoulder_separation", 0)) if a else 0)

        # Find backswing peak (max rotation in first half)
        half = n // 2
        backswing_idx = int(np.argmax(hip_shoulder_sep[:half])) if half > 0 else n // 4

        # Contact: peak wrist velocity after backswing
        search_start = max(backswing_idx, 1)
        if search_start < len(smoothed_vel):
            contact_idx = search_start + int(np.argmax(smoothed_vel[search_start:]))
        else:
            contact_idx = n * 3 // 4

        # Forward swing start: midpoint between backswing and contact
        forward_idx = (backswing_idx + contact_idx) // 2

        # Ready position: start
        # Follow through: after contact

        phase_names = [p.name for p in stroke_def.phases]
        boundaries = [0, backswing_idx, forward_idx, contact_idx, n - 1]

        return self._build_phases(phase_names, boundaries)

    def _detect_volley_phases(
        self, landmarks, angles, stroke_def
    ) -> list[DetectedPhase]:
        n = len(landmarks)

        # Simple equal-ish division for volley (compact stroke)
        split_step_end = n // 4
        prep_end = n // 2
        contact_end = n * 3 // 4

        phase_names = [p.name for p in stroke_def.phases]
        boundaries = [0, split_step_end, prep_end, contact_end, n - 1]

        return self._build_phases(phase_names, boundaries)

    def _compute_landmark_velocity(
        self, landmarks: list[np.ndarray], landmark_idx: int
    ) -> np.ndarray:
        """Compute frame-to-frame velocity of a single landmark."""
        n = len(landmarks)
        vel = np.zeros(n)
        for i in range(1, n):
            diff = landmarks[i][landmark_idx][:2] - landmarks[i - 1][landmark_idx][:2]
            vel[i] = np.linalg.norm(diff)
        return vel

    def _smooth(self, signal: np.ndarray) -> np.ndarray:
        """Apply moving average smoothing."""
        w = PHASE_VELOCITY_SMOOTHING_WINDOW
        if len(signal) <= w:
            return signal
        kernel = np.ones(w) / w
        return np.convolve(signal, kernel, mode="same")

    def _build_phases(
        self, names: list[str], boundaries: list[int]
    ) -> list[DetectedPhase]:
        """Build phase list from names and boundary indices."""
        phases = []
        # Ensure boundaries are sorted and within range
        boundaries = sorted(set(max(0, b) for b in boundaries))

        # Need len(names) + 1 boundaries
        while len(boundaries) < len(names) + 1:
            # Interpolate
            last = boundaries[-1]
            boundaries.append(last + 1)

        for i, name in enumerate(names):
            if i + 1 < len(boundaries) and boundaries[i] < boundaries[i + 1]:
                phases.append(DetectedPhase(
                    name=name,
                    start_idx=boundaries[i],
                    end_idx=boundaries[i + 1],
                ))

        return phases
