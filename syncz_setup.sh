#!/bin/bash

# SyncZ Setup Script
# Sets up dependencies and virtual environment for SyncZ

set -e

SCRIPT_PATH="$(realpath "$0")"
SCRIPT_DIR="$(cd -- "$(dirname "$SCRIPT_PATH")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"  # Changed from .env to .venv
VENV_PY="$VENV_DIR/bin/python"
SYNCZ_SCRIPT="$SCRIPT_DIR/syncz"

# Always work from the script directory
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

# Function to create and setup virtual environment
function setup_virtual_env() {
  if [ ! -f "$VENV_DIR/bin/activate" ]; then
    if ask_yes_no "No virtual environment found. Create one (.venv)? (y/N): "; then
      echo "Creating virtual environment..."
      python3 -m venv "$VENV_DIR"
      if [ $? -eq 0 ]; then
        echo "Virtual environment created successfully."
        echo "Installing packages..."
        "$VENV_PY" -m pip install --upgrade pip
        if [ -f "requirements.txt" ]; then
          "$VENV_PY" -m pip install -r requirements.txt
        fi
        # Install additional packages for progress bars
        "$VENV_PY" -m pip install rich requests-toolbelt
      else
        echo "Failed to create virtual environment."
        return 1
      fi
    else
      return 1
    fi
  else
    echo "Virtual environment found (.venv)..."
    # Check if required packages are installed
    if ! "$VENV_PY" -c "import requests, colorama, rich" 2>/dev/null; then
      echo "Installing missing packages..."
      "$VENV_PY" -m pip install requests colorama rich requests-toolbelt
    fi
  fi
  
  return 0
}

# Setup syncz command globally
function setup_syncz_command() {
  # Make sure syncz script is executable
  chmod +x "$SYNCZ_SCRIPT"
  
  # Check if syncz alias already exists
  if ! grep -q "alias syncz=" ~/.bashrc 2>/dev/null; then
    echo
    if ask_yes_no "Add 'syncz' command to your shell? (y/N): "; then
      echo "alias syncz='$SYNCZ_SCRIPT'" >> ~/.bashrc
      echo "✅ Alias 'syncz' added to ~/.bashrc"
      echo "   Run 'source ~/.bashrc' or open a new terminal to use it globally"
      echo ""
      echo "🎯 Usage examples:"
      echo "   syncz -cu        # Auto-upload orphaned files"
      echo "   syncz -cd        # Auto-delete orphaned files" 
      echo "   syncz --config   # Configure SyncZ"
      echo "   syncz --help     # Show help"
    fi
  else
    # Check if alias points to correct script
    EXISTING_LINE="$(grep -E "^alias syncz=" ~/.bashrc | head -n1)"
    if ! echo "$EXISTING_LINE" | grep -q "$SYNCZ_SCRIPT"; then
      echo
      echo "⚠️  Existing 'syncz' alias found:"
      echo "   $EXISTING_LINE"
      echo "📝 Should be:"
      echo "   alias syncz='$SYNCZ_SCRIPT'"
      if ask_yes_no "Update alias? (y/N): "; then
        sed -i "0,/^alias syncz=.*/s||alias syncz='$SYNCZ_SCRIPT'|" ~/.bashrc
        echo "✅ Alias updated."
      fi
    else
      echo "✅ 'syncz' command already configured correctly."
    fi
  fi
}

# Main setup process
echo "🚀 SyncZ Setup Script"
echo "===================="
echo ""

# Setup dependencies first
echo "🔧 Setting up virtual environment and dependencies..."
if setup_virtual_env; then
  echo "✅ Virtual environment ready"
else
  echo "⚠️  Continuing without virtual environment"
fi

echo ""

# Setup syncz command
echo "🔗 Setting up syncz command..."
setup_syncz_command

echo ""
echo "🎉 Setup complete!"
echo ""
echo "� Quick start:"
echo "   ./syncz --help       # Show all commands"
echo "   ./syncz -cu          # Auto-upload orphaned files"
echo "   ./syncz --config     # Configure SyncZ"
echo ""
echo "💡 If you added the alias, you can use 'syncz' from anywhere after:"
echo "   source ~/.bashrc"
echo ""
