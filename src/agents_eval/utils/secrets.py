import os

from dotenv import load_dotenv

from agents_eval.utils.paths import ROOT

load_dotenv(ROOT / ".tokens.env")

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
GPTJRC_TOKEN = os.getenv("GPTJRC_TOKEN")
ALOHA_TOKEN = os.getenv("ALOHA_TOKEN")
