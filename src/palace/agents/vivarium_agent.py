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
import json
import logging
import os
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from palace.agents.base_agent import Agent
from palace.evaluation.types import AgentResult
from palace.task_types.base import ExecutionEnvironment, Task
from palace.utils.paths import LOGS_PATH
from palace.utils.printing import print

if TYPE_CHECKING:
    from palace.evaluation.types import Attachment

_logger = logging.getLogger("palace.vivarium_agent")

# Transient HTTP status codes that are safe to retry.
_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504, 529})

# Network-level exceptions that indicate transient connectivity issues.
_TRANSIENT_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ReadError,
    httpx.RemoteProtocolError,
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
        extra_params: Extra kwargs merged into LLM API calls (e.g., reasoning_effort).
        harness: Agent harness to use ("builtin", "pi", "omp"). Default: "builtin".
        keep_last_env: Keep the last environment alive for debugging (default: False).
    """

    agentic: bool = True

    def __init__(
        self,
        name: str,
        url: str,
        token: str | None,
        vivarium_url: str | None = None,
        timeout_seconds: int = 7200,
        max_steps: int = 500,
        extra_params: dict | None = None,
        harness: str | None = None,
        keep_last_env: bool = False,
    ):
        self._name = name
        self._url = url
        self._token = token
        self._timeout = timeout_seconds
        self._max_steps = max_steps
        self._extra_params = extra_params
        self._harness = harness
        self._keep_last_env = keep_last_env
        self._last_kept_env: Any = None  # env kept for debugging
        self._trace_dir: Path | None = None  # directory for trace logs
        self._trace_file: Any = None  # current trace file handle
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
                "Install with: pip install vivarium-ai\n"
                "See https://github.com/vivarium-ai/vivarium for details."
            )

        auto_start = self._vivarium_url is None
        self._client = Client(url=self._vivarium_url, auto_start=auto_start)
        self._auto_started = auto_start

    def _log_trace_entry(self, task_id: str, entry: dict) -> None:
        """Write a trace entry to the task's trace log file."""
        if self._trace_dir is None:
            return
        # Lazily open trace file for this task
        if self._trace_file is None:
            safe_id = task_id.replace("/", "_")[:100]
            trace_path = self._trace_dir / f"{safe_id}_trace.jsonl"
            self._trace_file = open(trace_path, "w", encoding="utf-8")
        self._trace_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._trace_file.flush()

    def _close_trace_file(self) -> None:
        """Close the current trace file if open."""
        if self._trace_file:
            self._trace_file.close()
            self._trace_file = None

    @property
    def name(self) -> str:
        return self._name

    async def on_tasklist_start(self, tasklist_path: Path, info: dict) -> None:
        """Store environment configs. Specs registered lazily on first use."""
        started = " (auto-started)" if self._auto_started else ""
        harness_name = self._harness or "default"
        print(f"[blue]:whale: Agentic mode — Vivarium @ {self._client._url} (harness: {harness_name}){started}[/]")

        # Fail fast if vivarium is unreachable
        try:
            await self._client.health()
        except Exception as e:
            raise RuntimeError(
                f"Cannot reach Vivarium at {self._client._url}\n"
                f"  {e}\n"
                f"  Check the URL with: palace config set vivarium_url <url>"
            ) from e

        self._tasklist_path = tasklist_path

        # Set up trace directory for this run
        self._trace_dir = LOGS_PATH / "traces"
        self._trace_dir.mkdir(parents=True, exist_ok=True)

        # Resolve task_files search directories
        task_files_path = info.get("task_files_path", "task_files")
        self._task_files_dirs = sorted(d for d in tasklist_path.glob(task_files_path) if d.is_dir())

        # Discover environments via spec.json
        discovered_envs = _discover_environments(tasklist_path)

        if discovered_envs:
            # spec.json files found
            self._env_configs = {}
            self._env_paths: dict[str, Path] = {}  # env_name → directory path
            for env_name, env_path in discovered_envs.items():
                spec_file = env_path / "spec.json"
                try:
                    spec_json = json.loads(spec_file.read_text())
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in {spec_file}: {e}") from e
                except OSError as e:
                    raise ValueError(f"Cannot read {spec_file}: {e}") from e
                self._env_configs[env_name] = spec_json
                self._env_paths[env_name] = env_path
            _logger.info(f"Discovered {len(discovered_envs)} environment(s) via spec.json")
        else:
            # No environment defined — use vivarium's built-in default spec.
            # Vivarium registers "default" at startup; if missing, the 404 at
            # create_environment time is a clear enough error.
            self._env_configs = {"default": {}}
            self._env_paths = {"default": tasklist_path / "environment"}
            self._spec_ids["default"] = "default"

        # Pre-load seed functions and archives per unique environment path
        # For multi-env, seed.py may be in environment/ root (shared) or per-env subdir
        self._seed_fns: dict[str, object] = {}
        self._archives: dict[str, bytes | None] = {}
        shared_seed_path = tasklist_path / "environment" / "seed.py"
        shared_seed_fn = _load_fn(shared_seed_path, "seed") if shared_seed_path.exists() else None
        for env_name, env_path in self._env_paths.items():
            env_path_str = str(env_path.relative_to(tasklist_path))
            if env_path_str not in self._archives:
                if env_path.is_dir():
                    # Check per-env seed.py first, fall back to shared
                    per_env_seed = env_path / "seed.py"
                    if per_env_seed.exists():
                        self._seed_fns[env_path_str] = _load_fn(per_env_seed, "seed")
                    elif shared_seed_fn:
                        self._seed_fns[env_path_str] = shared_seed_fn
                    self._archives[env_path_str] = _tar_gz(env_path)
                else:
                    self._archives[env_path_str] = None

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
            env_path = self._env_paths[env_name]
            env_path_str = str(env_path.relative_to(self._tasklist_path))
            image = spec_json.get("image")
            _logger.info(f"Registering spec '{env_name}' (first use, image: {image})")

            # Retry on transient errors (503 disk pressure, 429, 5xx, connection issues)
            while True:
                try:
                    spec_id = await self._client.register_spec(spec_json, self._archives.get(env_path_str))
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
            except (
                httpx.HTTPStatusError,
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.ReadError,
                httpx.RemoteProtocolError,
            ) as e:
                if _is_transient_http(e):
                    _logger.debug(f"Transient error creating environment, retrying: {e}")
                    await asyncio.sleep(5)
                else:
                    raise

        self._envs[task.id] = env

        env_path = self._env_paths[env_name]
        env_path_str = str(env_path.relative_to(self._tasklist_path))
        seed_fn = self._seed_fns.get(env_path_str)
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
                    model_extra_params=self._extra_params,
                    sandbox_harness=self._harness,
                )
                break
            except (
                httpx.HTTPStatusError,
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.ReadError,
                httpx.RemoteProtocolError,
            ) as e:
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
            except (
                httpx.HTTPStatusError,
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.ReadError,
                httpx.RemoteProtocolError,
            ) as e:
                if _is_transient_http(e):
                    consecutive_failures += 1
                    if consecutive_failures > 15:  # ~30 seconds of failures
                        _logger.error(f"Vivarium unreachable for {consecutive_failures} consecutive polls, aborting")
                        return AgentResult(outcome="error", reason="vivarium_unreachable")
                    _logger.debug(f"Transient poll error ({consecutive_failures}): {e}")
                    await asyncio.sleep(2)
                    continue
                raise
            if data.status != "running":
                break
            for entry in data.trace[prev_tc:]:
                if self.verbose:
                    print(f"  {_format_trace_line(entry)}")
                self._log_trace_entry(task_id, entry)
            prev_tc = len(data.trace)
            await asyncio.sleep(1)
        else:
            return AgentResult(outcome="error", reason="timeout")

        # Print and log remaining trace
        for entry in data.trace[prev_tc:]:
            if self.verbose:
                print(f"  {_format_trace_line(entry)}")
            self._log_trace_entry(task_id, entry)

        if data and data.status == "completed":
            metrics = {
                "steps": data.metrics.steps_completed,
                "tool_calls": data.metrics.tool_calls_completed,
                "tokens_in": data.metrics.input_tokens,
                "tokens_out": data.metrics.output_tokens,
                "duration_seconds": data.metrics.elapsed_seconds,
            }
            return AgentResult(answer=data.answer, metrics=metrics, debug_logs=data.harness_stderr)

        error = data.error if data else "unknown"
        if self.verbose:
            print(f"  [red]⚠ Run failed: {error}[/]")
        return AgentResult(outcome="error", reason="agent_error", debug_logs=data.harness_stderr if data else None)

    async def on_task_end(self, task: Task) -> None:
        """Destroy the environment container (or keep for debugging)."""
        self._close_trace_file()  # Close trace file for this task
        env = self._envs.pop(task.id, None)
        if env:
            if self._keep_last_env:
                # Destroy previous kept env, keep this one
                if self._last_kept_env:
                    await self._last_kept_env.destroy()
                self._last_kept_env = env
                print(f"[yellow]🔍 Kept env for debugging: {env.id}[/]")
            else:
                await env.destroy()

    async def on_tasklist_end(self) -> None:
        """Cleanup specs and stop vivarium if auto-started."""
        # If keep_last_env, leave it alive for debugging (don't destroy)
        if self._last_kept_env:
            print(f"[yellow]🔍 Environment kept for debugging: {self._last_kept_env.id}[/]")
            self._last_kept_env = None  # Clear reference but don't destroy
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
                encoded.append(
                    {
                        "filename": att.filename,
                        "mime_type": att.mime_type,
                        "data": base64.b64encode(raw).decode("utf-8"),
                    }
                )
        note = "\n\n[Attached files: " + ", ".join(f"attachments/{f}" for f in filenames) + "]"
        return prompt + note, encoded or None

    def _package_task_files(self, task: Task) -> bytes | None:
        """Package task_files for upload, if any exist for this task."""
        for d in self._task_files_dirs:
            target = d / task.id
            if target.is_dir() and any(target.iterdir()):
                # Task files should include ALL files (no excludes)
                return _tar_gz(target, exclude_files=frozenset(), exclude_dirs=frozenset())
        return None


# Files/directories to exclude from spec archive sent to vivarium.
# These are palace-eval evaluation concerns (verification, seeding) that run locally,
# not runtime concerns that vivarium needs.
# Update this set if evaluation file conventions change.
_SPEC_ARCHIVE_EXCLUDE_FILES = frozenset({"verify.py", "seed.py"})  # Exact filename match
_SPEC_ARCHIVE_EXCLUDE_DIRS = frozenset({"verify_files"})  # Top-level directory match


def _discover_environments(tasklist_path: Path) -> dict[str, Path]:
    """Discover environment directories containing spec.json.

    Returns dict mapping env_name → env_directory_path.

    Single-env: environment/spec.json exists → {"default": environment/}
    Multi-env: environment/*/spec.json exists → {subdir_name: subdir_path, ...}

    Raises ValueError if both patterns exist (ambiguous structure).
    Returns empty dict if no spec.json found (legacy or default spec).
    """
    env_dir = tasklist_path / "environment"
    if not env_dir.is_dir():
        return {}

    # Check for multi-env: subdirectories with spec.json
    multi_envs = {d.name: d for d in env_dir.iterdir() if d.is_dir() and (d / "spec.json").exists()}

    # Check for single-env: spec.json directly in environment/
    single_env = (env_dir / "spec.json").exists()

    if multi_envs and single_env:
        raise ValueError(
            "Ambiguous environment structure: found both environment/spec.json "
            "and environment/*/spec.json. Use one or the other."
        )

    if multi_envs:
        return multi_envs
    elif single_env:
        return {"default": env_dir}
    else:
        return {}


def _should_exclude(relative_path: Path, exclude_files: frozenset[str], exclude_dirs: frozenset[str]) -> bool:
    """Check if a file should be excluded from archive.

    Args:
        relative_path: Path relative to archive root.
        exclude_files: Filenames to exclude (exact match on filename only).
        exclude_dirs: Directory names to exclude (match at any level in path).
    """
    # Exclude exact filename matches (e.g., "verify.py" at any level)
    if relative_path.name in exclude_files:
        return True
    # Exclude files inside excluded directories (e.g., anything under "verify_files/")
    if exclude_dirs and any(part in exclude_dirs for part in relative_path.parts[:-1]):
        return True
    return False


def _tar_gz(
    directory: Path,
    exclude_files: frozenset[str] = _SPEC_ARCHIVE_EXCLUDE_FILES,
    exclude_dirs: frozenset[str] = _SPEC_ARCHIVE_EXCLUDE_DIRS,
) -> bytes:
    """Create a tar.gz archive of a directory's contents.

    Args:
        directory: Directory to archive.
        exclude_files: Filenames to exclude (exact match). Default excludes verify.py, seed.py.
        exclude_dirs: Directory names to exclude (files inside are excluded). Default excludes verify_files/.

    Excludes verification files by default which are palace-eval concerns, not needed by vivarium.
    Pass empty frozensets to include all files.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in directory.rglob("*"):
            if f.is_file():
                relative_path = f.relative_to(directory)
                if _should_exclude(relative_path, exclude_files, exclude_dirs):
                    continue
                tar.add(f, arcname=str(relative_path))
    return buf.getvalue()


def _format_trace_line(entry: dict) -> str:
    """Format a trace entry (thinking or tool) as a clean one-liner."""
    entry_type = entry.get("type", "tool")

    # Handle thinking entries
    if entry_type == "thinking":
        content = entry.get("content", "")
        t = content.replace("\n", " ").strip()
        if len(t) > 300:
            t = t[:300] + "…"
        # Format token count as (15k) or (900)
        input_tokens = entry.get("input_tokens")
        if input_tokens:
            if input_tokens >= 1000:
                token_str = f"{input_tokens // 1000}k"
            else:
                token_str = str(input_tokens)
            return f"[yellow]({token_str})[/yellow] [italic]💭 {t}[/]"
        return f"[italic]💭 {t}[/]"

    # Handle tool entries
    tool = entry.get("tool", "unknown")
    args = entry.get("args", {})
    result = entry.get("result", "")
    # Format args
    parts = []
    for k, v in args.items():
        val = v if isinstance(v, str) else str(v)
        if len(val) > 100:
            val = val[:100] + "…"
        parts.append(f"[dim]{k}=[/][blue]{val}[/]")
    formatted_args = " ".join(parts)
    # Format result
    res = str(result).replace("\n", " ").strip()
    if len(res) > 300:
        res = res[:300] + "…"
    return f"[bold]{tool}[/] {formatted_args}\n    [dim]→ {res}[/]"


def _load_fn(path: Path, fn_name: str):
    """Load a function from a Python file."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, fn_name)
