"""Shared google-genai Client singleton.

All modules that need the Gemini API should call get_client() rather than
constructing their own client or calling genai.configure().  The Client
reads GOOGLE_API_KEY (or GEMINI_API_KEY) from the environment automatically
when no explicit key is supplied.
"""

import os

from google import genai

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return (and lazily create) the module-level genai Client."""
    global _client
    if _client is None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        _client = genai.Client(api_key=api_key) if api_key else genai.Client()
    return _client
