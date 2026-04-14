"""LLM layer errors (transport, parsing, availability)."""

from __future__ import annotations


class LLMError(Exception):
    """Base class for LLM client failures."""


class LLMTransportError(LLMError):
    """Retryable transport / upstream errors (timeout, 5xx, rate limit)."""


class LLMInvalidResponseError(LLMError):
    """Model returned content that does not match the expected contract."""


class LLMUnavailableError(LLMError):
    """Both primary and fallback models failed or the API is unusable (maps to LLM_UNAVAILABLE)."""

    def __init__(self, message: str, *, causes: list[BaseException] | None = None) -> None:
        super().__init__(message)
        self.causes = list(causes or [])
