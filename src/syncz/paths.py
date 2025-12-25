"""Common paths for the SyncZ codebase."""
from pathlib import Path

# Location of the installed package (src/syncz)
PACKAGE_ROOT = Path(__file__).resolve().parent

# Repository root (two levels up from this file)
PROJECT_ROOT = PACKAGE_ROOT.parent.parent

# Convenient references used across modules
SRC_DIR = PROJECT_ROOT / "src"
CONFIG_FILE = PROJECT_ROOT / "config.json"
