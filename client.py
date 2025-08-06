
import os
import json
import hashlib
import requests
import sys
import time
import shutil
from datetime import datetime, timedelta

# Try to import colorama for colored output
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
    COLOR_ENABLED = True
except ImportError:
    # Fallback for when colorama is not available
    class Fore:
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        MAGENTA = ""
        CYAN = ""
        WHITE = ""
        RESET = ""
    
    class Style:
        RESET_ALL = ""
    
    COLOR_ENABLED = False

def ctext(text, color=None):
    """Apply color to text if colorama is available"""
    if COLOR_ENABLED and color:
        return color + text + Style.RESET_ALL
    return text


def clean_old_deleted_files(deleted_dir="deleted", days=10):
    """Remove files from deleted directory that are older than specified days"""
    if not os.path.exists(deleted_dir):
        return
    
    cutoff_date = datetime.now() - timedelta(days=days)
    deleted_count = 0
    
    for root, dirs, files in os.walk(deleted_dir):
        for file in files:
            if file == ".deleted_info.json":
                continue
            file_path = os.path.join(root, file)
            try:
                # Check file modification time
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime < cutoff_date:
                    os.remove(file_path)
                    deleted_count += 1
                    print(ctext(f"  🗑️  Permanently deleted old file: {os.path.relpath(file_path, deleted_dir)}", Fore.YELLOW))
            except Exception as e:
                print(ctext(f"  ⚠️  Could not delete {file_path}: {e}", Fore.RED))
    
    if deleted_count > 0:
        print(ctext(f"🧹 Cleaned up {deleted_count} files older than {days} days", Fore.GREEN))


def move_to_deleted(file_path, deleted_dir="deleted"):
    """Move a file to the deleted directory instead of permanently deleting it"""
    if not os.path.exists(deleted_dir):
        os.makedirs(deleted_dir)
    
    filename = os.path.basename(file_path)
    deleted_path = os.path.join(deleted_dir, filename)
    
    # If file already exists in deleted, add timestamp
    if os.path.exists(deleted_path):
        name, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        deleted_path = os.path.join(deleted_dir, f"{name}_{timestamp}{ext}")
    
    try:
        shutil.move(file_path, deleted_path)
        return True
    except Exception as e:
        print(ctext(f"  ❌ Failed to move {file_path} to deleted folder: {e}", Fore.RED))
        return False

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

def show_current_config():
    config = load_config()
    print(ctext("\n" + "=" * 50, Fore.CYAN))
    print(ctext("           CURRENT CONFIGURATION", Fore.GREEN))
    print(ctext("=" * 50, Fore.CYAN))
    print(ctext(f"📁 Sync Path:   ", Fore.YELLOW) + ctext(f"{config.get('path', DEFAULT_PATH)}", Fore.WHITE))
    print(ctext(f"🌐 Server IP:   ", Fore.YELLOW) + ctext(f"{config.get('server_ip', DEFAULT_SERVER_IP)}", Fore.WHITE))
    print(ctext(f"🔌 Server Port: ", Fore.YELLOW) + ctext(f"{config.get('server_port', DEFAULT_SERVER_PORT)}", Fore.WHITE))
    print(ctext("=" * 50, Fore.CYAN))

def main_menu():
    show_current_config()
    while True:
        print(ctext("\n" + "╔" + "=" * 48 + "╗", Fore.CYAN))
        print(ctext("║" + " " * 16 + "SyncZ Main Menu" + " " * 17 + "║", Fore.GREEN))
        print(ctext("╠" + "=" * 48 + "╣", Fore.CYAN))
        print(ctext("║  ", Fore.CYAN) + ctext("1)", Fore.YELLOW) + ctext(" 🚀 Sync now (Client mode)" + " " * 21 + "║", Fore.WHITE))
        print(ctext("║  ", Fore.CYAN) + ctext("2)", Fore.YELLOW) + ctext(" 🖥️  Start Server" + " " * 30 + "║", Fore.WHITE))
        print(ctext("║  ", Fore.CYAN) + ctext("3)", Fore.YELLOW) + ctext(" ⚙️  Change config (path/ip/port)" + " " * 15 + "║", Fore.WHITE))
        print(ctext("║  ", Fore.CYAN) + ctext("q)", Fore.YELLOW) + ctext(" 🚪 Quit" + " " * 38 + "║", Fore.WHITE))
        print(ctext("╚" + "=" * 48 + "╝", Fore.CYAN))
        
        choice = input(ctext("Choose an option: ", Fore.YELLOW)).strip().lower()
        if choice == "1":
            do_sync()
        elif choice == "2":
            start_server()
        elif choice == "3":
            change_config()
            show_current_config()  # Show updated config after changes
        elif choice == "q":
            print(ctext("\n👋 Goodbye! Exiting SyncZ...", Fore.GREEN))
            sys.exit(0)
        else:
            print(ctext("❌ Invalid option. Please try again.", Fore.RED))

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


def start_server():
    import subprocess
    print(ctext("\n🖥️  Starting SyncZ Server...", Fore.GREEN))
    try:
        subprocess.run(["python3", "run_server.py"], check=True)
    except subprocess.CalledProcessError:
        print(ctext("❌ Failed to start server. Make sure run_server.py exists.",
                    Fore.RED))
    except KeyboardInterrupt:
        print(ctext("\n🛑 Server stopped by user.", Fore.YELLOW))


def do_sync():
    config = load_config()
    path = config.get("path", DEFAULT_PATH)
    SERVER_IP = config.get("server_ip", DEFAULT_SERVER_IP)
    SERVER_PORT = config.get("server_port", DEFAULT_SERVER_PORT)
    BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}"
    METADATA_URL = f"{BASE_URL}/metadata"
    LOCAL_JSON = "file_list.json"
    DOWNLOAD_DIR = "."
    DELETED_DIR = "deleted"
    
    # Clean up old deleted files first
    clean_old_deleted_files(DELETED_DIR, days=10)
    
    try:
        os.chdir(path)
    except Exception as e:
        print(f"Failed to change to sync path {path}: {e}")
        return
    # 1. Fetch remote metadata
    print(ctext("\n🔍 Fetching remote metadata...", Fore.BLUE))
    try:
        resp = requests.get(METADATA_URL, timeout=5)
        resp.raise_for_status()
        remote_meta = resp.json()
        print(ctext("✅ Remote metadata fetched successfully", Fore.GREEN))
    except requests.exceptions.RequestException as e:
        print(ctext(f"\n❌ Could not connect to server at {SERVER_IP}:{SERVER_PORT}.", Fore.RED))
        print(ctext(f"Error: {e}\n⬅️  Returning to main menu.", Fore.RED))
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
    if to_download:
        print(ctext(f"\n⬇️  Downloading {len(to_download)} files...", Fore.MAGENTA))
    for name in to_download:
        print(ctext(f"  📥 {name}", Fore.CYAN))
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
    if to_delete:
        print(ctext(f"\n🗑️  Moving {len(to_delete)} files to deleted folder...", Fore.YELLOW))
    for name in to_delete:
        for d in to_upload:
            if d["name"] == name:
                to_upload.remove(d)
                break
        
        # Ask confirmation before deleting PDF files
        if name.lower().endswith('.pdf'):
            while True:
                confirm = input(f"Move PDF file '{name}' to deleted folder? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    break
                elif confirm in ['n', 'no']:
                    print(f"Skipping deletion of {name}")
                    break
                else:
                    print("Please answer y or n.")
            if confirm in ['n', 'no']:
                continue
        
        print(ctext(f"  📁 Moving {name} to deleted folder...", Fore.YELLOW))
        file_path = os.path.join(DOWNLOAD_DIR, name)
        if os.path.exists(file_path):
            if move_to_deleted(file_path, DELETED_DIR):
                print(ctext(f"  ✅ Moved to deleted folder (will be permanently deleted in 10 days)", Fore.GREEN))
            else:
                print(ctext(f"  ❌ Failed to move {name}", Fore.RED))
        else:
            print(ctext(f"  ⚠️  File {name} not found locally", Fore.YELLOW))

    # 5. Upload new/changed (server must implement POST /upload)
    if to_upload:
        print(ctext(f"\n⬆️  Uploading {len(to_upload)} files...", Fore.GREEN))
    for m in to_upload:
        print(ctext(f"  📤 {m['name']}", Fore.GREEN))
        with open(m["name"], "rb") as f:
            files = {"file": f}
            data = {"mtime": str(m["mtime"])}
            upl = requests.post(f"{BASE_URL}/upload", files=files, data=data)
            upl.raise_for_status()

    # 6. Update local metadata
    print(ctext("\n🎉 Sync complete! All files are up to date.", Fore.GREEN))



def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    main_menu()
