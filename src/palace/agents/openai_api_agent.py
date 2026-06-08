import logging
from typing import TYPE_CHECKING, Any

from palace.agents import Agent
from palace.evaluation.types import AgentResult
from palace.models.api_model import APIModel
from palace.utils.multimodal import build_multimodal_content
from palace.utils.printing import print

if TYPE_CHECKING:
    from palace.evaluation.types import Attachment

_logger = logging.getLogger("palace.openai_api_agent")


class OpenAIAPIAgent(Agent):
    """Agent that calls an OpenAI-compatible or Anthropic API endpoint.

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
        """Initialize an OpenAIAPIAgent.

        Args:
            name: The name of the agent, corresponding to a model ID on the API server.
            url: The URL of the OpenAI-compatible API server.
            token: The API token for authentication. Defaults to None.
            api_type: The API type to use ("openai" or "anthropic").
                Auto-detected from model name if not specified.
        """
        if api_type is not None and api_type not in ["openai", "anthropic"]:
            raise ValueError("api_type must be either 'openai' or 'anthropic'")
        self._name = name
        self.url = url
        self.token = token
        self.api_type = api_type
        self._model = APIModel(model_id=name, url=url, token=token, api_type=api_type)

    @property
    def name(self) -> str:
        return self._name

    async def run(self, prompt: str, attachments: "list[Attachment] | None" = None, *, task_id: str | None = None) -> AgentResult:
        self._model.quiet = not self.verbose
        content = build_multimodal_content(prompt, attachments)
        try:
            output = await self._model.generate([{"role": "user", "content": content}])
        except Exception as e:
            _logger.warning(f"Agent error: {e}")
            if self.verbose:
                print(f"[bold red]OpenAIAPI agent error: {e}[/]")
            # If attachments were sent and error is content-related, mark as unsupported
            err_str = str(e).lower()
            if attachments and ("content block" in err_str or "image_url" in err_str or "input_audio" in err_str
                               or "unsupported" in err_str or "invalid_request_error" in err_str):
                return AgentResult(is_skipped=True, skip_reason="unsupported_attachment")
            return AgentResult(is_skipped=True, skip_reason="agent_error")

        return AgentResult(answer=output, metrics={})
