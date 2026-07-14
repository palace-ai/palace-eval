import logging
from typing import TYPE_CHECKING

from palace.agents import Agent
from palace.evaluation.types import AgentResult
from palace.models.api_model import create_api_model
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
    ):
        """Initialize an APIAgent.

        Args:
            name: The name of the agent, corresponding to a model ID on the API server.
            url: The URL of the API server.
            token: The API token for authentication. Defaults to None.
            api_type: The API type to use ("openai", "anthropic", or "azure").
                Auto-detected from model name if not specified.
        """
        if api_type is not None and api_type not in ["openai", "anthropic", "azure"]:
            raise ValueError("api_type must be 'openai', 'anthropic', or 'azure'")
        self._name = name
        self.url = url
        self.token = token
        self.api_type = api_type
        self._model = create_api_model(model_id=name, url=url, token=token, api_type=api_type)

    @property
    def name(self) -> str:
        return self._name

    async def run(self, prompt: str, attachments: "list[Attachment] | None" = None, *, task_id: str | None = None) -> AgentResult:
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

