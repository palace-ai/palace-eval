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

"""Palace configuration management.

Handles loading and saving configuration from ~/.config/palace/config.yaml.
Priority order for settings: CLI flags > env vars > config file.

Config file keys:
    url: API endpoint URL (OPENAI_LIKE_API_BASE_URL)
    key: API key (OPENAI_LIKE_API_KEY)
    judge_model: Model for judging answers (JUDGE_MODEL)
    concurrency: Number of parallel tasks (PALACE_CONCURRENCY)
    huggingface_token: HuggingFace token (HUGGINGFACE_TOKEN)
    github_token: GitHub token for API rate limits (GITHUB_TOKEN)
    vivarium_url: Remote Vivarium URL (VIVARIUM_URL)
"""

import os
from typing import Any

import yaml

from palace.utils.paths import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / "config.yaml"

# Mapping from config file keys to env var names
CONFIG_TO_ENV = {
    "url": "OPENAI_LIKE_API_BASE_URL",
    "key": "OPENAI_LIKE_API_KEY",
    "judge_model": "JUDGE_MODEL",
    "concurrency": "PALACE_CONCURRENCY",
    "huggingface_token": "HUGGINGFACE_TOKEN",
    "github_token": "GITHUB_TOKEN",
    "gitlab_token": "GITLAB_TOKEN",
    "vivarium_url": "VIVARIUM_URL",
}

# Valid config keys
VALID_KEYS = set(CONFIG_TO_ENV.keys())


def load_config() -> dict[str, Any]:
    """Load configuration from config file.

    Returns:
        Dictionary of config values. Empty dict if file doesn't exist or is invalid.
    """
    if not CONFIG_FILE.exists():
        return {}

    try:
        content = CONFIG_FILE.read_text()
        config = yaml.safe_load(content) or {}
        return config
    except yaml.YAMLError:
        # Invalid YAML - warn but continue with empty config
        import sys
        print(f"Warning: Config file {CONFIG_FILE} has invalid YAML syntax. Using defaults.", file=sys.stderr)
        return {}
    except Exception:
        # Other errors (permissions, etc.) - silent fallback
        return {}


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to config file.

    Args:
        config: Dictionary of config values to save.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Filter to only valid keys
    filtered = {k: v for k, v in config.items() if k in VALID_KEYS}

    with open(CONFIG_FILE, "w") as f:
        yaml.dump(filtered, f, default_flow_style=False)


def get_config_value(key: str) -> str | None:
    """Get a config value with priority: env var > config file.

    Args:
        key: Config key (e.g., "url", "key", "judge_model").

    Returns:
        The value, or None if not set anywhere.
    """
    if key not in VALID_KEYS:
        return None

    # Check env var first
    env_var = CONFIG_TO_ENV[key]
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value

    # Fall back to config file
    config = load_config()
    return config.get(key)


def set_config_value(key: str, value: str) -> None:
    """Set a config value in the config file.

    Args:
        key: Config key (e.g., "url", "key").
        value: Value to set.

    Raises:
        ValueError: If key is not a valid config key.
    """
    if key not in VALID_KEYS:
        raise ValueError(f"Invalid config key: {key}. Valid keys: {', '.join(sorted(VALID_KEYS))}")

    config = load_config()
    config[key] = value
    save_config(config)


def delete_config_value(key: str) -> bool:
    """Delete a config value from the config file.

    Args:
        key: Config key to delete.

    Returns:
        True if key was deleted, False if it didn't exist.
    """
    config = load_config()
    if key in config:
        del config[key]
        save_config(config)
        return True
    return False


def get_all_config() -> dict[str, dict[str, Any]]:
    """Get all config values with their sources.

    Returns:
        Dictionary mapping keys to {"value": ..., "source": "env"|"config"|None}.
    """
    config_file = load_config()
    result = {}

    for key, env_var in CONFIG_TO_ENV.items():
        env_value = os.environ.get(env_var)
        file_value = config_file.get(key)

        if env_value:
            result[key] = {"value": env_value, "source": "env"}
        elif file_value:
            result[key] = {"value": file_value, "source": "config"}
        else:
            result[key] = {"value": None, "source": None}

    return result
