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

"""Vivarium agent — delegates execution to vivarium service."""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import inspect
import io
import json
import logging
import os
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from palace.agents.base_agent import Agent
from palace.evaluation.types import AgentResult
from palace.utils.exceptions import UntrustedSwapError
from palace.utils.infra_errors import TRANSIENT_NETWORK_ERRORS as _TRANSIENT_NETWORK_ERRORS
from palace.utils.infra_errors import is_infra_error as _is_transient_http
from palace.utils.infra_errors import retry_transient as _retry_transient
from palace.utils.paths import LOGS_PATH
from palace.utils.printing import print

if TYPE_CHECKING:
    from palace.evaluation.types import Attachment
    from palace.task_types.base import ExecutionEnvironment, Task

_logger = logging.getLogger("palace.vivarium_agent")

# Default paths to save in untrusted-agent mode if VERIFY_PATHS not declared.
_DEFAULT_VERIFY_PATHS = ["/workspace"]

# Download attempts per VERIFY_PATH during the untrusted-agent swap (excluding
# the one immediate 404 retry). With exponential backoff 2→60s this bounds a
# pathological outage at ~5 minutes per path — enough to ride out a worker
# restart, short of stalling the job.
_SWAP_DOWNLOAD_ATTEMPTS = 5

# Swap download attempts per VERIFY_PATH (excluding the one immediate 404
# retry). With exponential backoff 2→60s this bounds a pathological outage
# at ~5 minutes per path — enough to ride out a worker restart, short of
# stalling the job.
_SWAP_DOWNLOAD_ATTEMPTS = 5


class VivariumAgent(Agent):
    """Agent that delegates execution to vivarium's sandboxed Docker environments.

    Args:
        name: Model name (passed to vivarium as model_name for LLM calls).
        url: LLM API base URL.
        token: LLM API key.
        vivarium_url: Vivarium service URL. If None, auto-starts via vivarium SDK.
        timeout_seconds: Max time per agent run (default 3 hours). Must stay
            below the dispatch-level task_timeout (12600s) so this graceful
            timeout — which preserves token/step metrics — fires first.
        max_steps: Max agent loop iterations per task (default 1000).
        extra_params: Extra kwargs merged into LLM API calls (e.g., reasoning_effort).
        harness: Agent harness to use ("builtin", "pi", "omp"). Default: "omp".
        keep_last_env: Keep the last environment alive for debugging (default: False).
        untrusted_agent: Enable hardened mode — destroy agent env and recreate fresh
            before verification. Defeats sandbox-level attacks. (default: False)
            A failed env swap (VERIFY_PATHS not downloadable) is a per-task
            error outcome, not a job abort.
    """

    agentic: bool = True

    def __init__(
        self,
        name: str,
        url: str,
        token: str | None,
        vivarium_url: str | None = None,
        timeout_seconds: int = 10800,
        max_steps: int = 1000,
        extra_params: dict | None = None,
        harness: str | None = None,
        keep_last_env: bool = False,
        untrusted_agent: bool = False,
    ):
        self._name = name
        self._url = url
        self._token = token
        self._timeout = timeout_seconds
        self._max_steps = max_steps
        self._extra_params = extra_params
        self._harness = harness or "omp"
        self._keep_last_env = keep_last_env
        self._untrusted_agent = untrusted_agent
        self._last_kept_env: Any = None  # env kept for debugging
        self._trace_dir: Path | None = None  # directory for trace logs
        self._trace_file: Any = None  # current trace file handle
        self._vivarium_url = vivarium_url or os.getenv("VIVARIUM_URL") or None
        self._spec_ids: dict[str, str] = {}  # env_name → vivarium spec_id
        self._env_configs: dict[str, dict] = {}  # env_name → spec config (lazy)
        self._seed_fns: dict[str, object] = {}  # env_path → seed function
        self._archives: dict[str, bytes | None] = {}  # env_path → tar.gz bytes
        self._task_files_dirs: list[Path] = []  # resolved task_files directories
        self._envs: dict[str, Any] = {}  # task_id → Environment (fresh env in untrusted mode)
        self._verify_paths: dict[str, list[str]] = {}  # env_path_str → paths to save
        self._task_env_names: dict[str, str] = {}  # task_id → env_name (for untrusted mode)
        self._tasks: dict[str, Task] = {}  # task_id → Task (for untrusted mode re-seeding)
        self._client: Any = None
        self._auto_started = False
        self._tasklist_path: Path | None = None

        try:
            from vivarium import Client
        except ImportError:
            raise RuntimeError(
                "Agentic evaluation requires vivarium. "
                "Install with: pip install vivarium-ai\n"
                "See https://github.com/vivarium-ai/vivarium for details."
            )

        auto_start = self._vivarium_url is None
        self._client = Client(url=self._vivarium_url, auto_start=auto_start)
        self._auto_started = auto_start

    def _log_trace_entry(self, task_id: str, entry: dict) -> None:
        """Write a trace entry to the task's trace log file."""
        if self._trace_dir is None:
            return
        # Lazily open trace file for this task
        if self._trace_file is None:
            safe_id = task_id.replace("/", "_")[:100]
            trace_path = self._trace_dir / f"{safe_id}_trace.jsonl"
            self._trace_file = open(trace_path, "w", encoding="utf-8")
        self._trace_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._trace_file.flush()

    def _close_trace_file(self) -> None:
        """Close the current trace file if open."""
        if self._trace_file:
            self._trace_file.close()
            self._trace_file = None

    @property
    def name(self) -> str:
        return self._name

    async def on_tasklist_start(self, tasklist_path: Path, info: dict) -> None:
        """Store environment configs. Specs registered lazily on first use."""
        started = " (auto-started)" if self._auto_started else ""
        harness_name = self._harness or "default"
        print(f"[blue]:whale: Agentic mode — Vivarium @ {self._client._url} (harness: {harness_name}){started}[/]")

        # Fail fast if vivarium is unreachable
        try:
            await self._client.health()
        except Exception as e:
            raise RuntimeError(
                f"Cannot reach Vivarium at {self._client._url}\n"
                f"  {e}\n"
                f"  Check the URL with: palace config set vivarium_url <url>"
            ) from e

        self._tasklist_path = tasklist_path

        # Set up trace directory for this run
        self._trace_dir = LOGS_PATH / "traces"
        self._trace_dir.mkdir(parents=True, exist_ok=True)

        # Resolve task_files search directories
        task_files_path = info.get("task_files_path", "task_files")
        self._task_files_dirs = sorted(d for d in tasklist_path.glob(task_files_path) if d.is_dir())

        # Discover environments via spec.json
        discovered_envs = _discover_environments(tasklist_path)

        if discovered_envs:
            # spec.json files found
            self._env_configs = {}
            self._env_paths: dict[str, Path] = {}  # env_name → directory path
            for env_name, env_path in discovered_envs.items():
                spec_file = env_path / "spec.json"
                try:
                    spec_json = json.loads(spec_file.read_text())
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in {spec_file}: {e}") from e
                except OSError as e:
                    raise ValueError(f"Cannot read {spec_file}: {e}") from e
                self._env_configs[env_name] = spec_json
                self._env_paths[env_name] = env_path
            _logger.info(f"Discovered {len(discovered_envs)} environment(s) via spec.json")
        else:
            # No environment defined — use vivarium's built-in default spec.
            # Vivarium registers "default" at startup; if missing, the 404 at
            # create_environment time is a clear enough error.
            self._env_configs = {"default": {}}
            self._env_paths = {"default": tasklist_path / "environment"}
            self._spec_ids["default"] = "default"

        # Pre-load seed functions and archives per unique environment path
        # For multi-env, seed.py may be in environment/ root (shared) or per-env subdir
        self._seed_fns: dict[str, object] = {}
        self._archives: dict[str, bytes | None] = {}
        self._verify_paths: dict[str, list[str]] = {}
        shared_seed_path = tasklist_path / "environment" / "seed.py"
        shared_seed_fn = _load_fn(shared_seed_path, "seed") if shared_seed_path.exists() else None
        shared_verify_paths = _load_verify_paths(tasklist_path / "environment" / "verify.py")

        for env_name, env_path in self._env_paths.items():
            env_path_str = str(env_path.relative_to(tasklist_path))
            if env_path_str not in self._archives:
                if env_path.is_dir():
                    # Check per-env seed.py first, fall back to shared
                    per_env_seed = env_path / "seed.py"
                    if per_env_seed.exists():
                        self._seed_fns[env_path_str] = _load_fn(per_env_seed, "seed")
                    elif shared_seed_fn:
                        self._seed_fns[env_path_str] = shared_seed_fn
                    self._archives[env_path_str] = _tar_gz(env_path)
                    # Load VERIFY_PATHS from per-env verify.py or fall back to shared
                    per_env_verify = env_path / "verify.py"
                    if per_env_verify.exists():
                        self._verify_paths[env_path_str] = _load_verify_paths(per_env_verify)
                    else:
                        self._verify_paths[env_path_str] = shared_verify_paths
                else:
                    self._archives[env_path_str] = None
                    self._verify_paths[env_path_str] = _DEFAULT_VERIFY_PATHS

        _logger.info(f"Loaded {len(self._env_configs)} environment config(s) (lazy registration)")

    async def on_task_start(self, task: Task) -> ExecutionEnvironment | None:
        """Create a sandboxed environment and run seed if present. Returns Environment."""
        # Resolve which spec to use for this task
        env_name = task.custom_fields.get("env")
        if env_name is None:
            if len(self._env_configs) == 1:
                env_name = next(iter(self._env_configs))
            else:
                raise ValueError(
                    f"Task '{task.id}' has no 'env' field but tasklist defines "
                    f"{len(self._env_configs)} environments: {list(self._env_configs.keys())}"
                )
        if env_name not in self._env_configs:
            raise ValueError(
                f"Task '{task.id}' references env '{env_name}' but available environments are: "
                f"{list(self._env_configs.keys())}"
            )

        # Lazy spec registration: register on first use
        if env_name not in self._spec_ids:
            spec_json = self._env_configs[env_name]
            env_path = self._env_paths[env_name]
            env_path_str = str(env_path.relative_to(self._tasklist_path))
            image = spec_json.get("image")
            _logger.info(f"Registering spec '{env_name}' (first use, image: {image})")

            # Retry on transient errors (503 disk pressure, 429, 5xx, connection issues)
            while True:
                try:
                    spec_id = await self._client.register_spec(spec_json, self._archives.get(env_path_str))
                    break
                except (httpx.HTTPStatusError, *_TRANSIENT_NETWORK_ERRORS) as e:
                    if _is_transient_http(e):
                        _logger.warning(f"Transient error registering spec, retrying in 30s: {e}")
                        await asyncio.sleep(30)
                    else:
                        raise
            self._spec_ids[env_name] = spec_id
            _logger.info(f"Spec '{env_name}' registered (image ready)")

        spec_id = self._spec_ids[env_name]
        task_files = self._package_task_files(task)

        # Retry on transient errors (429, 5xx, connection issues) until task timeout
        while True:
            try:
                env = await self._client.create_environment(
                    spec_id=spec_id,
                )
                break
            except (
                httpx.HTTPStatusError,
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.ReadError,
                httpx.RemoteProtocolError,
            ) as e:
                if _is_transient_http(e):
                    _logger.debug(f"Transient error creating environment, retrying: {e}")
                    await asyncio.sleep(5)
                else:
                    raise

        # Upload per-task files if any exist, to /task_files/ in the container.
        # Transient retry: idempotent (fixed dest, files overwritten), and a
        # failure here must not discard the just-created environment.
        if task_files:
            try:
                await _retry_transient(
                    lambda: env.upload_files(task_files, dest="/task_files/"),
                    what=f"task_files upload for {task.id}",
                )
            except Exception as e:
                await env.destroy()
                raise RuntimeError(f"Failed to upload task files for {task.id}: {e}") from e

        self._envs[task.id] = env
        self._task_env_names[task.id] = env_name  # Track for untrusted-agent mode
        self._tasks[task.id] = task  # Track for untrusted-agent mode re-seeding

        env_path = self._env_paths[env_name]
        env_path_str = str(env_path.relative_to(self._tasklist_path))
        seed_fn = self._seed_fns.get(env_path_str)
        if seed_fn:
            _logger.info(f"Seeding environment for {task.id}")
            seed_args = task.custom_fields.get("seed_args")

            async def _seed_once():
                result = seed_fn(seed_args, env)
                if inspect.isawaitable(result):
                    await result

            # Transient retry: seed resets the repo to the base commit first,
            # so re-running it after a mid-seed transient failure converges to
            # the same baseline state.
            await _retry_transient(_seed_once, what=f"seed for {task.id}")
            _logger.info(f"Seed complete for {task.id}")

        return env  # satisfies ExecutionEnvironment protocol (exec/read/write)

    async def run(
        self, prompt: str, attachments: "list[Attachment] | None" = None, *, task_id: str | None = None
    ) -> AgentResult:
        """Submit agent run and poll until completion."""
        assert task_id is not None, "VivariumAgent.run() requires task_id"
        env = self._envs[task_id]

        # Agentic presentation: write to disk, encode embeddable for API, add note
        encoded_attachments = None
        if attachments:
            prompt, encoded_attachments = await self._prepare_attachments(env, prompt, attachments)

        # Submit run with retry on transient errors
        for attempt in range(10):
            try:
                run = await self._client.run(
                    env,
                    objective=prompt,
                    model_url=self._url,
                    model_key=self._token or "",
                    model_name=self._name,
                    timeout_seconds=self._timeout,
                    max_steps=self._max_steps,
                    model_extra_params=self._extra_params,
                    harness=self._harness,
                )
                break
            except (
                httpx.HTTPStatusError,
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.ReadError,
                httpx.RemoteProtocolError,
            ) as e:
                if _is_transient_http(e) and attempt < 9:
                    _logger.warning(f"Transient error submitting run (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    raise

        # Poll with resilient error handling
        deadline = asyncio.get_event_loop().time() + self._timeout + 30
        prev_tc = 0
        data = None
        consecutive_failures = 0
        while asyncio.get_event_loop().time() < deadline:
            try:
                data = await self._client.get_run(run.id)
                consecutive_failures = 0
            except (
                httpx.HTTPStatusError,
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.ReadError,
                httpx.RemoteProtocolError,
            ) as e:
                # A 404 on an existing run is treated as transient: the
                # orchestrator's worker broadcast collapses any worker-side
                # hiccup (connect error, timeout, non-200) into a 404 when
                # only one worker is registered, so 404 cannot reliably
                # mean "run never existed" for a run we just submitted.
                # Bounded by consecutive_failures below, same as other
                # transient errors.
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                    is_transient = True
                else:
                    is_transient = _is_transient_http(e)
                if is_transient:
                    consecutive_failures += 1
                    if consecutive_failures > 15:  # ~30 seconds of failures
                        _logger.error(f"Vivarium unreachable for {consecutive_failures} consecutive polls, aborting")
                        return AgentResult(outcome="error", reason="vivarium_unreachable")
                    _logger.debug(f"Transient poll error ({consecutive_failures}): {e}")
                    await asyncio.sleep(2)
                    continue
                raise
            if data.status != "running":
                break
            for entry in data.trace[prev_tc:]:
                if self.verbose:
                    print(f"  {_format_trace_line(entry)}")
                self._log_trace_entry(task_id, entry)
            prev_tc = len(data.trace)
            await asyncio.sleep(1)
        else:
            return AgentResult(outcome="error", reason="timeout")

        # Print and log remaining trace
        for entry in data.trace[prev_tc:]:
            if self.verbose:
                print(f"  {_format_trace_line(entry)}")
            self._log_trace_entry(task_id, entry)

        if data and data.status == "completed":
            metrics = {
                "steps": data.metrics.steps_completed,
                "tool_calls": data.metrics.tool_calls_completed,
                "input_tokens": data.metrics.input_tokens,
                "output_tokens": data.metrics.output_tokens,
                "compute_seconds": data.metrics.elapsed_seconds,  # vivarium wall time ≈ compute time
            }
            agent_result = AgentResult(answer=data.answer, metrics=metrics, debug_logs=data.harness_stderr)
        else:
            error = data.error if data else "unknown"
            if self.verbose:
                print(f"  [red]⚠ Run failed: {error}[/]")
            agent_result = AgentResult(
                outcome="error", reason="agent_error", debug_logs=data.harness_stderr if data else None
            )

        # Untrusted mode: swap to fresh env before returning so verify runs clean.
        # Gated on outcome, not on the answer — verification runs for every
        # completed run (even without final text), so the swap must too, or an
        # answerless agent could grade itself against its own tampered env.
        # A failed swap is this task's error outcome, never a job abort.
        if self._untrusted_agent and agent_result.outcome == "success":
            try:
                await self._swap_to_fresh_env(task_id)
            except UntrustedSwapError as e:
                _logger.error(f"untrusted-agent: swap failed for {task_id}: {e}")
                return AgentResult(
                    outcome="error",
                    reason=f"untrusted_swap_failed: {e}",
                    # Preserve run evidence for post-mortem (never verified —
                    # outcome is error): metrics for cost accounting, answer
                    # and harness stderr as diagnostics, elapsed for wall time.
                    answer=agent_result.answer,
                    metrics=agent_result.metrics,
                    elapsed=agent_result.elapsed,
                    debug_logs=agent_result.debug_logs,
                )

        return agent_result

    async def _swap_to_fresh_env(self, task_id: str) -> None:
        """Download verify paths, destroy agent env, create fresh env, re-upload.

        Called after agent run in --untrusted-agent mode. After this method returns,
        self._envs[task_id] holds the fresh environment that verification will use.
        The original environment has been destroyed.

        Security model: only paths listed in VERIFY_PATHS (agent deliverables) are
        carried over from the agent environment. Harness infrastructure (task_files,
        tests, seeding) is re-provisioned from the local tasklist — trusted sources —
        so a compromised agent cannot tamper with the verifier itself (e.g. rewrite
        parser.py to always report PASSED).

        Raises UntrustedSwapError when no deliverable path could be saved:
        proceeding to verify in a pristine env would grade the harness, not
        the agent. This is a task-level failure — run() converts it to
        AgentResult(outcome="error") and the evaluation continues.
        """
        env = self._envs.get(task_id)
        if not env:
            _logger.warning(f"untrusted-agent: no env found for {task_id}, skipping swap")
            return

        # Look up which env this task used (stored in on_task_start)
        env_name = self._task_env_names.get(task_id)
        if not env_name or env_name not in self._spec_ids:
            _logger.warning(f"untrusted-agent: cannot determine env for {task_id}, skipping swap")
            return
        spec_id = self._spec_ids[env_name]

        # Get verify_paths for this env
        env_path = self._env_paths.get(env_name)
        if env_path and self._tasklist_path:
            env_path_str = str(env_path.relative_to(self._tasklist_path))
            verify_paths = self._verify_paths.get(env_path_str, _DEFAULT_VERIFY_PATHS)
        else:
            verify_paths = _DEFAULT_VERIFY_PATHS

        # Download each path from the agent env.
        # Classification (task-level either way — the job continues):
        #   - 404 → one immediate retry (rules out a destroy/race transient),
        #     then give up: the agent deleted its own deliverable
        #   - transient (5xx, connect/timeout — is_infra_error) → retried
        #     with exponential backoff, then give up: infra failure
        #   - anything else → treated as transient (conservative: infra until
        #     proven otherwise)
        saved: dict[str, bytes] = {}
        download_errors: list[str] = []
        for path in verify_paths:
            archive: bytes | None = None
            backoff = 2.0
            attempt = 0
            immediate_retries_left = 1  # extra immediate attempt for 404
            while attempt < _SWAP_DOWNLOAD_ATTEMPTS:
                attempt += 1
                try:
                    archive = await env.download_files(path)
                    break
                except Exception as e:
                    # str(e) can be empty (e.g. httpx error with no detail) —
                    # include the exception type so the log is never blank.
                    detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                    is_404 = isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404
                    if is_404:
                        if immediate_retries_left > 0:
                            immediate_retries_left -= 1
                            attempt -= 1  # immediate retry does not consume budget
                            _logger.warning(
                                f"untrusted-agent: download {path} from {task_id} returned 404, "
                                f"retrying once (possible destroy/race transient)"
                            )
                            continue
                        # 404 after the immediate retry is final — the path is
                        # genuinely gone (agent deleted its own deliverable).
                        download_errors.append(f"{path}: {detail}")
                        _logger.warning(f"untrusted-agent: could not download {path} from {task_id}: {detail}")
                        break
                    if attempt >= _SWAP_DOWNLOAD_ATTEMPTS:
                        download_errors.append(f"{path}: {detail}")
                        _logger.warning(f"untrusted-agent: could not download {path} from {task_id}: {detail}")
                        break
                    _logger.warning(
                        f"untrusted-agent: download {path} from {task_id} failed ({detail}), "
                        f"retrying in {backoff:.0f}s (attempt {attempt}/{_SWAP_DOWNLOAD_ATTEMPTS})"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)

            if archive is not None:
                saved[path] = archive
                _logger.debug(f"untrusted-agent: downloaded {path} from {task_id}")

        if not saved:
            raise UntrustedSwapError(
                f"none of the VERIFY_PATHS could be downloaded from the agent "
                f"environment for {task_id}. VERIFY_PATHS={verify_paths} do not exist in this "
                f"tasklist's containers. Errors: {'; '.join(download_errors)}. "
                f"Fix: declare the actual agent deliverable paths in VERIFY_PATHS in the "
                f"tasklist's environment/verify.py."
            )

        # Destroy original env — triggers webhook → provisioner kills worker
        try:
            await env.destroy()
        except Exception as e:
            _logger.warning(f"untrusted-agent: error destroying agent env {task_id}: {e}")

        # Create fresh environment (will be on a different worker).
        # Transient retry: under disk pressure the env creation can require an
        # image re-pull; a transient failure here escapes the swap unwrapped
        # (this call predates the UntrustedSwapError wrap below) and would
        # surface as a raw task error.
        fresh_env = await _retry_transient(
            lambda: self._client.create_environment(spec_id=spec_id),
            what=f"fresh env creation for {task_id}",
        )
        _logger.info(f"untrusted-agent: created fresh env {fresh_env.id} for {task_id}")

        # Re-provision trusted harness artifacts from local tasklist sources:
        # seed (baseline repo state, test patch, env setup) and task_files
        # (verify scripts). Never copied from the agent env — those are
        # untrusted by definition.
        # Order matters: seed FIRST (it resets the repo to the base commit,
        # which would wipe uploaded deliverables), THEN overlay agent work.
        task = self._tasks.get(task_id)
        seed_fn = self._seed_fns.get(env_path_str) if env_path and self._tasklist_path else None
        try:
            if task and seed_fn:
                _logger.info(f"untrusted-agent: re-seeding fresh env for {task_id}")
                seed_args = task.custom_fields.get("seed_args")

                async def _seed_once():
                    result = seed_fn(seed_args, fresh_env)
                    if inspect.isawaitable(result):
                        await result

                # Transient retry: seed starts by resetting the repo to the
                # base commit, so re-running it after a mid-seed transient
                # failure is safe (it converges to the same baseline state).
                await _retry_transient(_seed_once, what=f"re-seeding of fresh env for {task_id}")
            if task:
                task_files = self._package_task_files(task)
                if task_files:
                    try:
                        await _retry_transient(
                            lambda: fresh_env.upload_files(task_files, dest="/task_files/"),
                            what=f"task_files upload to fresh env for {task_id}",
                        )
                    except Exception as e:
                        raise UntrustedSwapError(f"could not upload task_files to fresh env for {task_id}: {e}") from e

            # Re-upload saved paths (agent deliverables) on top of the seeded baseline
            for path, archive in saved.items():
                try:
                    # download_files() returns a tar whose members are anchored at
                    # the basename of `path` (Docker get_archive semantics: a
                    # directory download yields '<basename>/...'). Extract
                    # relative to the PARENT directory so the tree lands back at
                    # its original location; using dest=path would double-nest
                    # (e.g. /workspace/findings/findings/findings.json).
                    dest = path.rstrip("/").rsplit("/", 1)[0] or "/"
                    await _retry_transient(
                        lambda: fresh_env.upload_files(archive, dest=dest),
                        what=f"re-upload of {path} to fresh env for {task_id}",
                    )
                    _logger.debug(f"untrusted-agent: uploaded {path} to fresh env (dest={dest})")
                except Exception as e:
                    raise UntrustedSwapError(f"could not re-upload {path} to fresh env for {task_id}: {e}") from e
        except BaseException:
            # Failure after fresh env creation: the original env is destroyed
            # but fresh_env was never registered in _envs — destroy it here or
            # it leaks (and its disk reclaim with it).
            try:
                await fresh_env.destroy()
            except Exception as cleanup_err:
                _logger.warning(
                    f"untrusted-agent: leaked fresh env {fresh_env.id} for {task_id} (destroy failed: {cleanup_err})"
                )
            raise

        # Replace env in _envs — verification and on_task_end will use this
        self._envs[task_id] = fresh_env

    def get_verify_env(self, task: Task) -> ExecutionEnvironment | None:
        """Return the environment to use for verification.

        In --untrusted-agent mode, returns the fresh env (now in _envs after swap).
        In normal mode, returns None (pipeline uses the original env from on_task_start).
        """
        if not self._untrusted_agent:
            return None
        return self._envs.get(task.id)

    async def on_task_end(self, task: Task) -> None:
        """Destroy the environment container (or keep for debugging)."""
        self._close_trace_file()  # Close trace file for this task
        self._task_env_names.pop(task.id, None)  # Clean up tracking

        env = self._envs.pop(task.id, None)
        self._tasks.pop(task.id, None)
        if env:
            if self._keep_last_env:
                # Destroy previous kept env, keep this one
                if self._last_kept_env:
                    await _retry_transient(
                        self._last_kept_env.destroy,
                        what=f"destroy of kept env for {task.id}",
                    )
                self._last_kept_env = env
                print(f"[yellow]🔍 Kept env for debugging: {env.id}[/]")
            else:
                # Transient retry: a teardown destroy that fails on a network
                # hiccup must not overwrite the task's real result (dispatch
                # records exceptions escaping execute_task as task_error).
                # Idempotent server-side (404 on missing env is tolerated),
                # so retrying is safe.
                await _retry_transient(
                    env.destroy,
                    what=f"destroy of env for {task.id}",
                )

    async def on_tasklist_end(self) -> None:
        """Cleanup specs and stop vivarium if auto-started."""
        # If keep_last_env, leave it alive for debugging (don't destroy)
        if self._last_kept_env:
            print(f"[yellow]🔍 Environment kept for debugging: {self._last_kept_env.id}[/]")
            self._last_kept_env = None  # Clear reference but don't destroy
        for spec_id in self._spec_ids.values():
            if spec_id == "default":
                continue  # don't delete vivarium's built-in default spec
            try:
                await self._client.delete_spec(spec_id)
            except Exception as e:
                # Best-effort cleanup: a 409 (spec still used by a leaked env)
                # or other error here must never mask the real tasklist failure
                # that brought us into this path.
                _logger.warning(f"untrusted-agent: could not delete spec {spec_id}: {type(e).__name__}: {e}")
        self._spec_ids = {}
        if self._auto_started:
            from vivarium import stop

            stop()
            self._auto_started = False
        await self._client.aclose()

    async def _prepare_attachments(
        self, env, prompt: str, attachments: "list[Attachment]"
    ) -> "tuple[str, list[dict] | None]":
        """Write all attachments to container, return (updated_prompt, encoded_for_api).

        - All files are written to /workspace/attachments/ for tool access.
        - Only image/audio are encoded for model-context embedding via vivarium API.
        - A note listing all files is appended to the prompt.
        """
        await env.exec("mkdir -p /workspace/attachments")
        filenames: list[str] = []
        encoded: list[dict] = []
        for att in attachments:
            raw = att.read_bytes()
            await env.write(f"/workspace/attachments/{att.filename}", raw)
            filenames.append(att.filename)
            if att.mime_type.startswith(("image/", "audio/")):
                encoded.append(
                    {
                        "filename": att.filename,
                        "mime_type": att.mime_type,
                        "data": base64.b64encode(raw).decode("utf-8"),
                    }
                )
        note = "\n\n[Attached files: " + ", ".join(f"attachments/{f}" for f in filenames) + "]"
        return prompt + note, encoded or None

    def _package_task_files(self, task: Task) -> bytes | None:
        """Package task_files for upload, if any exist for this task."""
        for d in self._task_files_dirs:
            target = d / task.id
            if target.is_dir() and any(target.iterdir()):
                # Task files should include ALL files (no excludes)
                return _tar_gz(target, exclude_files=frozenset(), exclude_dirs=frozenset())
        return None


# Files/directories to exclude from spec archive sent to vivarium.
# These are palace-eval evaluation concerns (verification, seeding) that run locally,
# not runtime concerns that vivarium needs.
# Update this set if evaluation file conventions change.
_SPEC_ARCHIVE_EXCLUDE_FILES = frozenset({"verify.py", "seed.py"})  # Exact filename match
_SPEC_ARCHIVE_EXCLUDE_DIRS = frozenset({"verify_files"})  # Top-level directory match


def _discover_environments(tasklist_path: Path) -> dict[str, Path]:
    """Discover environment directories containing spec.json.

    Returns dict mapping env_name → env_directory_path.

    Single-env: environment/spec.json exists → {"default": environment/}
    Multi-env: environment/*/spec.json exists → {subdir_name: subdir_path, ...}

    Raises ValueError if both patterns exist (ambiguous structure).
    Returns empty dict if no spec.json found (legacy or default spec).
    """
    env_dir = tasklist_path / "environment"
    if not env_dir.is_dir():
        return {}

    # Check for multi-env: subdirectories with spec.json
    multi_envs = {d.name: d for d in env_dir.iterdir() if d.is_dir() and (d / "spec.json").exists()}

    # Check for single-env: spec.json directly in environment/
    single_env = (env_dir / "spec.json").exists()

    if multi_envs and single_env:
        raise ValueError(
            "Ambiguous environment structure: found both environment/spec.json "
            "and environment/*/spec.json. Use one or the other."
        )

    if multi_envs:
        return multi_envs
    elif single_env:
        return {"default": env_dir}
    else:
        return {}


def _should_exclude(relative_path: Path, exclude_files: frozenset[str], exclude_dirs: frozenset[str]) -> bool:
    """Check if a file should be excluded from archive.

    Args:
        relative_path: Path relative to archive root.
        exclude_files: Filenames to exclude (exact match on filename only).
        exclude_dirs: Directory names to exclude (match at any level in path).
    """
    # Exclude exact filename matches (e.g., "verify.py" at any level)
    if relative_path.name in exclude_files:
        return True
    # Exclude files inside excluded directories (e.g., anything under "verify_files/")
    if exclude_dirs and any(part in exclude_dirs for part in relative_path.parts[:-1]):
        return True
    return False


def _tar_gz(
    directory: Path,
    exclude_files: frozenset[str] = _SPEC_ARCHIVE_EXCLUDE_FILES,
    exclude_dirs: frozenset[str] = _SPEC_ARCHIVE_EXCLUDE_DIRS,
) -> bytes:
    """Create a tar.gz archive of a directory's contents.

    Args:
        directory: Directory to archive.
        exclude_files: Filenames to exclude (exact match). Default excludes verify.py, seed.py.
        exclude_dirs: Directory names to exclude (files inside are excluded). Default excludes verify_files/.

    Excludes verification files by default which are palace-eval concerns, not needed by vivarium.
    Pass empty frozensets to include all files.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in directory.rglob("*"):
            if f.is_file():
                relative_path = f.relative_to(directory)
                if _should_exclude(relative_path, exclude_files, exclude_dirs):
                    continue
                tar.add(f, arcname=str(relative_path))
    return buf.getvalue()


def _format_trace_line(entry: dict) -> str:
    """Format a trace entry (thinking or tool) as a clean one-liner."""
    entry_type = entry.get("type", "tool")

    # Handle thinking entries
    if entry_type == "thinking":
        content = entry.get("content", "")
        t = content.replace("\n", " ").strip()
        if len(t) > 300:
            t = t[:300] + "…"
        # Format token count as (15k) or (900)
        input_tokens = entry.get("input_tokens")
        if input_tokens:
            if input_tokens >= 1000:
                token_str = f"{input_tokens // 1000}k"
            else:
                token_str = str(input_tokens)
            return f"[yellow]({token_str})[/yellow] [italic]💭 {t}[/]"
        return f"[italic]💭 {t}[/]"

    # Handle tool entries
    tool = entry.get("tool", "unknown")
    args = entry.get("args", {})
    result = entry.get("result", "")
    # Format args
    parts = []
    for k, v in args.items():
        val = v if isinstance(v, str) else str(v)
        if len(val) > 100:
            val = val[:100] + "…"
        parts.append(f"[dim]{k}=[/][blue]{val}[/]")
    formatted_args = " ".join(parts)
    # Format result
    res = str(result).replace("\n", " ").strip()
    if len(res) > 300:
        res = res[:300] + "…"
    return f"[bold]{tool}[/] {formatted_args}\n    [dim]→ {res}[/]"


def _load_fn(path: Path, fn_name: str):
    """Load a function from a Python file."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, fn_name)


def _load_verify_paths(verify_path: Path) -> list[str]:
    """Load VERIFY_PATHS from verify.py, or return default ["/workspace"]."""
    if not verify_path.exists():
        return _DEFAULT_VERIFY_PATHS
    spec = importlib.util.spec_from_file_location("_verify", verify_path)
    if spec is None or spec.loader is None:
        return _DEFAULT_VERIFY_PATHS
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "VERIFY_PATHS", _DEFAULT_VERIFY_PATHS)
