"""Shared dataclasses for the evaluation pipeline."""

from dataclasses import dataclass, field
from typing import Any

from palace.task_types.base import TaskVerificationResult


@dataclass
class Attachment:
    """A binary attachment to pass as perceptual input to the model."""

    path: str        # absolute filesystem path to the file
    mime_type: str   # e.g. "image/png", "audio/wav", "video/mp4"
    filename: str    # original filename (for display/reference)


@dataclass
class PreparedTask:
    """Result of prompt preparation stage."""

    prompt: str
    attachments: list[Attachment] = field(default_factory=list)
    attachment_content: str = ""


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
