"""Detect active motion segments (strokes) in a long video.

Takes processed pose data and finds segments where the player is actively
hitting a stroke vs standing idle.

Uses adaptive thresholds based on the video's own motion statistics,
so it works for normal-speed and slow-motion videos without tuning.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

import config
from pose.detector import VideoResult
from pose.landmarks import MOTION_LANDMARKS

logger = logging.getLogger(__name__)


@dataclass
class StrokeSegment:
    """A detected segment of active motion in a video."""
    start_frame: int
    end_frame: int
    landmarks: list[np.ndarray]  # Per-frame landmarks within segment
    angles: list[dict[str, float]]  # Per-frame angles within segment

    @property
    def duration_frames(self) -> int:
        return self.end_frame - self.start_frame

    def duration_seconds(self, fps: float) -> float:
        return self.duration_frames / fps

    @property
    def mid_frame(self) -> int:
        return (self.start_frame + self.end_frame) // 2


def compute_frame_motion(
    landmarks_prev: np.ndarray,
    landmarks_curr: np.ndarray,
) -> float:
    """Compute aggregate motion between two frames using key landmarks.

    Returns:
        Average 2D displacement of motion landmarks (normalized coords).
    """
    total = 0.0
    count = 0
    for idx in MOTION_LANDMARKS:
        diff = landmarks_curr[idx][:2] - landmarks_prev[idx][:2]
        total += np.linalg.norm(diff)
        count += 1
    return total / max(count, 1)


def _compute_adaptive_threshold(motion: np.ndarray) -> float:
    """Compute a velocity threshold adapted to the video's motion profile.

    Uses the motion distribution: threshold = median of non-zero motion + 0.5 * std.
    This separates "active stroke" motion from "idle/walking" motion regardless
    of whether the video is normal speed or slow-mo.

    Returns:
        Adaptive velocity threshold.
    """
    nonzero = motion[motion > 1e-6]
    if len(nonzero) < 10:
        return config.MOTION_VELOCITY_THRESHOLD  # fallback

    median = float(np.median(nonzero))
    std = float(np.std(nonzero))

    # Threshold: above-average motion = active stroke
    # Use 75th percentile as a robust split between idle and active
    p75 = float(np.percentile(nonzero, 75))
    p25 = float(np.percentile(nonzero, 25))
    iqr = p75 - p25

    # Active motion = above median + 0.3 * IQR (catches the "fast" part of the distribution)
    threshold = median + 0.3 * iqr

    # Sanity: at least some minimum, and cap at fallback if video has very uniform motion
    threshold = max(threshold, median * 0.5)

    logger.info(
        "Adaptive threshold: %.5f (median=%.5f, p25=%.5f, p75=%.5f, iqr=%.5f, n=%d)",
        threshold, median, p25, p75, iqr, len(nonzero),
    )
    return threshold


def _compute_adaptive_idle_frames(fps: float) -> int:
    """Compute idle frame count based on effective fps.

    We want ~0.5 seconds of idle to end a segment, regardless of fps.
    """
    return max(3, int(fps * 0.5))


def _compute_adaptive_min_frames(fps: float) -> int:
    """Minimum segment length based on effective fps.

    A stroke takes at least ~0.3 seconds.
    """
    return max(3, int(fps * 0.3))


def _compute_adaptive_merge_gap(fps: float) -> int:
    """Merge segments closer than ~0.3 seconds."""
    return max(2, int(fps * 0.3))


def segment_strokes(
    video_result: VideoResult,
    velocity_threshold: float | None = None,
    idle_frames: int | None = None,
    min_segment_frames: int | None = None,
    merge_gap_frames: int | None = None,
) -> list[StrokeSegment]:
    """Segment a video into individual stroke motions.

    Uses adaptive thresholds by default: analyzes the video's motion
    distribution to set a threshold that works for both normal and
    slow-motion videos.

    Args:
        video_result: Processed video with per-frame landmarks.
        velocity_threshold: Override adaptive threshold if set.
        idle_frames: Override adaptive idle frame count if set.
        min_segment_frames: Override adaptive minimum if set.
        merge_gap_frames: Override adaptive merge gap if set.

    Returns:
        List of StrokeSegment objects.
    """
    all_landmarks = video_result.all_landmarks
    all_angles = video_result.all_angles
    n_frames = len(all_landmarks)
    effective_fps = video_result.fps

    if n_frames < 2:
        return []

    # Compute per-frame motion
    motion = np.zeros(n_frames)
    for i in range(1, n_frames):
        if all_landmarks[i] is not None and all_landmarks[i - 1] is not None:
            motion[i] = compute_frame_motion(all_landmarks[i - 1], all_landmarks[i])

    # Smooth motion signal
    kernel_size = config.PHASE_VELOCITY_SMOOTHING_WINDOW
    if kernel_size > 1 and n_frames > kernel_size:
        kernel = np.ones(kernel_size) / kernel_size
        motion = np.convolve(motion, kernel, mode="same")

    # Use adaptive thresholds unless explicitly overridden
    if velocity_threshold is None:
        velocity_threshold = _compute_adaptive_threshold(motion)
    if idle_frames is None:
        idle_frames = _compute_adaptive_idle_frames(effective_fps)
    if min_segment_frames is None:
        min_segment_frames = _compute_adaptive_min_frames(effective_fps)
    if merge_gap_frames is None:
        merge_gap_frames = _compute_adaptive_merge_gap(effective_fps)

    logger.info(
        "Segmenting: %d frames, fps=%.1f, threshold=%.5f, idle=%d, min=%d, merge=%d",
        n_frames, effective_fps, velocity_threshold, idle_frames, min_segment_frames, merge_gap_frames,
    )

    # Find active segments
    active = motion > velocity_threshold
    raw_segments = []
    in_segment = False
    start = 0
    idle_count = 0

    for i in range(n_frames):
        if active[i]:
            if not in_segment:
                in_segment = True
                start = i
                idle_count = 0
            else:
                idle_count = 0
        else:
            if in_segment:
                idle_count += 1
                if idle_count >= idle_frames:
                    end = i - idle_count + 1
                    raw_segments.append((start, end))
                    in_segment = False

    # Close any open segment
    if in_segment:
        raw_segments.append((start, n_frames - 1))

    # Merge close segments
    merged = []
    for seg in raw_segments:
        if merged and seg[0] - merged[-1][1] <= merge_gap_frames:
            merged[-1] = (merged[-1][0], seg[1])
        else:
            merged.append(seg)

    # Filter by minimum length and build StrokeSegments
    segments = []
    for start, end in merged:
        if end - start < min_segment_frames:
            continue

        seg_landmarks = []
        seg_angles = []
        for i in range(start, end + 1):
            if all_landmarks[i] is not None:
                seg_landmarks.append(all_landmarks[i])
                seg_angles.append(all_angles[i] if all_angles[i] else {})
            else:
                # Interpolate or skip — for now, use last known
                if seg_landmarks:
                    seg_landmarks.append(seg_landmarks[-1])
                    seg_angles.append(seg_angles[-1])

        if len(seg_landmarks) >= min_segment_frames:
            segments.append(StrokeSegment(
                start_frame=start,
                end_frame=end,
                landmarks=seg_landmarks,
                angles=seg_angles,
            ))

    logger.info("Found %d stroke segments", len(segments))
    return segments
