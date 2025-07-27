import json
import os
import sys
import subprocess

def load_config(config_file, default_path, default_port):
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"path": default_path, "port": default_port}

def save_config(config_file, config):
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def prompt_for_path(default_path):
    path = input(f"Enter sync directory path for server (press Enter for '{default_path}'): ").strip()
    return path if path else default_path

def prompt_for_port(default_port):
    port = input(f"Enter server port (press Enter for '{default_port}'): ").strip()
    if not port:
        return default_port
    try:
        return int(port)
    except ValueError:
        print("Invalid port, using default.")
        return default_port

def main():
    CONFIG_FILE = "config.json"
    DEFAULT_PATH = "/home/jorge/zoteroReference"
    DEFAULT_PORT = 8000
    config = load_config(CONFIG_FILE, DEFAULT_PATH, DEFAULT_PORT)
    print("--- SyncZ Interactive Server Setup ---")
    config["path"] = prompt_for_path(config.get("path", DEFAULT_PATH))
    config["port"] = prompt_for_port(config.get("port", DEFAULT_PORT))
    save_config(CONFIG_FILE, config)
    print(f"Configuration saved to {CONFIG_FILE}.")
    print(f"Using path: {config['path']}")
    print(f"Port: {config['port']}")
    print("Starting server...\n")
    # Start the server
    python_exec = sys.executable or "python3"
    subprocess.run([python_exec, "run_server.py"])

if __name__ == "__main__":
    main()
