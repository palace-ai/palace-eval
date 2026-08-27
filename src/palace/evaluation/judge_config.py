"""Judge configuration dataclass."""

from dataclasses import dataclass


@dataclass
class JudgeConfig:
    """Configuration for the LLM judge used in verification.

    Attributes:
        url: API endpoint URL for the judge model.
        key: API key for authentication.
        model: Model identifier (e.g., "gpt-4o-mini").
        extra_params: Additional parameters passed to API calls (e.g., {"reasoning_effort": "high"}).
    """

    url: str | None = None
    key: str | None = None
    model: str | None = None
    extra_params: dict | None = None
