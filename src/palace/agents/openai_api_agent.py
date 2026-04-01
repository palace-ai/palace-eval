from typing import Any

from palace.agents import Agent
from palace.environments.base_environment import Environment
from palace.environments.unknown_environment import UnknownEnvironment
from palace.models.api_model import APIModel
from palace.utils.multimodal import build_multimodal_content


class OpenAIAPIAgent(Agent):
    """A class to connect to a remote agent deployed via OpenAI-compatible AI and call it as a black box.
    This class can also be used to test a normal LLM with no agentic behaviour, using the same agent evaluation pipeline.
    Metrics are not supported for this agent type yet.
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
        self._environment = UnknownEnvironment()

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return "Unknown remote model"

    @property
    def paradigm_name(self) -> str:
        return "Unknown remote paradigm"

    @property
    def environment(self) -> Environment:
        return self._environment

    def run(self, prompt: str, image: str | None = None) -> tuple[str | None, dict[str, Any] | None]:
        agent = APIModel(
            model_id=self.name, url=self.url, token=self.token, api_type=self.api_type
        )
        content = build_multimodal_content(prompt, image)
        try:
            output = agent.generate([{"role": "user", "content": content}])
        except Exception as e:
            print(f"[bold red]OpenAIAPI agent error: {e}[/]")
            return None, None

        return output, {}
