import os

from dotenv import load_dotenv

load_dotenv()

# Primary API endpoint (OpenAI-compatible)
OPENAI_LIKE_API_BASE_URL = os.getenv("OPENAI_LIKE_API_BASE_URL")

# Other service URLs
ALOHA_PROD_URL = os.getenv("ALOHA_PROD_URL")
ALOHA_STAGING_URL = os.getenv("ALOHA_STAGING_URL")
REACT_AGENT_ALOHA_URL = os.getenv("REACT_AGENT_ALOHA_URL")
TS_STAGING_URL = os.getenv("TS_STAGING_URL")
ABW_SERVE_STAGING_URL = os.getenv("ABW_SERVE_STAGING_URL")

# Judge model
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "minimax-m2")
