
import os
import json
import hashlib
import requests
import sys
import time

def generate_file_list(root_dir):
    rows = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            # Skip hidden files if needed
            if fname.startswith("."):
                continue
            full = os.path.join(dirpath, fname)
            rows.append({
                "name": os.path.relpath(full, root_dir).replace("\\", "/"),
                "sha256": sha256sum(full),
                "mtime": os.path.getmtime(full)
            })
    return rows


# --- Configuration ---
CONFIG_FILE = "config.json"
DEFAULT_PATH = "/root/shared/zoteroReference"
DEFAULT_SERVER_IP = "192.168.43.119"
DEFAULT_SERVER_PORT = 8000

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Default config if not present
    return {
        "path": DEFAULT_PATH,
        "server_ip": DEFAULT_SERVER_IP,
        "server_port": DEFAULT_SERVER_PORT
    }

def main_menu():
    while True:
        print("\n==== SyncZ Client Main Menu ====")
        print("1) Sync now")
        print("2) Change config (path/ip/port)")
        print("q) Quit")
        choice = input("Choose an option: ").strip().lower()
        if choice == "1":
            do_sync()
        elif choice == "2":
            change_config()
        elif choice == "q":
            print("Exiting.")
            sys.exit(0)
        else:
            print("Invalid option. Please try again.")

def change_config():
    config = load_config()
    print(f"Current path: {config.get('path', DEFAULT_PATH)}")
    new_path = input("Enter new sync path (leave blank to keep): ").strip()
    if new_path:
        config["path"] = new_path
    print(f"Current server IP: {config.get('server_ip', DEFAULT_SERVER_IP)}")
    new_ip = input("Enter new server IP (leave blank to keep): ").strip()
    if new_ip:
        config["server_ip"] = new_ip
    print(f"Current server port: {config.get('server_port', DEFAULT_SERVER_PORT)}")
    new_port = input("Enter new server port (leave blank to keep): ").strip()
    if new_port:
        try:
            config["server_port"] = int(new_port)
        except ValueError:
            print("Invalid port, keeping previous.")
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print("Config updated.")

def do_sync():
    config = load_config()
    path = config.get("path", DEFAULT_PATH)
    SERVER_IP = config.get("server_ip", DEFAULT_SERVER_IP)
    SERVER_PORT = config.get("server_port", DEFAULT_SERVER_PORT)
    BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}"
    METADATA_URL = f"{BASE_URL}/metadata"
    LOCAL_JSON = "file_list.json"
    DOWNLOAD_DIR = "."
    try:
        os.chdir(path)
    except Exception as e:
        print(f"Failed to change to sync path {path}: {e}")
        return
    # 1. Fetch remote metadata
    print("Fetching remote metadata...")
    try:
        resp = requests.get(METADATA_URL, timeout=5)
        resp.raise_for_status()
        remote_meta = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"\nCould not connect to server at {SERVER_IP}:{SERVER_PORT}.")
        print(f"Error: {e}\nReturning to main menu.")
        time.sleep(2)
        return

    # 2. Compute local metadata
    local_meta = generate_file_list(path)
    with open("file_list.json", "w", encoding="utf-8") as f:
        json.dump(local_meta, f, indent=2)

    remote_index = {m["name"]: (m["sha256"], m.get("mtime", 0)) for m in remote_meta}
    local_index  = {m["name"]: (m["sha256"], m.get("mtime", 0)) for m in local_meta}

    to_download = [
        name for name, (remote_hash, remote_mtime) in remote_index.items()
        if (
            name not in local_index or
            local_index[name][1] < remote_mtime  
            )
        ]

    to_upload = [
        m for m in local_meta
        if (
            m["name"] not in remote_index or
            remote_index.get(m["name"], ("", 0))[0] != m["sha256"] or
            remote_index.get(m["name"], ("", 0))[1] < m["mtime"]  # local is newer
        )
    ]
    to_upload = [m for m in to_upload if m["name"] != "file_list.json"]

    # 4. Download missing/changed
    for name in to_download:
        print(f"Downloading {name}...")
        dir_name = os.path.dirname(name)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        dl = requests.get(f"{BASE_URL}/{name}", stream=True)
        dl.raise_for_status()
        with open(name, "wb") as f:
            for chunk in dl.iter_content(4096):
                f.write(chunk)
        orig_mtime = remote_index[name][1]
        os.utime(name, (orig_mtime, orig_mtime))

    to_delete = [
        name for name in local_index
        # never delete your metadata file itself
        if name not in remote_index and name != LOCAL_JSON
    ]

    # 5. To delete.
    for name in to_delete:
        for d in to_upload:
            if d["name"] == name:
                to_upload.remove(d)
                break
        
        # Ask confirmation before deleting PDF files
        if name.lower().endswith('.pdf'):
            while True:
                confirm = input(f"Delete PDF file '{name}' (removed on server)? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    break
                elif confirm in ['n', 'no']:
                    print(f"Skipping deletion of {name}")
                    continue
                else:
                    print("Please answer y or n.")
                    continue
            if confirm in ['n', 'no']:
                continue
        
        print(f"Deleting local file {name} (removed on server)...")
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, name))
        except FileNotFoundError:
            pass  # already gone
        except Exception as e:
            print(f"  ! Failed to delete {name}: {e}")

    # 5. Upload new/changed (server must implement POST /upload)
    for m in to_upload:
        print(f"Uploading {m['name']}...")
        with open(m["name"], "rb") as f:
            files = {"file": f}
            data = {"mtime": str(m["mtime"])}
            upl = requests.post(f"{BASE_URL}/upload", files=files, data=data)
            upl.raise_for_status()

    # 6. Update local metadata
    print("Sync complete.")



def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    main_menu()
