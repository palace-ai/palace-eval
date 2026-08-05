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

"""Secret/token accessors.

These functions provide access to sensitive configuration values with proper priority:
CLI flags > env vars > config file.

Use these instead of reading env vars directly.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def get_huggingface_token() -> str | None:
    """Get HuggingFace token (env: HUGGINGFACE_TOKEN, config: huggingface_token)."""
    from palace.utils.config import get_config_value

    return get_config_value("huggingface_token")


def get_api_key() -> str | None:
    """Get API key (env: OPENAI_LIKE_API_KEY, config: key)."""
    from palace.utils.config import get_config_value

    return get_config_value("key")


# Legacy module-level variables for backward compatibility
# These only see env vars (evaluated at import time)
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
OPENAI_LIKE_API_KEY = os.getenv("OPENAI_LIKE_API_KEY")

# Other service tokens (internal, not exposed via config)
ALOHA_STAGING_TOKEN = os.getenv("ALOHA_STAGING_TOKEN")
TS_STAGING_TOKEN = os.getenv("TS_STAGING_TOKEN")
