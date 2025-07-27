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
  # Show current sync path
  if [ -f "$CONFIG_FILE" ]; then
    current_path=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['path'])")
    echo "Current sync path: $current_path"
  fi
  # Activate venv if exists
  if [ -f ".env/bin/activate" ]; then
    echo "Activating Python virtual environment (.env)..."
    # shellcheck disable=SC1091
    source .env/bin/activate
  fi
  read -p "Do you want to change the sync path? (y/N): " change_path
  if [[ "$change_path" =~ ^[Yy]$ ]]; then
    ask_path
    python3 client_interactive.py
  else
    python3 client.py
  fi
elif [ "$mode" = "2" ]; then
  echo "\nYou chose SERVER."
  # Show current sync path
  if [ -f "$CONFIG_FILE" ]; then
    current_path=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['path'])")
    echo "Current sync path: $current_path"
  fi
  read -p "Do you want to change the sync path? (y/N): " change_path
  if [[ "$change_path" =~ ^[Yy]$ ]]; then
    ask_path
    read -p "Do you want to change the server port? (y/N): " change_port
    if [[ "$change_port" =~ ^[Yy]$ ]]; then
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
