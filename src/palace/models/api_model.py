import logging
import re

from anthropic import AsyncAnthropic, omit
from anthropic import (
    RateLimitError as AnthropicRateLimitError,
    InternalServerError as AnthropicInternalServerError,
    APITimeoutError as AnthropicTimeoutError,
    APIConnectionError as AnthropicConnectionError,
)
from openai import APITimeoutError, AsyncOpenAI, OpenAIError, RateLimitError, InternalServerError, APIConnectionError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_delay,
)

from palace.models.base_model import Message, Model
from palace.utils.exceptions import TimeoutException
from palace.utils.printing import print

_THINKING_TAG_RE = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)
_logger = logging.getLogger("palace.api_model")


def _log_retry(retry_state):
    """Log retry to file (always) and print to terminal (if not quiet)."""
    wait = APIModel._WAIT_SEQUENCE[min(retry_state.attempt_number - 1, len(APIModel._WAIT_SEQUENCE) - 1)]
    exc = retry_state.outcome.exception()
    msg = f"RETRY waiting {wait}s (attempt #{retry_state.attempt_number}): {exc}"
    _logger.warning(msg)
    self = retry_state.args[0]
    if not self.quiet:
        print(msg)


class APIModel(Model):
    @classmethod
    def list_models(cls, url: str, token: str | None = None) -> list[str]:
        """List available models from the OpenAI-compatible API server."""
        from openai import OpenAI, RateLimitError
        import time
        client = OpenAI(api_key=token, base_url=url)
        for attempt in range(5):
            try:
                models = client.models.list()
                return [model.id for model in models.data]
            except RateLimitError:
                if attempt == 4:
                    raise
                time.sleep(5 * (attempt + 1))

    def __init__(
        self,
        /,
        model_id: str,
        url: str,
        token: str | None = None,
        api_type: str = "openai",
        strip_thinking: bool = True,
        quiet: bool = True,
    ):
        """
        A class to interact with OpenAI-compatible models.

        Arguments:
            model_id (str): The model identifier to use.
            url (str): The URL of the OpenAI compatible API server.
            token (str): The API token for authentication.
            api_type (str): The API type to use. Allowed values are `openai` and `anthropic`.
                Defaults to `openai`.
            strip_thinking (bool): Whether to strip <think>...</think> tags
                from model output. Defaults to True.
            quiet (bool): Whether to suppress retry log messages on terminal. Defaults to True.
        """
        assert api_type in {"openai", "anthropic"}, (
            "api_type must be either 'openai' or 'anthropic'"
        )
        self.api_type = api_type
        self.model_id = model_id
        self.strip_thinking = strip_thinking
        self.quiet = quiet

        if self.api_type == "openai":
            self.client = AsyncOpenAI(base_url=url, api_key=token or "no-key")
        elif self.api_type == "anthropic":
            self.client = AsyncAnthropic(
                base_url=url.removesuffix("/v1"),
                default_headers={"Authorization": f"Bearer {token}"},
            )
        else:
            raise ValueError(f"Unsupported API type: {api_type}")

    @property
    def name(self):
        """The name of the model."""
        return self.model_id

    async def generate(
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
        return await self.generate_with_retry(messages, **kwargs)

    # Custom backoff: 10s×3, then ramp to 300s, then 300s until 24h total
    _WAIT_SEQUENCE = [10, 10, 10, 20, 30, 40, 60, 80, 100, 120, 150, 180, 240, 300]

    @retry(
        stop=stop_after_delay(86400),
        wait=lambda retry_state: APIModel._WAIT_SEQUENCE[min(retry_state.attempt_number - 1, len(APIModel._WAIT_SEQUENCE) - 1)],
        retry=retry_if_exception_type((RateLimitError, InternalServerError, APITimeoutError, APIConnectionError, TimeoutException, AnthropicRateLimitError, AnthropicInternalServerError, AnthropicTimeoutError, AnthropicConnectionError)),
        before_sleep=lambda retry_state: _log_retry(retry_state),
    )
    async def generate_with_retry(self, messages: list[Message], **_) -> str:
        try:
            if self.api_type == "openai":
                chat_completion = await self.client.chat.completions.create(  # type: ignore
                    model=self.model_id,
                    messages=messages,  # type: ignore
                    stream=False,
                )
                if not chat_completion.choices or chat_completion.choices[0].message.content is None:
                    raise ValueError("Empty API response: no content returned")
                result = chat_completion.choices[0].message.content
            elif self.api_type == "anthropic":
                system_prompt = None
                msgs = messages
                if msgs and msgs[0]["role"] == "system":
                    system_prompt = msgs[0]
                    msgs = msgs[1:]
                chat_completion = await self.client.messages.create(  # type: ignore
                    model=self.model_id,
                    messages=msgs,  # type: ignore
                    max_tokens=2048,
                    stream=False,
                    system=str(system_prompt["content"])
                    if system_prompt is not None
                    else omit,
                )  # type: ignore
                result = chat_completion.content[0].text
            else:
                raise ValueError(f"Unsupported API type: {self.api_type}")

            if self.strip_thinking and result:
                cleaned = _THINKING_TAG_RE.sub('', result).strip()
                if cleaned:
                    result = cleaned

            return result
        except (TimeoutException, OpenAIError, AnthropicRateLimitError, AnthropicInternalServerError, AnthropicTimeoutError, AnthropicConnectionError):
            raise
