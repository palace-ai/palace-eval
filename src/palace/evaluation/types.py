"""Shared dataclasses for the evaluation pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from palace.task_types.base import TaskVerificationResult


@dataclass
class Attachment:
    """A resolved file attachment for model evaluation."""

    path: str        # absolute filesystem path to the file
    mime_type: str   # e.g. "image/png", "audio/wav", "text/plain"
    filename: str    # original filename (for display/reference)

    def read_bytes(self) -> bytes:
        """Read raw file content."""
        return Path(self.path).read_bytes()

    def read_text(self, max_length: int = 200_000) -> str | None:
        """Try reading as UTF-8 text. Returns None if not text or not decodable."""
        if not self.mime_type.startswith("text/"):
            return None
        try:
            text = Path(self.path).read_text(encoding="utf-8")
            return text[:max_length] if len(text) > max_length else text
        except (UnicodeDecodeError, OSError):
            return None


@dataclass
class PreparedTask:
    """Result of prompt preparation stage."""

    prompt: str
    attachments: list[Attachment] = field(default_factory=list)
    error: str | None = None  # e.g. "missing_attachment" — replaces __UNSUPPORTED__ sentinel


@dataclass
class AgentResult:
    """Result from an agent run.

    Outcomes:
        - "success": agent produced an answer (default when answer is set)
        - "error": infrastructure/transient failure
        - "unsupported": model capability limitation (e.g., context too long)
    """

    answer: str | None = None
    metrics: dict[str, Any] | None = None
    outcome: str = "success"  # "success", "error", "unsupported"
    reason: str | None = None
    elapsed: float = 0.0

    @property
    def is_skipped(self) -> bool:
        """Backward compat: True when outcome is not success."""
        return self.outcome != "success"

    @property
    def skip_reason(self) -> str | None:
        """Backward compat: returns reason for non-success outcomes."""
        return self.reason if self.is_skipped else None


@dataclass
class TaskResult:
    """Complete result of one task through the pipeline."""

    task_id: str
    report_entry: dict[str, Any]
    verification: TaskVerificationResult
