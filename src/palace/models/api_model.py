import re

from anthropic import Anthropic, omit
from openai import APITimeoutError, OpenAI, OpenAIError, RateLimitError, InternalServerError, APIConnectionError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from palace.models.base_model import Message, Model
from palace.utils.exceptions import TimeoutException
from palace.utils.printing import print

_THINKING_TAG_RE = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)


class APIModel(Model):
    @classmethod
    def list_models(cls, url: str, token: str | None = None) -> list[str]:
        """List available models from the OpenAI-compatible API server."""
        client = OpenAI(api_key=token, base_url=url)
        models = client.models.list()
        return [model.id for model in models.data]

    def __init__(
        self,
        /,
        model_id: str,
        url: str,
        token: str | None = None,
        api_type: str = "openai",
        strip_thinking_tags: bool = True,
    ):
        """
        A class to interact with OpenAI-compatible models.

        Arguments:
            model_id (str): The model identifier to use.
            url (str): The URL of the OpenAI compatible API server.
            token (str): The API token for authentication.
            api_type (str): The API type to use. Allowed values are `openai` and `anthropic`.
                Defaults to `openai`.
            strip_thinking_tags (bool): Whether to strip <think>...</think> tags
                from model output. Defaults to True.
        """
        assert api_type in {"openai", "anthropic"}, (
            "api_type must be either 'openai' or 'anthropic'"
        )
        self.api_type = api_type
        self.model_id = model_id
        self.strip_thinking_tags = strip_thinking_tags

        if self.api_type == "openai":
            self.client = OpenAI(base_url=url, api_key=token or "no-key")
        elif self.api_type == "anthropic":
            self.client = Anthropic(
                base_url=url.removesuffix("/v1"),
                default_headers={"Authorization": f"Bearer {token}"},
            )
        else:
            raise ValueError(f"Unsupported API type: {api_type}")

    @property
    def name(self):
        """The name of the model."""
        return self.model_id

    def generate(
        self,
        messages: list[Message],
        **kwargs,
    ) -> str:
        """Generate text based on the input messages.

        Arguments:
            messages (list[dict]): A list of messages in the format required by OpenAI chat completions.

        Returns:
            str: The generated text.

        Raises:
            Exception: If generation fails after exhausting all retries.
        """
        return self.generate_with_retry(messages, **kwargs)

    # Exponential backoff (total 40m10s)
    # x > 10s > x > 20s > x > 40s > x > 1m20s > x > 2m40s > x > 5m > x > 10m > x > 10m > x > 10m > x
    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=10, max=600),
        retry=retry_if_exception_type((RateLimitError, InternalServerError, APITimeoutError, APIConnectionError, TimeoutException)),
        before_sleep=lambda retry_state: print(
            f"Retrying in {retry_state.next_action.sleep:.0f}s due to: {retry_state.outcome.exception()}"  # type: ignore
        ),
    )
    def generate_with_retry(self, messages: list[Message], **_) -> str:
        try:
            if self.api_type == "openai":
                chat_completion = self.client.chat.completions.create(  # type: ignore
                    model=self.model_id,
                    messages=messages,  # type: ignore
                    stream=False,
                )
                result = chat_completion.choices[0].message.content
            elif self.api_type == "anthropic":
                system_prompt = None
                if messages[0]["role"] == "system":
                    system_prompt = messages.pop(0)
                chat_completion = self.client.messages.create(  # type: ignore
                    model=self.model_id,
                    messages=messages,  # type: ignore
                    max_tokens=2048,
                    stream=False,
                    system=str(system_prompt["content"])
                    if system_prompt is not None
                    else omit,
                )  # type: ignore
                result = chat_completion.content[0].text
            else:
                raise ValueError(f"Unsupported API type: {self.api_type}")

            if self.strip_thinking_tags and result:
                cleaned = _THINKING_TAG_RE.sub('', result).strip()
                if cleaned:
                    result = cleaned

            return result
        except (TimeoutException, OpenAIError, Exception):
            raise
