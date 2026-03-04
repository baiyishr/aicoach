"""Settings page — API key and model selection."""

import streamlit as st

from config import DEFAULT_MODEL
from llm.models import fetch_models


def render():
    """Render the settings page."""
    st.header("Settings")

    # API Key
    st.subheader("OpenRouter API Key")
    api_key = st.text_input(
        "API Key",
        value=st.session_state.get("api_key", ""),
        type="password",
        help="Get your API key from https://openrouter.ai/keys",
    )
    if api_key:
        st.session_state["api_key"] = api_key
        st.success("API key saved for this session.")

    # Model selection
    st.subheader("Model Selection")

    if api_key:
        if st.button("Fetch Available Models"):
            with st.spinner("Fetching models..."):
                models = fetch_models(api_key)
                if models:
                    st.session_state["available_models"] = models
                    st.success(f"Found {len(models)} models.")
                else:
                    st.error("Failed to fetch models. Check your API key.")

    available_models = st.session_state.get("available_models", [])
    if available_models:
        model_ids = [m["id"] for m in available_models]
        model_names = [f"{m['name']} ({m['id']})" for m in available_models]

        current_model = st.session_state.get("selected_model", DEFAULT_MODEL)
        default_idx = 0
        if current_model in model_ids:
            default_idx = model_ids.index(current_model)

        selected = st.selectbox(
            "Select Model",
            options=range(len(model_ids)),
            format_func=lambda i: model_names[i],
            index=default_idx,
        )
        st.session_state["selected_model"] = model_ids[selected]
    else:
        st.session_state.setdefault("selected_model", DEFAULT_MODEL)
        st.text_input(
            "Model ID",
            value=st.session_state["selected_model"],
            help="Enter a model ID or fetch the list above.",
            key="model_id_input",
            on_change=lambda: st.session_state.update(
                selected_model=st.session_state["model_id_input"]
            ),
        )

    st.divider()

    # Player settings
    st.subheader("Player Settings")
    dominant_side = st.selectbox(
        "Dominant Hand",
        options=["right", "left"],
        index=0 if st.session_state.get("dominant_side", "right") == "right" else 1,
    )
    st.session_state["dominant_side"] = dominant_side

    st.caption(f"Current model: `{st.session_state.get('selected_model', DEFAULT_MODEL)}`")
