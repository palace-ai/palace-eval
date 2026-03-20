import os

from dotenv import load_dotenv

load_dotenv()

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# Primary API key (OpenAI-compatible)
OPENAI_LIKE_API_KEY = os.getenv("OPENAI_LIKE_API_KEY")

# Other service tokens
ALOHA_STAGING_TOKEN = os.getenv("ALOHA_STAGING_TOKEN")
TS_STAGING_TOKEN = os.getenv("TS_STAGING_TOKEN")
