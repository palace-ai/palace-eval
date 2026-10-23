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

"""Palace evaluation exceptions."""


class TimeoutException(Exception):
    """Raised when an operation times out."""

    pass


class ConvergenceError(Exception):
    """Raised when an iterative process fails to converge."""

    pass


class FatalEvaluationError(Exception):
    """Base class for errors that should abort the entire evaluation.

    Only errors knowable *before* any task dispatch belong here:
    configuration errors, authentication failures, unreachable endpoints.
    Failures encountered during a task are that task's failure and must
    never raise this — convert them to a per-task error result instead.

    These exceptions will propagate through the task dispatch layer
    instead of being caught and converted to per-task errors.
    """

    pass


class UntrustedSwapError(Exception):
    """The --untrusted-agent env swap failed for one task.

    Raised by VivariumAgent._swap_to_fresh_env when VERIFY_PATHS cannot be
    downloaded from the agent environment (path missing after the run, or
    transient infrastructure errors that exhausted retries). Deliberately
    NOT a FatalEvaluationError: the agent already ran, the failure is this
    task's outcome, and the evaluation must continue with the remaining
    tasks. The caller converts it to AgentResult(outcome="error").
    """

    pass


class ModelNotFoundError(FatalEvaluationError):
    """Raised when the requested model doesn't exist on the API endpoint."""

    pass


class JudgeConfigurationError(FatalEvaluationError):
    """Raised when judge model is required but not configured."""

    pass


class AuthenticationError(FatalEvaluationError):
    """Raised when API authentication fails."""

    pass
