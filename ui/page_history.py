"""History page — view past coaching sessions."""

import streamlit as st

from storage.session_store import get_sessions, delete_session
from detection.reviewer import STROKE_TYPE_LABELS


def render():
    """Render the history page."""
    st.header("Session History")

    sessions = get_sessions()

    if not sessions:
        st.info("No past sessions yet. Analyze a student video to create one.")
        return

    for session in sessions:
        stroke_display = STROKE_TYPE_LABELS.get(session.stroke_type, session.stroke_type)
        timestamp = session.timestamp[:19].replace("T", " ")

        with st.expander(f"{timestamp} — {stroke_display}", expanded=False):
            st.caption(f"Video: {session.video_path}")
            st.caption(f"Sport: {session.sport}")

            tab_feedback, tab_report = st.tabs(["Coaching Feedback", "Comparison Report"])

            with tab_feedback:
                st.markdown(session.coaching_feedback)

            with tab_report:
                st.code(session.comparison_report, language=None)

            if st.button("Delete", key=f"del_session_{session.id}"):
                delete_session(session.id)
                st.success("Session deleted.")
                st.rerun()
