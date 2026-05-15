"""Vivarium agent — delegates execution to palace-vivarium service."""

import io
import json
import os
import tarfile
import time
from pathlib import Path
from typing import Any

import requests

from palace.agents.base_agent import Agent
from palace.environments.base_environment import Environment
from palace.environments.unknown_environment import UnknownEnvironment
from palace.task_types.base import Task
from palace.utils.printing import print


class VivariumAgent(Agent):
    """Agent that delegates execution to palace-vivarium's sandboxed Docker environments.

    Args:
        name: Model name (passed to vivarium as model_name for LLM calls).
        url: LLM API base URL.
        token: LLM API key.
        vivarium_url: Vivarium service URL. If None, auto-starts via palace_vivarium SDK.
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
        self._auto_started = False
        self._spec_id: str | None = None
        self._env_id: str | None = None
        self._tasklist_path: Path | None = None
        self._environment = UnknownEnvironment()

        if not self._vivarium_url:
            try:
                from palace_vivarium import start

                self._vivarium_url = start()
                self._auto_started = True
            except ImportError:
                raise RuntimeError(
                    "Agentic evaluation requires palace-vivarium. "
                    "Install with: pip install palace[agentic]"
                )

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def paradigm_name(self) -> str:
        return "vivarium"

    @property
    def environment(self) -> Environment:
        return self._environment

    def on_tasklist_start(self, tasklist_path: Path, info: dict) -> None:
        """Register environment spec with vivarium (upload archive once)."""
        self._tasklist_path = tasklist_path
        env_dir = tasklist_path / "environment"
        r = requests.post(
            f"{self._vivarium_url}/specs",
            data={"spec": json.dumps(info.get("environment", {}))},
            files={
                "environment": (
                    "environment.tar.gz",
                    _tar_gz(env_dir),
                    "application/gzip",
                )
            },
        )
        r.raise_for_status()
        self._spec_id = r.json()["id"]

    def on_task_start(self, task: Task) -> None:
        """Create a sandboxed environment for this task."""
        body = {"task_id": task.id, "seed_args": task.custom_fields.get("seed_args")}
        files = self._package_task_files(task)

        r = requests.post(
            f"{self._vivarium_url}/specs/{self._spec_id}/environments",
            data={"body": json.dumps(body)},
            files=files,
        )
        r.raise_for_status()
        self._env_id = r.json()["id"]
        task._env_id = self._env_id  # type: ignore[attr-defined]
        task._vivarium_url = self._vivarium_url  # type: ignore[attr-defined]

    def run(
        self, prompt: str, image: str | None = None
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Submit agent run and poll until completion."""
        r = requests.post(
            f"{self._vivarium_url}/environments/{self._env_id}/run",
            json={
                "objective": prompt,
                "model_url": self._url,
                "model_key": self._token or "",
                "model_name": self._name,
                "timeout_seconds": self._timeout,
                "max_steps": self._max_steps,
            },
        )
        r.raise_for_status()
        run_id = r.json()["run_id"]

        deadline = time.time() + self._timeout + 30
        prev_tc = 0
        trace_lines = []
        while time.time() < deadline:
            resp = requests.get(f"{self._vivarium_url}/runs/{run_id}")
            resp.raise_for_status()
            data = resp.json()
            if data["status"] != "running":
                break
            trace = data.get("tool_trace") or []
            for entry in trace[prev_tc:]:
                line = _format_trace_line(entry)
                trace_lines.append(line)
                print(f"  {line}")
            prev_tc = len(trace)
            time.sleep(1)
        else:
            return None, None

        if data["status"] == "completed":
            metrics = data.get("agent_metrics") or {}
            trace = data.get("tool_trace") or []
            for entry in trace[prev_tc:]:
                line = _format_trace_line(entry)
                print(f"  {line}")
            return data["answer"], metrics
        # Failed run
        print(f"  [red]⚠ Run failed: {data.get('error', 'unknown')}[/]")
        return None, None

    def on_task_end(self, task: Task) -> None:
        """Destroy the environment container."""
        if self._env_id:
            requests.delete(f"{self._vivarium_url}/environments/{self._env_id}")
            self._env_id = None

    def on_tasklist_end(self) -> None:
        """Cleanup spec and stop vivarium if auto-started."""
        if self._spec_id:
            requests.delete(f"{self._vivarium_url}/specs/{self._spec_id}")
            self._spec_id = None
        if self._auto_started:
            from palace_vivarium import stop

            stop()
            self._auto_started = False

    def _package_task_files(self, task: Task) -> dict | None:
        """Package task_files for upload, if any exist for this task."""
        assert self._tasklist_path is not None
        task_files_dir = self._tasklist_path / "task_files"
        if not task_files_dir.is_dir():
            return None
        target = task_files_dir / task.attachment if task.attachment else task_files_dir
        if not target.is_dir() or not any(target.iterdir()):
            return None
        return {
            "task_files": ("task_files.tar.gz", _tar_gz(target), "application/gzip")
        }


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
