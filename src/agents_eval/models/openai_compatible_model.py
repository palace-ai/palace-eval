from typing import Dict, List, Literal, Optional

from openai import OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agents_eval.models import Model
from agents_eval.utils.secrets import GPTJRC_TOKEN

OpenAICompatibleAPIURL = Literal["localhost", "gptjrc"]
_OpenAICompatibleAPIURLs = {
    "localhost": "http://localhost:8000/v1",
    "gptjrc": "https://api-gpt.jrc.ec.europa.eu/v1",
}


class OpenAICompatibleModel(Model):
    def __init__(
        self,
        model_id: str = "Qwen/Qwen3-8B",
        api_url: OpenAICompatibleAPIURL = "gptjrc",
    ):
        """
        A class to interact with OpenAI-compatible models.

        Arguments:
            model_id (str): The model ID to use as found on Huggingface. Defaults to "Qwen/Qwen3-8B".
            local (bool): Whether to use a local model (True) or GPT@JRC (False). Defaults to False.
        """
        if api_url not in _OpenAICompatibleAPIURLs:
            raise ValueError(
                f"Invalid api_url '{api_url}'. Must be one of {list(_OpenAICompatibleAPIURLs.keys())}."
            )

        self.model_id = model_id
        base_url = _OpenAICompatibleAPIURLs[api_url]

        self.client = OpenAI(api_key=GPTJRC_TOKEN, base_url=base_url)

    @property
    def name(self):
        """The name of the model."""
        return self.model_id

    @retry(
        stop=stop_after_attempt(5),  # Max 5 attempts
        wait=wait_exponential(
            multiplier=10, max=60
        ),  # Exponential backoff (10s -> 20s -> 40s -> 60s)
        retry=retry_if_exception_type(
            RateLimitError,
        ),  # Retry only on RateLimitError
        before_sleep=lambda retry_state: print(
            f"Waiting for {retry_state.next_action.sleep:.0f} seconds due to rate limit..."
        ),
    )
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = 0.0,
        **_,
    ) -> str:
        chat_completion = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            stream=False,
            temperature=temperature,
        )
        return chat_completion.choices[0].message.content
