"""Shared UI components and widgets."""

import os
import threading

import cv2
import numpy as np
import streamlit as st

from pose.drawing import draw_skeleton, create_thumbnail
from pose.detector import get_video_frame

VIDEO_EXTENSIONS = [
    ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v"),
    ("All files", "*.*"),
]


def _open_file_dialog(
    title: str = "Select a video file",
    filetypes: list | None = None,
    initial_dir: str | None = None,
) -> str | None:
    """Open a native OS file dialog and return the selected path.

    Runs tkinter in a separate thread to avoid conflicts with Streamlit.
    """
    if filetypes is None:
        filetypes = VIDEO_EXTENSIONS
    if initial_dir is None:
        initial_dir = os.path.expanduser("~")

    result = [None]

    def _run():
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        path = filedialog.askopenfilename(
            title=title,
            filetypes=filetypes,
            initialdir=initial_dir,
        )
        root.destroy()
        if path:
            result[0] = path

    thread = threading.Thread(target=_run)
    thread.start()
    thread.join()

    return result[0]


def video_file_picker(
    label: str = "Select video file",
    key: str = "video_path",
    help_text: str = "Click Browse to choose a video file, or type the path manually.",
) -> str | None:
    """A video file picker with a Browse button and manual text input.

    Args:
        label: Label displayed above the input.
        key: Session state key to store the selected path.
        help_text: Help text for the input.

    Returns:
        Selected video file path, or None.
    """
    col_input, col_btn = st.columns([5, 1])

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)  # vertical align with input
        if st.button("Browse", key=f"{key}_browse"):
            current = st.session_state.get(key, "")
            initial_dir = os.path.dirname(current) if current and os.path.exists(os.path.dirname(current)) else None
            selected = _open_file_dialog(title=label, initial_dir=initial_dir)
            if selected:
                st.session_state[key] = selected
                st.rerun()

    with col_input:
        path = st.text_input(
            label,
            value=st.session_state.get(key, ""),
            help=help_text,
            key=f"{key}_input",
        )
        if path != st.session_state.get(key, ""):
            st.session_state[key] = path

    return st.session_state.get(key, "") or None


def render_stroke_thumbnail(
    video_path: str,
    frame_idx: int,
    landmarks: np.ndarray | None = None,
    size: tuple[int, int] = (240, 180),
) -> np.ndarray | None:
    """Render a stroke thumbnail from a video frame.

    Returns:
        RGB image array or None.
    """
    frame = get_video_frame(video_path, frame_idx)
    if frame is None:
        return None

    thumb = create_thumbnail(frame, landmarks, size)
    # Convert BGR to RGB for Streamlit
    return cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)


def metric_card(label: str, value: str, delta: str | None = None):
    """Display a metric card."""
    st.metric(label=label, value=value, delta=delta)


def angle_comparison_chart(
    phase_name: str,
    student_angles: dict[str, list[float]],
    pro_angles: dict[str, list[float]],
):
    """Display an angle comparison chart for a phase."""
    import pandas as pd

    common_joints = sorted(set(student_angles.keys()) & set(pro_angles.keys()))
    if not common_joints:
        st.info(f"No comparable data for {phase_name}")
        return

    # Show first common joint as a line chart
    for joint in common_joints[:3]:  # Limit to top 3 joints
        student_vals = student_angles[joint]
        pro_vals = pro_angles[joint]

        min_len = min(len(student_vals), len(pro_vals))
        df = pd.DataFrame({
            "Student": student_vals[:min_len],
            "Pro": pro_vals[:min_len],
        })

        joint_display = joint.replace("_", " ").title()
        st.caption(f"{joint_display}")
        st.line_chart(df, height=150)


def video_player(video_path: str, label: str = "Video"):
    """Display a video file."""
    try:
        st.video(video_path)
    except Exception as e:
        st.error(f"Cannot play video: {e}")
