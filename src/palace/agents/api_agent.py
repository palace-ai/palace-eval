# Copyright (C) 2025 European Union
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL) v. 1.2
# as published by the European Union.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.
#
# You should have received a copy of the European Union Public Licence
# along with this program. If not, see <https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12>.

import logging
from typing import TYPE_CHECKING

from palace.agents import Agent
from palace.evaluation.types import AgentResult
from palace.models.api_model import create_api_model
from palace.utils.exceptions import ModelNotFoundError
from palace.utils.multimodal import build_multimodal_content
from palace.utils.printing import print

if TYPE_CHECKING:
    from palace.evaluation.types import Attachment

_logger = logging.getLogger("palace.api_agent")

# Patterns that indicate a deterministic model capability limitation (not transient)
_UNSUPPORTED_PATTERNS = [
    "context_length_exceeded",
    "too many tokens",
    "prompt is too long",
    "maximum context length",
    "input too long",
    "exceeds the model's maximum",
    "content_too_large",
    "request too large",
    "input tokens exceed",
]

# Patterns indicating the model doesn't exist — should abort evaluation
_MODEL_NOT_FOUND_PATTERNS = [
    "model not found",
    "not available",
    "does not exist",
    "unknown model",
    "invalid model",
    "no such model",
]


def _is_unsupported_error(e: Exception) -> bool:
    """Detect deterministic capability limitations from API errors.

    Returns True for errors that indicate the model cannot process the input
    (e.g., context too long, unsupported modality). These are permanent for
    the given input and should not be retried.
    """
    # OpenAI / vLLM: BadRequestError has a .code attribute
    if hasattr(e, "code") and e.code == "context_length_exceeded":
        return True
    # Message-based detection (Anthropic, vLLM variants, other providers)
    msg = str(e).lower()
    return any(p in msg for p in _UNSUPPORTED_PATTERNS)


def _is_model_not_found(e: Exception) -> bool:
    """Detect model-not-found errors that should abort the evaluation.

    Returns True for errors that indicate the model doesn't exist on the endpoint.
    These are configuration errors, not per-task issues.
    """
    msg = str(e).lower()
    return any(p in msg for p in _MODEL_NOT_FOUND_PATTERNS)


class APIAgent(Agent):
    """Agent that calls an API endpoint (OpenAI-compatible, Azure OpenAI, or Anthropic).

    Can be used for both agentic and non-agentic (black-box LLM) evaluation.
    """

    def __init__(
        self,
        /,
        name: str,
        url: str,
        token: str | None = None,
        api_type: str | None = None,
        extra_params: dict | None = None,
    ):
        """Initialize an APIAgent.

        Args:
            name: The name of the agent, corresponding to a model ID on the API server.
            url: The URL of the API server.
            token: The API token for authentication. Defaults to None.
            api_type: The API type to use ("openai", "anthropic", or "azure").
                Auto-detected from model name if not specified.
            extra_params: Extra kwargs to merge into every API call for this model.
        """
        if api_type is not None and api_type not in ["openai", "anthropic", "azure"]:
            raise ValueError("api_type must be 'openai', 'anthropic', or 'azure'")
        self._name = name
        self.url = url
        self.token = token
        self.api_type = api_type
        self._model = create_api_model(
            model_id=name, url=url, token=token, api_type=api_type, extra_params=extra_params
        )

    @property
    def name(self) -> str:
        return self._name

    async def run(
        self, prompt: str, attachments: "list[Attachment] | None" = None, *, task_id: str | None = None
    ) -> AgentResult:
        self._model.quiet = not self.verbose
        # Inline text attachments into prompt (non-agentic presentation)
        if attachments:
            prompt = self._inline_text_attachments(prompt, attachments)
        content = build_multimodal_content(prompt, attachments)
        try:
            output = await self._model.generate([{"role": "user", "content": content}])
        except Exception as e:
            _logger.warning(f"Agent error: {e}")
            if self.verbose:
                print(f"[bold red]OpenAIAPI agent error: {e}[/]")
            # Model not found is a fatal configuration error — abort evaluation
            if _is_model_not_found(e):
                raise ModelNotFoundError(f"Model '{self._name}' not found on {self.url}: {e}") from e
            if _is_unsupported_error(e):
                return AgentResult(outcome="unsupported", reason=f"unsupported: {e}")
            return AgentResult(outcome="error", reason=f"agent_error: {e}")

        return AgentResult(answer=output, metrics={})

    @staticmethod
    def _inline_text_attachments(prompt: str, attachments: "list[Attachment]") -> str:
        """Inline text file content into the prompt for non-agentic evaluation."""
        for att in attachments:
            text = att.read_text()
            if text:
                prompt = f"Start of text attachment >>>\n{text}\n<<< End of text attachment\n\n{prompt}"
        return prompt

    async def on_tasklist_end(self) -> None:
        """Close the API client to prevent async generator cleanup errors."""
        await self._model.close()
