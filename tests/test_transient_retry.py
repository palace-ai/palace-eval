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

"""Tests for transient-retry behaviour of vivarium lifecycle stages.

Covers the shared retry_transient helper (budget, classification passthrough,
factory re-invocation), the poll-loop 404-as-transient branch, and the
verify-file injection retry in the agentic task type.
"""

import asyncio

import httpx
import pytest

from palace.utils.infra_errors import (
    TRANSIENT_NETWORK_ERRORS,
    TRANSIENT_RETRIES,
    is_infra_error,
    retry_transient,
)


def _status_error(code: int) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(
        f"{code}",
        request=httpx.Request("GET", "http://vivarium.test"),
        response=httpx.Response(code, request=httpx.Request("GET", "http://vivarium.test")),
    )


class TestRetryTransient:
    def test_retries_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _async_noop)
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.ReadTimeout("")
            return "ok"

        assert asyncio.run(retry_transient(flaky, what="test")) == "ok"
        assert calls["n"] == 3

    def test_exhausts_budget_and_reraises_original(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _async_noop)
        calls = {"n": 0}

        async def always_timeout():
            calls["n"] += 1
            raise httpx.ReadTimeout("")

        with pytest.raises(httpx.ReadTimeout):
            asyncio.run(retry_transient(always_timeout, what="test"))
        assert calls["n"] == TRANSIENT_RETRIES + 1

    def test_non_transient_raises_immediately(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _async_noop)
        calls = {"n": 0}

        async def bad_status():
            calls["n"] += 1
            raise _status_error(401)

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(retry_transient(bad_status, what="test"))
        assert calls["n"] == 1

    def test_factory_reinvoked_after_failure(self, monkeypatch):
        # A re-await of the same coroutine would raise
        # RuntimeError("coroutine is being awaited already") — the helper must
        # call the factory again instead.
        monkeypatch.setattr(asyncio, "sleep", _async_noop)
        seen = []

        def factory():
            async def coro():
                if not seen:
                    seen.append(object())
                    raise httpx.ConnectError("")
                return "done"

            return coro()

        assert asyncio.run(retry_transient(factory, what="test")) == "done"
        assert len(seen) == 1

    def test_all_network_error_types_retried(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _async_noop)
        for exc_type in TRANSIENT_NETWORK_ERRORS:
            calls = {"n": 0}

            async def flaky():
                calls["n"] += 1
                if calls["n"] < 2:
                    raise exc_type("")
                return "ok"

            assert asyncio.run(retry_transient(flaky, what="test")) == "ok"


class TestPoll404Transient:
    """The poll loop's classification branch: 404 on get_run is transient."""

    @pytest.mark.parametrize(
        "code,expected",
        [(500, True), (429, True), (401, False), (400, False)],
    )
    def test_status_codes(self, code, expected):
        # 404 is deliberately excluded: is_infra_error classifies it as
        # permanent; the poll branch overrides that specifically for get_run.
        assert is_infra_error(_status_error(code)) == expected

    def test_404_is_treated_as_transient_by_poll_branch(self):
        # Mirror the branch in vivarium_agent.run(): the isinstance-404 check
        # short-circuits before is_infra_error.
        def poll_classify(e):
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                return True
            return is_infra_error(e)

        assert poll_classify(_status_error(404)) is True
        assert poll_classify(_status_error(401)) is False
        assert poll_classify(httpx.ReadTimeout("")) is True


class _InjectEnv:
    """Fake ExecutionEnvironment with scripted exec failures."""

    def __init__(self, fail_times: int, exc: Exception):
        self.fail_times = fail_times
        self.exc = exc
        self.exec_calls = 0
        self.written: list[str] = []

    async def exec(self, cmd, timeout=120):
        self.exec_calls += 1
        if self.exec_calls <= self.fail_times:
            raise self.exc
        return 0, ""

    async def write(self, path, content):
        self.written.append(path)


class TestInjectVerifyFilesRetry:
    def _make_task(self, tmp_path):
        from palace.task_types.agentic import AgenticTask

        vdir = tmp_path / "environment" / "verify_files" / "t1"
        vdir.mkdir(parents=True)
        (vdir / "check.py").write_text("x")

        task = AgenticTask.__new__(AgenticTask)
        task.id = "t1"
        task.custom_fields = {}
        task._tasklist_path = tmp_path
        return task

    def test_retries_then_injects(self, tmp_path, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _async_noop)
        task = self._make_task(tmp_path)
        env = _InjectEnv(fail_times=2, exc=httpx.ReadTimeout(""))

        asyncio.run(task._inject_verify_files(env))
        assert env.written == ["/verify_files/check.py"]
        # 1 failed mkdir + 1 failed retry + 1 successful mkdir + write's execs
        assert env.exec_calls >= 3

    def test_non_transient_raises_immediately(self, tmp_path, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _async_noop)
        task = self._make_task(tmp_path)
        env = _InjectEnv(fail_times=99, exc=_status_error(401))

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(task._inject_verify_files(env))
        assert env.exec_calls == 1

    def test_budget_exhaustion_raises_last_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _async_noop)
        task = self._make_task(tmp_path)
        env = _InjectEnv(fail_times=99, exc=httpx.ReadTimeout(""))

        with pytest.raises(httpx.ReadTimeout):
            asyncio.run(task._inject_verify_files(env))
        assert env.exec_calls == TRANSIENT_RETRIES + 1


async def _async_noop(_=None):
    pass
