<p align="center">
  <img src="https://img.shields.io/badge/sport-tennis-22c55e?style=for-the-badge" alt="Tennis">
  <img src="https://img.shields.io/badge/AI-pose%20analysis-3b82f6?style=for-the-badge" alt="Pose Analysis">
  <img src="https://img.shields.io/badge/video-stays%20local-f59e0b?style=for-the-badge" alt="Privacy">
</p>

# 🎾 AI Coach

**Analyze your tennis strokes against pro players and get AI-powered coaching feedback — all without uploading a single frame.**

AI Coach uses MediaPipe pose estimation running entirely in your browser to extract body landmarks from video, then compares your form against pro reference profiles phase-by-phase. An LLM generates personalized coaching tips based on the biomechanical differences.

---

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│  Browser                                                │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  Video    │───▶│  MediaPipe   │───▶│  Landmarks    │  │
│  │  (local)  │    │  WASM + GPU  │    │  + Angles     │  │
│  └──────────┘    └──────────────┘    └───────┬───────┘  │
│                                              │ JSON     │
└──────────────────────────────────────────────┼──────────┘
                                               ▼
┌──────────────────────────────────────────────────────────┐
│  Server (Python)                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │  Segment   │─▶│  Classify  │─▶│  Compare vs Pro    │  │
│  │  Strokes   │  │  Stroke    │  │  Phase-by-Phase    │  │
│  └────────────┘  └────────────┘  └─────────┬──────────┘  │
│                                            ▼             │
│                                  ┌────────────────────┐  │
│                                  │  LLM Coaching      │  │
│                                  │  (OpenRouter API)  │  │
│                                  └────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Video never leaves your machine.** Only numeric landmark coordinates are sent to the server.

---

## Features

- **Browser-side pose detection** — MediaPipe runs in WebAssembly with GPU acceleration, no Python CV dependencies needed at runtime
- **Multi-person tracking** — select which player to analyze when multiple people are in frame
- **Automatic stroke detection** — segments continuous video into individual strokes using adaptive motion thresholds
- **Stroke classification** — identifies serves, forehands, one-handed backhands, two-handed backhands, and volleys
- **Phase-by-phase comparison** — aligns student stroke phases (trophy, backswing, contact, follow-through, etc.) against pro reference profiles
- **Interactive charts** — visualize joint angle differences across each phase with Chart.js
- **AI coaching feedback** — LLM analyzes the biomechanical report and generates actionable practice tips
- **YouTube import** — paste a URL to download pro or student videos directly
- **Session history** — save and review past coaching sessions
- **Privacy-first** — video stays in the browser; server only sees landmark numbers

---

## Quick Start

### Prerequisites

- Python 3.11+
- An [OpenRouter](https://openrouter.ai/keys) API key (for AI coaching feedback)
- yt-dlp (optional, for YouTube downloads): `pip install yt-dlp`

### Install & Run

```bash
git clone https://github.com/baiyishr/aicoach.git
cd aicoach
pip install -r requirements.txt
python app.py
```

Open **http://localhost:8000** in your browser.

### First Time Setup

1. Go to **Settings** → paste your OpenRouter API key
2. Go to **References** → import a pro tennis video → detect strokes → build reference profiles
3. Go to **Analyze** → import a student video → detect strokes → compare against the pro → get AI coaching

---

## Project Structure

```
aicoach/
├── static/
│   ├── pose-engine.js      # MediaPipe JS wrapper, angle computation, skeleton drawing
│   ├── app.js               # Frontend logic — local video processing, UI state
│   ├── index.html            # Single-page app
│   └── style.css             # UI styling
├── server.py                 # FastAPI backend — landmarks processing, comparison, coaching
├── config.py                 # App configuration and constants
├── pose/
│   ├── detector.py           # MediaPipe Python wrapper (used for reference, not at runtime)
│   ├── angles.py             # Joint angle computation
│   ├── landmarks.py          # MediaPipe landmark constants
│   └── drawing.py            # Skeleton overlay drawing
├── detection/
│   ├── segmenter.py          # Adaptive motion segmentation
│   ├── classifier.py         # Stroke classification dispatcher
│   └── reviewer.py           # Stroke review data structures
├── comparison/
│   ├── reference.py          # Build averaged pro reference profiles
│   ├── alignment.py          # Phase detection and alignment
│   ├── diff.py               # Angle difference computation
│   └── report.py             # Text report generation
├── sport/tennis/
│   ├── phases.py             # Tennis-specific phase detection
│   ├── classifier_rules.py   # Forehand/backhand/serve classification rules
│   ├── strokes.py            # Stroke type definitions
│   └── metrics.py            # Tennis-specific metrics
├── llm/
│   ├── client.py             # OpenRouter API client
│   ├── models.py             # Model listing
│   └── prompt_builder.py     # Coaching prompt construction
├── storage/
│   ├── reference_store.py    # Reference profile persistence (JSON)
│   ├── session_store.py      # Session history (SQLite)
│   └── settings_store.py     # App settings persistence
└── requirements.txt
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Pose estimation (browser) | [MediaPipe Tasks Vision](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) WASM + GPU |
| Frontend | Vanilla JS, Chart.js, Marked.js |
| Backend | FastAPI, NumPy |
| AI coaching | OpenRouter API (Claude, GPT, etc.) |
| Storage | JSON files (references), SQLite (sessions) |

---

## License

MIT
