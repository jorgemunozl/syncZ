#!/bin/bash

# SyncZ - Universal Entry Point
# Handles setup, dependencies, and launches the appropriate interface

set -e

# Offer to add a syncz alias to ~/.bashrc, with robust yes/no prompt
SCRIPT_PATH="$(realpath "$0")"
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
fi

# Function to create and setup virtual environment
function setup_virtual_env() {
  if [ ! -f ".env/bin/activate" ]; then
    if ask_yes_no "No virtual environment found. Create one (.env)? (y/N): "; then
      echo "Creating virtual environment..."
      python3 -m venv .env
      if [ $? -eq 0 ]; then
        echo "Virtual environment created successfully."
        source .env/bin/activate
        pip install --upgrade pip
        if [ -f "requirements.txt" ]; then
          pip install -r requirements.txt
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
    source .env/bin/activate
  fi
  return 0
}

# Setup dependencies first
echo "🔧 Checking dependencies..."
setup_virtual_env

# Now launch the main SyncZ interface
echo "🚀 Launching SyncZ..."
python3 client.py
