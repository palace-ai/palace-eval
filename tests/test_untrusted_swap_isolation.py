"""Tests for --untrusted-agent swap failure isolation.

Covers the job-1215 regression class: a transient 500 during VERIFY_PATHS
download must NOT abort the evaluation (previously FatalEvaluationError);
it becomes a per-task error outcome and the job continues.

- 404 → one immediate retry, then give up (agent deleted its deliverable)
- transient 5xx → retried with backoff, then per-task error
- 500-then-success → swap proceeds
- metrics preserved on swap failure (cost accounting)
- UntrustedSwapError is not a FatalEvaluationError
"""

import httpx
import pytest

from palace.agents.vivarium_agent import (
    _SWAP_DOWNLOAD_ATTEMPTS,
    VivariumAgent,
)
from palace.utils.exceptions import FatalEvaluationError, UntrustedSwapError


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://vivarium.test/environments/e1/files")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"{status} error", request=request, response=response)


class _FakeEnv:
    """Vivarium Environment stub with a scripted download_files behaviour."""

    def __init__(self, script):
        # script: list of either Exception instances or bytes — one per call
        self.script = list(script)
        self.calls: list[str] = []
        self.destroyed = False
        self.id = "env-fake"

    async def download_files(self, path: str) -> bytes:
        self.calls.append(path)
        item = self.script.pop(0) if self.script else self.script
        if isinstance(item, Exception):
            raise item
        return item

    async def upload_files(self, archive: bytes, dest: str = "/") -> None:
        pass

    async def destroy(self) -> None:
        self.destroyed = True


def _make_agent(env, tmp_path) -> VivariumAgent:
    """VivariumAgent bypassing __init__ (no real vivarium client needed)."""
    agent = VivariumAgent.__new__(VivariumAgent)
    agent._untrusted_agent = True
    agent._envs = {"t1": env}
    agent._task_env_names = {"t1": "repo_env"}
    agent._spec_ids = {"repo_env": "spec-123"}
    agent._env_paths = {"repo_env": tmp_path / "environments" / "repo_env"}
    agent._verify_paths = {}  # → _DEFAULT_VERIFY_PATHS
    agent._tasks = {}
    agent._seed_fns = {}
    agent._tasklist_path = tmp_path
    agent._keep_last_env = False
    agent._trace_dir = None
    agent._trace_file = None
    agent._task_files_dirs = []
    agent._client = _FakeClient()
    agent._auto_started = False
    agent._name = "test-model"
    agent._url = "http://llm.test"
    agent._token = "k"
    agent._timeout = 60
    agent._max_steps = 10
    agent._extra_params = None
    agent._harness = None
    agent._verbose = False
    return agent


def _make_task():
    class _T:
        id = "t1"
        custom_fields = {}

    return _T()


class TestUntrustedSwapErrorClassification:
    def test_not_fatal(self):
        """Swap errors must never abort the job — not a FatalEvaluationError."""
        assert not issubclass(UntrustedSwapError, FatalEvaluationError)

    @pytest.mark.asyncio
    async def test_404_retries_once_then_task_level_error(self, tmp_path, monkeypatch):
        """404 after the immediate retry → per-task error, not fatal."""
        monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)
        env = _FakeEnv([_http_status_error(404), _http_status_error(404)])
        agent = _make_agent(env, tmp_path)

        result = await agent.run(prompt="p", task_id="t1")
        assert result.outcome == "error"
        assert result.reason is not None and "untrusted_swap_failed" in result.reason
        assert "VERIFY_PATHS" in result.reason  # actionable fix message preserved
        # pipeline's finally → on_task_end destroys the original env; here we
        # assert the swap error itself did not silently keep it registered
        assert agent._envs.get("t1") is env

    @pytest.mark.asyncio
    async def test_404_once_then_success_swallows_transient(self, tmp_path, monkeypatch):
        """A single 404 (destroy/race transient) must not fail the task."""
        monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)
        env = _FakeEnv([_http_status_error(404), b"archive-bytes"])
        agent = _make_agent(env, tmp_path)
        agent._client = _FakeClient()
        agent._tasks = {"t1": _make_task()}

        result = await agent.run(prompt="p", task_id="t1")
        # Swap completed (no error outcome from swap); run succeeded
        assert result.outcome == "success"
        assert len(env.calls) == 2

    @pytest.mark.asyncio
    async def test_persistent_500_retried_then_task_level_error(self, tmp_path, monkeypatch):
        """The job-1215 regression: persistent 500 → per-task error, not job abort."""
        monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)
        env = _FakeEnv([_http_status_error(500) for _ in range(_SWAP_DOWNLOAD_ATTEMPTS)])
        agent = _make_agent(env, tmp_path)

        result = await agent.run(prompt="p", task_id="t1")
        assert result.outcome == "error"
        assert result.reason is not None and "untrusted_swap_failed" in result.reason
        assert len(env.calls) == _SWAP_DOWNLOAD_ATTEMPTS  # retried, not given up at first

    @pytest.mark.asyncio
    async def test_500_then_success_swap_proceeds(self, tmp_path, monkeypatch):
        """One transient 500 then success → swap completes, task scored."""
        monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)
        env = _FakeEnv([_http_status_error(500), b"archive-bytes"])
        agent = _make_agent(env, tmp_path)
        agent._client = _FakeClient()
        agent._tasks = {"t1": _make_task()}

        result = await agent.run(prompt="p", task_id="t1")
        assert result.outcome == "success"
        assert len(env.calls) == 2

    @pytest.mark.asyncio
    async def test_connect_error_retried_then_task_level_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)
        env = _FakeEnv([httpx.ConnectError("worker down") for _ in range(_SWAP_DOWNLOAD_ATTEMPTS)])
        agent = _make_agent(env, tmp_path)

        result = await agent.run(prompt="p", task_id="t1")
        assert result.outcome == "error"
        assert result.reason is not None and "untrusted_swap_failed" in result.reason

    @pytest.mark.asyncio
    async def test_metrics_preserved_on_swap_failure(self, tmp_path, monkeypatch):
        """Token/step metrics from the completed agent run survive for cost accounting."""
        monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)
        env = _FakeEnv([_http_status_error(500) for _ in range(_SWAP_DOWNLOAD_ATTEMPTS)])
        agent = _make_agent(env, tmp_path)

        result = await agent.run(prompt="p", task_id="t1")
        assert result.outcome == "error"
        assert result.metrics is not None
        assert result.metrics["input_tokens"] == 100
        assert result.metrics["output_tokens"] == 50


class TestSwapProvisioningOrder:
    """Swap must provision trusted artefacts in the same order as initial
    setup (on_task_start): task_files → seed → agent deliverables.

    Seeds that consume task_files (e.g. SWE-bench-Pro reading
    /task_files/run_script.sh) silently no-op under a seed-first order
    because their missing-file guard exits 0. Deliverables must still come
    after seed so a seed-side workspace reset cannot wipe them.
    """

    @pytest.mark.asyncio
    async def test_task_files_before_seed_before_deliverables(self, tmp_path, monkeypatch):
        monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)
        env = _FakeEnv([b"archive-bytes"])
        agent = _make_agent(env, tmp_path)
        agent._tasks = {"t1": _make_task()}

        # Real task_files dir so _package_task_files produces an upload:
        # task_files_path glob "*/task_files" style — here a single dir with
        # the task's subdirectory containing one file.
        tf_dir = tmp_path / "task_files" / "t1"
        tf_dir.mkdir(parents=True)
        (tf_dir / "run_script.sh").write_text("#!/bin/bash\n")
        agent._task_files_dirs = [tmp_path / "task_files"]

        order: list[str] = []

        async def recording_upload(archive: bytes, dest: str = "/", **kw):
            # fresh_env uploads: task_files go to /task_files/, the deliverable
            # overlay lands at the parent of its VERIFY_PATH ("/" for /app).
            order.append("task_files" if dest == "/task_files/" else "deliverable")

        fresh_env = agent._client.fresh_env
        fresh_env.upload_files = recording_upload

        async def seed_fn(seed_args, container):
            order.append("seed")

        # _make_agent sets _env_paths = {repo_env: tmp_path/"environments"/"repo_env"}
        # → env_path_str as computed by _swap_to_fresh_env is "environments/repo_env"
        agent._seed_fns = {"environments/repo_env": seed_fn}

        result = await agent.run(prompt="p", task_id="t1")
        assert result.outcome == "success"
        assert order == ["task_files", "seed", "deliverable"]


class _FakeRun:
    id = "run-1"
    status = "completed"
    answer = "agent answer"
    trace: list = []
    harness_stderr = ""

    class metrics:
        steps_completed = 3
        tool_calls_completed = 1
        input_tokens = 100
        output_tokens = 50
        elapsed_seconds = 12.5


class _FakeClient:
    """Client stub: create_environment for swap, run/get_run for the agent run."""

    def __init__(self):
        self.fresh_env = _FakeEnv([])

    async def create_environment(self, spec_id=None):
        return self.fresh_env

    async def run(self, env, **kwargs):
        return _FakeRun()

    async def get_run(self, run_id):
        return _FakeRun()


async def _nosleep(_):
    return None
