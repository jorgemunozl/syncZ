# CRUSH.md for SyncZ Project

## How to Build/Run/Lint/Test

- **Run client (CLI):**   `python client.py`
- **Run client (interactive):** `python client_interactive.py`
- **Run server (CLI):**   `python run_server.py`
- **Run server (interactive):** `python run_server_interactive.py`
- **New CLI wrapper:** `./syncz -c` (client), `./syncz -s` (server), `./syncz -ci` (interactive client), `./syncz -si` (interactive server)
- **Requirements:** Install `requests` (and optionally `colorama` for color CLI)
- **Lint:** No formal linter configured (use `flake8` or `ruff` if desired)
- **Tests:** No tests defined—testing is currently manual via execution

## Code Style Guidelines

- **Python 3.6+** (uses f-strings, dict comprehensions, etc.)
- **Imports:** Order by stdlib, 3rd-party, project (
  - Imports go at the top of the file
  - Example: `import os` then `import requests`
)
- **Naming:**
  - `snake_case` for variables, functions, and files
  - `UPPER_SNAKE_CASE` for constants
- **Types:** No type hints/annotations are used; type checking is not enforced
- **Formatting:** Follows standard 4-space indentation
- **Error Handling:**
  - Prefer targeted exceptions (`except FileNotFoundError` or `except requests.exceptions.RequestException`)
  - Avoid broad `except Exception` unless necessary
- **Configuration:** Managed in `config.json`. Scripts will prompt interactively if config is missing or invalid.
- **CLI conventions:**
  - New entry script `syncz` supports flags: `-c` (client), `-s` (server), `-ci` (client interactive), `-si` (server interactive)
- **Dependency Management:** List in `requirements.txt`. Install with `pip install -r requirements.txt`.
- **No Cursor/Copilot rules or pre-commit hooks yet.**

## General
- `.crush/` and generated files like `file_list.json` are ignored by git (see `.gitignore`)

---
This file is meant to help future agents (human or bot) act in accordance with this repo’s standards.
