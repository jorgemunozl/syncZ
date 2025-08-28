import os
import json
import hashlib
import requests
import sys
import time
import shutil
import argparse
from datetime import datetime, timedelta
import re
import unicodedata
from rich.progress import Progress, BarColumn, TimeRemainingColumn, TransferSpeedColumn
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
try:
    from wcwidth import wcwidth as _wcwidth, wcswidth as _wcswidth
except Exception:
    _wcwidth = None
    _wcswidth = None

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
                    rel = os.path.relpath(file_path, deleted_dir)
                    print(ctext(
                        f"  🗑️  Permanently deleted old file: {rel}",
                        Fore.YELLOW,
                    ))
            except Exception as e:
                print(ctext(f"  ⚠️  Could not delete {file_path}: {e}", Fore.RED))

    if deleted_count > 0:
        print(ctext(
            f"🧹 Cleaned up {deleted_count} files older than {days} days",
            Fore.GREEN,
        ))


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
        print(ctext(
            f"  ❌ Failed to move {file_path} to deleted folder: {e}",
            Fore.RED,
        ))
        return False


def make_session():
    """Create a requests session with retry configuration"""
    session = requests.Session()
    
    # Create a retry strategy
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        backoff_factor=1
    )
    
    # Create an adapter with the retry strategy
    adapter = HTTPAdapter(max_retries=retry_strategy)
    
    # Mount the adapter to the session
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def upload_with_rich(session, file_path, upload_url, server_config, mtime=None):
    """Upload a file with Rich progress bar"""
    try:
        with open(file_path, 'rb') as f:
            # Create the multipart encoder with file and mtime
            fields = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            if mtime:
                fields['mtime'] = str(mtime)
                
            encoder = MultipartEncoder(fields=fields)
            
            # Create progress bar
            progress = Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                "•",
                "[progress.filesize]{task.completed}/{task.total}",
                "•",
                TransferSpeedColumn(),
                "•",
                TimeRemainingColumn(),
            )
            
            with progress:
                task_id = progress.add_task(
                    f"Uploading {os.path.basename(file_path)}",
                    total=encoder.len
                )
                
                def update_progress(monitor):
                    progress.update(task_id, completed=monitor.bytes_read)
                
                # Create monitor to track progress
                monitor = MultipartEncoderMonitor(encoder, update_progress)
                
                # Upload the file
                response = session.post(
                    upload_url,
                    data=monitor,
                    headers={'Content-Type': monitor.content_type},
                    timeout=300
                )
                
                return response
    except Exception as e:
        print(ctext(f"  ❌ Upload failed: {e}", Fore.RED))
        return None


def generate_file_list(root_dir):
    rows = []
    for dirpath, _, filenames in os.walk(root_dir):
        # Skip the deleted directory and its subdirectories
        if "deleted" in os.path.relpath(dirpath, root_dir).split(os.sep):
            continue

        for fname in filenames:
            # Skip hidden files if needed
            if fname.startswith("."):
                continue
            # Skip JSON files
            if fname.lower().endswith('.json'):
                continue
            full = os.path.join(dirpath, fname)
            rows.append({
                "name": os.path.relpath(full, root_dir).replace("\\", "/"),
                "sha256": sha256sum(full),
                "mtime": os.path.getmtime(full)
            })
    return rows


# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
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


def get_primary_ip():
    """Return the primary local IPv4 address used for outbound connections."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    except Exception:
        try:
            import socket
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def show_current_config():
    config = load_config()
    print(ctext("\n" + "=" * 50, Fore.CYAN))
    print(ctext("           CURRENT CONFIGURATION", Fore.GREEN))
    print(ctext("=" * 50, Fore.CYAN))
    # Show local primary IP so the user can verify network details
    local_ip = get_primary_ip()
    print(ctext("🖥 Local IP:    ", Fore.YELLOW) + ctext(local_ip, Fore.WHITE))
    print(
        ctext("📁 Sync Path:   ", Fore.YELLOW)
        + ctext(f"{config.get('path', DEFAULT_PATH)}", Fore.WHITE)
    )
    print(
        ctext("🌐 Server IP:   ", Fore.YELLOW)
        + ctext(f"{config.get('server_ip', DEFAULT_SERVER_IP)}", Fore.WHITE)
    )
    print(
        ctext("🔌 Server Port: ", Fore.YELLOW)
        + ctext(
            f"{config.get('server_port', DEFAULT_SERVER_PORT)}",
            Fore.WHITE,
        )
    )
    print(ctext("=" * 50, Fore.CYAN))


def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def request_metadata_regeneration(base_url):
    """Request the server to regenerate its metadata file"""
    try:
        print(ctext("🔄 Requesting server to regenerate metadata...", Fore.YELLOW))
        response = requests.post(f"{base_url}/regenerate-metadata", timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get("status") == "success":
            print(ctext(f"✅ Server regenerated metadata: {result.get('message')}", Fore.GREEN))
            return True
        else:
            print(ctext(f"⚠️  Server response: {result.get('message')}", Fore.YELLOW))
            return False
    except requests.exceptions.RequestException as e:
        print(ctext(f"⚠️  Could not request metadata regeneration: {e}", Fore.YELLOW))
        return False
    except Exception as e:
        print(ctext(f"⚠️  Error requesting metadata regeneration: {e}", Fore.YELLOW))
        return False


# --- Progress helpers -------------------------------------------------
# Progress helpers
def _format_size(n):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024.0:
            return f"{n:3.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"


def print_progress(name, transferred, total):
    total = int(total) if total else 0
    if total > 0:
        pct = transferred / total
        bar_len = 30
        filled = int(pct * bar_len)
        bar = "█" * filled + "-" * (bar_len - filled)
        left = ctext("  " + name, Fore.CYAN)
        stats = f"{pct*100:6.2f}% |{bar}| {_format_size(transferred)}/{_format_size(total)}"
        sys.stdout.write(f"\r{left} {stats}")
    else:
        # Unknown total size
        left = ctext("  " + name, Fore.CYAN)
        sys.stdout.write(f"\r{left} {_format_size(transferred)} transferred")
    sys.stdout.flush()


class UploadFileWithProgress:
    """
    File-like wrapper for streaming uploads with progress reporting.
    This is a working implementation that properly handles file streaming.
    """
    def __init__(self, path, callback=None):
        self.path = path
        self._file = open(path, 'rb')
        self.callback = callback
        self.total_size = os.path.getsize(path)
        self.bytes_read = 0
        
    def read(self, size=-1):
        """Read data from the file and report progress"""
        data = self._file.read(size)
        if data:
            self.bytes_read += len(data)
            if self.callback:
                self.callback(self.path, self.bytes_read, self.total_size)
        return data
        
    def __len__(self):
        """Return the total file size"""
        return self.total_size
        
    def close(self):
        """Close the underlying file"""
        if hasattr(self, '_file') and self._file:
            self._file.close()
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
NARROW_EMOJI = {"🖥", "⚙"}


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)

# Fallback emoji detection (used only if wcwidth is unavailable)


def _is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x1F300 <= cp <= 0x1F5FF or
        0x1F600 <= cp <= 0x1F64F or
        0x1F680 <= cp <= 0x1F6FF or
        0x1F900 <= cp <= 0x1F9FF or
        0x1FA70 <= cp <= 0x1FAFF or
        0x2600 <= cp <= 0x26FF or
        0x2700 <= cp <= 0x27BF
    )


def _char_width(ch: str) -> int:
    # Handle zero-width characters explicitly in fallback path
    # Variation Selectors and Joiners
    if ord(ch) in (0xFE0E, 0xFE0F, 0x200D, 0x200B, 0x2060):
        return 0
    if _wcwidth is not None:
        w = _wcwidth(ch)
        return w if w > 0 else 0
    # fallback heuristic
    if unicodedata.combining(ch):
        return 0
    if _is_emoji(ch):
        # Some terminals render certain emojis as narrow (width=1)
        if ch in NARROW_EMOJI:
            return 1
        return 2
    eaw = unicodedata.east_asian_width(ch)
    if eaw in ("F", "W"):
        return 2
    return 1


def _count_narrow_emoji_clusters(s: str) -> int:
    count = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in NARROW_EMOJI:
            # Optional variation selector
            if i + 1 < len(s) and s[i + 1] == "\uFE0F":
                i += 2
            else:
                i += 1
            count += 1
            continue
        i += 1
    return count


def visible_width(s: str) -> int:
    s2 = strip_ansi(s)
    if _wcswidth is not None:
        w = _wcswidth(s2)
        if w < 0:
            w = 0
        # Adjust for emojis that render as narrow in many terminals
        w -= _count_narrow_emoji_clusters(s2)
        return max(w, 0)
    return sum(_char_width(ch) for ch in s2)


def _truncate_to_width(text: str, width: int) -> str:
    total = 0
    out = []
    for ch in text:
        w = _char_width(ch)
        if total + w > width:
            break
        out.append(ch)
        total += w
    return "".join(out)


def line_content(text: str, width: int, align: str = "left") -> str:
    text = _truncate_to_width(text, width)
    w = visible_width(text)
    pad = max(0, width - w)
    if align == "center":
        left = pad // 2
        right = pad - left
        return " " * left + text + " " * right
    return text + " " * pad


def box_top(width: int) -> str:
    return ctext("╔" + "═" * width + "╗", Fore.CYAN)


def box_sep(width: int) -> str:
    return ctext("╠" + "═" * width + "╣", Fore.CYAN)


def box_bottom(width: int) -> str:
    return ctext("╚" + "═" * width + "╝", Fore.CYAN)


def box_line(text: str, width: int, content_color=Fore.WHITE, align: str = "left") -> str:
    return (
        ctext("║", Fore.CYAN)
        + ctext(line_content(text, width, align=align), content_color)
        + ctext("║", Fore.CYAN)
    )


def delete_orphan_locals():
    """Mirror server: move local-only files into deleted/ safely."""
    config = load_config()
    path = config.get("path", DEFAULT_PATH)
    SERVER_IP = config.get("server_ip", DEFAULT_SERVER_IP)
    SERVER_PORT = config.get("server_port", DEFAULT_SERVER_PORT)
    BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}"
    METADATA_URL = f"{BASE_URL}/metadata"
    DELETED_DIR = "deleted"

    # Clean up old deleted files first
    clean_old_deleted_files(DELETED_DIR, days=10)

    orig_cwd = os.getcwd()
    try:
        try:
            os.chdir(path)
        except Exception as e:
            print(ctext(f"Failed to change to sync path {path}: {e}", Fore.RED))
            return

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

        # Build indices
        local_meta = generate_file_list(path)
        remote_index = {m["name"]: True for m in remote_meta}

        to_delete = [
            m["name"] for m in local_meta
            if m["name"] != "file_list.json" and m["name"] not in remote_index
        ]

        if not to_delete:
            print(ctext("\n✅ No local orphans to delete. Everything matches the server.", Fore.GREEN))
            return

        print(ctext(f"\n🗑️  Found {len(to_delete)} local files not on server.", Fore.YELLOW))
        proceed = input(ctext("Proceed to move them into 'deleted/'? (y/N): ", Fore.YELLOW)).strip().lower()
        if proceed not in ("y", "yes"):
            print(ctext("Cancelled.", Fore.YELLOW))
            return

        for name in to_delete:
            # Ask confirmation before deleting PDF files
            if name.lower().endswith('.pdf'):
                while True:
                    confirm = input(f"Move PDF file '{name}' to deleted folder? (y/n): ").strip().lower()
                    if confirm in ['y', 'yes']:
                        break
                    elif confirm in ['n', 'no']:
                        print(f"Skipping deletion of {name}")
                        name = None
                        break
                    else:
                        print("Please answer y or n.")
                if not name:
                    continue

            print(ctext(f"  📁 Moving {name} to deleted folder...", Fore.YELLOW))
            file_path = os.path.join(".", name)
            if os.path.exists(file_path):
                if move_to_deleted(file_path, DELETED_DIR):
                    print(ctext("  ✅ Moved (permanent deletion in 10 days)", Fore.GREEN))
                else:
                    print(ctext(f"  ❌ Failed to move {name}", Fore.RED))
            else:
                print(ctext(f"  ⚠️  File {name} not found locally", Fore.YELLOW))
    finally:
        try:
            os.chdir(orig_cwd)
        except Exception:
            pass


def preview_sync():
    """Preview files to be uploaded, downloaded, deleted without sync"""
    config = load_config()
    path = config.get("path", DEFAULT_PATH)
    SERVER_IP = config.get("server_ip", DEFAULT_SERVER_IP)
    SERVER_PORT = config.get("server_port", DEFAULT_SERVER_PORT)
    BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}"
    METADATA_URL = f"{BASE_URL}/metadata"

    orig_cwd = os.getcwd()
    try:
        try:
            os.chdir(path)
        except Exception as e:
            msg = f"Failed to change to sync path {path}: {e}"
            print(ctext(msg, Fore.RED))
            return

        # 1. Fetch remote metadata
        msg = "\n🔍 Fetching remote metadata for preview..."
        print(ctext(msg, Fore.BLUE))
        try:
            resp = requests.get(METADATA_URL, timeout=5)
            resp.raise_for_status()
            remote_meta = resp.json()
            print(ctext("✅ Remote metadata fetched successfully",
                        Fore.GREEN))
        except requests.exceptions.RequestException as e:
            msg = f"\n❌ Could not connect to server at {SERVER_IP}:{SERVER_PORT}."
            print(ctext(msg, Fore.RED))
            print(ctext(f"Error: {e}\n⬅️  Returning to main menu.",
                        Fore.RED))
            time.sleep(2)
            return

        # 2. Compute local metadata
        local_meta = generate_file_list(path)

        remote_index = {
            m["name"]: (m["sha256"], m.get("mtime", 0))
            for m in remote_meta
            if not m["name"].lower().endswith('.json')
        }
        local_index = {
            m["name"]: (m["sha256"], m.get("mtime", 0))
            for m in local_meta
            if not m["name"].lower().endswith('.json')
        }

        # 3. Calculate what would be downloaded
        to_download = [
            name for name, (remote_hash, remote_mtime) in remote_index.items()
            if (
                name not in local_index or
                local_index[name][1] < remote_mtime
            )
        ]

        # 4. Find orphaned files first (local files not on server)
        orphans = [
            m for m in local_meta
            if (
                not m["name"].lower().endswith('.json')
                and m["name"] not in remote_index
            )
        ]

        # 5. Calculate what would be uploaded (EXCLUDING orphans)
        to_upload = [
            m for m in local_meta
            if (
                not m["name"].lower().endswith('.json')
                and m["name"] in remote_index  # Only files that exist on server
                and (
                    remote_index.get(m["name"], ("", 0))[0] != m["sha256"] or
                    remote_index.get(m["name"], ("", 0))[1] < m["mtime"]
                )
            )
        ]

        # 6. Display preview results
        print(ctext("\n" + "=" * 60, Fore.CYAN))
        print(ctext("📋 SYNC PREVIEW - Files that would be affected",
                    Fore.CYAN))
        print(ctext("=" * 60, Fore.CYAN))

        # Downloads
        if to_download:
            msg = f"\n⬇️  DOWNLOADS ({len(to_download)} files):"
            print(ctext(msg, Fore.MAGENTA))
            for name in to_download:
                if name in local_index:
                    reason = "Local file is older"
                else:
                    reason = "New file from server"
                print(ctext(f"  📥 {name}", Fore.CYAN))
                print(ctext(f"      Reason: {reason}", Fore.WHITE))
        else:
            print(ctext("\n⬇️  DOWNLOADS: None", Fore.GREEN))

        # Uploads
        if to_upload:
            msg = f"\n⬆️  UPLOADS ({len(to_upload)} files):"
            print(ctext(msg, Fore.GREEN))
            for m in to_upload:
                name = m["name"]
                if name in remote_index:
                    local_hash = m["sha256"]
                    local_mtime = m["mtime"]
                    remote_hash, remote_mtime = remote_index[name]
                    
                    reasons = []
                    if local_hash != remote_hash:
                        reasons.append("Hash differs")
                    if local_mtime > remote_mtime:
                        reasons.append("Local newer")
                    reason = (", ".join(reasons) if reasons
                              else "Different content")
                else:
                    reason = "New file (not on server)"
                
                print(ctext(f"  📤 {name}", Fore.CYAN))
                print(ctext(f"      Reason: {reason}", Fore.WHITE))
        else:
            print(ctext("\n⬆️  UPLOADS: None", Fore.GREEN))

        # Orphaned files (would require user decision)
        if orphans:
            msg = (f"\n🤔 ORPHANED FILES ({len(orphans)} files) "
                   "- User decision required:")
            print(ctext(msg, Fore.YELLOW))
            msg = "    These files exist locally but not on server:"
            print(ctext(msg, Fore.WHITE))
            for m in orphans:
                print(ctext(f"  📄 {m['name']}", Fore.CYAN))
            msg = ("\n    📝 Note: In interactive mode, "
                   "you'll be asked whether to:")
            print(ctext(msg, Fore.WHITE))
            print(ctext("         • Upload each file to server", Fore.WHITE))
            print(ctext("         • Move to deleted folder", Fore.WHITE))
            print(ctext("         • Skip (leave as-is)", Fore.WHITE))
            msg = ("    🤖 CLI modes: Use -cu (auto-upload) "
                   "or -cd (auto-delete)")
            print(ctext(msg, Fore.WHITE))
        else:
            print(ctext("\n🤔 ORPHANED FILES: None", Fore.GREEN))

        # Summary
        total_changes = len(to_download) + len(to_upload) + len(orphans)
        print(ctext("\n📊 SUMMARY:", Fore.CYAN))
        print(ctext(f"    Downloads: {len(to_download)} files", Fore.WHITE))
        print(ctext(f"    Uploads:   {len(to_upload)} files", Fore.WHITE))
        msg = f"    Orphans:   {len(orphans)} files (need decision)"
        print(ctext(msg, Fore.WHITE))
        msg = f"    Total:     {total_changes} files would be affected"
        print(ctext(msg, Fore.WHITE))

        if total_changes == 0:
            print(ctext("\n🎉 All files are already synchronized!",
                        Fore.GREEN))
        else:
            msg = "\n💡 To perform actual sync, use option 1 (Merge)"
            print(ctext(msg, Fore.YELLOW))

        print(ctext("\n" + "=" * 60, Fore.CYAN))
        input(ctext("\nPress Enter to return to main menu...", Fore.YELLOW))

    finally:
        try:
            os.chdir(orig_cwd)
        except Exception:
            pass


def main_menu():
    show_current_config()
    width = 48
    while True:
        print(ctext("\n" + box_top(width), None))
        print(
            box_line(
                "SyncZ Main Menu",
                width,
                content_color=Fore.GREEN,
                align="center",
            )
        )
        print(box_sep(width))
        print(box_line("1) 🔀 Merge", width))
        print(box_line("2) 🖥 Start Server", width))
        print(box_line("3) ⚙ Change config (path/ip/port)", width))
        print(box_line("4) 📤 Push (delete local orphans)", width))
        print(box_line("5) 📋 Preview (show planned changes)", width))
        print(box_line("q) 🚪 Quit", width))
        print(box_bottom(width))

        choice = input(ctext("Choose an option: ", Fore.YELLOW)).strip().lower()
        if choice == "1":
            do_sync()
        elif choice == "2":
            start_server()
        elif choice == "3":
            change_config()
            show_current_config()  # Show updated config after changes
        elif choice == "4":
            delete_orphan_locals()
        elif choice == "5":
            preview_sync()
        elif choice == "q":
            print(ctext("\n👋 Goodbye! Exiting SyncZ...", Fore.GREEN))
            sys.exit(0)
        else:
            print(ctext("❌ Invalid option. Please try again.", Fore.RED))


def change_config():
    config = load_config()
    print(f"Current path: {config.get('path', DEFAULT_PATH)}")
    print("Options: press Enter to keep current, or 't' for Termux preset")
    print("Termux preset path: /root/shared/zoteroReference")
    new_path = input("New sync path or shortcut: ").strip()
    if new_path.lower() in ("t", "termux"):
        config["path"] = "/root/shared/zoteroReference"
    elif new_path:
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


def do_sync(auto_upload=False, auto_delete=False):
    config = load_config()
    path = config.get("path", DEFAULT_PATH)
    SERVER_IP = config.get("server_ip", DEFAULT_SERVER_IP)
    SERVER_PORT = config.get("server_port", DEFAULT_SERVER_PORT)
    BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}"
    METADATA_URL = f"{BASE_URL}/metadata"
    # Note: we intentionally do not define LOCAL_JSON or a download dir here,
    # as we no longer perform local deletions based on server state.
    DELETED_DIR = "deleted"

    # Clean up old deleted files first
    clean_old_deleted_files(DELETED_DIR, days=10)

    orig_cwd = os.getcwd()
    try:
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

        remote_index = {
            m["name"]: (m["sha256"], m.get("mtime", 0))
            for m in remote_meta
            if not m["name"].lower().endswith('.json')
        }
        local_index = {
            m["name"]: (m["sha256"], m.get("mtime", 0))
            for m in local_meta
            if not m["name"].lower().endswith('.json')
        }

        to_download = [
            name for name, (remote_hash, remote_mtime) in remote_index.items()
            if (
                name not in local_index or
                local_index[name][1] < remote_mtime
            )
        ]

        # Find orphaned files first (local files not on server)
        orphans = [
            m for m in local_meta
            if (
                not m["name"].lower().endswith('.json')
                and m["name"] not in remote_index
            )
        ]

        # Build upload list, EXCLUDING orphans (they'll be handled separately)
        to_upload = [
            m for m in local_meta
            if (
                not m["name"].lower().endswith('.json')
                and m["name"] in remote_index  # Only files that exist on server
                and (
                    remote_index.get(m["name"], ("", 0))[0] != m["sha256"] or
                    remote_index.get(m["name"], ("", 0))[1] < m["mtime"]
                )
            )
        ]
        
        # Debug: Show detailed upload reasons
        if to_upload:
            print(ctext("\n🔍 DEBUG: Files marked for upload:", Fore.YELLOW))
            for m in to_upload:
                name = m["name"]
                local_hash = m["sha256"]
                local_mtime = m["mtime"]

                if name in remote_index:
                    remote_hash, remote_mtime = remote_index[name]
                    hash_diff = local_hash != remote_hash
                    time_diff = local_mtime > remote_mtime

                    print(ctext(f"  📄 {name}:", Fore.CYAN))
                    reason_parts = []
                    if hash_diff:
                        reason_parts.append('Hash differs')
                    if time_diff:
                        reason_parts.append('Local newer')
                    print(ctext(f"    Reason: {', '.join(reason_parts)}", Fore.CYAN))
                    print(ctext(f"    Local:  {local_hash[:12]}... @ {local_mtime}", Fore.CYAN))
                    print(ctext(f"    Remote: {remote_hash[:12]}... @ {remote_mtime}", Fore.CYAN))
                    print(ctext(f"    Time diff: {local_mtime - remote_mtime:.6f}s", Fore.CYAN))
                else:
                    print(ctext(f"  📄 {name}: New file (not on server)", Fore.CYAN))

        # Handle orphan files (local files not on server)
        if orphans:
            print(
                ctext(
                    f"\nFound {len(orphans)} local files not on server.",
                    Fore.YELLOW,
                )
            )
            
            if auto_upload:
                msg = "🤖 Auto-upload mode: uploading all orphaned files..."
                print(ctext(msg, Fore.CYAN))
                for m in orphans:
                    if not any(x["name"] == m["name"] for x in to_upload):
                        to_upload.append(m)
                        msg = f"  ⬆️  Queued for upload: {m['name']}"
                        print(ctext(msg, Fore.GREEN))
            elif auto_delete:
                msg = ("🤖 Auto-delete mode: moving all orphaned files "
                       "to deleted folder...")
                print(ctext(msg, Fore.CYAN))
                for m in orphans:
                    name = m["name"]
                    # No need to remove from upload list since orphans
                    # are not in upload list anymore
                    
                    # Move file to deleted folder
                    fp = os.path.join(".", name)
                    msg = f"  📁 Moving {name} to deleted folder..."
                    print(ctext(msg, Fore.YELLOW))
                    if os.path.exists(fp):
                        if move_to_deleted(fp, DELETED_DIR):
                            print(
                                ctext(
                                    "  ✅ Moved (delete in 10 days)",
                                    Fore.GREEN,
                                )
                            )
                        else:
                            msg = f"  ❌ Failed to move {name}"
                            print(ctext(msg, Fore.RED))
                    else:
                        warn = f"  ⚠️  File {name} not found locally"
                        print(ctext(warn, Fore.YELLOW))
            else:
                msg = "Decide for each: upload, delete, or skip."
                print(ctext(msg, Fore.YELLOW))
                for m in orphans:
                    name = m["name"]
                    while True:
                        prompt = (
                            f"Orphan: '{name}' -> "
                            + "[u]pload/[d]elete/[s]kip? (u/d/s): "
                        )
                        ans = input(prompt).strip().lower()
                        if ans in ("u", "d", "s"):
                            break
                        print("Please answer u, d, or s.")

                    if ans == "u":
                        # Add to upload list (orphans not in upload by default)
                        if not any(x["name"] == name for x in to_upload):
                            to_upload.append(m)
                    elif ans == "d":
                        # Ask confirmation for PDFs
                        if name.lower().endswith(".pdf"):
                            c = input(
                                f"Move PDF '{name}' to deleted folder? (y/n): "
                            ).strip().lower()
                            if c not in ("y", "yes"):
                                print("Skipped.")
                                continue
                        
                        # Move file to deleted folder (no need to remove from
                        # upload list since orphans are not in upload list)
                        fp = os.path.join(".", name)
                        msg = f"  📁 Moving {name} to deleted folder..."
                        print(ctext(msg, Fore.YELLOW))
                        if os.path.exists(fp):
                            if move_to_deleted(fp, DELETED_DIR):
                                print(
                                    ctext(
                                        "  ✅ Moved (delete in 10 days)",
                                        Fore.GREEN,
                                    )
                                )
                            else:
                                msg = f"  ❌ Failed to move {name}"
                                print(ctext(msg, Fore.RED))
                        else:
                            warn = f"  ⚠️  File {name} not found locally"
                            print(ctext(warn, Fore.YELLOW))
                    # For skip option, do nothing (orphan stays as-is)

        # Debug: Show final upload list after processing orphans
        if to_upload:
            print(ctext(f"\n📋 Final upload queue: {len(to_upload)} files", Fore.CYAN))
            for m in to_upload:
                print(ctext(f"  • {m['name']}", Fore.CYAN))

        # 4. Download missing/changed
        if to_download:
            msg = f"\n⬇️  Downloading {len(to_download)} files..."
            print(ctext(msg, Fore.MAGENTA))
            for name in to_download:
                print(ctext(f"  📥 {name}", Fore.CYAN))
                dir_name = os.path.dirname(name)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                dl = requests.get(f"{BASE_URL}/{name}", stream=True)
                dl.raise_for_status()
                total = int(dl.headers.get("Content-Length", 0) or 0)
                transferred = 0
                with open(name, "wb") as f:
                    for chunk in dl.iter_content(4096):
                        if not chunk:
                            continue
                        f.write(chunk)
                        transferred += len(chunk)
                        print_progress(name, transferred, total)
                # Ensure final progress line ends and print a newline
                sys.stdout.write("\n")
                orig_mtime = remote_index[name][1]
                os.utime(name, (orig_mtime, orig_mtime))

        # Important: do not delete local-only files.
        # If a file exists locally but not on the server, treat it as a
        # candidate for upload (two-way sync behavior).
        # Deletions would require explicit tombstones or a force-mirror mode,
        # which we do not implement here to avoid accidental data loss.

        # 5. Upload new/changed (server must implement POST /upload)
        if to_upload:
            print(ctext(f"\n⬆️  Uploading {len(to_upload)} files...", Fore.GREEN))
            
            # Create session with retry configuration
            session = make_session()
            
            for m in to_upload:
                # Skip files that no longer exist (e.g., moved to deleted folder)
                if not os.path.exists(m["name"]):
                    print(ctext(f"  ⏭️  Skipping {m['name']} (file not found)", Fore.YELLOW))
                    continue
                    
                print(ctext(f"  📤 {m['name']}", Fore.GREEN))
                
                try:
                    # Use Rich progress bar for upload
                    response = upload_with_rich(session, m["name"], f"{BASE_URL}/upload", config, m["mtime"])
                    
                    if response and response.status_code == 200:
                        print(ctext("    ✅ Uploaded successfully", Fore.GREEN))
                    else:
                        status = response.status_code if response else 'No response'
                        print(ctext(f"    ❌ Upload failed with status: {status}", Fore.RED))
                    
                except requests.exceptions.Timeout:
                    print(ctext("    ⏰ Upload timed out", Fore.YELLOW))
                    print(ctext(f"    ⏰ Upload timeout for {m['name']}", Fore.RED))
                    continue
                except requests.exceptions.ConnectionError:
                    print()  # New line after progress bar
                    print(ctext(f"    🔌 Connection error for {m['name']}", Fore.RED))
                    continue
                except requests.exceptions.RequestException as e:
                    print()  # New line after progress bar
                    print(ctext(f"    ❌ Request error for {m['name']}: {e}", Fore.RED))
                    continue
                except Exception as e:
                    print()  # New line after progress bar
                    print(ctext(f"    ❌ Unexpected error for {m['name']}: {e}", Fore.RED))
                    continue

        # 6. Update local metadata
        print(ctext("\n🎉 Sync complete! All files are up to date.", Fore.GREEN))
        
        # 7. Request server to regenerate metadata if any files were uploaded or downloaded
        if to_upload or to_download:
            request_metadata_regeneration(BASE_URL)
    finally:
        # Always restore original working directory after sync
        try:
            os.chdir(orig_cwd)
        except Exception:
            pass


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="SyncZ - File synchronization tool",
        prog="syncz"
    )
    
    # Main action flags
    parser.add_argument('-c', '--sync', action='store_true',
                        help='Run sync operation')
    parser.add_argument('-u', '--upload', action='store_true',
                        help='Auto-upload orphaned files (use with -c)')
    parser.add_argument('-d', '--delete', action='store_true',
                        help='Auto-delete orphaned files (use with -c)')
    parser.add_argument('-p', '--preview', action='store_true',
                        help='Preview changes without performing sync')
    
    # Configuration flags
    parser.add_argument('--config', action='store_true',
                        help='Show configuration menu')
    parser.add_argument('--server', action='store_true',
                        help='Start server')
    parser.add_argument('--push', action='store_true',
                        help='Push mode (delete local orphans)')
    
    return parser.parse_args()


def main():
    """Main entry point that handles both CLI and interactive modes"""
    args = parse_arguments()
    
    # Handle command-line interface
    if len(sys.argv) > 1:
        if args.sync:
            # Validate conflicting flags
            if args.upload and args.delete:
                msg = ("❌ Error: Cannot use both --upload and --delete "
                       "flags together")
                print(ctext(msg, Fore.RED))
                sys.exit(1)
            
            # Display mode information
            if args.upload:
                print(ctext("🤖 SyncZ Auto-Upload Mode (-cu)", Fore.CYAN))
                msg = "   All orphaned files will be automatically uploaded"
                print(ctext(msg, Fore.CYAN))
            elif args.delete:
                print(ctext("🤖 SyncZ Auto-Delete Mode (-cd)", Fore.CYAN))
                msg = ("   All orphaned files will be automatically moved "
                       "to deleted folder")
                print(ctext(msg, Fore.CYAN))
            else:
                print(ctext("🔄 SyncZ Interactive Sync Mode", Fore.CYAN))
            
            # Run sync with appropriate flags
            do_sync(auto_upload=args.upload, auto_delete=args.delete)
            
        elif args.preview:
            print(ctext("👁️  SyncZ Preview Mode", Fore.CYAN))
            msg = "   Showing changes without performing sync"
            print(ctext(msg, Fore.CYAN))
            preview_sync()
            
        elif args.config:
            show_current_config()
            change_config()
            show_current_config()
            
        elif args.server:
            start_server()
            
        elif args.push:
            delete_orphan_locals()
            
        else:
            # Show help if no valid action specified
            parse_arguments().print_help()
    else:
        # No arguments provided, run interactive mode
        main_menu()


if __name__ == "__main__":
    main()
