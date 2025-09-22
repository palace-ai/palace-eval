from typing import Dict, List, Literal, Optional

from openai import OpenAI, OpenAIError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from palace.models.base_model import Model
from palace.utils.exceptions import TimeoutException
from palace.utils.printing import print
from palace.utils.secrets import GPTJRC_TOKEN
from palace.utils.threading import with_timeout

OpenAICompatibleAPIURL = Literal["localhost", "gptjrc"]
_OpenAICompatibleAPIURLs = {
    "localhost": "http://localhost:8000/v1",
    "gptjrc": "https://api-gpt.jrc.ec.europa.eu/v1",
}

_huggingface_to_gptjrc_model_names_map = {
    "meta-llama/Llama-3.3-70B-Instruct": "llama-3.3-70b-instruct",
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503": "mistral-small-3.1-24b",
    "Qwen/Qwen3-32B": "qwen3-32b",
    "Qwen/Qwen2.5-Coder-32B-Instruct": "qwen-coder-2.5-instruct",
}


class OpenAICompatibleModel(Model):
    def __init__(
        self,
        model_id: str = "Qwen/Qwen3-32B",
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

        if model_id in _huggingface_to_gptjrc_model_names_map:
            model_id = _huggingface_to_gptjrc_model_names_map[model_id]
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
        timeout_seconds: Optional[int] = 60,
        # temperature: Optional[float] = 0.0,
        **_,
    ) -> str:
        try:
            chat_completion = with_timeout(seconds=timeout_seconds)(
                self.client.chat.completions.create
            )(
                model=self.model_id,
                messages=messages,
                stream=False,
                # temperature=temperature,
            )
            return chat_completion.choices[0].message.content
        except TimeoutException as e:
            print(
                f"[bold yellow on_red]\nTIMEOUT EXCEPTION IS CAUGHT!\n[/][yellow]{messages}\n"
            )
            return f"Timeout occurred: {e}"
        except OpenAIError as e:
            print(
                f"[bold yellow]The model could not generate text for this request. An unexpected exception occurred or the request timed out:\n{e}[/]"
            )
            return "The model could not generate text because it timed out. Please try again."
        except Exception as e:
            print(f"[bold yellow]Critical unknown error while generating text:\n{e}[/]")
            return "The model could not generate text due to an unknown error. Please try again."
