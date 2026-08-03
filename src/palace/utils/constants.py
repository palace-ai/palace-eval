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

import os

from dotenv import load_dotenv

load_dotenv()

# Primary API endpoint (OpenAI-compatible)
OPENAI_LIKE_API_BASE_URL = os.getenv("OPENAI_LIKE_API_BASE_URL")

# Optional MCP server URLs (set in environment for MCP endpoint support)
ALOHA_STAGING_URL = os.getenv("ALOHA_STAGING_URL")
TS_STAGING_URL = os.getenv("TS_STAGING_URL")
ABW_SERVE_STAGING_URL = os.getenv("ABW_SERVE_STAGING_URL")

# Judge model (required - no default)
JUDGE_MODEL = os.getenv("JUDGE_MODEL")
