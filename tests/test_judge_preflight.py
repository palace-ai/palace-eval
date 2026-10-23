"""Tests for the judge configuration preflight (task-failure-isolation spec).

A QA tasklist with an unconfigured judge must fail at preflight — before any
task dispatch — instead of costing one completed agent run before the lazy
Judge construction in verify() discovers the problem.
"""

import pytest

from palace.evaluation.judge_config import JudgeConfig
from palace.judge import validate_judge_config
from palace.utils.exceptions import JudgeConfigurationError


class TestValidateJudgeConfig:
    def test_missing_model_raises(self):
        with pytest.raises(JudgeConfigurationError, match="judge_model"):
            validate_judge_config(None, "http://judge.test")

    def test_missing_url_raises(self):
        with pytest.raises(JudgeConfigurationError, match="URL"):
            validate_judge_config("gpt-4o", None)

    def test_valid_config_passes(self):
        validate_judge_config("gpt-4o", "http://judge.test")


class TestJudgeInitDelegates:
    def test_judge_init_uses_shared_validation(self, monkeypatch):
        """Judge.__init__ must raise the same errors via validate_judge_config."""
        from palace.judge import Judge

        monkeypatch.setenv("JUDGE_MODEL", "")
        monkeypatch.delenv("JUDGE_MODEL", raising=False)
        monkeypatch.setattr("palace.judge.get_judge_url", lambda: "http://judge.test")
        with pytest.raises(JudgeConfigurationError, match="judge_model"):
            Judge(judge_model=None, judge_prompt="p")

    def test_judge_init_valid_construction(self, monkeypatch):
        from palace.judge import Judge

        monkeypatch.setattr("palace.judge.get_judge_url", lambda: "http://judge.test")
        judge = Judge(judge_model="gpt-4o", judge_prompt="p")
        assert judge.judge_model is not None


class TestPreflightIntegration:
    def test_preflight_gates_qa_tasklists(self, monkeypatch, tmp_path):
        """evaluate_async preflight raises before dispatch for QA tasklists."""
        # Tasklist fixture: minimal QA info.json + tasks.json
        (tmp_path / "info.json").write_text('{"task_type": "QA", "tasks_path": "tasks.json"}')
        (tmp_path / "tasks.json").write_text("[]")

        from palace.evaluation.orchestrator import Evaluation
        from palace.utils.exceptions import JudgeConfigurationError

        monkeypatch.setattr("palace.evaluation.orchestrator.resolve_local_path", lambda t: tmp_path)
        monkeypatch.setattr("palace.evaluation.orchestrator.get_judge_model", lambda: None)
        monkeypatch.setattr("palace.evaluation.orchestrator.get_judge_url", lambda: None)

        ev = Evaluation(judge_config=JudgeConfig())
        with pytest.raises(JudgeConfigurationError):
            import asyncio

            asyncio.run(ev.evaluate_async("m", "some-tasklist"))

    def test_no_preflight_for_classification(self, monkeypatch, tmp_path):
        """Classification tasklists don't use the judge — no preflight raise."""
        (tmp_path / "info.json").write_text('{"task_type": "Classification", "tasks_path": "tasks.json"}')
        (tmp_path / "tasks.json").write_text("[]")

        from palace.evaluation.orchestrator import Evaluation
        from palace.utils.exceptions import JudgeConfigurationError

        monkeypatch.setattr("palace.evaluation.orchestrator.resolve_local_path", lambda t: tmp_path)
        monkeypatch.setattr("palace.evaluation.orchestrator.get_judge_model", lambda: None)
        monkeypatch.setattr("palace.evaluation.orchestrator.get_judge_url", lambda: None)

        ev = Evaluation(judge_config=JudgeConfig())
        # Must NOT raise JudgeConfigurationError at preflight (will fail later
        # at agent creation, which we don't reach in this unit test)
        import asyncio

        try:
            asyncio.run(ev.evaluate_async("m", "some-tasklist"))
        except JudgeConfigurationError:
            pytest.fail("Preflight raised for a non-judged tasklist")
        except Exception:
            pass  # agent-creation errors are out of scope here
