import os

from dotenv import load_dotenv

load_dotenv()

# Primary API endpoint (OpenAI-compatible)
OPENAI_LIKE_API_BASE_URL = os.getenv("OPENAI_LIKE_API_BASE_URL")

# Internal service URLs (JRC infrastructure)
ALOHA_STAGING_URL = os.getenv("ALOHA_STAGING_URL")
TS_STAGING_URL = os.getenv("TS_STAGING_URL")
ABW_SERVE_STAGING_URL = os.getenv("ABW_SERVE_STAGING_URL")

# Judge model
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-oss-120b")
