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

"""Configuration value accessors.

These functions provide access to configuration values with proper priority:
CLI flags > env vars > config file.

Use these instead of reading env vars directly.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def get_api_url() -> str | None:
    """Get API URL (env: OPENAI_LIKE_API_BASE_URL, config: url)."""
    from palace.utils.config import get_config_value

    return get_config_value("url")


def get_judge_model() -> str | None:
    """Get judge model (env: JUDGE_MODEL, config: judge_model)."""
    from palace.utils.config import get_config_value

    return get_config_value("judge_model")


def get_judge_url() -> str | None:
    """Get judge API URL (env: JUDGE_API_URL, config: judge_url).

    Falls back to the main API URL if not set.
    """
    from palace.utils.config import get_config_value

    return get_config_value("judge_url") or get_config_value("url")


def get_judge_key() -> str | None:
    """Get judge API key (env: JUDGE_API_KEY, config: judge_key).

    Falls back to the main API key if not set.
    """
    from palace.utils.config import get_config_value

    return get_config_value("judge_key") or get_config_value("key")


# Legacy module-level variables for backward compatibility
# These only see env vars (evaluated at import time)
OPENAI_LIKE_API_BASE_URL = os.getenv("OPENAI_LIKE_API_BASE_URL")
JUDGE_MODEL = os.getenv("JUDGE_MODEL")
