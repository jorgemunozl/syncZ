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
function ask_ip() {
  read -p "Enter server IP (leave blank to keep current): " new_ip
  if [ ! -z "$new_ip" ]; then
    python3 -c "import json; c=json.load(open('$CONFIG_FILE')); c['server_ip']='$new_ip'; json.dump(c, open('$CONFIG_FILE','w'), indent=2)"
    echo "Server IP updated to $new_ip"
  fi
}
# Function to install requirements
function install_requirements() {
  if [ -f "requirements.txt" ]; then
    echo "Checking/installing Python requirements..."
    if [ -f ".env/bin/activate" ]; then
      source .env/bin/activate
      pip install --upgrade pip
      pip install -r requirements.txt
    else
      pip3 install --user --upgrade pip
      pip3 install --user -r requirements.txt
    fi
  fi
}
#!/bin/bash

# SyncZ Setup Script
# Guides user to run as client or server, and optionally change path/port

set -e

CONFIG_FILE="config.json"

function ask_path() {
  read -p "Enter sync directory path (leave blank to keep current): " new_path
  if [ ! -z "$new_path" ]; then
    python3 -c "import json; c=json.load(open('$CONFIG_FILE')); c['path']='$new_path'; json.dump(c, open('$CONFIG_FILE','w'), indent=2)"
    echo "Path updated to $new_path"
  fi
}

function ask_port() {
  read -p "Enter server port (leave blank to keep current): " new_port
  if [ ! -z "$new_port" ]; then
    python3 -c "import json; c=json.load(open('$CONFIG_FILE')); c['port']=int('$new_port'); json.dump(c, open('$CONFIG_FILE','w'), indent=2)"
    echo "Port updated to $new_port"
  fi
}

clear
echo "====================="
echo "   SyncZ Launcher   "
echo "====================="
echo "1) Client"
echo "2) Server"
echo "q) Quit"
echo
read -p "Run as (1/2/q): " mode

if [ "$mode" = "1" ]; then
  echo "\nYou chose CLIENT."
  # Show current sync path and server IP
  if [ -f "$CONFIG_FILE" ]; then
    current_path=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['path'])")
    current_ip=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('server_ip', ''))")
    echo "Current sync path: $current_path"
    echo "Current server IP: $current_ip"
    if ask_yes_no "Do you want to change the server IP? (y/N): "; then
      ask_ip
    fi
  fi
  # Activate venv if exists
  if [ -f ".env/bin/activate" ]; then
    echo "Activating Python virtual environment (.env)..."
    # shellcheck disable=SC1091
    source .env/bin/activate
  fi
  install_requirements
  if ask_yes_no "Do you want to change the sync path? (y/N): "; then
    ask_path
    python3 client_interactive.py
  else
    python3 client.py
  fi
elif [ "$mode" = "2" ]; then
  echo "\nYou chose SERVER."
  # Show current sync path and server IP
  if [ -f "$CONFIG_FILE" ]; then
    current_path=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['path'])")
    current_ip=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('server_ip', ''))")
    echo "Current sync path: $current_path"
    echo "Current server IP: $current_ip"
    if ask_yes_no "Do you want to change the server IP? (y/N): "; then
      ask_ip
    fi
  fi
  install_requirements
  if ask_yes_no "Do you want to change the sync path? (y/N): "; then
    ask_path
    if ask_yes_no "Do you want to change the server port? (y/N): "; then
      ask_port
    fi
    python3 run_server_interactive.py
  else
    python3 run_server.py
  fi
else
  echo "Exiting."
  exit 0
fi
