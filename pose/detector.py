"""MediaPipe Pose Landmarker wrapper for video processing."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import requests

import config
from pose.angles import landmarks_to_array, compute_joint_angles

logger = logging.getLogger(__name__)


@dataclass
class FrameResult:
    """Pose detection result for a single frame."""
    frame_idx: int
    timestamp_ms: float
    landmarks: np.ndarray | None  # (33, 3) or None if no detection
    angles: dict[str, float] | None
    all_poses: list[np.ndarray] = field(default_factory=list)  # All detected poses


@dataclass
class VideoResult:
    """Full video pose detection results."""
    video_path: str
    fps: float
    total_frames: int
    width: int
    height: int
    frame_step: int = 1  # How many source frames per processed frame
    frames: list[FrameResult] = field(default_factory=list)

    @property
    def landmarks_sequence(self) -> list[np.ndarray]:
        """Get list of landmark arrays (only detected frames)."""
        return [f.landmarks for f in self.frames if f.landmarks is not None]

    @property
    def all_landmarks(self) -> list[np.ndarray | None]:
        """Get landmarks for all frames (None for undetected)."""
        return [f.landmarks for f in self.frames]

    @property
    def all_angles(self) -> list[dict[str, float] | None]:
        """Get angles for all frames."""
        return [f.angles for f in self.frames]

    def get_frame_landmarks(self, frame_idx: int) -> np.ndarray | None:
        """Get landmarks for a specific frame index."""
        if 0 <= frame_idx < len(self.frames):
            return self.frames[frame_idx].landmarks
        return None


def ensure_model() -> Path:
    """Download the MediaPipe pose model if not present.

    Returns:
        Path to the model file.
    """
    config.ensure_dirs()
    model_path = config.MEDIAPIPE_MODEL_PATH

    if model_path.exists():
        return model_path

    logger.info("Downloading MediaPipe pose model...")
    response = requests.get(config.MEDIAPIPE_MODEL_URL, stream=True, timeout=60)
    response.raise_for_status()

    with open(model_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    logger.info("Model downloaded to %s", model_path)
    return model_path


def _pick_closest_pose(
    poses: list[np.ndarray],
    anchor: np.ndarray,
) -> int:
    """Pick the pose closest to an anchor position (by hip-center distance).

    Args:
        poses: List of landmark arrays (33, 3).
        anchor: Previous frame's landmarks for the tracked person.

    Returns:
        Index of the closest pose.
    """
    from pose.landmarks import LEFT_HIP, RIGHT_HIP

    anchor_center = (anchor[LEFT_HIP][:2] + anchor[RIGHT_HIP][:2]) / 2
    best_idx = 0
    best_dist = float("inf")

    for i, pose in enumerate(poses):
        center = (pose[LEFT_HIP][:2] + pose[RIGHT_HIP][:2]) / 2
        dist = float(np.linalg.norm(center - anchor_center))
        if dist < best_dist:
            best_dist = dist
            best_idx = i

    return best_idx


TARGET_PROCESS_FPS = 15  # We don't need every frame — 15fps is plenty for stroke detection
MAX_PROCESS_HEIGHT = 720  # Downscale to this height before MediaPipe


def process_video(
    video_path: str,
    progress_callback=None,
    track_person_idx: int | None = None,
) -> VideoResult:
    """Process a video file and extract pose landmarks.

    Optimizations applied:
      - Frame skipping: processes at ~15fps regardless of source fps
      - Downscaling: resizes frames to 720p height before MediaPipe

    Args:
        video_path: Path to the video file.
        progress_callback: Optional callable(current_frame, total_frames).
        track_person_idx: If set, detect multiple poses and track the person
            initially at this index (0-based) across frames using position
            continuity. If None, detect one pose (original behavior).

    Returns:
        VideoResult with per-frame landmarks and angles.
    """
    model_path = ensure_model()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if fps <= 0:
        fps = 30.0
    if total_frames <= 0:
        total_frames = 0

    # Frame skip: e.g., 60fps video → skip every other frame to get ~15fps
    frame_step = max(1, round(fps / TARGET_PROCESS_FPS))
    effective_fps = fps / frame_step
    frames_to_process = total_frames // frame_step if total_frames > 0 else 0

    logger.info(
        "Processing %s: %dfps source, step=%d (effective %.1ffps), ~%d frames to process, %dx%d",
        video_path, int(fps), frame_step, effective_fps, frames_to_process, width, height,
    )

    # Downscale factor
    scale = min(1.0, MAX_PROCESS_HEIGHT / height) if height > MAX_PROCESS_HEIGHT else 1.0

    multi_person = track_person_idx is not None
    num_poses = 5 if multi_person else 1

    result = VideoResult(
        video_path=video_path,
        fps=effective_fps,
        total_frames=total_frames,
        width=width,
        height=height,
        frame_step=frame_step,
    )

    # Use MediaPipe PoseLandmarker
    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=VisionRunningMode.VIDEO,
        num_poses=num_poses,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    prev_tracked = None  # Previous frame's tracked landmarks for continuity

    with PoseLandmarker.create_from_options(options) as landmarker:
        frame_idx = 0  # Source frame counter
        processed_idx = 0  # Processed frame counter
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Skip frames for speed
            if frame_idx % frame_step != 0:
                frame_idx += 1
                continue

            timestamp_ms = int(frame_idx * 1000.0 / fps)

            # Downscale for speed
            if scale < 1.0:
                small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            else:
                small = frame

            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            detection = landmarker.detect_for_video(mp_image, timestamp_ms)

            landmarks = None
            angles = None
            all_poses = []

            if detection.pose_landmarks and len(detection.pose_landmarks) > 0:
                all_poses = [landmarks_to_array(p) for p in detection.pose_landmarks]

                if multi_person and len(all_poses) > 1:
                    if prev_tracked is not None:
                        chosen = _pick_closest_pose(all_poses, prev_tracked)
                    else:
                        chosen = min(track_person_idx, len(all_poses) - 1)
                    landmarks = all_poses[chosen]
                else:
                    if multi_person and track_person_idx is not None:
                        chosen = min(track_person_idx, len(all_poses) - 1)
                        landmarks = all_poses[chosen]
                    else:
                        landmarks = all_poses[0]

                prev_tracked = landmarks
                angles = compute_joint_angles(landmarks)

            result.frames.append(FrameResult(
                frame_idx=frame_idx,  # Store original frame index for thumbnail extraction
                timestamp_ms=float(timestamp_ms),
                landmarks=landmarks,
                angles=angles,
                all_poses=all_poses,
            ))

            processed_idx += 1
            frame_idx += 1
            if progress_callback and processed_idx % 10 == 0:
                progress_callback(processed_idx, frames_to_process)

    cap.release()
    result.total_frames = processed_idx
    logger.info("Processed %d frames (from %d source frames)", processed_idx, frame_idx)
    return result


def preview_people(video_path: str, frame_idx: int = 30) -> dict:
    """Detect all people in a single frame for player selection.

    Args:
        video_path: Path to the video file.
        frame_idx: Which frame to sample (default: frame 30 = ~1 second in).

    Returns:
        Dict with 'frame' (BGR ndarray), 'poses' (list of (33,3) arrays),
        and 'centers' (list of (x, y) hip-center positions, normalized).
    """
    from pose.landmarks import LEFT_HIP, RIGHT_HIP

    model_path = ensure_model()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Clamp frame_idx
    frame_idx = min(frame_idx, max(total_frames - 1, 0))

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise ValueError("Cannot read frame from video")

    timestamp_ms = int(frame_idx * 1000.0 / max(fps, 1))

    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=VisionRunningMode.IMAGE,
        num_poses=5,
        min_pose_detection_confidence=0.3,
        min_pose_presence_confidence=0.3,
    )

    with PoseLandmarker.create_from_options(options) as landmarker:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection = landmarker.detect(mp_image)

    poses = []
    centers = []
    if detection.pose_landmarks:
        for p in detection.pose_landmarks:
            arr = landmarks_to_array(p)
            poses.append(arr)
            center = ((arr[LEFT_HIP][:2] + arr[RIGHT_HIP][:2]) / 2).tolist()
            centers.append(center)

    return {
        "frame": frame,
        "poses": poses,
        "centers": centers,
    }


def get_video_frame(video_path: str, frame_idx: int) -> np.ndarray | None:
    """Extract a single frame from a video.

    Args:
        video_path: Path to the video file.
        frame_idx: Frame index to extract.

    Returns:
        BGR frame array or None.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()

    return frame if ret else None


def get_video_info(video_path: str) -> dict:
    """Get basic video information.

    Returns:
        Dict with fps, total_frames, width, height, duration_seconds.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    info["duration_seconds"] = info["total_frames"] / max(info["fps"], 1)
    cap.release()
    return info
