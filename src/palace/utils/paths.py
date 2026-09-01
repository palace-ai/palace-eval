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

from importlib.resources import files
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir

PACKAGE_ROOT = Path(str(files("palace")))

USER_DIR = Path(user_cache_dir("palace"))
USER_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_DIR = Path(user_config_dir("palace"))
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

IO_ADAPTERS_FILE = CONFIG_DIR / "io_adapters.yaml"
BUNDLED_IO_ADAPTERS_FILE = PACKAGE_ROOT / "bundled_io_adapters.yaml"

MODEL_EXTRA_PARAMS_FILE = CONFIG_DIR / "model_extra_params.yaml"
BUNDLED_MODEL_EXTRA_PARAMS_FILE = PACKAGE_ROOT / "bundled_model_extra_params.yaml"

TASKLISTS_PATH = USER_DIR / "tasklists"
TASKLISTS_PATH.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = USER_DIR / "results"
RESULTS_PATH.mkdir(parents=True, exist_ok=True)
LOGS_PATH = USER_DIR / "logs"
LOGS_PATH.mkdir(parents=True, exist_ok=True)


def resolve_local_path(identifier: str) -> Path | None:
    """Resolve a tasklist identifier (display name, folder name, or ID) to local path.

    This function handles all forms of tasklist identification:
    - Display name from info.json (e.g., "SWE-bench Verified")
    - Folder name (e.g., "SWE-bench-Verified")
    - ID with org (e.g., "palace-ai/swe-bench-verified")

    Args:
        identifier: Any form of tasklist identifier.

    Returns:
        Path to the tasklist directory if found and has info.json, None otherwise.

    Example:
        >>> from palace.utils.paths import resolve_local_path
        >>> path = resolve_local_path("SWE-bench Verified")
        >>> if path:
        ...     print(f"Found at: {path}")
    """
    import json

    identifier_lower = identifier.lower()

    # 1. Try exact folder match first (fastest)
    path = TASKLISTS_PATH / identifier
    if (path / "info.json").exists():
        return path

    # 2. Try org/name -> org--name folder format
    if "/" in identifier:
        folder_name = identifier.replace("/", "--")
        path = TASKLISTS_PATH / folder_name
        if (path / "info.json").exists():
            return path

    # 3. Try case-insensitive folder match
    if TASKLISTS_PATH.exists():
        for d in TASKLISTS_PATH.iterdir():
            if d.is_dir() and d.name.lower() == identifier_lower:
                if (d / "info.json").exists():
                    return d

    # 4. Try matching display name from info.json (handles spaces, etc.)
    if TASKLISTS_PATH.exists():
        for d in TASKLISTS_PATH.iterdir():
            if not d.is_dir():
                continue

            info_file = d / "info.json"
            if not info_file.exists():
                continue

            try:
                info = json.loads(info_file.read_text())
                display_name = info.get("name", "")
                if display_name.lower() == identifier_lower:
                    return d
            except (json.JSONDecodeError, OSError):
                continue

    return None
