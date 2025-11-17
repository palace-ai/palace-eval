from typing import Literal

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

_huggingface_to_gptjrc_model_names_map = {
    "meta-llama/Llama-3.3-70B-Instruct": "llama-3.3-70b-instruct",
    "MiniMaxAI/MiniMax-M2": "minimax-m2",
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503": "mistral-small-3.1-24b",
    "Qwen/Qwen3-32B": "qwen3-32b",
    "Qwen/Qwen2.5-Coder-32B-Instruct": "qwen-coder-2.5-instruct",
    "openai/gpt-4o": "gpt-4o",
    "openai/gpt-oss-120b": "gpt-oss-120b",
}


class OpenAICompatibleModel(Model):
    def __init__(
        self,
        url: str,
        token: str | None = None,
        model_id: Literal[
            "meta-llama/Llama-3.3-70B-Instruct",
            "MiniMaxAI/MiniMax-M2",
            "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
            "Qwen/Qwen3-32B",
            "Qwen/Qwen2.5-Coder-32B-Instruct",
            "openai/gpt-4o",
            "openai/gpt-oss-120b",
        ] = "Qwen/Qwen3-32B",
    ):
        """
        A class to interact with OpenAI-compatible models.

        Arguments:
            model_id (str): The model ID to use as found on Huggingface. Defaults to "Qwen/Qwen3-8B".
            url (str): The URL of the OpenAI compatible API server.
        """
        if model_id not in _huggingface_to_gptjrc_model_names_map:
            raise ValueError(
                "BUG: keys in _huggingface_to_gptjrc_model_names_map and allowed Literals for model_id don't match."
            )
        self.model_id = _huggingface_to_gptjrc_model_names_map[model_id]
        self.client = OpenAI(api_key=token, base_url=url)

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
            f"Waiting for {retry_state.next_action.sleep:.0f} seconds due to rate limit..."  # type: ignore
        ),
    )
    def generate(
        self,
        messages: list[dict[str, str]],
        **_,
    ) -> str:
        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,  # type: ignore
                stream=False,
            )  # type: ignore
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
