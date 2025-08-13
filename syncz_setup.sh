#!/bin/bash

# SyncZ - Universal Entry Point
# Handles setup, dependencies, and launches the appropriate interface

set -e

# Offer to add a syncz alias to ~/.bashrc, with robust yes/no prompt
SCRIPT_PATH="$(realpath "$0")"
SCRIPT_DIR="$(cd -- "$(dirname "$SCRIPT_PATH")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.env"
VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# Always work from the script directory so .env and files resolve correctly
cd "$SCRIPT_DIR"
function ask_yes_no() {
  local prompt="$1"
  local answer
  while true; do
    read -p "$prompt" answer
    case "$answer" in
      [Yy]|[Yy][Ee][Ss]) return 0 ;;
      [Nn]|[Nn][Oo]|"") return 1 ;;
      *) echo "Please answer y or n." ;;
    esac
  done
}

if ! grep -q "alias syncz=" ~/.bashrc 2>/dev/null; then
  echo
  if ask_yes_no "Do you want to add a 'syncz' command to your shell (in ~/.bashrc)? (y/N): "; then
    echo "alias syncz='bash $SCRIPT_PATH'" >> ~/.bashrc
    echo "Alias 'syncz' added. Run 'source ~/.bashrc' or open a new terminal to use it."
  fi
else
  # If alias exists but points to a different path (e.g., repo was renamed/moved), offer to update it
  EXISTING_LINE="$(grep -E "^alias syncz=" ~/.bashrc | head -n1)"
  if ! echo "$EXISTING_LINE" | grep -q "$SCRIPT_PATH"; then
    echo
    echo "Detected existing 'syncz' alias that points to a different path:"
    echo "  $EXISTING_LINE"
    echo "Desired alias:"
    echo "  alias syncz='bash $SCRIPT_PATH'"
    if ask_yes_no "Update alias to the new path? (y/N): "; then
      # Replace the first occurrence of the alias line
      sed -i "0,/^alias syncz=.*/s||alias syncz='bash $SCRIPT_PATH'|" ~/.bashrc
      echo "Alias updated. Run 'source ~/.bashrc' or open a new terminal to use it."
    fi
  fi
fi

# Function to create and setup virtual environment
function setup_virtual_env() {
  if [ ! -f "$VENV_DIR/bin/activate" ]; then
    if ask_yes_no "No virtual environment found. Create one (.env)? (y/N): "; then
      echo "Creating virtual environment..."
      python3 -m venv "$VENV_DIR"
      if [ $? -eq 0 ]; then
        echo "Virtual environment created successfully."
        # Activate for current shell usage
        # shellcheck disable=SC1090
        source "$VENV_DIR/bin/activate"
        "$VENV_PY" -m pip install --upgrade pip
        if [ -f "requirements.txt" ]; then
          "$VENV_PY" -m pip install -r requirements.txt
        fi
      else
        echo "Failed to create virtual environment. Continuing without it."
        return 1
      fi
    else
      return 1
    fi
  else
    echo "Activating Python virtual environment (.env)..."
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
  fi
  
  # Check if required packages are installed
  if ! "$VENV_PY" -c "import requests, colorama" 2>/dev/null; then
    echo "Installing required packages..."
    "$VENV_PY" -m pip install requests colorama
  fi
  
  return 0
}

# Setup dependencies first
echo "🔧 Checking dependencies..."
setup_virtual_env

# Now launch the main SyncZ interface
echo "🚀 Launching SyncZ..."
"$VENV_PY" client.py
