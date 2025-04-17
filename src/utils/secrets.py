import os

from dotenv import load_dotenv

load_dotenv(".tokens.env")

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
GPTJRC_TOKEN = os.getenv("GPTJRC_TOKEN")
ALOHA_TOKEN = os.getenv("ALOHA_TOKEN")
