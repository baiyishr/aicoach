"""OpenRouter HTTP client for LLM API calls."""

import logging

import requests

from config import OPENROUTER_API_URL, DEFAULT_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for the OpenRouter API."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self.base_url = OPENROUTER_API_URL

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = LLM_MAX_TOKENS,
        temperature: float = LLM_TEMPERATURE,
    ) -> str:
        """Send a chat completion request.

        Args:
            messages: List of {role, content} message dicts.
            max_tokens: Maximum response tokens.
            temperature: Sampling temperature.

        Returns:
            The assistant's response text.

        Raises:
            RuntimeError: If the API call fails.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                raise RuntimeError(f"Unexpected API response: {data}")

        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("error", {}).get("message", "")
            except Exception:
                error_detail = e.response.text[:200]
            raise RuntimeError(f"OpenRouter API error: {e} — {error_detail}") from e
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Request failed: {e}") from e
