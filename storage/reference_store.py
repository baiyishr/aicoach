"""Save and load reference profiles as JSON files."""

import json
from pathlib import Path

from sport.base import ReferenceProfile
from config import REFERENCES_DIR


def _get_profile_path(sport: str, stroke_type: str) -> Path:
    """Get the file path for a reference profile."""
    return REFERENCES_DIR / f"{sport}_{stroke_type}.json"


def save_reference(profile: ReferenceProfile) -> Path:
    """Save a reference profile to disk.

    Args:
        profile: The reference profile to save.

    Returns:
        Path to the saved file.
    """
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    path = _get_profile_path(profile.sport, profile.stroke_type)

    with open(path, "w") as f:
        json.dump(profile.to_dict(), f, indent=2)

    return path


def load_reference(sport: str, stroke_type: str) -> ReferenceProfile | None:
    """Load a reference profile from disk.

    Returns:
        ReferenceProfile or None if not found.
    """
    path = _get_profile_path(sport, stroke_type)
    if not path.exists():
        return None

    with open(path) as f:
        data = json.load(f)

    return ReferenceProfile.from_dict(data)


def list_references(sport: str | None = None) -> list[ReferenceProfile]:
    """List all saved reference profiles.

    Args:
        sport: Optional filter by sport.

    Returns:
        List of ReferenceProfile objects.
    """
    if not REFERENCES_DIR.exists():
        return []

    profiles = []
    for path in REFERENCES_DIR.glob("*.json"):
        try:
            with open(path) as f:
                data = json.load(f)
            profile = ReferenceProfile.from_dict(data)
            if sport is None or profile.sport == sport:
                profiles.append(profile)
        except (json.JSONDecodeError, KeyError):
            continue

    return profiles


def delete_reference(sport: str, stroke_type: str) -> bool:
    """Delete a reference profile.

    Returns:
        True if deleted, False if not found.
    """
    path = _get_profile_path(sport, stroke_type)
    if path.exists():
        path.unlink()
        return True
    return False
