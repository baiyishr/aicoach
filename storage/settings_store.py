"""Persistent settings storage with encrypted API key.

Settings are stored in data/settings.json. The API key is encrypted using
Fernet symmetric encryption with a machine-local key stored in data/.keyfile.
"""

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

from config import DATA_DIR

SETTINGS_PATH = DATA_DIR / "settings.json"
KEYFILE_PATH = DATA_DIR / ".keyfile"


def _get_fernet() -> Fernet:
    """Get or create a Fernet instance using a local key file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if KEYFILE_PATH.exists():
        raw = KEYFILE_PATH.read_bytes()
    else:
        raw = secrets.token_bytes(32)
        KEYFILE_PATH.write_bytes(raw)
        os.chmod(KEYFILE_PATH, 0o600)

    # Derive a valid Fernet key (url-safe base64 of 32 bytes)
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def _encrypt(value: str) -> str:
    """Encrypt a string value."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def _decrypt(token: str) -> str:
    """Decrypt a string value."""
    f = _get_fernet()
    return f.decrypt(token.encode()).decode()


def load_settings() -> dict:
    """Load settings from disk.

    Returns:
        Dict with keys: api_key, selected_model, dominant_side.
        Missing keys get defaults.
    """
    defaults = {
        "api_key": "",
        "selected_model": "",
        "dominant_side": "right",
    }

    if not SETTINGS_PATH.exists():
        return defaults

    try:
        with open(SETTINGS_PATH) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return defaults

    result = dict(defaults)

    # Decrypt API key
    encrypted_key = data.get("api_key_encrypted", "")
    if encrypted_key:
        try:
            result["api_key"] = _decrypt(encrypted_key)
        except Exception:
            result["api_key"] = ""

    if data.get("selected_model"):
        result["selected_model"] = data["selected_model"]
    if data.get("dominant_side"):
        result["dominant_side"] = data["dominant_side"]

    return result


def save_settings(
    api_key: str | None = None,
    selected_model: str | None = None,
    dominant_side: str | None = None,
):
    """Save settings to disk. Only updates provided fields.

    Args:
        api_key: Plaintext API key (will be encrypted on disk).
        selected_model: Model ID string.
        dominant_side: "right" or "left".
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing
    existing = {}
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    if api_key is not None:
        existing["api_key_encrypted"] = _encrypt(api_key) if api_key else ""
    if selected_model is not None:
        existing["selected_model"] = selected_model
    if dominant_side is not None:
        existing["dominant_side"] = dominant_side

    with open(SETTINGS_PATH, "w") as f:
        json.dump(existing, f, indent=2)
    os.chmod(SETTINGS_PATH, 0o600)
