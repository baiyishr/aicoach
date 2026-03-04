"""Analyze page — import student video, compare with pro, get AI coaching."""

import os

import cv2
import numpy as np
import streamlit as st

from pose.detector import process_video, get_video_frame
from pose.drawing import draw_skeleton, draw_side_by_side
from detection.segmenter import segment_strokes
from detection.classifier import classify_all_segments
from detection.reviewer import DetectionResult, STROKE_TYPES, STROKE_TYPE_LABELS
from comparison.diff import compute_diff
from comparison.report import generate_report
from storage.reference_store import list_references, load_reference
from llm.client import OpenRouterClient
from llm.prompt_builder import build_coaching_prompt
from storage.session_store import save_session
from ui.components import angle_comparison_chart, video_file_picker


def render():
    """Render the analysis page."""
    st.header("Analyze Student")

    # Check for references
    references = list_references()
    if not references:
        st.warning(
            "No pro reference profiles found. "
            "Go to **References** to import a pro video first."
        )
        return

    video_path = video_file_picker(
        label="Student video file",
        key="student_video_path",
        help_text="Click Browse to choose a student's tennis video, or type the path manually.",
    )

    if not video_path:
        st.info("Select a student's tennis video to analyze.")
        return

    if not os.path.isfile(video_path):
        st.error(f"File not found: {video_path}")
        return

    dominant_side = st.session_state.get("dominant_side", "right")

    # Step 1: Process and detect strokes
    if st.button("Detect Strokes", key="detect_student"):
        progress_bar = st.progress(0, text="Processing video with MediaPipe...")

        def on_progress(current, total):
            if total > 0:
                progress_bar.progress(
                    min(current / total, 1.0),
                    text=f"Processing frame {current}/{total}...",
                )

        try:
            video_result = process_video(video_path, progress_callback=on_progress)
            progress_bar.progress(1.0, text="Detecting strokes...")

            segments = segment_strokes(video_result)
            classified = classify_all_segments(segments, dominant_side=dominant_side)

            detection = DetectionResult.from_classified(
                video_path=video_path,
                fps=video_result.fps,
                total_frames=video_result.total_frames,
                classified=classified,
            )

            st.session_state["student_detection"] = detection
            st.session_state["student_video_result"] = video_result
            progress_bar.empty()
            st.success(f"Detected {len(classified)} strokes!")
        except Exception as e:
            progress_bar.empty()
            st.error(f"Error processing video: {e}")
            return

    detection: DetectionResult | None = st.session_state.get("student_detection")
    if detection is None:
        return

    # Step 2: Review detected strokes
    st.subheader("Review Detected Strokes")

    confirmed = detection.confirmed_strokes
    if not confirmed:
        st.warning("No strokes detected or all discarded.")
        return

    for stroke in detection.strokes:
        seg = stroke.classified.segment
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

        with col1:
            mid_frame = seg.mid_frame
            frame = get_video_frame(detection.video_path, mid_frame)
            if frame is not None:
                lm = seg.landmarks[len(seg.landmarks) // 2] if seg.landmarks else None
                if lm is not None:
                    frame = draw_skeleton(frame, lm)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                st.image(frame_rgb, width=200, caption=f"Frames {seg.start_frame}-{seg.end_frame}")

        with col2:
            current_label = stroke.final_label
            label_options = STROKE_TYPES
            current_idx = label_options.index(current_label) if current_label in label_options else 0

            new_label = st.selectbox(
                f"Stroke #{stroke.id}",
                options=label_options,
                format_func=lambda x: STROKE_TYPE_LABELS.get(x, x),
                index=current_idx,
                key=f"student_label_{stroke.id}",
            )
            if new_label != stroke.final_label:
                stroke.relabel(new_label)

        with col3:
            conf = stroke.classified.confidence
            st.caption(f"Auto: {stroke.classified.stroke_type} ({conf:.0%})")

        with col4:
            if stroke.discarded:
                if st.button("Restore", key=f"student_restore_{stroke.id}"):
                    stroke.restore()
                    st.rerun()
            else:
                if st.button("Discard", key=f"student_discard_{stroke.id}"):
                    stroke.discard()
                    st.rerun()

    st.divider()

    # Step 3: Select stroke to analyze
    confirmed = detection.confirmed_strokes
    if not confirmed:
        return

    st.subheader("Compare with Pro Reference")

    stroke_options = [
        f"#{s.id}: {STROKE_TYPE_LABELS.get(s.final_label, s.final_label)} "
        f"(frames {s.classified.segment.start_frame}-{s.classified.segment.end_frame})"
        for s in confirmed
    ]

    selected_idx = st.selectbox(
        "Select stroke to analyze",
        options=range(len(confirmed)),
        format_func=lambda i: stroke_options[i],
    )
    selected_stroke = confirmed[selected_idx]
    stroke_type = selected_stroke.final_label

    # Select matching reference
    matching_refs = [r for r in references if r.stroke_type == stroke_type]
    if not matching_refs:
        st.warning(
            f"No pro reference found for **{STROKE_TYPE_LABELS.get(stroke_type, stroke_type)}**. "
            f"Import a pro video with this stroke type."
        )
        return

    ref_profile = matching_refs[0]  # Use first match
    st.info(
        f"Comparing against: **{STROKE_TYPE_LABELS.get(ref_profile.stroke_type)}** reference "
        f"({ref_profile.num_samples} sample(s))"
    )

    if st.button("Compare", type="primary"):
        seg = selected_stroke.classified.segment
        diff_result = compute_diff(
            student_landmarks=seg.landmarks,
            student_angles=seg.angles,
            reference=ref_profile,
            stroke_type=stroke_type,
        )

        report = generate_report(diff_result)

        st.session_state["current_diff"] = diff_result
        st.session_state["current_report"] = report
        st.session_state["current_stroke_type"] = stroke_type

    # Step 4: Show comparison results
    diff_result = st.session_state.get("current_diff")
    report = st.session_state.get("current_report")

    if diff_result and report:
        st.subheader("Comparison Results")

        # Side-by-side skeleton (student mid-frame)
        seg = selected_stroke.classified.segment
        mid_idx = len(seg.landmarks) // 2
        student_frame = get_video_frame(detection.video_path, seg.mid_frame)
        if student_frame is not None and mid_idx < len(seg.landmarks):
            student_lm = seg.landmarks[mid_idx]
            annotated = draw_skeleton(student_frame, student_lm)
            st.image(
                cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB),
                caption="Student pose at mid-stroke",
                width=400,
            )

        # Phase comparison charts
        from comparison.alignment import align_student_stroke, align_phases

        student_phases = align_student_stroke(
            seg.landmarks, seg.angles, stroke_type
        )
        aligned = align_phases(student_phases, ref_profile)

        for student_phase, ref_phase in aligned:
            if ref_phase:
                phase_display = student_phase["name"].replace("_", " ").title()
                with st.expander(f"Phase: {phase_display}", expanded=False):
                    angle_comparison_chart(
                        student_phase["name"],
                        student_phase["normalized_angles"],
                        ref_phase["normalized_angles"],
                    )

        # Text report
        with st.expander("Full Comparison Report", expanded=True):
            st.code(report, language=None)

        # Step 5: AI Coaching
        st.subheader("AI Coaching Feedback")

        api_key = st.session_state.get("api_key", "")
        if not api_key:
            st.warning("Set your OpenRouter API key in **Settings** to get AI coaching feedback.")
        else:
            if st.button("Get AI Coaching", type="primary"):
                model = st.session_state.get("selected_model", "anthropic/claude-sonnet-4-20250514")
                client = OpenRouterClient(api_key=api_key, model=model)
                messages = build_coaching_prompt(report)

                with st.spinner("Getting coaching feedback..."):
                    try:
                        feedback = client.chat(messages)
                        st.session_state["current_feedback"] = feedback
                    except RuntimeError as e:
                        st.error(f"LLM error: {e}")

            feedback = st.session_state.get("current_feedback")
            if feedback:
                st.markdown(feedback)

                # Save session
                if st.button("Save to History"):
                    session_id = save_session(
                        video_path=detection.video_path,
                        stroke_type=stroke_type,
                        comparison_report=report,
                        coaching_feedback=feedback,
                    )
                    st.success(f"Session saved! (ID: {session_id})")
