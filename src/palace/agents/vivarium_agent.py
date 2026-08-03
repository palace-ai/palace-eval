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

"""Vivarium agent — delegates execution to vivarium service."""

import asyncio
import base64
import importlib.util
import inspect
import io
import logging
import os
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from palace.agents.base_agent import Agent
from palace.evaluation.types import AgentResult
from palace.task_types.base import ExecutionEnvironment, Task
from palace.utils.printing import print

if TYPE_CHECKING:
    from palace.evaluation.types import Attachment

_logger = logging.getLogger("palace.vivarium_agent")

# Transient HTTP status codes that are safe to retry.
_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504, 529})

# Network-level exceptions that indicate transient connectivity issues.
_TRANSIENT_NETWORK_ERRORS = (
    httpx.ConnectError, httpx.TimeoutException, httpx.ReadError, httpx.RemoteProtocolError,
)


def _is_transient_http(exc: Exception) -> bool:
    """Return True if the exception represents a transient/retryable HTTP error."""
    if isinstance(exc, _TRANSIENT_NETWORK_ERRORS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _TRANSIENT_STATUS_CODES
    return False


class VivariumAgent(Agent):
    """Agent that delegates execution to vivarium's sandboxed Docker environments.

    Args:
        name: Model name (passed to vivarium as model_name for LLM calls).
        url: LLM API base URL.
        token: LLM API key.
        vivarium_url: Vivarium service URL. If None, auto-starts via vivarium SDK.
        timeout_seconds: Max time per agent run.
        max_steps: Max agent loop iterations per task.
    """

    agentic: bool = True

    def __init__(
        self,
        name: str,
        url: str,
        token: str | None,
        vivarium_url: str | None = None,
        timeout_seconds: int = 7200,
        max_steps: int = 200,
    ):
        self._name = name
        self._url = url
        self._token = token
        self._timeout = timeout_seconds
        self._max_steps = max_steps
        self._vivarium_url = vivarium_url or os.getenv("VIVARIUM_URL") or None
        self._spec_ids: dict[str, str] = {}  # env_name → vivarium spec_id
        self._env_configs: dict[str, dict] = {}  # env_name → spec config (lazy)
        self._seed_fns: dict[str, object] = {}  # env_path → seed function
        self._archives: dict[str, bytes | None] = {}  # env_path → tar.gz bytes
        self._task_files_dirs: list[Path] = []  # resolved task_files directories
        self._envs: dict[str, Any] = {}  # task_id → Environment
        self._client: Any = None
        self._auto_started = False
        self._tasklist_path: Path | None = None

        try:
            from vivarium import Client
        except ImportError:
            raise RuntimeError(
                "Agentic evaluation requires vivarium. "
                "Install with:\n"
                "  git clone https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/research/vivarium.git\n"
                "  uv pip install -e vivarium/"
            )

        auto_start = self._vivarium_url is None
        self._client = Client(url=self._vivarium_url, auto_start=auto_start)
        self._auto_started = auto_start

    @property
    def name(self) -> str:
        return self._name

    async def on_tasklist_start(self, tasklist_path: Path, info: dict) -> None:
        """Store environment configs. Specs registered lazily on first use."""
        started = " (auto-started)" if self._auto_started else ""
        print(f"[blue]:whale: Agentic mode — Vivarium @ {self._client._url}{started}[/]")

        self._tasklist_path = tasklist_path

        # Resolve task_files search directories
        task_files_path = info.get("task_files_path", "task_files")
        self._task_files_dirs = sorted(d for d in tasklist_path.glob(task_files_path) if d.is_dir())

        # Store environment configurations for lazy registration
        if "env" in info:
            self._env_configs = info["env"]
        else:
            # No env key — use vivarium's built-in default spec.
            # Vivarium registers "default" at startup; if missing, the 404 at
            # create_environment time is a clear enough error.
            self._env_configs = {"default": {}}
            self._spec_ids["default"] = "default"

        # Pre-load seed functions and archives per unique environment path
        self._seed_fns: dict[str, object] = {}
        self._archives: dict[str, bytes | None] = {}
        for env_name, env_config in self._env_configs.items():
            env_path = env_config.get("path", "environment")
            if env_path not in self._archives:
                env_dir = tasklist_path / env_path
                if env_dir.is_dir():
                    seed_path = env_dir / "seed.py"
                    if seed_path.exists():
                        self._seed_fns[env_path] = _load_fn(seed_path, "seed")
                    self._archives[env_path] = _tar_gz(env_dir)
                else:
                    self._archives[env_path] = None

        _logger.info(f"Loaded {len(self._env_configs)} environment config(s) (lazy registration)")

    async def on_task_start(self, task: Task) -> ExecutionEnvironment | None:
        """Create a sandboxed environment and run seed if present. Returns Environment."""
        # Resolve which spec to use for this task
        env_name = task.custom_fields.get("env")
        if env_name is None:
            if len(self._env_configs) == 1:
                env_name = next(iter(self._env_configs))
            else:
                raise ValueError(
                    f"Task '{task.id}' has no 'env' field but tasklist defines "
                    f"{len(self._env_configs)} environments: {list(self._env_configs.keys())}"
                )
        if env_name not in self._env_configs:
            raise ValueError(
                f"Task '{task.id}' references env '{env_name}' but available environments are: "
                f"{list(self._env_configs.keys())}"
            )

        # Lazy spec registration: register on first use
        if env_name not in self._spec_ids:
            spec_json = self._env_configs[env_name]
            env_path = spec_json.get("path", "environment")
            image = spec_json.get("image")
            _logger.info(f"Registering spec '{env_name}' (first use, image: {image})")

            # Retry on transient errors (503 disk pressure, 429, 5xx, connection issues)
            while True:
                try:
                    spec_id = await self._client.register_spec(spec_json, self._archives.get(env_path))
                    break
                except (httpx.HTTPStatusError, *_TRANSIENT_NETWORK_ERRORS) as e:
                    if _is_transient_http(e):
                        _logger.warning(f"Transient error registering spec, retrying in 30s: {e}")
                        await asyncio.sleep(30)
                    else:
                        raise
            self._spec_ids[env_name] = spec_id
            _logger.info(f"Spec '{env_name}' registered (image ready)")

        spec_id = self._spec_ids[env_name]
        task_files = self._package_task_files(task)

        # Retry on transient errors (429, 5xx, connection issues) until task timeout
        while True:
            try:
                env = await self._client.create_environment(
                    spec_id=spec_id,
                    task_id=task.id,
                    task_files=task_files,
                )
                break
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException,
                    httpx.ReadError, httpx.RemoteProtocolError) as e:
                if _is_transient_http(e):
                    _logger.debug(f"Transient error creating environment, retrying: {e}")
                    await asyncio.sleep(5)
                else:
                    raise

        self._envs[task.id] = env

        env_path = self._env_configs[env_name].get("path", "environment")
        seed_fn = self._seed_fns.get(env_path)
        if seed_fn:
            _logger.info(f"Seeding environment for {task.id}")
            seed_args = task.custom_fields.get("seed_args")
            result = seed_fn(seed_args, env)
            if inspect.isawaitable(result):
                await result
            _logger.info(f"Seed complete for {task.id}")

        return env  # satisfies ExecutionEnvironment protocol (exec/read/write)

    async def run(
        self, prompt: str, attachments: "list[Attachment] | None" = None, *, task_id: str | None = None
    ) -> AgentResult:
        """Submit agent run and poll until completion."""
        assert task_id is not None, "VivariumAgent.run() requires task_id"
        env = self._envs[task_id]

        # Agentic presentation: write to disk, encode embeddable for API, add note
        encoded_attachments = None
        if attachments:
            prompt, encoded_attachments = await self._prepare_attachments(env, prompt, attachments)

        # Submit run with retry on transient errors
        for attempt in range(10):
            try:
                run = await self._client.run(
                    env,
                    objective=prompt,
                    model_url=self._url,
                    model_key=self._token or "",
                    model_name=self._name,
                    timeout_seconds=self._timeout,
                    max_steps=self._max_steps,
                    attachments=encoded_attachments,
                )
                break
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException,
                    httpx.ReadError, httpx.RemoteProtocolError) as e:
                if _is_transient_http(e) and attempt < 9:
                    _logger.warning(f"Transient error submitting run (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    raise

        # Poll with resilient error handling
        deadline = asyncio.get_event_loop().time() + self._timeout + 30
        prev_tc = 0
        data = None
        consecutive_failures = 0
        while asyncio.get_event_loop().time() < deadline:
            try:
                data = await self._client.get_run(run.id)
                consecutive_failures = 0
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException,
                    httpx.ReadError, httpx.RemoteProtocolError) as e:
                if _is_transient_http(e):
                    consecutive_failures += 1
                    if consecutive_failures > 60:
                        _logger.error(f"Vivarium unreachable for {consecutive_failures} consecutive polls")
                        return AgentResult(outcome="error", reason="vivarium_unreachable")
                    _logger.debug(f"Transient poll error ({consecutive_failures}): {e}")
                    await asyncio.sleep(2)
                    continue
                raise
            if data.status != "running":
                break
            if self.verbose:
                for entry in data.tool_trace[prev_tc:]:
                    print(f"  {_format_trace_line(entry)}")
            prev_tc = len(data.tool_trace)
            await asyncio.sleep(1)
        else:
            return AgentResult(outcome="error", reason="timeout")

        # Print remaining trace
        if self.verbose:
            for entry in data.tool_trace[prev_tc:]:
                print(f"  {_format_trace_line(entry)}")

        if data and data.status == "completed":
            metrics = {
                "steps": data.metrics.steps_completed,
                "tool_calls": data.metrics.tool_calls_completed,
                "tokens_in": data.metrics.input_tokens,
                "tokens_out": data.metrics.output_tokens,
                "duration_seconds": data.metrics.elapsed_seconds,
            }
            return AgentResult(answer=data.answer, metrics=metrics)

        error = data.error if data else "unknown"
        if self.verbose:
            print(f"  [red]⚠ Run failed: {error}[/]")
        return AgentResult(outcome="error", reason="agent_error")

    async def on_task_end(self, task: Task) -> None:
        """Destroy the environment container."""
        env = self._envs.pop(task.id, None)
        if env:
            await env.destroy()

    async def on_tasklist_end(self) -> None:
        """Cleanup specs and stop vivarium if auto-started."""
        for spec_id in self._spec_ids.values():
            if spec_id == "default":
                continue  # don't delete vivarium's built-in default spec
            await self._client.delete_spec(spec_id)
        self._spec_ids = {}
        if self._auto_started:
            from vivarium import stop
            stop()
            self._auto_started = False
        await self._client.aclose()

    async def _prepare_attachments(
        self, env, prompt: str, attachments: "list[Attachment]"
    ) -> "tuple[str, list[dict] | None]":
        """Write all attachments to container, return (updated_prompt, encoded_for_api).

        - All files are written to /workspace/attachments/ for tool access.
        - Only image/audio are encoded for model-context embedding via vivarium API.
        - A note listing all files is appended to the prompt.
        """
        await env.exec("mkdir -p /workspace/attachments")
        filenames: list[str] = []
        encoded: list[dict] = []
        for att in attachments:
            raw = att.read_bytes()
            await env.write(f"/workspace/attachments/{att.filename}", raw)
            filenames.append(att.filename)
            if att.mime_type.startswith(("image/", "audio/")):
                encoded.append({
                    "filename": att.filename,
                    "mime_type": att.mime_type,
                    "data": base64.b64encode(raw).decode("utf-8"),
                })
        note = "\n\n[Attached files: " + ", ".join(f"attachments/{f}" for f in filenames) + "]"
        return prompt + note, encoded or None

    def _package_task_files(self, task: Task) -> bytes | None:
        """Package task_files for upload, if any exist for this task."""
        for d in self._task_files_dirs:
            target = d / task.id
            if target.is_dir() and any(target.iterdir()):
                return _tar_gz(target)
        return None


def _tar_gz(directory: Path) -> bytes:
    """Create a tar.gz archive of a directory's contents."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in directory.rglob("*"):
            if f.is_file():
                tar.add(f, arcname=str(f.relative_to(directory)))
    return buf.getvalue()


def _format_trace_line(entry: dict) -> str:
    """Format a tool trace entry as a clean one-liner."""
    tool = entry["tool"]
    args = entry.get("args", {})
    result = entry.get("result", "")
    thought = entry.get("thought", "")
    # Format thought
    prefix = ""
    if thought:
        t = thought.replace("\n", " ").strip()
        if len(t) > 200:
            t = t[:200] + "…"
        prefix = f"[dim italic]💭 {t}[/]\n  "
    # Format args
    parts = []
    for k, v in args.items():
        val = v if isinstance(v, str) else str(v)
        if len(val) > 80:
            val = val[:80] + "…"
        parts.append(f"[dim]{k}=[/][dim blue]{val}[/]")
    formatted_args = " ".join(parts)
    # Format result
    res = str(result).replace("\n", " ").strip()
    if len(res) > 200:
        res = res[:200] + "…"
    return f"{prefix}[bold]{tool}[/] {formatted_args}\n    [dim]→ {res}[/]"


def _load_fn(path: Path, fn_name: str):
    """Load a function from a Python file."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, fn_name)
