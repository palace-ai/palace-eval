from importlib.resources import files
from pathlib import Path

from platformdirs import user_cache_dir

PACKAGE_ROOT = Path(str(files("palace")))

USER_DIR = Path(user_cache_dir("palace"))
USER_DIR.mkdir(parents=True, exist_ok=True)

TASKLISTS_PATH = USER_DIR / "tasklists"
TASKLISTS_PATH.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = USER_DIR / "results"
RESULTS_PATH.mkdir(parents=True, exist_ok=True)
