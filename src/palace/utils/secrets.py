import os

from dotenv import load_dotenv

# from palace.utils.paths import PROJECT_ROOT

# load_dotenv(PROJECT_ROOT / ".env")

load_dotenv()

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
GPTJRC_PROD_TOKEN = os.getenv("GPTJRC_PROD_TOKEN")
GPTJRC_STAGING_TOKEN = os.getenv("GPTJRC_STAGING_TOKEN")
ALOHA_STAGING_TOKEN = os.getenv("ALOHA_STAGING_TOKEN")
TS_STAGING_TOKEN = os.getenv("TS_STAGING_TOKEN")
