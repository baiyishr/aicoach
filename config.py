"""Application constants and configuration."""

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent
MODELS_DIR = PROJECT_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"
REFERENCES_DIR = DATA_DIR / "references"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "sessions.db"

# MediaPipe
MEDIAPIPE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task"
)
MEDIAPIPE_MODEL_PATH = MODELS_DIR / "pose_landmarker_heavy.task"

# Detection thresholds
MOTION_VELOCITY_THRESHOLD = 0.015  # Normalized velocity to detect active motion
MOTION_IDLE_FRAMES = 10  # Frames below threshold to end a segment
MOTION_MIN_SEGMENT_FRAMES = 15  # Minimum frames for a valid stroke segment
MOTION_MERGE_GAP_FRAMES = 8  # Merge segments closer than this

# Classification confidence
MIN_CLASSIFICATION_CONFIDENCE = 0.3

# Phase detection
PHASE_VELOCITY_SMOOTHING_WINDOW = 5  # Frames for velocity smoothing

# Comparison
SIGNIFICANT_ANGLE_DIFF = 10.0  # Degrees — flag differences above this
PHASE_NORMALIZATION_POINTS = 50  # Number of points per phase after normalization

# LLM
OPENROUTER_API_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"
LLM_MAX_TOKENS = 1500
LLM_TEMPERATURE = 0.7

# Video processing
TARGET_FPS = 30  # Resample videos to this FPS if needed
MAX_VIDEO_DURATION_SECONDS = 600  # 10 minutes max

# Supported sports (extensible)
SUPPORTED_SPORTS = ["tennis"]
DEFAULT_SPORT = "tennis"


def ensure_dirs():
    """Create required directories if they don't exist."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)


def get_openrouter_api_key() -> str | None:
    """Get OpenRouter API key from environment or Streamlit secrets."""
    return os.environ.get("OPENROUTER_API_KEY")
