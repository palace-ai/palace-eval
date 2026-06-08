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
    """Result from an agent run."""

    answer: str | None = None
    metrics: dict[str, Any] | None = None
    is_skipped: bool = False
    skip_reason: str | None = None
    elapsed: float = 0.0


@dataclass
class TaskResult:
    """Complete result of one task through the pipeline."""

    task_id: str
    report_entry: dict[str, Any]
    verification: TaskVerificationResult
