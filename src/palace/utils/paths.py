from importlib.resources import files
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir

PACKAGE_ROOT = Path(str(files("palace")))

USER_DIR = Path(user_cache_dir("palace"))
USER_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_DIR = Path(user_config_dir("palace"))
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

IO_ADAPTERS_FILE = CONFIG_DIR / "io_adapters.yaml"

TASKLISTS_PATH = USER_DIR / "tasklists"
TASKLISTS_PATH.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = USER_DIR / "results"
RESULTS_PATH.mkdir(parents=True, exist_ok=True)
