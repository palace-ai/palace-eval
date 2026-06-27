import logging
import re
from abc import abstractmethod

from openai import APITimeoutError, AsyncOpenAI, RateLimitError, InternalServerError, APIConnectionError
from anthropic import AsyncAnthropic, omit
from anthropic import (
    RateLimitError as AnthropicRateLimitError,
    InternalServerError as AnthropicInternalServerError,
    APITimeoutError as AnthropicTimeoutError,
    APIConnectionError as AnthropicConnectionError,
)
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

_MAX_IDENTICAL_500_RETRIES = 3
_RETRYABLE_EXCEPTIONS = (
    RateLimitError, InternalServerError, APITimeoutError, APIConnectionError,
    TimeoutException,
    AnthropicRateLimitError, AnthropicInternalServerError, AnthropicTimeoutError, AnthropicConnectionError,
)


def _log_retry(retry_state):
    """Log retry and abort on repeated identical 500 errors."""
    wait = APIModel._WAIT_SEQUENCE[min(retry_state.attempt_number - 1, len(APIModel._WAIT_SEQUENCE) - 1)]
    exc = retry_state.outcome.exception()
    msg = f"RETRY waiting {wait}s (attempt #{retry_state.attempt_number}): {exc}"
    _logger.warning(msg)
    self = retry_state.args[0]
    if not self.quiet:
        print(msg)
    self._check_permanent_failure(exc)


def create_api_model(
    model_id: str,
    url: str,
    token: str | None = None,
    api_type: str | None = None,
    strip_thinking: bool = True,
    quiet: bool = True,
) -> "APIModel":
    """Create the appropriate API model based on provider type.

    Arguments:
        model_id: The model identifier to use.
        url: The URL of the API server.
        token: The API token for authentication.
        api_type: "openai" or "anthropic". Auto-detected from model_id if not specified.
        strip_thinking: Whether to strip <think>...</think> tags from output.
        quiet: Whether to suppress retry log messages on terminal.
    """
    if api_type is None:
        api_type = "anthropic" if "claude" in model_id.lower() else "openai"
    if api_type == "anthropic":
        return AnthropicModel(model_id, url, token, strip_thinking=strip_thinking, quiet=quiet)
    if api_type == "openai":
        return OpenAIModel(model_id, url, token, strip_thinking=strip_thinking, quiet=quiet)
    raise ValueError(f"Unsupported api_type: {api_type!r}. Must be 'openai' or 'anthropic'.")


class APIModel(Model):
    """Base class for API-backed models with retry logic."""

    # Custom backoff: 10s×3, then ramp to 300s, then 300s until 24h total
    _WAIT_SEQUENCE = [10, 10, 10, 20, 30, 40, 60, 80, 100, 120, 150, 180, 240, 300]

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

    def __init__(self, model_id: str, url: str, token: str | None = None, *, strip_thinking: bool = True, quiet: bool = True):
        self.model_id = model_id
        self.url = url
        self.token = token
        self.strip_thinking = strip_thinking
        self.quiet = quiet
        self._retry_state = {"last_error": None, "count": 0}

    @property
    def name(self):
        """The name of the model."""
        return self.model_id

    def _check_permanent_failure(self, exc):
        """Raise if the same 500 error has repeated too many times."""
        if not isinstance(exc, (InternalServerError, AnthropicInternalServerError)):
            self._retry_state = {"last_error": None, "count": 0}
            return
        key = str(exc)
        if key == self._retry_state["last_error"]:
            self._retry_state["count"] += 1
        else:
            self._retry_state = {"last_error": key, "count": 1}
        if self._retry_state["count"] >= _MAX_IDENTICAL_500_RETRIES:
            raise RuntimeError(f"Permanent API error (repeated {self._retry_state['count']}x): {key[:200]}") from exc

    def _strip_thinking_tags(self, text: str) -> str:
        if self.strip_thinking and text:
            cleaned = _THINKING_TAG_RE.sub('', text).strip()
            if cleaned:
                return cleaned
        return text

    async def generate(self, messages: list[Message], **kwargs) -> str:
        """Generate text based on the input messages."""
        return await self._generate_with_retry(messages, **kwargs)

    @abstractmethod
    async def _call_api(self, messages: list[Message]) -> str:
        """Provider-specific API call. Receives agnostic messages, returns text."""
        ...

    @retry(
        stop=stop_after_delay(86400),
        wait=lambda retry_state: APIModel._WAIT_SEQUENCE[min(retry_state.attempt_number - 1, len(APIModel._WAIT_SEQUENCE) - 1)],
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        before_sleep=lambda retry_state: _log_retry(retry_state),
    )
    async def _generate_with_retry(self, messages: list[Message], **_) -> str:
        result = await self._call_api(messages)
        return self._strip_thinking_tags(result)


class OpenAIModel(APIModel):
    """OpenAI-compatible API model."""

    def __init__(self, model_id: str, url: str, token: str | None = None, *, strip_thinking: bool = True, quiet: bool = True):
        super().__init__(model_id, url, token, strip_thinking=strip_thinking, quiet=quiet)
        self.client = AsyncOpenAI(base_url=url, api_key=token or "no-key", timeout=3000)

    @staticmethod
    def _format_content(content):
        """Convert agnostic content parts to OpenAI format."""
        if not isinstance(content, list):
            return content
        parts = []
        for part in content:
            if part["type"] == "image":
                parts.append({"type": "image_url", "image_url": {"url": f"data:{part['media_type']};base64,{part['data']}"}})
            elif part["type"] == "audio":
                parts.append({"type": "input_audio", "input_audio": {"data": part["data"], "format": part["format"]}})
            else:
                parts.append(part)
        return parts

    async def _call_api(self, messages: list[Message]) -> str:
        formatted = [{"role": m["role"], "content": self._format_content(m["content"])} for m in messages]
        response = await self.client.chat.completions.create(
            model=self.model_id,
            messages=formatted,  # type: ignore
            max_tokens=16384,
            stream=False,
        )
        if not response.choices or response.choices[0].message.content is None:
            raise ValueError("Empty API response: no content returned")
        return response.choices[0].message.content


class AnthropicModel(APIModel):
    """Anthropic API model."""

    def __init__(self, model_id: str, url: str, token: str | None = None, *, strip_thinking: bool = True, quiet: bool = True):
        super().__init__(model_id, url, token, strip_thinking=strip_thinking, quiet=quiet)
        self.client = AsyncAnthropic(
            base_url=url.removesuffix("/v1"),
            default_headers={"Authorization": f"Bearer {token}"},
            timeout=3000,
        )

    @staticmethod
    def _format_content(content):
        """Convert agnostic content parts to Anthropic format."""
        if not isinstance(content, list):
            return content
        parts = []
        for part in content:
            if part["type"] == "image":
                parts.append({"type": "image", "source": {"type": "base64", "media_type": part["media_type"], "data": part["data"]}})
            elif part["type"] == "audio":
                # Anthropic doesn't support audio; pass as text fallback
                parts.append({"type": "text", "text": "[audio attachment not supported]"})
            else:
                parts.append(part)
        return parts

    async def _call_api(self, messages: list[Message]) -> str:
        system_prompt = None
        msgs = messages
        if msgs and msgs[0]["role"] == "system":
            system_prompt = str(msgs[0]["content"])
            msgs = msgs[1:]
        formatted = [{"role": m["role"], "content": self._format_content(m["content"])} for m in msgs]
        response = await self.client.messages.create(
            model=self.model_id,
            messages=formatted,  # type: ignore
            max_tokens=16384,
            stream=False,
            system=system_prompt if system_prompt is not None else omit,
        )  # type: ignore
        return response.content[0].text
