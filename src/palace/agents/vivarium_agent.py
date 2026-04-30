"""Vivarium agent — delegates execution to palace-vivarium service."""

import io
import json
import os
import tarfile
import time
from pathlib import Path
from typing import Any

import requests as req

from palace.agents.base_agent import Agent
from palace.environments.base_environment import Environment
from palace.environments.unknown_environment import UnknownEnvironment
from palace.task_types.base import Task


class VivariumAgent(Agent):
    """Agent that runs inside palace-vivarium's sandboxed Docker environments.

    Manages the vivarium spec/environment lifecycle via HTTP and delegates
    the agent loop (LLM + tool calling) to vivarium.
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
        self._vivarium_url = vivarium_url or os.getenv("VIVARIUM_URL")
        self._timeout_seconds = timeout_seconds
        self._max_steps = max_steps
        self._auto_started = False
        self._spec_id: str | None = None
        self._current_env_id: str | None = None
        self._environment = UnknownEnvironment()

        # Auto-start vivarium if no URL provided
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
        """Register environment spec with vivarium."""
        self._tasklist_path = tasklist_path
        env_config = info.get("environment", {})
        env_dir = tasklist_path / "environment"
        archive = _create_archive(env_dir)
        r = req.post(
            f"{self._vivarium_url}/specs",
            data={"spec": json.dumps(env_config)},
            files={"environment": ("environment.tar.gz", archive, "application/gzip")},
        )
        r.raise_for_status()
        self._spec_id = r.json()["id"]

    def on_task_start(self, task: Task) -> None:
        """Create vivarium environment for this task, with task_files if present."""
        body = {"task_id": task.id, "initial_state": getattr(task, "initial_state", None)}

        # Package task_files directory if it exists
        task_files_dir = self._tasklist_path / "task_files"
        files = None
        if task_files_dir.is_dir() and any(task_files_dir.iterdir()):
            task_files_archive = _create_archive(task_files_dir)
            files = {"task_files": ("task_files.tar.gz", task_files_archive, "application/gzip")}

        r = req.post(
            f"{self._vivarium_url}/specs/{self._spec_id}/environments",
            data={"body": json.dumps(body)},
            files=files,
        )
        r.raise_for_status()
        self._current_env_id = r.json()["id"]
        # Set env_id on task so AgenticTask.verify() can use it
        task._env_id = self._current_env_id  # type: ignore[attr-defined]
        task._vivarium_url = self._vivarium_url  # type: ignore[attr-defined]

    def run(self, prompt: str, image: str | None = None) -> tuple[str | None, dict[str, Any] | None]:
        """Submit agent run to vivarium and poll until completion."""
        r = req.post(
            f"{self._vivarium_url}/environments/{self._current_env_id}/run",
            json={
                "objective": prompt,
                "model_url": self._url,
                "model_key": self._token or "",
                "model_name": self._name,
                "timeout_seconds": self._timeout_seconds,
                "max_steps": self._max_steps,
            },
        )
        r.raise_for_status()
        run_id = r.json()["run_id"]

        # Poll until done (client-side timeout = server timeout + 30s buffer)
        deadline = time.time() + self._timeout_seconds + 30
        while time.time() < deadline:
            resp = req.get(f"{self._vivarium_url}/runs/{run_id}")
            resp.raise_for_status()
            data = resp.json()
            if data["status"] != "running":
                break
            time.sleep(2)
        else:
            return None, None  # Client-side timeout

        if data["status"] == "completed":
            return data["answer"], data.get("agent_metrics")
        return None, None

    def on_task_end(self, task: Task) -> None:
        """Destroy vivarium environment."""
        if self._current_env_id:
            req.delete(f"{self._vivarium_url}/environments/{self._current_env_id}")
            self._current_env_id = None

    def on_tasklist_end(self) -> None:
        """Unregister spec and stop vivarium if auto-started."""
        if self._spec_id:
            req.delete(f"{self._vivarium_url}/specs/{self._spec_id}")
            self._spec_id = None
        if self._auto_started:
            from palace_vivarium import stop
            stop()
            self._auto_started = False


def _create_archive(env_dir: Path) -> bytes:
    """Create tar.gz of environment directory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in env_dir.rglob("*"):
            if f.is_file():
                tar.add(f, arcname=str(f.relative_to(env_dir)))
    return buf.getvalue()
