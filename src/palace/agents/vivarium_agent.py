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

from palace.agents.base_agent import Agent
from palace.evaluation.types import AgentResult
from palace.task_types.base import ExecutionEnvironment, Task
from palace.utils.printing import print

if TYPE_CHECKING:
    from palace.evaluation.types import Attachment

_logger = logging.getLogger("palace.vivarium_agent")


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
        timeout_seconds: int = 3600,
        max_steps: int = 100,
    ):
        self._name = name
        self._url = url
        self._token = token
        self._timeout = timeout_seconds
        self._max_steps = max_steps
        self._vivarium_url = vivarium_url or os.getenv("VIVARIUM_URL") or None
        self._spec_ids: dict[str, str] = {}  # env_name → vivarium spec_id
        self._env_configs: dict[str, dict] = {}  # env_name → spec config (lazy)
        self._archive_bytes: bytes | None = None
        self._envs: dict[str, Any] = {}  # task_id → Environment
        self._client: Any = None
        self._auto_started = False
        self._tasklist_path: Path | None = None
        self._seed_fn = None

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
        """Store environment configs and load seed script. Specs registered lazily on first use."""
        started = " (auto-started)" if self._auto_started else ""
        print(f"[blue]:whale: Agentic mode — Vivarium @ {self._client._url}{started}[/]")

        self._tasklist_path = tasklist_path
        env_dir = tasklist_path / "environment"

        if env_dir.is_dir():
            seed_path = env_dir / "seed.py"
            if seed_path.exists():
                self._seed_fn = _load_fn(seed_path, "seed")
            self._archive_bytes = _tar_gz(env_dir)
        else:
            self._archive_bytes = None

        # Store environment configurations for lazy registration
        if "env" not in info:
            raise ValueError("info.json must contain an 'env' key with named environment configurations")
        self._env_configs = info["env"]
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
            image = spec_json.get("image")
            _logger.info(f"Registering spec '{env_name}' (first use, image: {image})")
            try:
                spec_id = await self._client.register_spec(spec_json, self._archive_bytes)
            except Exception as e:
                raise RuntimeError(
                    f"Cannot register spec '{env_name}' with Vivarium at {self._client._url}. "
                    f"Check that the server is running.\n  Original error: {e}"
                ) from e
            self._spec_ids[env_name] = spec_id
            _logger.info(f"Spec '{env_name}' registered (image ready)")

        spec_id = self._spec_ids[env_name]
        task_files = self._package_task_files(task)

        env = await self._client.create_environment(
            spec_id=spec_id,
            task_id=task.id,
            task_files=task_files,
        )
        self._envs[task.id] = env

        if self._seed_fn:
            _logger.info(f"Seeding environment for {task.id}")
            seed_args = task.custom_fields.get("seed_args")
            result = self._seed_fn(seed_args, env)
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

        # Encode attachments as base64 for vivarium API
        encoded_attachments = None
        if attachments:
            encoded_attachments = []
            for att in attachments:
                raw = Path(att.path).read_bytes()
                encoded_attachments.append({
                    "filename": att.filename,
                    "mime_type": att.mime_type,
                    "data": base64.b64encode(raw).decode("utf-8"),
                })

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

        # Poll with live trace printing
        deadline = asyncio.get_event_loop().time() + self._timeout + 30
        prev_tc = 0
        data = None
        while asyncio.get_event_loop().time() < deadline:
            data = await self._client.get_run(run.id)
            if data.status != "running":
                break
            if self.verbose:
                for entry in data.tool_trace[prev_tc:]:
                    print(f"  {_format_trace_line(entry)}")
            prev_tc = len(data.tool_trace)
            await asyncio.sleep(1)
        else:
            return AgentResult(is_skipped=True, skip_reason="timeout")

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
        return AgentResult(is_skipped=True, skip_reason="agent_error")

    async def on_task_end(self, task: Task) -> None:
        """Destroy the environment container."""
        env = self._envs.pop(task.id, None)
        if env:
            await env.destroy()

    async def on_tasklist_end(self) -> None:
        """Cleanup specs and stop vivarium if auto-started."""
        for spec_id in self._spec_ids.values():
            await self._client.delete_spec(spec_id)
        self._spec_ids = {}
        if self._auto_started:
            from vivarium import stop
            stop()
            self._auto_started = False
        await self._client.aclose()

    def _package_task_files(self, task: Task) -> bytes | None:
        """Package task_files for upload, if any exist for this task."""
        assert self._tasklist_path is not None
        task_files_dir = self._tasklist_path / "task_files"
        if not task_files_dir.is_dir():
            return None
        target = task_files_dir / task.id
        if not target.is_dir() or not any(target.iterdir()):
            return None
        return _tar_gz(target)


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
