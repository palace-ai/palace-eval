"""Tests for the per-task timeout hierarchy.

Job-1361 regression class: the dispatch-level task budget (task_timeout in
dispatch.py) fired *before* the agent's internal graceful timeout
(VivariumAgent.timeout_seconds), so tasks over ~2h10m were killed by
asyncio.wait_for with a bare TimeoutError — no AgentResult, no metrics,
no skip_reason detail. The dispatch budget must sit ABOVE the agent
timeout so the graceful path (AgentResult(outcome="error",
reason="timeout") with token/step metrics preserved) wins the race.
"""

import inspect

import pytest

from palace.agents.vivarium_agent import VivariumAgent
from palace.evaluation.dispatch import dispatch_tasks
from palace.utils.infra_errors import is_infra_error

AGENT_TIMEOUT = inspect.signature(VivariumAgent.__init__).parameters["timeout_seconds"].default
DISPATCH_TIMEOUT = inspect.signature(dispatch_tasks).parameters["task_timeout"].default


class TestTimeoutHierarchy:
    def test_dispatch_budget_exceeds_agent_timeout(self):
        """Dispatch must allow headroom above the agent's graceful timeout."""
        assert AGENT_TIMEOUT < DISPATCH_TIMEOUT, (
            f"agent timeout ({AGENT_TIMEOUT}s) must be below dispatch "
            f"task_timeout ({DISPATCH_TIMEOUT}s) so graceful agent timeout "
            "fires first and preserves metrics"
        )

    def test_agent_default_is_three_hours(self):
        assert AGENT_TIMEOUT == 10800  # 3h

    def test_dispatch_default_is_12600(self):
        """3.5h dispatch ceiling: 3h agent + headroom for seed/swap/verify."""
        assert DISPATCH_TIMEOUT == 12600

    @pytest.mark.asyncio
    async def test_asyncio_timeout_is_infra(self):
        """A dispatch-level timeout is classified as infra (skipped, not wrong)."""
        assert is_infra_error(TimeoutError())
