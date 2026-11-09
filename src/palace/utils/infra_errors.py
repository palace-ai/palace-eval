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

"""Classification of infrastructure failures during evaluation.

Distinguishes "the model failed the task" from "the evaluation
infrastructure failed the task". The latter must be recorded as
``outcome="error"`` (excluded from scores), never as ``incorrect``.

Shared by the agentic task type (verification stage) and the vivarium
agent (agent/seed stages), so all stages classify identically.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

_logger = logging.getLogger("palace.infra_errors")

T = TypeVar("T")

# Transient HTTP status codes that are safe to retry: rate limiting,
# capacity/disk pressure, and gateway/worker timeouts. Any of these
# surfacing during verification means the *harness* failed, not the model.
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504, 529})

# Network-level exceptions that indicate transient connectivity issues.
TRANSIENT_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)

# Retry budget for transient infrastructure failures in lifecycle stages
# (seed, uploads, swap, verification injection, teardown). Fixed short
# sleeps ride out worker hiccups without meaningfully delaying the job.
TRANSIENT_RETRIES = 4
TRANSIENT_RETRY_SLEEP = 5.0


async def retry_transient(coro_factory: Callable[[], Awaitable[T]], *, what: str) -> T:
    """Await an async call, retrying transient infrastructure failures.

    coro_factory must be a zero-arg callable returning a fresh coroutine
    (httpx coroutines cannot be re-awaited after a failure).

    Raises the last exception when the retry budget is exhausted, so callers
    keep their existing error semantics — the retries only absorb the
    transient window.
    """
    for attempt in range(TRANSIENT_RETRIES + 1):
        try:
            return await coro_factory()
        except (httpx.HTTPStatusError, *TRANSIENT_NETWORK_ERRORS) as exc:
            if not is_infra_error(exc) or attempt == TRANSIENT_RETRIES:
                raise
            _logger.warning(f"Transient error during {what} (attempt {attempt + 1}/{TRANSIENT_RETRIES + 1}): {exc}")
            await asyncio.sleep(TRANSIENT_RETRY_SLEEP)


# Body substrings identifying disk-pressure rejections (e.g. vivarium returns
# 422 with "Disk pressure critical: ..."). A 422 whose body matches these
# is a transient capacity problem, not a malformed request.
_DISK_PRESSURE_PATTERNS = ("disk", "enospc", "no space left")


def is_infra_error(exc: BaseException) -> bool:
    """Return True if the exception represents an infrastructure failure.

    Infrastructure failures are: transient HTTP status errors (5xx, 429,
    disk-pressure 422), network-level exceptions (connect/timeout/read),
    and the asyncio timeout raised when a whole task exceeds its budget.
    Anything else is treated as a genuine task failure.
    """
    import asyncio

    if isinstance(exc, TRANSIENT_NETWORK_ERRORS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code in TRANSIENT_STATUS_CODES:
            return True
        if exc.response.status_code == 422:
            # Disk-pressure rejections ride a 422 in some vivarium versions;
            # the body names the cause. Body may be unreadable (streaming/
            # partial) — treating as infra is then safer than misclassifying.
            try:
                body = (exc.response.text or "").lower()
            except Exception:
                return True
            return any(p in body for p in _DISK_PRESSURE_PATTERNS)
        return False
    if isinstance(exc, asyncio.TimeoutError):
        # Task-level wait_for budget expired — the harness could not finish
        # the task in time (often caused by infra slowness upstream).
        return True
    return False
