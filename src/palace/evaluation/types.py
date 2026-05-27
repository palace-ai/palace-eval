"""Shared dataclasses for the evaluation pipeline."""

from dataclasses import dataclass, field
from typing import Any

from palace.task_types.base import TaskVerificationResult


@dataclass
class PreparedTask:
    """Result of prompt preparation stage."""

    prompt: str
    image: str | None = None
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
