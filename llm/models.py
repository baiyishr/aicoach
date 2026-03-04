"""Fetch available models from OpenRouter."""

import logging

import requests

from config import OPENROUTER_API_URL

logger = logging.getLogger(__name__)


def fetch_models(api_key: str) -> list[dict]:
    """Fetch the list of available models from OpenRouter.

    Args:
        api_key: OpenRouter API key.

    Returns:
        List of model dicts with 'id' and 'name' keys.
    """
    try:
        response = requests.get(
            f"{OPENROUTER_API_URL}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        models = []
        for m in data.get("data", []):
            models.append({
                "id": m["id"],
                "name": m.get("name", m["id"]),
                "context_length": m.get("context_length", 0),
                "pricing": m.get("pricing", {}),
            })

        # Sort by name
        models.sort(key=lambda x: x["name"])
        return models

    except Exception as e:
        logger.error("Failed to fetch models: %s", e)
        return []
