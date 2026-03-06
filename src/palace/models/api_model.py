from anthropic import Anthropic, omit
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


class APIModel(Model):
    @classmethod
    def list_models(cls, url: str, token: str | None = None) -> list[str]:
        """List available models from the OpenAI-compatible API server."""
        client = OpenAI(api_key=token, base_url=url)
        models = client.models.list()
        return [model.id for model in models.data]

    _DEFAULT_MODEL_ID = "llama-3.3-70b-instruct"

    def __init__(
        self,
        /,
        model_id: str,
        url: str,
        token: str | None = None,
        api_type: str = "openai",
    ):
        """
        A class to interact with OpenAI-compatible models.

        Arguments:
            url (str): The URL of the OpenAI compatible API server.
            token (str): The API token for authentication.
            api_type (str): The API type to use. Allowed values are `openai` and `anthropic`.
                Defaults to `openai`.
        """
        assert api_type in {"openai", "anthropic"}, (
            "api_type must be either 'openai' or 'anthropic'"
        )
        self.api_type = api_type

        if model_id in _huggingface_to_gptjrc_model_names_map:
            self.model_id = _huggingface_to_gptjrc_model_names_map[model_id]
        else:
            self.model_id = model_id

        if self.api_type == "openai":
            self.client = OpenAI(base_url=url, api_key=token)
        elif self.api_type == "anthropic":
            self.client = Anthropic(
                base_url=url.removesuffix(
                    "/v1"
                ),  # GPTJRC's Anthropic-compatible API doesn't want the /v1 suffix in the base URL
                default_headers={
                    "Authorization": f"Bearer {token}"
                },  # GPTJRC's Anthropic-compatible API uses Bearer token instead of api_key parameter
            )
        else:
            raise ValueError(f"Unsupported API type: {api_type}")

    @property
    def name(self):
        """The name of the model."""
        return self.model_id

    def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> str:
        """Generate text based on the input messages.

        Arguments:
            messages (list[dict]): A list of messages in the format required by OpenAI chat completions.

        Returns:
            str: The generated text.
        """
        try:
            return self.generate_with_retry(messages, **kwargs)
        except TimeoutException as e:
            print(
                f"[bold yellow on_red]\nTimeoutException raised during model generation! This likely comes from a threading issue and not from the API.\n[/][yellow]{messages}\n"
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

    # Exponential backoff (total 40m10s)
    # x > 10s > x > 20s > x > 40s > x > 1m20s > x > 2m40s > x > 5m > x > 10m > x > 10m > x > 10m > x
    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=10, max=600),
        retry=retry_if_exception_type((RateLimitError, TimeoutException, OpenAIError)),
        before_sleep=lambda retry_state: print(
            f"Waiting for {retry_state.next_action.sleep:.0f} seconds due to rate limit..."  # type: ignore
        ),
    )
    def generate_with_retry(self, messages: list[dict[str, str]], **_) -> str:
        try:
            if self.api_type == "openai":
                chat_completion = self.client.chat.completions.create(  # type: ignore
                    model=self.model_id,
                    messages=messages,  # type: ignore
                    stream=False,
                )
                return chat_completion.choices[0].message.content
            elif self.api_type == "anthropic":
                system_prompt = None
                if messages[0]["role"] == "system":
                    system_prompt = messages.pop(0)
                    print(
                        f"[bold yellow][WARN] System prompt was set for an Anthropic API model, but might not be used by the GPT@JRC backend: {system_prompt['content']}[/]"
                    )
                chat_completion = self.client.messages.create(  # type: ignore
                    model=self.model_id,
                    messages=messages,  # type: ignore
                    max_tokens=2048,
                    stream=False,
                    system=system_prompt[
                        "content"
                    ]  # BUG: `system` parameter doesn't seem to be used by GPT@JRC backend
                    if system_prompt is not None
                    else omit,
                )  # type: ignore
                return chat_completion.content[0].text
            else:
                raise ValueError(f"Unsupported API type: {self.api_type}")
        except (TimeoutException, OpenAIError, Exception):
            raise
