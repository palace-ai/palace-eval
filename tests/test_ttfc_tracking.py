"""Tests for time-to-first-chunk (TTFC) / time-to-first-content-chunk (TTFCC) tracking.

Both are measured from just before the request is sent (same start timestamp
as compute_seconds):
- ttfc_seconds: first output chunk (content or reasoning)
- ttfcc_seconds: first *content* chunk (differs from ttfc only when reasoning
  is streamed before the content)

Both must be None when no output chunk arrives (e.g. usage-only streams) and
strictly <= compute_seconds on success.
"""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from palace.models.api_model import OpenAIModel


def _chunk(content=None, reasoning=None, usage=None, finish_reason=None, **extra):
    """Build a minimal OpenAI-shaped stream chunk (extra attrs at top level)."""
    delta = SimpleNamespace(content=content, reasoning_content=reasoning)
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=usage, **extra)


def _make_model() -> OpenAIModel:
    return OpenAIModel(model_id="test-model", url="http://test", token="sk-test")


class TestCollectOpenAIStreamTTFC:
    def test_ttfc_present_on_content(self):
        model = _make_model()

        async def stream():
            yield _chunk(content="")
            yield _chunk(content="Hel")
            yield _chunk(content="lo")
            yield _chunk(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2), finish_reason="stop")

        start = time.perf_counter()
        text, usage, stream_stats = asyncio.run(model._collect_openai_stream(stream(), request_start=start))
        elapsed = time.perf_counter() - start

        assert text == "Hello"
        assert usage == {"input_tokens": 1, "output_tokens": 2}
        assert stream_stats["ttfc_seconds"] is not None
        assert 0 <= stream_stats["ttfc_seconds"] <= elapsed
        assert stream_stats["ttfcc_seconds"] is not None
        assert stream_stats["output_chunks"] == 2

    def test_ttfc_present_on_reasoning_only(self):
        """Reasoning models emit reasoning_content before content — ttfc counts
        it, ttfcc lands on the first *content* chunk."""
        model = _make_model()

        async def stream():
            yield _chunk(reasoning="thinking...")
            yield _chunk(content="answer")

        _, _, stream_stats = asyncio.run(model._collect_openai_stream(stream(), request_start=time.perf_counter()))
        assert stream_stats["ttfc_seconds"] is not None
        assert stream_stats["ttfcc_seconds"] is not None
        assert stream_stats["output_chunks"] == 2

    def test_ttfcc_after_ttfc_when_reasoning_streamed(self):
        """With reasoning first, ttfc <= ttfcc (content arrives later)."""
        model = _make_model()

        async def stream():
            yield _chunk(reasoning="thinking...")
            await asyncio.sleep(0.2)
            yield _chunk(content="answer")

        start = time.perf_counter()
        _, _, stream_stats = asyncio.run(model._collect_openai_stream(stream(), request_start=start))
        assert stream_stats["ttfc_seconds"] is not None
        assert stream_stats["ttfcc_seconds"] is not None
        assert stream_stats["ttfc_seconds"] < 0.15  # first reasoning chunk arrives fast
        assert stream_stats["ttfcc_seconds"] > 0.15  # content chunk after the gap
        # Reasoning-only chunks are still output chunks
        assert stream_stats["output_chunks"] == 2

    def test_ttfc_captured_at_first_output_chunk(self):
        """TTFC must reflect the first output chunk, not stream end."""
        model = _make_model()

        async def stream():
            yield _chunk(content="first")
            await asyncio.sleep(0.2)
            yield _chunk(content="second")

        start = time.perf_counter()
        _, _, stream_stats = asyncio.run(model._collect_openai_stream(stream(), request_start=start))

        assert stream_stats["ttfc_seconds"] is not None
        assert stream_stats["ttfc_seconds"] < 0.15  # well below the 0.2s gap before the last chunk

    def test_ttfc_none_for_empty_stream(self):
        model = _make_model()

        async def stream():
            yield _chunk(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=0))

        with pytest.raises(ValueError, match="Empty API response"):
            asyncio.run(model._collect_openai_stream(stream(), request_start=time.perf_counter()))

    def test_server_latency_checkpoint_captured(self):
        """usage.latency_checkpoint must be surfaced as server_* fields (Azure APIM)."""
        model = _make_model()
        checkpoint = SimpleNamespace(
            engine_ttft_ms=610, service_ttft_ms=909, user_visible_ttft_ms=740, engine_tbt_ms=19
        )

        async def stream():
            yield _chunk(content="hi")
            yield _chunk(
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, latency_checkpoint=checkpoint),
                finish_reason="stop",
            )

        _, _, stream_stats = asyncio.run(model._collect_openai_stream(stream(), request_start=time.perf_counter()))
        assert stream_stats["server_latency"]["engine_ttft_ms"] == 610
        assert stream_stats["server_latency"]["service_ttft_ms"] == 909
        assert stream_stats["server_latency"]["user_visible_ttft_ms"] == 740
        assert stream_stats["server_latency"]["engine_tbt_ms"] == 19

    def test_server_latency_checkpoint_at_chunk_top_level(self):
        """On streams Azure APIM sends latency_checkpoint on a separate final
        chunk (choices: []) at the top level, not inside usage."""
        model = _make_model()
        checkpoint = {"engine_ttft_ms": 473, "engine_tbt_ms": 21, "engine_ttlt_ms": 11883}

        async def stream():
            yield _chunk(content="hi")
            yield _chunk(latency_checkpoint=checkpoint)  # no usage, no choices

        _, _, stream_stats = asyncio.run(model._collect_openai_stream(stream(), request_start=time.perf_counter()))
        assert stream_stats["server_latency"]["engine_ttft_ms"] == 473
        assert stream_stats["server_latency"]["engine_tbt_ms"] == 21
        assert stream_stats["server_latency"]["engine_ttlt_ms"] == 11883

    def test_no_server_fields_without_checkpoint(self):
        model = _make_model()

        async def stream():
            yield _chunk(content="hi")
            yield _chunk(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1), finish_reason="stop")

        _, _, stream_stats = asyncio.run(model._collect_openai_stream(stream(), request_start=time.perf_counter()))
        assert stream_stats.get("server_latency") == {}


class TestCallApiStatsShape:
    def test_call_api_returns_ttfc_in_stats(self):
        """_call_api must include ttfc/ttfcc in the stats dict."""
        model = _make_model()

        async def stream():
            yield _chunk(content="hi")
            yield _chunk(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1), finish_reason="stop")

        model.client = MagicMock()
        model.client.chat.completions.create = AsyncMock(return_value=stream())

        with patch("palace.models.api_model.time.perf_counter", side_effect=time.perf_counter):
            _, stats = asyncio.run(model._call_api([{"role": "user", "content": "hello"}]))

        assert stats["ttfc_seconds"] is not None
        assert stats["ttfc_seconds"] <= stats["compute_seconds"]
        assert stats["ttfcc_seconds"] is not None
        assert stats["input_tokens"] == 1
        assert stats["output_tokens"] == 1


class TestReportEntryShape:
    def test_operational_bucket_shape(self):
        """Operational metrics must live in entry["operational"], nested by
        metric type; nothing duplicated at entry level."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={"input_tokens": 10, "output_tokens": 5, "compute_seconds": 1.0, "ttfc_seconds": 0.2},
        )
        entry = build_report(task, result, vr, {}, "none")
        op = entry["operational"]
        assert "ttfc_seconds" in op["timing"]
        assert "ttfc_seconds" not in entry
        assert "ttfc_seconds" not in op["throughput"]  # single location
        assert set(op.keys()) == {"reasoning_status", "timing", "throughput", "tokens", "chunks", "attempts"}
        assert op["timing"]["wall_seconds"] == 0.0  # wall time inside timing

    def test_vivarium_style_metrics_still_passed_through(self):
        """Non-operational metrics (steps, tool_calls) must still be copied to entry level."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "steps": 3,
                "tool_calls": 2,
                "input_tokens": 10,
                "output_tokens": 5,
                "compute_seconds": 1.0,
                "ttfc_seconds": 0.2,
            },
        )
        entry = build_report(task, result, vr, {}, "none")
        assert entry["steps"] == 3
        assert entry["tool_calls"] == 2
        assert "steps" not in entry["operational"]["timing"]


def _make_task(task_id: str = "t1", expected: str = "a"):
    from palace.task_types.qa import QATask

    return QATask.from_dict({"id": task_id, "objective": "q", "expected": expected, "task_type": "QA"})


class TestBuildReportTiming:
    def test_timing_includes_ttfc(self):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 10,
                "output_tokens": 5,
                "compute_seconds": 1.234,
                "ttfc_seconds": 0.1234,
                "ttfcc_seconds": 0.1234,
                "reasoning_tokens": 0,
            },
        )
        entry = build_report(task, result, vr, {}, "none")
        assert entry["operational"]["timing"]["ttfc_seconds"] == 0.12
        assert entry["operational"]["timing"]["ttfcc_seconds"] == 0.12
        assert entry["operational"]["timing"]["total_seconds"] == 1.23
        assert entry["operational"]["timing"]["wall_seconds"] == 0.0

    def test_timing_ttfc_null_when_reasoning_absent_and_no_ttfc(self):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(answer="a", metrics={"compute_seconds": 1.0})
        entry = build_report(task, result, vr, {}, "none")
        assert entry["operational"]["timing"]["ttfc_seconds"] is None
        assert entry["operational"]["timing"]["ttfcc_seconds"] is None
        assert entry["operational"]["throughput"]["prefill_cps"] is None
        assert entry["operational"]["throughput"]["generation_cps"] is None
        assert entry["operational"]["throughput"]["total_cps"] is None

    def test_ttfc_null_when_reasoning_hidden(self):
        """Hidden reasoning sits inside ttfc — as a TTFT proxy it is unreliable."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 100,
                "output_tokens": 60,
                "compute_seconds": 3.5,
                "ttfc_seconds": 2.0,
                "ttfcc_seconds": 2.0,
                "output_chunks": 20,
                "reasoning_tokens": 40,
            },
        )
        op = build_report(task, result, vr, {}, "none")["operational"]
        assert op["reasoning_status"] == "hidden"
        assert op["timing"]["ttfc_seconds"] is None  # nulled — unreliable
        assert op["timing"]["ttfcc_seconds"] == 2.0  # exact: first chunk IS content
        assert op["throughput"]["prefill_cps"] is None
        assert op["throughput"]["generation_cps"] is None  # window excludes hidden reasoning time
        assert op["throughput"]["content_cps"] == 13.3  # (60-40) / (3.5-2.0) — exact fallback
        assert op["throughput"]["total_cps"] is not None

    def test_ttfc_null_when_reasoning_unknown(self):
        """No reasoning chunks AND no server count — regime unknown, both
        client latency metrics nulled."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 100,
                "output_tokens": 60,
                "compute_seconds": 2.5,
                "ttfc_seconds": 0.5,
                "ttfcc_seconds": 0.5,
                "output_chunks": 30,
            },
        )
        op = build_report(task, result, vr, {}, "none")
        op = op["operational"]
        assert op["reasoning_status"] is None
        assert op["timing"]["ttfc_seconds"] is None
        assert op["timing"]["ttfcc_seconds"] is None
        assert op["throughput"]["prefill_cps"] is None
        assert op["throughput"]["generation_cps"] is None
        assert op["throughput"]["content_cps"] is None
        assert op["throughput"]["total_cps"] is None  # token accounting uncertifiable


class TestThroughputMetrics:
    """Prefill/generation/content/total rates, per task and run-level aggregates."""

    def test_per_task_throughput_values_streamed(self):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        # ttfc=0.5s for 100 input tokens -> prefill 200 tok/s
        # generation window = 2.5-0.5 = 2.0s; 60 output tokens -> 30 tok/s
        # total = 160 tokens / 2.5s -> 64 tok/s
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 100,
                "output_tokens": 60,
                "compute_seconds": 2.5,
                "ttfc_seconds": 0.5,
                "ttfcc_seconds": 1.0,
                "output_chunks": 32,
                "reasoning_chunks": 12,
                "reasoning_tokens": 20,
            },
        )
        tp = build_report(task, result, vr, {}, "none")["operational"]["throughput"]
        assert tp["prefill_cps"] == 200.0
        assert tp["generation_cps"] == 30.0
        assert tp["content_cps"] == 26.7  # (60-20) / (2.5-1.0)
        assert tp["total_cps"] == 64.0

    def test_per_task_throughput_none_without_ttfc(self):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(answer="a", metrics={"input_tokens": 100, "output_tokens": 60, "compute_seconds": 2.5})
        tp = build_report(task, result, vr, {}, "none")["operational"]["throughput"]
        assert tp["prefill_cps"] is None
        assert tp["generation_cps"] is None

    def test_generation_cps_includes_reasoning_tokens(self):
        """generation = output = reasoning + content: the full output count
        goes in the numerator when reasoning is streamed."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 100,
                "output_tokens": 60,
                "compute_seconds": 2.5,
                "ttfc_seconds": 0.5,
                "output_chunks": 60,
                "reasoning_chunks": 20,
                "reasoning_tokens": 30,
            },
        )
        tp = build_report(task, result, vr, {}, "none")["operational"]["throughput"]
        assert tp["generation_cps"] == 30.0  # 60 / 2.0, NOT (60-30)/2.0

    def test_content_cps_null_when_reasoning_streamed_without_count(self):
        """Reasoning visible as chunks but the server doesn't report the token
        split: the content numerator is uncertifiable -> None."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 100,
                "output_tokens": 60,
                "compute_seconds": 2.5,
                "ttfc_seconds": 0.5,
                "ttfcc_seconds": 1.0,
                "output_chunks": 40,
                "reasoning_chunks": 20,
            },
        )
        op = build_report(task, result, vr, {}, "none")["operational"]
        assert op["reasoning_status"] == "streamed"
        assert op["throughput"]["content_cps"] is None
        assert op["throughput"]["generation_cps"] == 30.0  # output rate unaffected
        assert op["throughput"]["total_cps"] == 64.0  # token accounting certified (streamed)

    def test_tokens_block_includes_reasoning_tokens(self):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={"input_tokens": 10, "output_tokens": 5, "compute_seconds": 1.0, "reasoning_tokens": 3},
        )
        entry = build_report(task, result, vr, {}, "none")
        assert entry["operational"]["tokens"] == {
            "input_tokens": 10,
            "output_tokens": 5,
            "reasoning_tokens": 3,
        }

    def test_reasoning_status_in_operational_root(self):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={"compute_seconds": 1.0, "ttfc_seconds": 0.2, "output_chunks": 9, "reasoning_chunks": 4},
        )
        op = build_report(task, result, vr, {}, "none")["operational"]
        assert op["reasoning_status"] == "streamed"
        assert op["chunks"]["reasoning_chunks"] == 4
        assert op["chunks"]["output_chunks"] == 9
        assert "reasoning_status" not in op["chunks"]  # moved to the bucket root

    def test_prefill_null_when_reasoning_hidden(self):
        """Hidden reasoning sits inside ttfc — the prefill rate would be
        distorted (observed: 23.4 tok/s for a 1 041-token prompt)."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 1041,
                "output_tokens": 6806,
                "compute_seconds": 44.55,
                "ttfc_seconds": 44.53,
                "ttfcc_seconds": 44.53,
                "output_chunks": 4,
                "reasoning_chunks": 0,
                "reasoning_tokens": 6792,
            },
        )
        op = build_report(task, result, vr, {}, "none")["operational"]
        assert op["reasoning_status"] == "hidden"
        assert op["throughput"]["prefill_cps"] is None
        assert op["timing"]["ttfc_seconds"] is None
        # Content window = 44.55 - 44.53 = 0.02s < 1.0s minimum -> nulled
        assert op["throughput"]["content_cps"] is None

    def test_prefill_kept_when_reasoning_streamed(self):
        """With streamed reasoning, ttfc lands on the first reasoning chunk
        (emitted right after prefill) — the prefill rate is exact."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 1000,
                "output_tokens": 500,
                "compute_seconds": 10.0,
                "ttfc_seconds": 0.5,
                "ttfcc_seconds": 1.0,
                "output_chunks": 200,
                "reasoning_chunks": 100,
            },
        )
        op = build_report(task, result, vr, {}, "none")["operational"]
        assert op["throughput"]["prefill_cps"] == 2000.0
        assert op["reasoning_status"] == "streamed"

    def test_prefill_kept_when_reasoning_known_empty(self):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 1000,
                "output_tokens": 100,
                "compute_seconds": 5.0,
                "ttfc_seconds": 0.5,
                "ttfcc_seconds": 0.5,
                "output_chunks": 100,
                "reasoning_chunks": 0,
                "reasoning_tokens": 0,
            },
        )
        op = build_report(task, result, vr, {}, "none")["operational"]
        assert op["throughput"]["prefill_cps"] == 2000.0
        assert op["reasoning_status"] == "none"
        assert op["timing"]["ttfcc_seconds"] == 0.5  # == ttfc in absent mode

    def test_rates_null_below_minimum_window(self):
        """JRC-style buffering: 3-4 chunks over a rounded ~0.02s window turned
        into junk rates (182-732 tok/s from 8-14 visible tokens). A minimum
        window of 1s guards prefill/generation/content; total_cps is exempt."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 1033,
                "output_tokens": 152,
                "compute_seconds": 1.33,
                "ttfc_seconds": 1.26,
                "ttfcc_seconds": 1.26,
                "output_chunks": 4,
                "reasoning_chunks": 0,
                "reasoning_tokens": 139,
            },
        )
        tp = build_report(task, result, vr, {}, "none")["operational"]["throughput"]
        assert tp["generation_cps"] is None
        assert tp["content_cps"] is None
        assert tp["total_cps"] is not None  # robust to buffered delivery

    def test_generation_cps_null_for_buffered_delivery(self):
        """Endpoints that deliver the response in <=2 output chunks make the
        phase windows meaningless — phase rates must be None."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        for n_chunks in (1, 2):
            result = AgentResult(
                answer="a",
                metrics={
                    "input_tokens": 100,
                    "output_tokens": 60,
                    "compute_seconds": 2.5,
                    "ttfc_seconds": 0.5,
                    "ttfcc_seconds": 0.5,
                    "output_chunks": n_chunks,
                    "reasoning_chunks": 0,
                    "reasoning_tokens": 0,
                },
            )
            tp = build_report(task, result, vr, {}, "none")["operational"]["throughput"]
            assert tp["generation_cps"] is None, n_chunks
            assert tp["content_cps"] is None, n_chunks
            assert tp["prefill_cps"] is None, n_chunks

    def test_generation_cps_kept_when_token_like(self):
        """>2 output chunks (token-like delivery) keeps the phase rates."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "input_tokens": 100,
                "output_tokens": 60,
                "compute_seconds": 2.5,
                "ttfc_seconds": 0.5,
                "ttfcc_seconds": 0.5,
                "output_chunks": 60,
                "reasoning_chunks": 0,
                "reasoning_tokens": 0,
            },
        )
        tp = build_report(task, result, vr, {}, "none")["operational"]["throughput"]
        assert tp["generation_cps"] == 30.0
        assert tp["content_cps"] == 30.0  # all output is content in absent mode

    def test_output_chunks_in_chunks_bucket(self):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={"compute_seconds": 1.0, "ttfc_seconds": 0.2, "output_chunks": 7},
        )
        entry = build_report(task, result, vr, {}, "none")
        assert entry["operational"]["chunks"]["output_chunks"] == 7
        assert "output_chunks" not in entry

    def test_server_latency_fields_in_timing_server(self):
        """server_latency (from latency_checkpoint) lands in
        operational.timing.server, normalized ms -> seconds."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "compute_seconds": 1.0,
                "ttfc_seconds": 0.2,
                "output_chunks": 5,
                "server_latency": {"engine_ttft_ms": 610, "engine_tbt_ms": 19, "custom_field_ms": 5},
            },
        )
        server = build_report(task, result, vr, {}, "none")["operational"]["timing"]["server"]
        assert server["engine_ttft_seconds"] == 0.61
        assert server["engine_tbt_seconds"] == 0.019
        assert "custom_field_ms" not in server  # schema is fixed
        assert server["service_ttft_seconds"] is None  # absent -> None, key exists

    def test_server_schema_null_when_endpoint_provides_nothing(self):
        """The full server schema must exist with None values on endpoints
        without a latency checkpoint (consistent JSON shape everywhere)."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "compute_seconds": 1.0,
                "ttfc_seconds": 0.2,
                "ttfcc_seconds": 0.2,
                "output_chunks": 5,
                "reasoning_tokens": 0,
            },
        )
        op = build_report(task, result, vr, {}, "none")["operational"]
        assert set(op["timing"].keys()) == {"total_seconds", "wall_seconds", "ttfc_seconds", "ttfcc_seconds", "server"}
        assert set(op["timing"]["server"].keys()) == {
            "engine_ttft_seconds",
            "service_ttft_seconds",
            "user_visible_ttft_seconds",
            "pre_inference_seconds",
            "engine_tbt_seconds",
            "service_tbt_seconds",
            "engine_ttlt_seconds",
        }
        assert all(v is None for v in op["timing"]["server"].values())
        assert op["timing"]["ttfc_seconds"] == 0.2  # client-measured, reasoning absent
        assert set(op["throughput"].keys()) == {"prefill_cps", "generation_cps", "content_cps", "total_cps"}
        assert op["chunks"]["output_chunks"] == 5
        assert op["attempts"] is None  # attempts only present when the model reports them

    def test_total_chunks_in_chunks_bucket(self):
        """total_chunks (all stream frames) rides alongside output/reasoning
        chunks — the gateway-buffering diagnostic."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={"compute_seconds": 1.0, "ttfc_seconds": 0.2, "output_chunks": 5, "total_chunks": 12},
        )
        chunks = build_report(task, result, vr, {}, "none")["operational"]["chunks"]
        assert chunks["total_chunks"] == 12
        assert chunks["output_chunks"] == 5
        assert "total_chunks" not in build_report(task, result, vr, {}, "none")  # not at entry level

    def test_total_chunks_null_when_not_reported(self):
        """Vivarium agents don't produce chunk stats — key exists with None."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(answer="a", metrics={"compute_seconds": 1.0, "steps": 3})
        entry = build_report(task, result, vr, {}, "none")
        assert entry["operational"]["chunks"]["total_chunks"] is None
        assert entry["steps"] == 3  # passthrough unaffected

    def test_attempts_in_operational_root(self):
        """attempts (from the retry layer) lands at the operational root."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={"compute_seconds": 1.0, "ttfc_seconds": 0.2, "attempts": 4},
        )
        op = build_report(task, result, vr, {}, "none")["operational"]
        assert op["attempts"] == 4
        assert "attempts" not in op["timing"]

    def test_attempts_absent_is_null(self):
        """Agents without retry reporting (vivarium) get attempts=None."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(answer="a", metrics={"compute_seconds": 1.0, "steps": 2})
        op = build_report(task, result, vr, {}, "none")["operational"]
        assert op["attempts"] is None

    def test_per_task_zero_tokens_none(self):
        """Endpoints without usage data must not produce division artefacts."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult

        task = _make_task()
        vr = TaskVerificationResult(is_correct=True)
        result = AgentResult(
            answer="a",
            metrics={
                "compute_seconds": 2.5,
                "ttfc_seconds": 0.5,
                "ttfcc_seconds": 0.5,
                "output_chunks": 20,
                "reasoning_chunks": 0,
                "reasoning_tokens": 0,
            },
        )
        tp = build_report(task, result, vr, {}, "none")["operational"]["throughput"]
        assert tp["prefill_cps"] is None
        assert tp["generation_cps"] is None
        assert tp["total_cps"] is None

    def test_run_level_mean_min_max(self):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult
        from palace.task_types.qa import QATask

        vr = TaskVerificationResult(is_correct=True)
        report = {}
        for i, (inp, out, compute, ttfc) in enumerate([(100, 60, 2.5, 0.5), (300, 30, 1.5, 0.25), (50, 10, 4.0, 0.1)]):
            task = QATask.from_dict({"id": f"t{i}", "objective": "q", "expected": "a", "task_type": "QA"})
            result = AgentResult(
                answer="a",
                metrics={
                    "input_tokens": inp,
                    "output_tokens": out,
                    "compute_seconds": compute,
                    "ttfc_seconds": ttfc,
                    "ttfcc_seconds": ttfc,
                    "output_chunks": 30,
                    "reasoning_chunks": 0,
                    "reasoning_tokens": 0,
                },
            )
            report[f"t{i}"] = build_report(task, result, vr, {}, "none")

        # Per-task nested values feed run-level aggregation
        prefill = [e["operational"]["throughput"]["prefill_cps"] for e in report.values()]
        generation = [e["operational"]["throughput"]["generation_cps"] for e in report.values()]
        total = [e["operational"]["throughput"]["total_cps"] for e in report.values()]
        assert all(v is not None for v in prefill + generation + total)
        # Task 0: 200 prefill; Task 1: 1200 prefill; Task 2: 500 prefill
        assert min(prefill) == 200.0 and max(prefill) == 1200.0
        # Generation: 30, 30/(1.5-0.25)=24, 10/3.9≈2.6
        assert max(generation) == 30.0
        assert all(g > 0 for g in generation)

    def test_run_level_server_aggregation(self):
        """Server-reported fields aggregate into operational.timing.server with
        _mean/_min/_max suffixes."""
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult, TaskVerificationResult
        from palace.task_types.qa import QATask

        vr = TaskVerificationResult(is_correct=True)
        checkpoints = [
            {"engine_ttft_ms": 500, "engine_tbt_ms": 20},
            {"engine_ttft_ms": 700, "engine_tbt_ms": 40},
            {"engine_ttft_ms": 900, "engine_tbt_ms": 30},
        ]
        entries = []
        for i, cp in enumerate(checkpoints):
            task = QATask.from_dict({"id": f"t{i}", "objective": "q", "expected": "a", "task_type": "QA"})
            result = AgentResult(
                answer="a",
                metrics={
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "compute_seconds": 2.0,
                    "ttfc_seconds": 0.5,
                    "output_chunks": 20,
                    "reasoning_chunks": 0,
                    "reasoning_tokens": 0,
                    "server_latency": cp,
                },
            )
            entries.append(build_report(task, result, vr, {}, "none"))

        # Simulate the orchestrator bucket fill (aggregation loop contract)
        ttft_vals = [e["operational"]["timing"]["server"]["engine_ttft_seconds"] for e in entries]
        tbt_vals = [e["operational"]["timing"]["server"]["engine_tbt_seconds"] for e in entries]
        assert ttft_vals == [0.5, 0.7, 0.9]
        assert tbt_vals == [0.02, 0.04, 0.03]
        # Aggregation semantics: mean/min/max over per-task seconds values
        assert round(sum(ttft_vals) / 3, 4) == 0.7
        # Authoritative tok/s from mean TBT: 1 / mean_tbt_seconds
        assert round(1 / (sum(tbt_vals) / 3), 1) == 33.3


class TestStatsSuffixes:
    """_stats_suffixes: mean/min/p50/p95/max with nearest-rank percentiles."""

    def test_basic_stats(self):
        from palace.evaluation.orchestrator import _stats_suffixes

        s = _stats_suffixes([1.0, 2.0, 3.0, 4.0, 5.0], 2)
        assert s["_mean"] == 3.0
        assert s["_min"] == 1.0
        assert s["_max"] == 5.0
        assert s["_p50"] == 3.0  # median of 5 sorted values
        assert s["_p95"] == 5.0  # ceil(0.95*5)=5 -> last value

    def test_p95_nearest_rank(self):
        from palace.evaluation.orchestrator import _stats_suffixes

        # 100 values 1..100: p95 = ceil(0.95*100) = 95th value
        s = _stats_suffixes([float(i) for i in range(1, 101)], 2)
        assert s["_p95"] == 95.0
        assert s["_p50"] == 50.0

    def test_p95_catches_tail_outlier(self):
        from palace.evaluation.orchestrator import _stats_suffixes

        # 4 fast tasks + 1 slow outlier: mean hides it, p95 catches it
        # n=5: p95 rank = ceil(0.95*5) = ceil(4.75) = 5 -> the outlier itself
        values = [0.5, 0.5, 0.5, 0.5, 8.0]
        s = _stats_suffixes(values, 2)
        assert s["_mean"] == 2.0
        assert s["_p95"] == 8.0
        assert s["_p50"] == 0.5  # rank ceil(2.5)=3 -> 0.5

    def test_p95_needs_enough_samples_to_see_outlier(self):
        """With 100 fast + 1 slow, nearest-rank p95 lands on a fast value —
        p95 is a tail estimator, not an outlier detector at small n."""
        from palace.evaluation.orchestrator import _stats_suffixes

        values = [0.5] * 100 + [8.0]
        s = _stats_suffixes(values, 2)
        assert s["_mean"] == 0.57  # (0.5*100 + 8) / 101
        assert s["_p95"] == 0.5  # rank 96 of 101 sorted -> still 0.5
        assert s["_max"] == 8.0  # max always catches the outlier

    def test_empty_values_all_none(self):
        from palace.evaluation.orchestrator import _stats_suffixes

        s = _stats_suffixes([], 2)
        assert s == {"_mean": None, "_min": None, "_p50": None, "_p95": None, "_max": None}

    def test_single_value(self):
        from palace.evaluation.orchestrator import _stats_suffixes

        s = _stats_suffixes([2.5], 2)
        assert s == {"_mean": 2.5, "_min": 2.5, "_p50": 2.5, "_p95": 2.5, "_max": 2.5}


class TestRunLevelAttempts:
    """Run-level attempts aggregation: total/max across tasks."""

    def _build_report(self, attempts_list):
        from palace.evaluation.pipeline import build_report
        from palace.evaluation.types import AgentResult
        from palace.task_types.base import TaskVerificationResult
        from palace.task_types.qa import QATask

        vr = TaskVerificationResult(is_correct=True)
        report = {}
        for i, attempts in enumerate(attempts_list):
            task = QATask.from_dict({"id": f"t{i}", "objective": "q", "expected": "a", "task_type": "QA"})
            metrics = {"compute_seconds": 1.0, "ttfc_seconds": 0.2, "output_chunks": 10, "reasoning_tokens": 0}
            if attempts is not None:
                metrics["attempts"] = attempts
            report[f"t{i}"] = build_report(task, AgentResult(answer="a", metrics=metrics), vr, {}, "none")
        return report

    def test_attempts_aggregated(self):
        # 3 tasks: 1, 4, 1 attempts -> total 6, max 4
        report = self._build_report([1, 4, 1])
        # Simulate the orchestrator collection (same contract as the real loop)
        attempt_values = [
            e["operational"]["attempts"] for e in report.values() if e["operational"].get("attempts") is not None
        ]
        assert sum(attempt_values) == 6
        assert max(attempt_values) == 4

    def test_attempts_absent_all_tasks(self):
        report = self._build_report([None, None])
        attempt_values = [
            e["operational"]["attempts"] for e in report.values() if e["operational"].get("attempts") is not None
        ]
        assert attempt_values == []  # orchestrator yields attempts: {"total": None, "max": None}
