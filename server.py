"""FastAPI backend for AI Coach."""

import asyncio
import os
import subprocess
import tempfile
import traceback
from pathlib import Path

import numpy as np

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import ensure_dirs, DEFAULT_MODEL, DATA_DIR
from pose.detector import FrameResult, VideoResult
from pose.angles import compute_joint_angles
from detection.segmenter import segment_strokes
from detection.classifier import classify_all_segments
from detection.reviewer import DetectionResult, STROKE_TYPE_LABELS, STROKE_TYPES
from comparison.reference import build_reference_profile
from comparison.diff import compute_diff
from comparison.alignment import align_student_stroke, align_phases
from comparison.report import generate_report
from storage.reference_store import (
    save_reference, load_reference, list_references, delete_reference,
)
from storage.session_store import save_session, get_sessions, get_session, delete_session
from llm.client import OpenRouterClient
from llm.models import fetch_models
from llm.prompt_builder import build_coaching_prompt
from storage.settings_store import load_settings, save_settings

ensure_dirs()

app = FastAPI(title="AI Coach — Tennis")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load persisted settings on startup
_persisted = load_settings()

# In-memory state (per server process)
_state: dict = {
    "api_key": _persisted["api_key"] or os.environ.get("OPENROUTER_API_KEY", ""),
    "selected_model": _persisted["selected_model"] or DEFAULT_MODEL,
    "dominant_side": _persisted["dominant_side"] or "right",
    "ref_detection": None,
    "ref_video_result": None,
    "student_detection": None,
    "student_video_result": None,
}


# ── Pydantic models ──────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    api_key: str | None = None
    selected_model: str | None = None
    dominant_side: str | None = None


class YouTubeRequest(BaseModel):
    url: str


class ProcessLandmarksRequest(BaseModel):
    target: str
    landmarks: list       # list of (33x3 or null) per frame
    angles: list          # list of (angle dict or null) per frame
    fps: float
    total_frames: int
    frame_step: int = 1
    width: int = 0
    height: int = 0


class RelabelRequest(BaseModel):
    target: str
    stroke_id: int
    new_label: str


class DiscardRequest(BaseModel):
    target: str
    stroke_id: int


class CompareRequest(BaseModel):
    stroke_id: int


class CoachingRequest(BaseModel):
    report: str


class SaveSessionRequest(BaseModel):
    video_path: str
    stroke_type: str
    comparison_report: str
    coaching_feedback: str


# ── Routes ────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse("static/index.html")


# ── YouTube download ──────────────────────────────────────────────────

# Temp dir for YouTube downloads — cleaned up after browser fetches the file
_yt_temp_dir = Path(tempfile.mkdtemp(prefix="aicoach_yt_"))
# Track downloaded files for cleanup: filename -> filepath
_yt_downloads: dict[str, Path] = {}


@app.post("/api/youtube-download")
async def youtube_download(req: YouTubeRequest):
    """Download a YouTube video using yt-dlp to a temp directory."""
    url = req.url.strip()
    if not url:
        raise HTTPException(400, "No URL provided")

    _yt_temp_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(_yt_temp_dir / "%(title)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--no-playlist",
        "--print", "after_move:filepath",
        url,
    ]

    try:
        result = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True, timeout=600,
        )
    except FileNotFoundError:
        raise HTTPException(500, "yt-dlp is not installed. Run: pip install yt-dlp")
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Download timed out (>10 min)")

    if result.returncode != 0:
        err = result.stderr.strip().split("\n")[-1] if result.stderr else "Unknown error"
        raise HTTPException(500, f"yt-dlp failed: {err}")

    filepath = result.stdout.strip().split("\n")[-1]
    if not os.path.isfile(filepath):
        raise HTTPException(500, "Download completed but file not found")

    filename = os.path.basename(filepath)
    _yt_downloads[filename] = Path(filepath)

    return {"filename": filename}


# ── Video serving (for YouTube downloads) ─────────────────────────────

@app.get("/api/video/{filename:path}")
async def serve_video(filename: str):
    """Serve a temp-downloaded video file, then schedule cleanup."""
    filepath = _yt_downloads.get(filename)
    if not filepath or not filepath.is_file():
        raise HTTPException(404, "Video not found")

    async def _cleanup_later():
        """Delete the temp file after a delay (give browser time to load)."""
        await asyncio.sleep(120)  # 2 minutes should be enough
        try:
            if filepath.exists():
                filepath.unlink()
            _yt_downloads.pop(filename, None)
        except OSError:
            pass

    asyncio.create_task(_cleanup_later())
    return FileResponse(str(filepath), media_type="video/mp4")


# ── Settings ──────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    return {
        "api_key": bool(_state["api_key"]),
        "api_key_masked": _state["api_key"][-4:] if _state["api_key"] else "",
        "selected_model": _state["selected_model"],
        "dominant_side": _state["dominant_side"],
    }


@app.post("/api/settings")
async def update_settings(s: SettingsUpdate):
    if s.api_key is not None:
        _state["api_key"] = s.api_key
    if s.selected_model is not None:
        _state["selected_model"] = s.selected_model
    if s.dominant_side is not None:
        _state["dominant_side"] = s.dominant_side
    save_settings(
        api_key=s.api_key,
        selected_model=s.selected_model,
        dominant_side=s.dominant_side,
    )
    return {"ok": True}


@app.get("/api/models")
async def get_models():
    if not _state["api_key"]:
        raise HTTPException(400, "No API key set")
    models = fetch_models(_state["api_key"])
    return {"models": models}


# ── Process landmarks (from browser) ──────────────────────────────────

def _reconstruct_video_result(req: ProcessLandmarksRequest) -> VideoResult:
    """Reconstruct a VideoResult from browser-sent landmark data."""
    frames = []
    for i, (lm, ang) in enumerate(zip(req.landmarks, req.angles)):
        landmarks = np.array(lm, dtype=np.float64) if lm is not None else None
        angles = ang  # Already a dict or None
        frames.append(FrameResult(
            frame_idx=i * req.frame_step,
            timestamp_ms=i * (1000.0 / req.fps),
            landmarks=landmarks,
            angles=angles,
        ))

    return VideoResult(
        video_path="browser",
        fps=req.fps,
        total_frames=req.total_frames,
        width=req.width,
        height=req.height,
        frame_step=req.frame_step,
        frames=frames,
    )


def _run_landmark_detection(req: ProcessLandmarksRequest, dominant_side: str):
    """Segment and classify strokes from browser landmarks."""
    video_result = _reconstruct_video_result(req)

    segments = segment_strokes(video_result)
    classified = classify_all_segments(segments, dominant_side=dominant_side)

    detection = DetectionResult.from_classified(
        video_path="browser",
        fps=video_result.fps,
        total_frames=video_result.total_frames,
        classified=classified,
    )

    _state[f"{req.target}_detection"] = detection
    _state[f"{req.target}_video_result"] = video_result

    strokes_data = []
    for stroke in detection.strokes:
        seg = stroke.classified.segment
        mid_frame = seg.mid_frame

        # Compute time for the mid frame so browser can generate thumbnail
        mid_frame_time = mid_frame / max(video_result.fps, 1)

        strokes_data.append({
            "id": stroke.id,
            "stroke_type": stroke.classified.stroke_type,
            "final_label": stroke.final_label,
            "display_label": stroke.display_label,
            "confidence": round(stroke.classified.confidence, 2),
            "start_frame": seg.start_frame,
            "end_frame": seg.end_frame,
            "mid_frame": mid_frame,
            "mid_frame_time": round(mid_frame_time, 3),
            "duration": round(seg.duration_seconds(detection.fps), 2),
            "discarded": stroke.discarded,
            "thumbnail": "",  # Browser will generate
        })

    return {
        "fps": round(video_result.fps, 1),
        "total_frames": video_result.total_frames,
        "num_strokes": len(classified),
        "strokes": strokes_data,
    }


@app.post("/api/process-landmarks")
async def process_landmarks(req: ProcessLandmarksRequest):
    """Process browser-extracted landmarks: segment strokes and classify."""
    if not req.landmarks:
        raise HTTPException(400, "No landmarks provided")

    try:
        result = await asyncio.to_thread(
            _run_landmark_detection, req, _state["dominant_side"],
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── Review ────────────────────────────────────────────────────────────

@app.post("/api/relabel")
async def relabel_stroke(req: RelabelRequest):
    detection = _state.get(f"{req.target}_detection")
    if not detection:
        raise HTTPException(400, "No detection data")
    detection.relabel(req.stroke_id, req.new_label)
    return {"ok": True}


@app.post("/api/discard")
async def discard_stroke(req: DiscardRequest):
    detection = _state.get(f"{req.target}_detection")
    if not detection:
        raise HTTPException(400, "No detection data")
    for s in detection.strokes:
        if s.id == req.stroke_id:
            if s.discarded:
                s.restore()
            else:
                s.discard()
            return {"ok": True, "discarded": s.discarded}
    raise HTTPException(404, "Stroke not found")


# ── References ────────────────────────────────────────────────────────

@app.post("/api/build-references")
async def build_references():
    detection = _state.get("ref_detection")
    if not detection:
        raise HTTPException(400, "No detection data. Detect strokes first.")

    confirmed = detection.confirmed_strokes
    if not confirmed:
        raise HTTPException(400, "No confirmed strokes")

    type_counts = {}
    for s in confirmed:
        t = s.final_label
        type_counts[t] = type_counts.get(t, 0) + 1

    built = 0
    results = []
    for stroke_type, count in type_counts.items():
        strokes = detection.strokes_by_type(stroke_type)
        profile = build_reference_profile(strokes, stroke_type)
        if profile:
            save_reference(profile)
            built += 1
            results.append({
                "stroke_type": stroke_type,
                "display": STROKE_TYPE_LABELS.get(stroke_type, stroke_type),
                "samples": count,
            })

    return {"built": built, "profiles": results}


@app.get("/api/references")
async def get_references():
    profiles = list_references()
    return {
        "references": [
            {
                "stroke_type": p.stroke_type,
                "sport": p.sport,
                "display": STROKE_TYPE_LABELS.get(p.stroke_type, p.stroke_type),
                "num_samples": p.num_samples,
            }
            for p in profiles
        ]
    }


@app.delete("/api/references/{sport}/{stroke_type}")
async def remove_reference(sport: str, stroke_type: str):
    if delete_reference(sport, stroke_type):
        return {"ok": True}
    raise HTTPException(404, "Reference not found")


# ── Compare ───────────────────────────────────────────────────────────

@app.post("/api/compare")
async def compare_stroke(req: CompareRequest):
    detection = _state.get("student_detection")
    if not detection:
        raise HTTPException(400, "No student detection data")

    stroke = None
    for s in detection.confirmed_strokes:
        if s.id == req.stroke_id:
            stroke = s
            break
    if not stroke:
        raise HTTPException(404, "Stroke not found or discarded")

    stroke_type = stroke.final_label
    ref_profile = load_reference("tennis", stroke_type)
    if not ref_profile:
        raise HTTPException(
            400,
            f"No pro reference for {STROKE_TYPE_LABELS.get(stroke_type, stroke_type)}. "
            "Import a pro video first."
        )

    seg = stroke.classified.segment
    diff_result = compute_diff(
        student_landmarks=seg.landmarks,
        student_angles=seg.angles,
        reference=ref_profile,
        stroke_type=stroke_type,
    )
    report = generate_report(diff_result)

    # Phase chart data
    student_phases = align_student_stroke(seg.landmarks, seg.angles, stroke_type)
    aligned = align_phases(student_phases, ref_profile)

    charts = []
    for sp, rp in aligned:
        if not rp:
            continue
        common = sorted(set(sp["normalized_angles"].keys()) & set(rp["normalized_angles"].keys()))
        joints = []
        for j in common:
            sv = sp["normalized_angles"][j]
            rv = rp["normalized_angles"][j]
            min_len = min(len(sv), len(rv))
            joints.append({"joint": j, "student": sv[:min_len], "pro": rv[:min_len]})
        charts.append({"phase": sp["name"], "joints": joints})

    # Return mid_frame_idx for browser-side snapshot generation
    mid_frame_idx = len(seg.landmarks) // 2

    # Top issues
    top_issues = []
    for phase_name, ad in diff_result.top_issues:
        top_issues.append({
            "phase": phase_name,
            "joint": ad.joint,
            "student_avg": round(ad.student_avg, 1),
            "pro_avg": round(ad.pro_avg, 1),
            "diff": round(ad.abs_diff, 1),
            "direction": "more" if ad.diff > 0 else "less",
        })

    return {
        "report": report,
        "charts": charts,
        "mid_frame_idx": mid_frame_idx,
        "stroke_type": stroke_type,
        "display_label": STROKE_TYPE_LABELS.get(stroke_type, stroke_type),
        "top_issues": top_issues,
        "ref_samples": ref_profile.num_samples,
    }


# ── Coaching ──────────────────────────────────────────────────────────

@app.post("/api/coaching")
async def get_coaching(req: CoachingRequest):
    if not _state["api_key"]:
        raise HTTPException(400, "No API key set. Go to Settings.")

    client = OpenRouterClient(
        api_key=_state["api_key"],
        model=_state["selected_model"],
    )
    messages = build_coaching_prompt(req.report)
    try:
        feedback = client.chat(messages)
        return {"feedback": feedback}
    except RuntimeError as e:
        raise HTTPException(500, str(e))


# ── Sessions ──────────────────────────────────────────────────────────

@app.post("/api/sessions")
async def create_session(req: SaveSessionRequest):
    sid = save_session(
        video_path=req.video_path,
        stroke_type=req.stroke_type,
        comparison_report=req.comparison_report,
        coaching_feedback=req.coaching_feedback,
    )
    return {"id": sid}


@app.get("/api/sessions")
async def list_sessions():
    sessions = get_sessions()
    return {
        "sessions": [
            {
                "id": s.id,
                "timestamp": s.timestamp[:19].replace("T", " "),
                "video_path": s.video_path,
                "stroke_type": s.stroke_type,
                "display_label": STROKE_TYPE_LABELS.get(s.stroke_type, s.stroke_type),
                "comparison_report": s.comparison_report,
                "coaching_feedback": s.coaching_feedback,
            }
            for s in sessions
        ]
    }


@app.delete("/api/sessions/{session_id}")
async def remove_session(session_id: int):
    if delete_session(session_id):
        return {"ok": True}
    raise HTTPException(404, "Session not found")


# ── Stroke types (for dropdowns) ─────────────────────────────────────

@app.get("/api/stroke-types")
async def stroke_types():
    return {"types": [{"value": k, "label": v} for k, v in STROKE_TYPE_LABELS.items()]}
