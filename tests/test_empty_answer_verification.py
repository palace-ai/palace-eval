"""Tests for verification gating on outcome instead of answer.

Regression class: Tau2-bench-Airline job 1432 — 49/50 tasks ran the full
agent loop (25-47 steps, DB mutations) but produced no final text. The old
gate (`answer is not None`) skipped verification entirely, yet the fabricated
result inherited outcome="success" — so the tasks counted in the denominator
and were auto-failed without being graded, yielding accuracy 0.00.

New contract: a completed agent run (outcome="success") is ALWAYS verified.
The answer is verification input, not verification eligibility.
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from palace.agents.vivarium_agent import VivariumAgent
from palace.evaluation.pipeline import build_report, execute_task
from palace.evaluation.types import AgentResult
from palace.task_types.base import Task, TaskVerificationResult


def _tasklist_dir():
    """Temp dir standing in for the tasklist root (needs task_files/ to exist)."""
    d = Path(tempfile.mkdtemp())
    (d / "task_files").mkdir(exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# pipeline gate
# ---------------------------------------------------------------------------


class _RecordingAgent:
    """Minimal Agent stand-in: returns the scripted AgentResult, records verify env."""

    def __init__(self, agent_result):
        self._agent_result = agent_result
        self.verify_env_used = None

    @property
    def name(self):
        return "test-agent"

    def get_verify_env(self, task):
        return None

    async def on_tasklist_start(self, tasks, tasklist_path):
        return

    async def on_tasklist_end(self):
        return

    async def on_task_start(self, task):
        return _StubEnv()

    async def on_task_end(self, task):
        return

    async def run(self, prompt, attachments=None, *, task_id=None):
        return self._agent_result


class _StubEnv:
    """ExecutionEnvironment stub."""

    async def exec(self, command):
        return SimpleNamespace(exit_code=0, stdout="", stderr="")

    async def read(self, path):
        return b""

    async def write(self, path, data):
        return


class _EnvVerifiedTask(Task):
    """Agentic-style task: verification reads the env, ignores the answer."""

    def __init__(self, is_correct):
        self.id = "t1"
        self.objective = "do the thing"
        self.attachments = []
        self.custom_verificator = None
        self._is_correct = is_correct

    def adapt_prompt(self):
        return self.objective

    def expected_display(self):
        return None

    async def verify(self, answer, env=None, **kwargs):
        # Record that verification ran and with what answer
        type(self).last_answer = answer
        type(self).last_env = env
        return TaskVerificationResult(is_correct=self._is_correct, reasoning="env check")


class _JudgeTask(_EnvVerifiedTask):
    """Answer-based task: judge would see the empty answer."""

    async def verify(self, answer, env=None, **kwargs):
        type(self).last_answer = answer
        # Judge sees empty PROVIDED ANSWER → incorrect (natural path)
        return TaskVerificationResult(is_correct=answer != "", reasoning="judge")


class _SilentRenderer:
    def __getattr__(self, name):
        return lambda *a, **k: None

    verbose = False

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def loading(self):
        return self._Ctx()


@pytest.mark.asyncio
async def test_empty_answer_env_task_is_verified_and_correct():
    """Agentic task with answer=None: verification MUST run and grade the env."""
    task = _EnvVerifiedTask(is_correct=True)
    agent = _RecordingAgent(AgentResult(answer=None, metrics={"steps": 25}))
    _EnvVerifiedTask.last_answer = None
    _EnvVerifiedTask.last_env = None

    result = await execute_task(
        0,
        task,
        agent,
        adapter=None,
        tasklist_path=_tasklist_dir(),
        task_files_dirs=[],
        analyzers=[],
        detail="compact",
        renderer=_SilentRenderer(),
    )

    assert result.verification.outcome == "correct"
    assert result.verification.is_correct is True
    assert _EnvVerifiedTask.last_answer == ""  # empty string passed to verify, not None
    assert _EnvVerifiedTask.last_env is not None


@pytest.mark.asyncio
async def test_empty_answer_answer_task_naturally_incorrect():
    """Answer-based task with answer=None: judge path sees '', returns incorrect."""
    task = _JudgeTask(is_correct=False)
    agent = _RecordingAgent(AgentResult(answer=None, metrics={"steps": 3}))
    _JudgeTask.last_answer = None

    result = await execute_task(
        0,
        task,
        agent,
        adapter=None,
        tasklist_path=_tasklist_dir(),
        task_files_dirs=[],
        analyzers=[],
        detail="compact",
        renderer=_SilentRenderer(),
    )

    assert result.verification.outcome == "incorrect"
    assert result.verification.is_correct is False
    assert _JudgeTask.last_answer == ""


@pytest.mark.asyncio
async def test_error_run_still_skips_verification():
    """outcome='error' skips verification, outcome preserved (no success inheritance)."""
    _EnvVerifiedTask.last_answer = None
    task = _EnvVerifiedTask(is_correct=True)
    agent = _RecordingAgent(AgentResult(outcome="error", reason="agent_error"))

    result = await execute_task(
        0,
        task,
        agent,
        adapter=None,
        tasklist_path=_tasklist_dir(),
        task_files_dirs=[],
        analyzers=[],
        detail="compact",
        renderer=_SilentRenderer(),
    )

    assert result.verification.outcome == "error"
    assert result.verification.reason == "agent_error"
    assert _EnvVerifiedTask.last_answer is None  # verify never called


@pytest.mark.asyncio
async def test_unsupported_run_skips_verification():
    _EnvVerifiedTask.last_answer = None
    task = _EnvVerifiedTask(is_correct=True)
    agent = _RecordingAgent(AgentResult(outcome="unsupported", reason="unsupported: ctx"))

    result = await execute_task(
        0,
        task,
        agent,
        adapter=None,
        tasklist_path=_tasklist_dir(),
        task_files_dirs=[],
        analyzers=[],
        detail="compact",
        renderer=_SilentRenderer(),
    )

    assert result.verification.outcome == "unsupported"
    assert _EnvVerifiedTask.last_answer is None


# ---------------------------------------------------------------------------
# build_report: no-answer diagnostic
# ---------------------------------------------------------------------------


def test_report_flags_missing_final_answer_on_success():
    ar = AgentResult(answer=None, outcome="success", metrics={"steps": 10})
    vr = TaskVerificationResult(is_correct=True)
    entry = build_report(SimpleNamespace(objective="o"), ar, vr, {}, "compact")
    assert entry["operational"]["final_answer"] is False
    assert entry["actual"] is None
    assert entry["outcome"] == "correct"  # graded, not fabricated


def test_report_no_flag_when_answer_present():
    ar = AgentResult(answer="hello", outcome="success", metrics={})
    vr = TaskVerificationResult(is_correct=False)
    entry = build_report(SimpleNamespace(objective="o"), ar, vr, {}, "compact")
    assert "final_answer" not in entry.get("operational", {})


def test_report_no_flag_on_error_outcome():
    ar = AgentResult(answer=None, outcome="error", reason="timeout")
    vr = TaskVerificationResult(is_correct=False, outcome="error", reason="timeout")
    entry = build_report(SimpleNamespace(objective="o"), ar, vr, {}, "compact")
    assert "final_answer" not in entry.get("operational", {})


# ---------------------------------------------------------------------------
# untrusted-agent swap gate
# ---------------------------------------------------------------------------


class _FakeRun:
    id = "run-1"
    status = "completed"
    answer = None  # completed with NO final text
    error = None
    trace: list = []
    harness_stderr = ""

    class metrics:
        steps_completed = 20
        tool_calls_completed = 8
        input_tokens = 100
        output_tokens = 50
        elapsed_seconds = 30.0


class _FreshEnv:
    def __init__(self):
        self.id = "env-fresh"

    async def upload_files(self, archive: bytes, dest: str = "/") -> None:
        pass

    async def destroy(self) -> None:
        pass


class _FakeClient:
    def __init__(self):
        self.fresh_env = _FreshEnv()

    async def create_environment(self, spec_id=None):
        return self.fresh_env

    async def run(self, env, **kwargs):
        return _FakeRun()

    async def get_run(self, run_id):
        return _FakeRun()


class _SwapTrackingEnv:
    def __init__(self, payload=b"archive"):
        self.payload = payload
        self.calls: list[str] = []
        self.destroyed = False
        self.id = "env-agent"

    async def download_files(self, path: str) -> bytes:
        self.calls.append(path)
        return self.payload

    async def upload_files(self, archive: bytes, dest: str = "/") -> None:
        pass

    async def destroy(self) -> None:
        self.destroyed = True


def _make_swap_agent(env, tmp_path) -> VivariumAgent:
    """VivariumAgent bypassing __init__, mirroring test_untrusted_swap_isolation."""
    agent = VivariumAgent.__new__(VivariumAgent)
    agent._untrusted_agent = True
    agent._envs = {"t1": env}
    agent._task_env_names = {"t1": "repo_env"}
    agent._spec_ids = {"repo_env": "spec-123"}
    agent._env_paths = {"repo_env": tmp_path / "environments" / "repo_env"}
    agent._verify_paths = {}
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


async def _nosleep(_):
    return None


@pytest.mark.asyncio
async def test_swap_runs_for_completed_run_without_answer(tmp_path, monkeypatch):
    """Security: an answerless completed run MUST still swap before verification."""
    monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)
    env = _SwapTrackingEnv()
    agent = _make_swap_agent(env, tmp_path)

    result = await agent.run(prompt="p", task_id="t1")

    assert result.outcome == "success"
    assert result.answer is None
    assert len(env.calls) > 0  # swap happened (VERIFY_PATHS downloaded)
    assert env.destroyed  # agent env destroyed — verification cannot touch it
    assert agent._envs["t1"].id == "env-fresh"  # fresh env registered for verify


@pytest.mark.asyncio
async def test_swap_skipped_for_error_run(tmp_path, monkeypatch):
    """Error runs don't verify, so no swap — same as before."""
    monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)

    class _FailRun(_FakeRun):
        status = "failed"

    env = _SwapTrackingEnv()
    agent = _make_swap_agent(env, tmp_path)

    async def _get_run(run_id):
        return _FailRun()

    agent._client.get_run = _get_run

    result = await agent.run(prompt="p", task_id="t1")

    assert result.outcome == "error"
    assert len(env.calls) == 0  # no swap for failed runs


# ---------------------------------------------------------------------------
# review fixes: task-type empty-answer handling + swap evidence preservation
# ---------------------------------------------------------------------------


def test_instruction_following_empty_answer_not_vacuously_correct():
    """Empty answer must not pass vacuously-true constraints (no_comma in '', etc.)."""
    from palace.task_types.instruction_following import InstructionFollowingTask

    t = InstructionFollowingTask.__new__(InstructionFollowingTask)
    t.id = "t1"
    t.objective = "write without commas"
    t.attachments = []
    t.custom_verificator = None
    t.custom_fields = {
        "task_type_fields": {
            "constraints": [
                {"type": "punctuation:no_comma", "params": {}},
                {"type": "keywords:existence", "params": {"keywords": ["x"]}},
            ]
        }
    }

    import asyncio

    vr = asyncio.run(t.verify(""))
    assert vr.is_correct is False
    assert vr.metrics["score"] == 0.0


def test_agentic_verify_crash_classification_is_deliberate():
    """Documented decision (commit e74a626): non-infra verify exceptions grade
    as 'incorrect'; only infra errors are excluded from scores. This test pins
    that behaviour so any future change is a conscious decision, not drift."""
    import asyncio

    from palace.task_types.agentic import AgenticTask

    t = AgenticTask.__new__(AgenticTask)
    t.id = "t1"
    t.custom_fields = {}

    async def bad_fn(expected, answer, ctx):
        raise TypeError("signature mismatch")

    AgenticTask._verify_fn = bad_fn
    try:
        vr = asyncio.run(t.verify("", env=_StubEnv()))
    finally:
        AgenticTask._verify_fn = None

    assert vr.outcome == "incorrect"  # documented deliberate behaviour
    assert vr.is_skipped is False
    assert "Verify failed" in vr.reasoning


@pytest.mark.asyncio
async def test_swap_failure_preserves_run_evidence(tmp_path, monkeypatch):
    """Swap failure must keep answer/metrics/elapsed/debug_logs for post-mortem."""
    monkeypatch.setattr("palace.agents.vivarium_agent.asyncio.sleep", _nosleep)

    env = _SwapTrackingEnv()  # download succeeds...

    # ...but fresh env rejects the re-upload
    class _RejectingEnv(_FreshEnv):
        async def upload_files(self, archive: bytes, dest: str = "/") -> None:
            raise RuntimeError("upload rejected")

    class _AnsweredRun(_FakeRun):
        answer = "agent-work-evidence"

    agent = _make_swap_agent(env, tmp_path)
    agent._client = _FakeClient()
    agent._client.fresh_env = _RejectingEnv()

    async def _get_run(run_id):
        return _AnsweredRun()

    agent._client.get_run = _get_run

    result = await agent.run(prompt="p", task_id="t1")

    assert result.outcome == "error"
    assert "untrusted_swap_failed" in result.reason
    assert result.answer == "agent-work-evidence"  # run evidence preserved
    assert result.metrics is not None and result.metrics["input_tokens"] == 100
    assert result.debug_logs == ""
