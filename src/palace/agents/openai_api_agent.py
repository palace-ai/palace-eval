import logging
from typing import Any

from palace.agents import Agent
from palace.evaluation.types import AgentResult
from palace.models.api_model import APIModel
from palace.utils.multimodal import build_multimodal_content
from palace.utils.printing import print

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
        api_type: str = "openai",
    ):
        """Initialize an OpenAIAPIAgent.

        Args:
            name: The name of the agent, corresponding to a model ID on the API server.
            url: The URL of the OpenAI-compatible API server.
            token: The API token for authentication. Defaults to None.
            api_type: The API type to use ("openai" or "anthropic"). Defaults to "openai".
        """
        if api_type not in ["openai", "anthropic"]:
            raise ValueError("api_type must be either 'openai' or 'anthropic'")
        self._name = name
        self.url = url
        self.token = token
        self.api_type = api_type
        self._model = APIModel(model_id=name, url=url, token=token, api_type=api_type)

    @property
    def name(self) -> str:
        return self._name

    async def run(self, prompt: str, image: str | None = None, *, task_id: str | None = None) -> AgentResult:
        self._model.quiet = not self.verbose
        content = build_multimodal_content(prompt, image)
        try:
            output = await self._model.generate([{"role": "user", "content": content}])
        except Exception as e:
            _logger.warning(f"Agent error: {e}")
            if self.verbose:
                print(f"[bold red]OpenAIAPI agent error: {e}[/]")
            return AgentResult(is_skipped=True, skip_reason="agent_error")

        return AgentResult(answer=output, metrics={})
