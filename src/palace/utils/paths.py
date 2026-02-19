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


# Split into tasklists and results and pointing to a user directory
# PROJECT_ROOT = Path(__file__).parents[3]

# Renamed to PACKAGE_ROOT and computed dynamically
# CODE_ROOT = PROJECT_ROOT / "src" / "palace"

# Deprecated the possibility to run local models
# MODELS_DIR = Path("/mnt/storage2/hf_models")
