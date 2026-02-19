import os

from dotenv import load_dotenv

# from palace.utils.paths import PROJECT_ROOT

# load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()
VERBOSE_MODE = os.getenv("VERBOSE_MODE")
