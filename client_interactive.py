import os
import json
import hashlib
import requests

def load_config(config_file, default_path, default_ip, default_port):
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "path": default_path,
        "server_ip": default_ip,
        "server_port": default_port
    }

def save_config(config_file, config):
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def prompt_for_path(default_path):
    path = input(f"Enter sync directory path (press Enter for '{default_path}'): ").strip()
    return path if path else default_path

def prompt_for_ip(default_ip):
    ip = input(f"Enter server IP address (press Enter for '{default_ip}'): ").strip()
    return ip if ip else default_ip

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
    DEFAULT_PATH = "/root/shared/zoteroReference"
    DEFAULT_SERVER_IP = "192.168.43.119"
    DEFAULT_SERVER_PORT = 8000

    config = load_config(CONFIG_FILE, DEFAULT_PATH, DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT)
    print("--- SyncZ Interactive Client Setup ---")
    config["path"] = prompt_for_path(config.get("path", DEFAULT_PATH))
    config["server_ip"] = prompt_for_ip(config.get("server_ip", DEFAULT_SERVER_IP))
    config["server_port"] = prompt_for_port(config.get("server_port", DEFAULT_SERVER_PORT))
    save_config(CONFIG_FILE, config)
    print(f"Configuration saved to {CONFIG_FILE}.")
    print(f"Using path: {config['path']}")
    print(f"Server: {config['server_ip']}:{config['server_port']}")

    # --- Main sync logic (same as client.py, but using config) ---
    os.chdir(config["path"])
    BASE_URL = f"http://{config['server_ip']}:{config['server_port']}"
    METADATA_URL = f"{BASE_URL}/metadata"
    LOCAL_JSON = "file_list.json"
    DOWNLOAD_DIR = "."

    def sha256sum(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()

    def generate_file_list(root_dir):
        rows = []
        for dirpath, _, filenames in os.walk(root_dir):
            for fname in filenames:
                if fname.startswith("."):
                    continue
                full = os.path.join(dirpath, fname)
                rows.append({
                    "name": os.path.relpath(full, root_dir).replace("\\", "/"),
                    "sha256": sha256sum(full),
                    "mtime": os.path.getmtime(full)
                })
        return rows

    print("Fetching remote metadata...")
    resp = requests.get(METADATA_URL)
    resp.raise_for_status()
    remote_meta = resp.json()

    local_meta = generate_file_list(config["path"])
    with open(LOCAL_JSON, "w", encoding="utf-8") as f:
        json.dump(local_meta, f, indent=2)

    remote_index = {m["name"]: (m["sha256"], m.get("mtime", 0)) for m in remote_meta}
    local_index = {m["name"]: (m["sha256"], m.get("mtime", 0)) for m in local_meta}

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
            remote_index.get(m["name"], ("", 0))[1] < m["mtime"]
        )
    ]
    for m in to_upload[:]:
        if m["name"] == "file_list.json":
            to_upload.remove(m)

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
        if name not in remote_index and name != LOCAL_JSON
    ]
    for name in to_delete:
        for d in to_upload:
            if d["name"] == name:
                to_upload.remove(d)
                break
        print(f"Deleting local file {name} (removed on server)...")
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, name))
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"  ! Failed to delete {name}: {e}")

    for m in to_upload:
        print(f"Uploading {m['name']}...")
        with open(m["name"], "rb") as f:
            files = {"file": f}
            data = {"mtime": str(m["mtime"])}
            upl = requests.post(f"{BASE_URL}/upload", files=files, data=data)
            upl.raise_for_status()

    print("Sync complete.")

if __name__ == "__main__":
    main()
