# Copyright (C) 2025 European Union
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL) v. 1.2
# as published by the European Union.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.
#
# You should have received a copy of the European Union Public Licence
# along with this program. If not, see <https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12>.

import logging
import re
from abc import abstractmethod

from anthropic import (
    APIConnectionError as AnthropicConnectionError,
)
from anthropic import (
    APITimeoutError as AnthropicTimeoutError,
)
from anthropic import AsyncAnthropic, omit
from anthropic import (
    InternalServerError as AnthropicInternalServerError,
)
from anthropic import (
    RateLimitError as AnthropicRateLimitError,
)
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncAzureOpenAI,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    retry,
    stop_after_delay,
)

from palace.models.base_model import Message, Model
from palace.utils.exceptions import TimeoutException
from palace.utils.printing import print

_THINKING_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_logger = logging.getLogger("palace.api_model")

_MAX_IDENTICAL_500_RETRIES = 3
_RETRYABLE_EXCEPTIONS = (
    RateLimitError,
    InternalServerError,
    APITimeoutError,
    APIConnectionError,
    TimeoutException,
    AnthropicRateLimitError,
    AnthropicInternalServerError,
    AnthropicTimeoutError,
    AnthropicConnectionError,
)

# Connection errors that indicate permanent failure (wrong host/port/config), not worth retrying.
_PERMANENT_CONNECTION_ERRORS = (ConnectionRefusedError,)


def _is_permanent_connection_error(exc: Exception) -> bool:
    """Check if exception chain contains a permanent connection error."""
    while exc:
        if isinstance(exc, _PERMANENT_CONNECTION_ERRORS):
            return True
        # Check args[0] for nested exceptions (httpcore wraps errors this way)
        if hasattr(exc, "args") and exc.args and isinstance(exc.args[0], Exception):
            if _is_permanent_connection_error(exc.args[0]):
                return True
        exc = exc.__cause__
    return False


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
    extra_params: dict | None = None,
) -> "APIModel":
    """Create the appropriate API model based on provider type.

    Arguments:
        model_id: The model identifier to use.
        url: The URL of the API server.
        token: The API token for authentication.
        api_type: "openai", "anthropic", or "azure". Auto-detected from model_id and url if not specified.
        strip_thinking: Whether to strip <think>...</think> tags from output.
        quiet: Whether to suppress retry log messages on terminal.
        extra_params: Extra kwargs to merge into every API call for this model.
    """
    if api_type is None:
        if "claude" in model_id.lower():
            api_type = "anthropic"
        elif "azure-api.net" in url or "openai.azure.com" in url:
            api_type = "azure"
        else:
            api_type = "openai"
    if api_type == "anthropic":
        return AnthropicModel(
            model_id, url, token, strip_thinking=strip_thinking, quiet=quiet, extra_params=extra_params
        )
    if api_type == "azure":
        return AzureOpenAIModel(
            model_id, url, token, strip_thinking=strip_thinking, quiet=quiet, extra_params=extra_params
        )
    if api_type == "openai":
        return OpenAIModel(model_id, url, token, strip_thinking=strip_thinking, quiet=quiet, extra_params=extra_params)
    raise ValueError(f"Unsupported api_type: {api_type!r}. Must be 'openai', 'anthropic', or 'azure'.")


class APIModel(Model):
    """Base class for API-backed models with retry logic."""

    # Custom backoff: 10s×3, then ramp to 300s, then 300s until 24h total
    _WAIT_SEQUENCE = [10, 10, 10, 20, 30, 40, 60, 80, 100, 120, 150, 180, 240, 300]

    @classmethod
    def list_models(cls, url: str, token: str | None = None) -> list[str]:
        """List available models from the OpenAI-compatible API server."""
        import time

        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=token or "no-key", base_url=url)
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
        model_id: str,
        url: str,
        token: str | None = None,
        *,
        strip_thinking: bool = True,
        quiet: bool = True,
        extra_params: dict | None = None,
    ):
        self.model_id = model_id
        self.url = url
        self.token = token
        self.strip_thinking = strip_thinking
        self.quiet = quiet
        self.extra_params = extra_params or {}
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
            cleaned = _THINKING_TAG_RE.sub("", text).strip()
            if cleaned:
                return cleaned
        return text

    @staticmethod
    def _extract_text_from_content(content) -> str | None:
        """Extract text from delta.content, handling both string and structured list formats.

        Mistral's API returns delta.content as a list of structured parts when reasoning
        is enabled: [{'type': 'thinking', ...}, {'type': 'text', 'text': '...'}].
        Other providers return a plain string. This method normalizes both to a string,
        extracting only 'text' parts and skipping 'thinking' parts.
        """
        if isinstance(content, str):
            return content if content else None
        if isinstance(content, list):
            texts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                    texts.append(part["text"])
            return "".join(texts) if texts else None
        return None

    async def _collect_openai_stream(self, stream) -> str:
        """Collect text from an OpenAI-compatible stream with diagnostics on empty response."""
        collected: list[str] = []
        chunk_count = 0
        finish_reason: str | None = None
        reasoning_chars = 0
        usage: dict | None = None
        async for chunk in stream:
            chunk_count += 1
            if chunk.usage:
                usage = {"prompt": chunk.usage.prompt_tokens, "completion": chunk.usage.completion_tokens}
            if chunk.choices:
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                delta = choice.delta
                if delta.content:
                    text = self._extract_text_from_content(delta.content)
                    if text:
                        collected.append(text)
                # Track reasoning_content (vLLM/DeepSeek/Qwen3 reasoning models)
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    reasoning_chars += len(reasoning)
        if not collected:
            diag = f"finish_reason={finish_reason!r}, chunks={chunk_count}, reasoning_chars={reasoning_chars}"
            if usage:
                diag += f", usage={usage}"
            raise ValueError(f"Empty API response: no content returned ({diag})")
        return "".join(collected)

    async def generate(self, messages: list[Message], **kwargs) -> str:
        """Generate text based on the input messages."""
        return await self._generate_with_retry(messages, **kwargs)

    async def close(self) -> None:
        """Close the underlying HTTP client. Call this when done with the model."""
        if hasattr(self.client, "close"):
            await self.client.close()

    @abstractmethod
    async def _call_api(self, messages: list[Message]) -> str:
        """Provider-specific API call. Receives agnostic messages, returns text."""
        ...

    @retry(
        stop=stop_after_delay(86400),
        wait=lambda retry_state: APIModel._WAIT_SEQUENCE[
            min(retry_state.attempt_number - 1, len(APIModel._WAIT_SEQUENCE) - 1)
        ],
        retry=lambda rs: (
            isinstance(rs.outcome.exception(), _RETRYABLE_EXCEPTIONS)
            and not _is_permanent_connection_error(rs.outcome.exception())
        ),
        before_sleep=lambda retry_state: _log_retry(retry_state),
    )
    async def _generate_with_retry(self, messages: list[Message], **_) -> str:
        result = await self._call_api(messages)
        return self._strip_thinking_tags(result)


class OpenAIModel(APIModel):
    """OpenAI-compatible API model."""

    def __init__(
        self,
        model_id: str,
        url: str,
        token: str | None = None,
        *,
        strip_thinking: bool = True,
        quiet: bool = True,
        extra_params: dict | None = None,
    ):
        super().__init__(model_id, url, token, strip_thinking=strip_thinking, quiet=quiet, extra_params=extra_params)
        self.client = AsyncOpenAI(base_url=url, api_key=token or "no-key", timeout=3000)

    @staticmethod
    def _format_content(content):
        """Convert agnostic content parts to OpenAI format."""
        if not isinstance(content, list):
            return content
        parts = []
        for part in content:
            if part["type"] == "image":
                parts.append(
                    {"type": "image_url", "image_url": {"url": f"data:{part['media_type']};base64,{part['data']}"}}
                )
            elif part["type"] == "audio":
                parts.append({"type": "input_audio", "input_audio": {"data": part["data"], "format": part["format"]}})
            else:
                parts.append(part)
        return parts

    async def _call_api(self, messages: list[Message]) -> str:
        formatted = [{"role": m["role"], "content": self._format_content(m["content"])} for m in messages]
        kwargs = {
            "model": self.model_id,
            "messages": formatted,
            "max_completion_tokens": 32768,
            "stream": True,
        }
        kwargs.update(self.extra_params)
        stream = await self.client.chat.completions.create(**kwargs)  # type: ignore
        return await self._collect_openai_stream(stream)


class AzureOpenAIModel(APIModel):
    """Azure OpenAI API model using deployment-based routing and api-key auth."""

    DEFAULT_API_VERSION = "2024-10-21"

    def __init__(
        self,
        model_id: str,
        url: str,
        token: str | None = None,
        *,
        api_version: str | None = None,
        strip_thinking: bool = True,
        quiet: bool = True,
        extra_params: dict | None = None,
    ):
        super().__init__(model_id, url, token, strip_thinking=strip_thinking, quiet=quiet, extra_params=extra_params)
        self.api_version = api_version or self.DEFAULT_API_VERSION
        self.client = AsyncAzureOpenAI(
            azure_endpoint=url,
            api_key=token or "no-key",
            api_version=self.api_version,
            timeout=3000,
        )

    @staticmethod
    def _format_content(content):
        """Convert agnostic content parts to OpenAI format."""
        if not isinstance(content, list):
            return content
        parts = []
        for part in content:
            if part["type"] == "image":
                parts.append(
                    {"type": "image_url", "image_url": {"url": f"data:{part['media_type']};base64,{part['data']}"}}
                )
            elif part["type"] == "audio":
                parts.append({"type": "input_audio", "input_audio": {"data": part["data"], "format": part["format"]}})
            else:
                parts.append(part)
        return parts

    async def _call_api(self, messages: list[Message]) -> str:
        formatted = [{"role": m["role"], "content": self._format_content(m["content"])} for m in messages]
        kwargs = {
            "model": self.model_id,
            "messages": formatted,
            "max_completion_tokens": 32768,
            "stream": True,
        }
        kwargs.update(self.extra_params)
        stream = await self.client.chat.completions.create(**kwargs)  # type: ignore
        return await self._collect_openai_stream(stream)


class AnthropicModel(APIModel):
    """Anthropic API model."""

    def __init__(
        self,
        model_id: str,
        url: str,
        token: str | None = None,
        *,
        strip_thinking: bool = True,
        quiet: bool = True,
        extra_params: dict | None = None,
    ):
        super().__init__(model_id, url, token, strip_thinking=strip_thinking, quiet=quiet, extra_params=extra_params)
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
                parts.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": part["media_type"], "data": part["data"]},
                    }
                )
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
        collected: list[str] = []
        kwargs = {
            "model": self.model_id,
            "messages": formatted,
            "max_tokens": 32768,
            "system": system_prompt if system_prompt is not None else omit,
        }
        # SDK 1.x: extra params (temperature, thinking, etc.) go via extra_body
        async with self.client.messages.stream(**kwargs, extra_body=self.extra_params or None) as stream:  # type: ignore
            async for text in stream.text_stream:
                collected.append(text)
        if not collected:
            # Get final message for diagnostics
            try:
                final = await stream.get_final_message()
                stop = final.stop_reason
                usage = {"input": final.usage.input_tokens, "output": final.usage.output_tokens}
                diag = f"stop_reason={stop!r}, usage={usage}"
            except Exception:
                diag = "no final message available"
            raise ValueError(f"Empty API response: no content returned ({diag})")
        return "".join(collected)
