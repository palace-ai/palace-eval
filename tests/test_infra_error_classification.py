"""Tests for infrastructure-error classification during agentic verification.

Covers:
- is_infra_error: transient HTTP statuses, network errors, disk-pressure 422,
  asyncio timeouts, and non-infra exceptions
- AgenticTask.verify: infra exceptions during verify_fn produce
  outcome="error" (excluded from scores), not incorrect
- Aggregation: error outcomes excluded from accuracy denominator
"""

import asyncio

import httpx
import pytest

from palace.task_types.agentic import AgenticTask
from palace.task_types.base import TaskVerificationResult
from palace.utils.infra_errors import is_infra_error


def _http_status_error(status: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://vivarium.test/environments/e1/exec")
    response = httpx.Response(status, request=request, content=body.encode())
    return httpx.HTTPStatusError(f"{status} error", request=request, response=response)


class TestIsInfraError:
    def test_transient_status_codes(self):
        for code in (429, 500, 502, 503, 504, 529):
            assert is_infra_error(_http_status_error(code)), code

    def test_non_transient_status(self):
        assert not is_infra_error(_http_status_error(400))
        assert not is_infra_error(_http_status_error(404))
        assert not is_infra_error(_http_status_error(409))

    def test_disk_pressure_422_body(self):
        assert is_infra_error(_http_status_error(422, "Disk pressure critical: 95% used"))
        assert is_infra_error(_http_status_error(422, "ENOSPC: no space left on device"))

    def test_non_disk_422(self):
        assert not is_infra_error(_http_status_error(422, "invalid spec field: image"))

    def test_network_errors(self):
        assert is_infra_error(httpx.ConnectError("connection refused"))
        assert is_infra_error(httpx.ConnectTimeout("timed out"))
        assert is_infra_error(httpx.ReadTimeout("read timed out"))

    def test_asyncio_timeout(self):
        assert is_infra_error(asyncio.TimeoutError())

    def test_genuine_task_failure_is_not_infra(self):
        assert not is_infra_error(ValueError("bad answer format"))
        assert not is_infra_error(RuntimeError("verify script crashed"))
        assert not is_infra_error(KeyError("missing key"))


class _FakeEnv:
    """ExecutionEnvironment stub whose exec raises the given exception."""

    def __init__(self, exc: Exception | None = None, exec_result: tuple[int, str] = (0, "")):
        self.exc = exc
        self.exec_result = exec_result
        self.calls: list[str] = []

    async def exec(self, cmd: str, timeout: int = 120) -> tuple[int, str]:
        self.calls.append(cmd)
        if self.exc is not None:
            raise self.exc
        return self.exec_result

    async def read(self, path: str) -> str:
        return ""

    async def write(self, path: str, content: bytes) -> None:
        pass


def _make_task() -> AgenticTask:
    task = AgenticTask.__new__(AgenticTask)
    task.id = "t1"
    task.custom_fields = {"expected_outcome": {}}
    task._verify_fn = None
    task._tasklist_path = None
    return task


def _set_verify_fn(task: AgenticTask, fn) -> None:
    task._verify_fn = fn


@pytest.mark.asyncio
class TestVerifyInfraClassification:
    async def test_504_during_verification_is_error_not_incorrect(self):
        """The job-1175 regression: orchestrator 504 must not count as a wrong answer."""
        task = _make_task()

        async def verify_fn(expected, answer, ctx):
            _, _ = await ctx.exec("bash /tmp/eval.sh", timeout=1800)
            return {"is_correct": False, "reasoning": "unreachable"}

        _set_verify_fn(task, verify_fn)
        env = _FakeEnv(exc=_http_status_error(504))

        result = await task.verify("answer", env=env)
        assert result.outcome == "error"
        assert result.is_correct is False
        assert result.is_skipped is True
        assert "verify_infra_error" in result.reason
        assert "504" in result.reason

    async def test_connect_error_during_verification_is_error(self):
        task = _make_task()

        async def verify_fn(expected, answer, ctx):
            _, _ = await ctx.exec("bash /tmp/eval.sh", timeout=1800)
            return {"is_correct": False, "reasoning": "unreachable"}

        _set_verify_fn(task, verify_fn)
        env = _FakeEnv(exc=httpx.ConnectError("worker unreachable"))

        result = await task.verify("answer", env=env)
        assert result.outcome == "error"
        assert result.is_skipped is True

    async def test_genuine_verify_exception_still_incorrect(self):
        task = _make_task()

        async def verify_fn(expected, answer, ctx):
            _, _ = await ctx.exec("bash /tmp/eval.sh", timeout=1800)
            return {"is_correct": False, "reasoning": "unreachable"}

        _set_verify_fn(task, verify_fn)
        env = _FakeEnv(exc=ValueError("parser.py exploded"))

        result = await task.verify("answer", env=env)
        assert result.outcome == "incorrect"
        assert result.is_skipped is False
        assert "Verify failed" in result.reasoning

    async def test_clean_verification_result_passthrough(self):
        task = _make_task()
        _set_verify_fn(
            task,
            lambda e, a, ctx: {"is_correct": True, "reasoning": "FAIL_TO_PASS: 3/3", "metrics": {"resolution": "FULL"}},
        )
        env = _FakeEnv()

        result = await task.verify("answer", env=env)
        assert result.outcome == "correct"
        assert result.is_correct is True


class TestAggregateExcludesErrors:
    def test_errors_excluded_from_accuracy(self):
        correct = TaskVerificationResult(is_correct=True)
        incorrect = TaskVerificationResult(is_correct=False)
        error = TaskVerificationResult(is_correct=False, outcome="error", reason="verify_infra_error: 504")

        agg = AgenticTask.aggregate([correct, incorrect, error])
        # Errors excluded: 1 correct / 2 evaluated
        assert agg["accuracy"] == pytest.approx(0.5)
