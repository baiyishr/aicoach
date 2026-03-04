"""References page — import pro videos, auto-detect strokes, build profiles."""

import os

import cv2
import numpy as np
import streamlit as st

from pose.detector import process_video, get_video_frame
from pose.drawing import draw_skeleton
from detection.segmenter import segment_strokes
from detection.classifier import classify_all_segments
from detection.reviewer import DetectionResult, STROKE_TYPES, STROKE_TYPE_LABELS
from comparison.reference import build_reference_profile
from storage.reference_store import save_reference, list_references, delete_reference
from ui.components import video_file_picker


def render():
    """Render the references management page."""
    st.header("Pro Reference Profiles")

    tab_import, tab_manage = st.tabs(["Import Pro Video", "Manage References"])

    with tab_import:
        _render_import()

    with tab_manage:
        _render_manage()


def _render_import():
    """Import a pro video and build reference profiles."""
    video_path = video_file_picker(
        label="Pro video file",
        key="ref_video_path",
        help_text="Click Browse to choose a pro tennis video, or type the path manually.",
    )

    if not video_path:
        st.info("Select a pro tennis video to get started.")
        return

    if not os.path.isfile(video_path):
        st.error(f"File not found: {video_path}")
        return

    dominant_side = st.session_state.get("dominant_side", "right")

    # Step 1: Process video
    if st.button("Detect Strokes", key="detect_ref"):
        progress_bar = st.progress(0, text="Processing video with MediaPipe...")

        def on_progress(current, total):
            if total > 0:
                progress_bar.progress(
                    min(current / total, 1.0),
                    text=f"Processing frame {current}/{total}..."
                )

        try:
            video_result = process_video(video_path, progress_callback=on_progress)
            progress_bar.progress(1.0, text="Detecting strokes...")

            segments = segment_strokes(video_result)
            classified = classify_all_segments(segments, dominant_side=dominant_side)

            detection_result = DetectionResult.from_classified(
                video_path=video_path,
                fps=video_result.fps,
                total_frames=video_result.total_frames,
                classified=classified,
            )

            st.session_state["ref_detection"] = detection_result
            st.session_state["ref_video_result"] = video_result
            progress_bar.empty()
            st.success(f"Detected {len(classified)} strokes!")

        except Exception as e:
            progress_bar.empty()
            st.error(f"Error processing video: {e}")
            return

    # Step 2: Review detected strokes
    detection: DetectionResult | None = st.session_state.get("ref_detection")
    if detection is None:
        return

    st.subheader("Review Detected Strokes")
    st.caption(f"Video: {detection.video_path} | {detection.total_frames} frames @ {detection.fps:.1f} fps")

    for stroke in detection.strokes:
        seg = stroke.classified.segment
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

        with col1:
            # Thumbnail
            mid_frame = seg.mid_frame
            frame = get_video_frame(detection.video_path, mid_frame)
            if frame is not None:
                lm = seg.landmarks[len(seg.landmarks) // 2] if seg.landmarks else None
                if lm is not None:
                    frame = draw_skeleton(frame, lm)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                st.image(frame_rgb, width=200, caption=f"Frames {seg.start_frame}-{seg.end_frame}")

        with col2:
            # Label selector
            current_label = stroke.final_label
            label_options = STROKE_TYPES
            current_idx = label_options.index(current_label) if current_label in label_options else 0

            new_label = st.selectbox(
                f"Stroke #{stroke.id}",
                options=label_options,
                format_func=lambda x: STROKE_TYPE_LABELS.get(x, x),
                index=current_idx,
                key=f"ref_label_{stroke.id}",
            )
            if new_label != stroke.final_label:
                stroke.relabel(new_label)

        with col3:
            conf = stroke.classified.confidence
            st.caption(f"Auto: {stroke.classified.stroke_type} ({conf:.0%})")
            duration = seg.duration_seconds(detection.fps)
            st.caption(f"Duration: {duration:.2f}s")

        with col4:
            if stroke.discarded:
                if st.button("Restore", key=f"ref_restore_{stroke.id}"):
                    stroke.restore()
                    st.rerun()
            else:
                if st.button("Discard", key=f"ref_discard_{stroke.id}"):
                    stroke.discard()
                    st.rerun()

        st.divider()

    # Step 3: Build reference profiles
    confirmed = detection.confirmed_strokes
    if not confirmed:
        st.warning("No confirmed strokes. Review and keep at least some strokes.")
        return

    st.subheader("Build Reference Profiles")

    # Show counts by type
    type_counts = {}
    for s in confirmed:
        t = s.final_label
        type_counts[t] = type_counts.get(t, 0) + 1

    for stroke_type, count in type_counts.items():
        display = STROKE_TYPE_LABELS.get(stroke_type, stroke_type)
        st.write(f"**{display}**: {count} stroke(s)")

    if st.button("Build & Save Reference Profiles", type="primary"):
        built = 0
        for stroke_type in type_counts:
            strokes = detection.strokes_by_type(stroke_type)
            profile = build_reference_profile(strokes, stroke_type)
            if profile:
                save_reference(profile)
                built += 1

        if built > 0:
            st.success(f"Built and saved {built} reference profile(s)!")
        else:
            st.warning("Could not build any profiles. Need more stroke data.")


def _render_manage():
    """Manage existing reference profiles."""
    profiles = list_references()

    if not profiles:
        st.info("No reference profiles saved yet. Import a pro video to create some.")
        return

    for profile in profiles:
        display = STROKE_TYPE_LABELS.get(profile.stroke_type, profile.stroke_type)
        with st.expander(f"{display} ({profile.sport}) — {profile.num_samples} sample(s)"):
            st.json(profile.to_dict())

            if st.button(f"Delete {display}", key=f"del_{profile.sport}_{profile.stroke_type}"):
                delete_reference(profile.sport, profile.stroke_type)
                st.success(f"Deleted {display} reference.")
                st.rerun()
