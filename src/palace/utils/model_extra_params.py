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

"""Model extra params — per-model configurable API call parameters.

Allows users to define extra kwargs merged into provider API calls via YAML
config or programmatic API, so that models can be evaluated with specific
inference parameters (e.g., reasoning_effort, temperature, max_tokens).

Same pattern as I/O adapters: file-based YAML with glob matching,
priority resolution (explicit > user file > bundled > None).
"""

import fnmatch
from pathlib import Path

import yaml

from palace.utils.paths import MODEL_EXTRA_PARAMS_FILE


def load_model_extra_params(file_path: Path | None = None) -> dict[str, dict]:
    """Load extra params from YAML file.

    Returns ordered dict of {glob_pattern: params_dict}.
    Returns empty dict if file doesn't exist.
    Raises ValueError on invalid config.
    """
    path = file_path or MODEL_EXTRA_PARAMS_FILE
    if not path.exists():
        return {}

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Extra params file must be a YAML mapping, got {type(raw).__name__}")

    params: dict[str, dict] = {}
    for pattern, config in raw.items():
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise ValueError(
                f"Invalid extra params for '{pattern}': expected a mapping, got {type(config).__name__}"
            )
        params[str(pattern)] = config

    return params


def get_model_extra_params(
    model_name: str,
    explicit_params: dict | None = None,
    file_params: dict[str, dict] | None = None,
    bundled_params: dict[str, dict] | None = None,
) -> tuple[dict, str] | None:
    """Get extra params for a model. Priority: explicit > user file > bundled > None.

    Args:
        model_name: The model name to match against param patterns.
        explicit_params: Programmatic params dict (highest priority).
        file_params: Pre-loaded user file params from load_model_extra_params().
        bundled_params: Pre-loaded bundled params from load_model_extra_params().

    Returns:
        Tuple of (params_dict, source) where source is "explicit", "user", or
        "bundled". Returns None if no params match.
    """
    if explicit_params is not None:
        return explicit_params, "explicit"

    if file_params:
        for pattern, params in file_params.items():
            if fnmatch.fnmatch(model_name, pattern):
                return params, "user"

    if bundled_params:
        for pattern, params in bundled_params.items():
            if fnmatch.fnmatch(model_name, pattern):
                return params, "bundled"

    return None
