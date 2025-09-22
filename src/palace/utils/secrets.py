import os

from dotenv import load_dotenv

from palace.utils.paths import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".tokens.env")

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
GPTJRC_TOKEN = os.getenv("GPTJRC_TOKEN")
ALOHA_TOKEN = os.getenv("ALOHA_TOKEN")
