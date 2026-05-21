"""Vivarium agent — delegates execution to vivarium service."""

import importlib.util
import io
import os
import tarfile
import time
from pathlib import Path
from typing import Any

from palace.agents.base_agent import Agent
from palace.task_types.base import Task
from palace.utils.printing import print


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

    def __init__(
        self,
        name: str,
        url: str,
        token: str | None,
        vivarium_url: str | None = None,
        timeout_seconds: int = 300,
        max_steps: int = 50,
    ):
        self._name = name
        self._url = url
        self._token = token
        self._timeout = timeout_seconds
        self._max_steps = max_steps
        self._vivarium_url = vivarium_url or os.getenv("VIVARIUM_URL")
        self._spec_id: str | None = None
        self._env = None  # vivarium.Environment
        self._client = None  # vivarium.Client
        self._auto_started = False
        self._tasklist_path: Path | None = None
        self._seed_fn = None
        self._verify_fn = None
        self._verify_context_decl: dict = {}

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

    DEFAULT_SPEC = {
        "tools": ["web_search", "bash", "read", "write", "web_fetch"],
    }

    def on_tasklist_start(self, tasklist_path: Path, info: dict) -> None:
        """Register environment spec with vivarium and load seed/verify scripts."""
        from palace.utils.printing import print as pprint
        started = " (auto-started)" if self._auto_started else ""
        pprint(f"[blue]:whale: Agentic mode — Vivarium @ {self._client._url}{started}[/]")

        self._tasklist_path = tasklist_path
        env_dir = tasklist_path / "environment"

        if env_dir.is_dir():
            seed_path = env_dir / "seed.py"
            if seed_path.exists():
                self._seed_fn = _load_fn(seed_path, "seed")
            verify_path = env_dir / "verify.py"
            if verify_path.exists():
                mod = _load_module(verify_path)
                self._verify_fn = mod.verify
                self._verify_context_decl = getattr(mod, "CONTEXT", {})

            spec_json = info.get("environment", {})
            archive_bytes = _tar_gz(env_dir)
        else:
            spec_json = self.DEFAULT_SPEC
            archive_bytes = None

        self._spec_id = self._client.register_spec(spec_json, archive_bytes)

    def on_task_start(self, task: Task) -> None:
        """Create a sandboxed environment and run seed if present."""
        task_files = self._package_task_files(task)

        self._env = self._client.create_environment(
            spec_id=self._spec_id,
            task_id=task.id,
            task_files=task_files,
        )
        container = self._client.container(self._env.id)
        task._container = container  # type: ignore[attr-defined]
        task._verify_fn = self._verify_fn  # type: ignore[attr-defined]
        task._verify_context_decl = self._verify_context_decl  # type: ignore[attr-defined]
        task._tasklist_path = self._tasklist_path  # type: ignore[attr-defined]

        if self._seed_fn:
            seed_args = task.custom_fields.get("seed_args")
            self._seed_fn(seed_args, container)

    def run(
        self, prompt: str, image: str | None = None
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Submit agent run and poll until completion."""
        run = self._client.run(
            self._env,
            objective=prompt,
            model_url=self._url,
            model_key=self._token or "",
            model_name=self._name,
            timeout_seconds=self._timeout,
            max_steps=self._max_steps,
        )

        # Custom poll loop for live trace printing
        deadline = time.time() + self._timeout + 30
        prev_tc = 0
        while time.time() < deadline:
            data = self._client.get_run(run.id)
            if data.status != "running":
                break
            for entry in data.tool_trace[prev_tc:]:
                line = _format_trace_line(entry)
                print(f"  {line}")
            prev_tc = len(data.tool_trace)
            time.sleep(1)
        else:
            return None, None

        # Print any remaining trace entries
        for entry in data.tool_trace[prev_tc:]:
            print(f"  {_format_trace_line(entry)}")

        result = run.result
        if result and result.status == "completed":
            metrics = {
                "steps": result.metrics.steps,
                "tool_calls": result.metrics.tool_calls,
                "tokens_in": result.metrics.input_tokens,
                "tokens_out": result.metrics.output_tokens,
                "duration_seconds": result.metrics.wall_time_seconds,
            }
            return result.answer, metrics

        error = result.error if result else "unknown"
        print(f"  [red]⚠ Run failed: {error}[/]")
        return None, None

    def on_task_end(self, task: Task) -> None:
        """Destroy the environment container."""
        if self._env:
            self._env.destroy()
            self._env = None

    def on_tasklist_end(self) -> None:
        """Cleanup spec and stop vivarium if auto-started."""
        if self._spec_id:
            self._client.delete_spec(self._spec_id)
            self._spec_id = None
        if self._auto_started:
            from vivarium import stop
            stop()
            self._auto_started = False

    def _package_task_files(self, task: Task) -> bytes | None:
        """Package task_files for upload, if any exist for this task."""
        assert self._tasklist_path is not None
        task_files_dir = self._tasklist_path / "task_files"
        if not task_files_dir.is_dir():
            return None
        target = task_files_dir / task.attachment if task.attachment else task_files_dir
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
    args = entry.get("args", "")
    result = entry.get("result", "")
    return f"[bold]{tool}[/] [dim]{args}[/]\n    [dim]→ {result}[/]"


def _load_fn(path: Path, fn_name: str):
    """Load a function from a Python file."""
    mod = _load_module(path)
    return getattr(mod, fn_name)


def _load_module(path: Path):
    """Load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
