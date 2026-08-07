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

    Subclass this for configuration errors, authentication failures,
    or other issues that affect all tasks and shouldn't be retried.

    These exceptions will propagate through the task dispatch layer
    instead of being caught and converted to per-task errors.
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
