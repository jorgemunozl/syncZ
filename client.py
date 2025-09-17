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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests_toolbelt.multipart.encoder import MultipartEncoder
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


def detect_moves(local_meta, remote_meta):
    """Detect file moves by comparing SHA256 hashes between local and remote"""
    # Create hash-to-path mappings
    local_hash_to_path = {}
    remote_hash_to_path = {}
    
    for m in local_meta:
        if not m["name"].lower().endswith('.json'):
            hash_val = m["sha256"]
            if hash_val not in local_hash_to_path:
                local_hash_to_path[hash_val] = []
            local_hash_to_path[hash_val].append(m["name"])
    
    for m in remote_meta:
        if not m["name"].lower().endswith('.json'):
            hash_val = m["sha256"]
            if hash_val not in remote_hash_to_path:
                remote_hash_to_path[hash_val] = []
            remote_hash_to_path[hash_val].append(m["name"])
    
    # Detect moves: same hash, different paths
    moves = []
    
    # Check for files that moved from remote to local (need to move locally)
    for hash_val, remote_paths in remote_hash_to_path.items():
        if hash_val in local_hash_to_path:
            local_paths = local_hash_to_path[hash_val]
            
            # Find paths that exist on remote but not locally (potential moves)
            for remote_path in remote_paths:
                if remote_path not in local_paths:
                    # Check if there's a local path with same hash but 
                    # different location
                    for local_path in local_paths:
                        if local_path not in remote_paths:
                            # This is a move: remote_path -> local_path
                            moves.append({
                                'type': 'remote_to_local',
                                'hash': hash_val,
                                'from_path': remote_path,
                                'to_path': local_path,
                                'action': 'move_local'  # Move file locally to match remote
                            })
                            break
    
    # Check for files that moved from local to remote (need to move on server)
    for hash_val, local_paths in local_hash_to_path.items():
        if hash_val in remote_hash_to_path:
            remote_paths = remote_hash_to_path[hash_val]
            
            # Find paths that exist locally but not remotely (potential moves)
            for local_path in local_paths:
                if local_path not in remote_paths:
                    # Check if there's a remote path with same hash but different location
                    for remote_path in remote_paths:
                        if remote_path not in local_paths:
                            # This is a move: local_path -> remote_path
                            # Check if we haven't already processed this move
                            move_exists = any(
                                m['type'] == 'local_to_remote' and 
                                m['from_path'] == local_path and 
                                m['to_path'] == remote_path
                                for m in moves
                            )
                            if not move_exists:
                                moves.append({
                                    'type': 'local_to_remote',
                                    'hash': hash_val,
                                    'from_path': local_path,
                                    'to_path': remote_path,
                                    'action': 'move_remote'  # Move file on server
                                })
                            break
    
    return moves


def ctext(text, color=None):
    """Apply color to text if colorama is available"""
    if COLOR_ENABLED and color:
        return color + text + Style.RESET_ALL
    return text


def format_file_size(size_bytes):
    """Format file size in human-readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    if i == 0:  # Bytes
        return f"{int(size)} {size_names[i]}"
    else:
        return f"{size:.2f} {size_names[i]}"


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
    """Upload a file without showing progress bars (silent upload)."""
    try:
        with open(file_path, 'rb') as f:
            # Create the multipart encoder with file and optional mtime
            fields = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            if mtime:
                fields['mtime'] = str(mtime)

            encoder = MultipartEncoder(fields=fields)

            # Perform upload without progress monitoring
            response = session.post(
                upload_url,
                data=encoder,
                headers={'Content-Type': encoder.content_type},
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

# Consider small timestamp differences as equal to avoid ping-pong updates
TIMESTAMP_TOLERANCE = 1.0  # seconds


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


def request_file_move(base_url, from_path, to_path):
    """Request server to move a file from one path to another"""
    move_url = f"{base_url}/move"
    move_data = {
        "from_path": from_path,
        "to_path": to_path
    }
    
    try:
        response = requests.post(move_url, json=move_data, timeout=10)
        if response.status_code == 200:
            print(ctext(f"✅ Server moved: {from_path} → {to_path}", Fore.GREEN))
            return True
        else:
            print(ctext(f"❌ Server move failed: {response.status_code}", Fore.RED))
            return False
    except requests.exceptions.RequestException as e:
        print(ctext(f"❌ Move request failed: {e}", Fore.RED))
        return False


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
# Progress bar utilities removed as part of simplifying output (no progress bars)


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
    """Enhanced configuration interface with beautiful formatting"""
    config = load_config()
    width = 48
    
    while True:
        # Display current configuration in a beautiful box
        print(ctext("\n" + box_top(width), None))
        print(box_line("⚙️  SyncZ Configuration", width,
                       content_color=Fore.YELLOW, align="center"))
        print(box_sep(width))
        
        # Current settings
        current_path = config.get('path', DEFAULT_PATH)
        current_ip = config.get('server_ip', DEFAULT_SERVER_IP)
        current_port = config.get('server_port', DEFAULT_SERVER_PORT)
        
        print(box_line(f"📁 Sync Path: {current_path}", width,
                       content_color=Fore.WHITE))
        print(box_line(f"🌐 Server IP: {current_ip}", width,
                       content_color=Fore.WHITE))
        print(box_line(f"🔌 Server Port: {current_port}", width,
                       content_color=Fore.WHITE))
        
        print(box_sep(width))
        print(box_line("1) 📁 Change sync path", width))
        print(box_line("2) 🌐 Change server IP", width))
        print(box_line("3) 🔌 Change server port", width))
        print(box_line("4) 📱 Use Termux preset", width))
        print(box_line("5) 💾 Save and exit", width))
        print(box_line("q) 🚪 Exit without saving", width))
        print(box_bottom(width))
        
        choice = input(ctext("Choose an option: ", Fore.YELLOW))
        choice = choice.strip().lower()
        
        if choice == "1":
            print(ctext("\n📁 Configure Sync Path", Fore.CYAN))
            print(ctext(f"Current: {current_path}", Fore.WHITE))
            prompt = "Enter new path (or press Enter to keep current):"
            print(ctext(prompt, Fore.YELLOW))
            new_path = input(ctext("Path: ", Fore.GREEN)).strip()
            if new_path:
                if os.path.exists(new_path):
                    config["path"] = new_path
                    print(ctext("✅ Path updated successfully!", Fore.GREEN))
                else:
                    create_prompt = "Path doesn't exist. Create it? (y/n): "
                    create = input(ctext(create_prompt, Fore.YELLOW))
                    if create.lower() in ('y', 'yes'):
                        try:
                            os.makedirs(new_path, exist_ok=True)
                            config["path"] = new_path
                            msg = "✅ Path created and updated successfully!"
                            print(ctext(msg, Fore.GREEN))
                        except Exception as e:
                            err_msg = f"❌ Error setting path: {e}"
                            print(ctext(err_msg, Fore.RED))
                    else:
                        print(ctext("❌ Path not changed.", Fore.YELLOW))
            else:
                print(ctext("📁 Path unchanged.", Fore.BLUE))
                
        elif choice == "2":
            print(ctext("\n🌐 Configure Server IP", Fore.CYAN))
            print(ctext(f"Current: {current_ip}", Fore.WHITE))
            print(ctext("Common options:", Fore.YELLOW))
            print(ctext("  127.0.0.1  - Local only", Fore.WHITE))
            print(ctext("  192.168.x.x - Local network", Fore.WHITE))
            new_ip = input(ctext("New IP (or press Enter to keep): ",
                                 Fore.GREEN)).strip()
            if new_ip:
                # Basic IP validation
                parts = new_ip.split('.')
                is_valid = (len(parts) == 4 and
                            all(part.isdigit() and 0 <= int(part) <= 255
                                for part in parts))
                if is_valid:
                    config["server_ip"] = new_ip
                    print(ctext("✅ Server IP updated successfully!",
                                Fore.GREEN))
                else:
                    err_msg = "❌ Invalid IP format. Please use x.x.x.x format."
                    print(ctext(err_msg, Fore.RED))
            else:
                print(ctext("🌐 IP unchanged.", Fore.BLUE))
                
        elif choice == "3":
            print(ctext("\n🔌 Configure Server Port", Fore.CYAN))
            print(ctext(f"Current: {current_port}", Fore.WHITE))
            print(ctext("Common ports: 8000, 8080, 3000, 5000", Fore.YELLOW))
            new_port = input(ctext("New port (or press Enter to keep): ",
                                   Fore.GREEN)).strip()
            if new_port:
                try:
                    port_num = int(new_port)
                    if 1 <= port_num <= 65535:
                        config["server_port"] = port_num
                        print(ctext("✅ Server port updated successfully!",
                                    Fore.GREEN))
                    else:
                        err_msg = "❌ Port must be between 1 and 65535."
                        print(ctext(err_msg, Fore.RED))
                except ValueError:
                    print(ctext("❌ Invalid port number.", Fore.RED))
            else:
                print(ctext("🔌 Port unchanged.", Fore.BLUE))
                
        elif choice == "4":
            print(ctext("\n📱 Applying Termux Preset...", Fore.CYAN))
            termux_path = "/root/shared/zoteroReference"
            config["path"] = termux_path
            config["server_ip"] = "192.168.43.119"  # Common mobile hotspot IP
            config["server_port"] = 8000
            print(ctext("✅ Termux preset applied:", Fore.GREEN))
            print(ctext(f"  📁 Path: {termux_path}", Fore.WHITE))
            print(ctext("  🌐 IP: 192.168.43.119", Fore.WHITE))
            print(ctext("  🔌 Port: 8000", Fore.WHITE))
            
        elif choice == "5":
            # Save configuration
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                print(ctext("\n💾 Configuration saved successfully!",
                            Fore.GREEN))
                break
            except Exception as e:
                print(ctext(f"❌ Error saving config: {e}", Fore.RED))
                
        elif choice == "q":
            print(ctext("\n🚪 Exiting without saving changes.", Fore.YELLOW))
            break
            
        else:
            print(ctext("❌ Invalid option. Please try again.", Fore.RED))
        
        input(ctext("\nPress Enter to continue...", Fore.CYAN))


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

        # 3. Detect file moves before other operations
        print(ctext("\n🔍 Detecting file moves...", Fore.BLUE))
        moves = detect_moves(local_meta, remote_meta)
        
        if moves:
            print(ctext(f"\n📋 Detected {len(moves)} file moves:", Fore.CYAN))
            for move in moves:
                from_path = move['from_path']
                to_path = move['to_path']
                print(ctext(f"  🔄 {from_path} → {to_path}", Fore.CYAN))
                
                if move['action'] == 'move_remote':
                    # File moved locally, need to move on server
                    success = request_file_move(BASE_URL, from_path, to_path)
                    if not success:
                        print(ctext("  ❌ Failed to move on server", Fore.RED))
                        
                elif move['action'] == 'move_local':
                    # File moved on server, need to move locally
                    try:
                        # Create destination directory if needed
                        os.makedirs(os.path.dirname(to_path), exist_ok=True)
                        
                        # Move the local file
                        if os.path.exists(from_path):
                            os.rename(from_path, to_path)
                            msg = f"  ✅ Moved locally: {from_path} → {to_path}"
                            print(ctext(msg, Fore.GREEN))
                        else:
                            msg = f"  ⚠️  Source file not found: {from_path}"
                            print(ctext(msg, Fore.YELLOW))
                            
                    except OSError as e:
                        msg = f"  ❌ Failed to move locally: {e}"
                        print(ctext(msg, Fore.RED))
        else:
            print(ctext("✅ No file moves detected", Fore.GREEN))

        # 4. Rebuild indices after moves
        if moves:
            print(ctext("\n🔄 Refreshing metadata after moves...", Fore.BLUE))
            # Regenerate local metadata after moves
            local_meta = generate_file_list(path)
            # Request server to regenerate metadata
            request_metadata_regeneration(BASE_URL)
            # Fetch updated remote metadata
            try:
                resp = requests.get(METADATA_URL, timeout=5)
                resp.raise_for_status()
                remote_meta = resp.json()
            except requests.exceptions.RequestException:
                msg = "⚠️  Could not fetch updated remote metadata"
                print(ctext(msg, Fore.YELLOW))

        remote_index = {
            m["name"]: (m["sha256"], m.get("mtime", 0.0))
            for m in remote_meta
            if not m["name"].lower().endswith('.json')
        }
        local_index = {
            m["name"]: (m["sha256"], m.get("mtime", 0.0))
            for m in local_meta
            if not m["name"].lower().endswith('.json')
        }

        # Determine actions using timestamps with tolerance to avoid oscillation
        to_download = []
        conflicts = []  # equal timestamp but different hash
        for name, (remote_hash, remote_mtime) in remote_index.items():
            if name not in local_index:
                to_download.append(name)
                continue
            local_hash, local_mtime = local_index[name]
            if (remote_mtime - local_mtime) > TIMESTAMP_TOLERANCE:
                to_download.append(name)
            elif abs(remote_mtime - local_mtime) <= TIMESTAMP_TOLERANCE and remote_hash != local_hash:
                # Conflict: same time but different content -> prefer server by default
                conflicts.append(name)
                to_download.append(name)

        # Find orphaned files first (local files not on server)
        orphans = [
            m for m in local_meta
            if (
                not m["name"].lower().endswith('.json')
                and m["name"] not in remote_index
            )
        ]

        # Build upload list only when local is newer by tolerance
        to_upload = []
        for m in local_meta:
            name = m["name"]
            if name.lower().endswith('.json'):
                continue
            if name in remote_index:
                remote_hash, remote_mtime = remote_index[name]
                local_hash, local_mtime = m["sha256"], m.get("mtime", 0.0)
                if (local_mtime - remote_mtime) > TIMESTAMP_TOLERANCE:
                    to_upload.append(m)
                # If timestamps are equal within tolerance but hashes differ, we already chose download
            # Orphans are handled separately below
        
        # Debug: Show detailed upload reasons
        if to_upload:
            print(ctext("\n🔍 DEBUG: Files marked for upload:", Fore.YELLOW))
            for m in to_upload:
                name = m["name"]
                local_hash = m["sha256"]
                local_mtime = m.get("mtime", 0.0)
                if name in remote_index:
                    remote_hash, remote_mtime = remote_index[name]
                    print(ctext(f"  📄 {name}:", Fore.CYAN))
                    reason = "Local newer"
                    print(ctext(f"    Reason: {reason}", Fore.CYAN))
                    print(ctext(f"    Local:  {local_hash[:12]}... @ {local_mtime}", Fore.CYAN))
                    print(ctext(f"    Remote: {remote_hash[:12]}... @ {remote_mtime}", Fore.CYAN))
                    print(ctext(f"    Time diff: {local_mtime - remote_mtime:.6f}s", Fore.CYAN))

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

        # Ensure no file is both in download and upload lists
        to_download_set = set(to_download)
        to_upload = [m for m in to_upload if m["name"] not in to_download_set]

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
                orig_mtime = remote_index[name][1]
                os.utime(name, (orig_mtime, orig_mtime))
                
                # Show download success with file size
                try:
                    file_size = os.path.getsize(name)
                    file_size_readable = format_file_size(file_size)
                    msg = (f"    ✅ Downloaded successfully "
                           f"({file_size_readable})")
                    print(ctext(msg, Fore.GREEN))
                except OSError:
                    msg = "    ✅ Downloaded successfully"
                    print(ctext(msg, Fore.GREEN))

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
            
            for i, m in enumerate(to_upload, 1):
                # Skip files that no longer exist (e.g., moved to deleted folder)
                if not os.path.exists(m["name"]):
                    msg = f"  ⏭️  Skipping {m['name']} (file not found)"
                    print(ctext(msg, Fore.YELLOW))
                    continue
                
                # Get file size for upload message
                try:
                    file_size = os.path.getsize(m["name"])
                    file_size_readable = format_file_size(file_size)
                    filename = m['name']
                    count_info = f"[{i}/{len(to_upload)}]"
                    size_info = f"({file_size_readable})"
                    msg = f"  📤 {count_info} {filename} {size_info}"
                    print(ctext(msg, Fore.GREEN))
                except OSError:
                    msg = f"  📤 [{i}/{len(to_upload)}] {m['name']}"
                    print(ctext(msg, Fore.GREEN))
                
                try:
                    # Perform upload without a progress bar
                    upload_url = f"{BASE_URL}/upload"
                    response = upload_with_rich(session, m["name"], upload_url,
                                                config, m["mtime"])
                    
                    if response and response.status_code == 200:
                        # Get file size for success message
                        try:
                            file_size = os.path.getsize(m["name"])
                            size_readable = format_file_size(file_size)
                            msg = f"    ✅ Upload completed ({size_readable})"
                            print(ctext(msg, Fore.GREEN))
                        except OSError:
                            print(ctext("    ✅ Upload completed", Fore.GREEN))
                    else:
                        status = response.status_code if response else 'None'
                        msg = f"    ❌ Upload failed (HTTP {status})"
                        print(ctext(msg, Fore.RED))
                    
                except requests.exceptions.Timeout:
                    print(ctext("    ⏰ Upload timed out", Fore.YELLOW))
                    continue
                except requests.exceptions.ConnectionError:
                    print(ctext("    🔌 Connection error", Fore.RED))
                    continue
                except requests.exceptions.RequestException as e:
                    error_msg = str(e)[:50]
                    msg = f"    ❌ Request error: {error_msg}..."
                    print(ctext(msg, Fore.RED))
                    continue
                except Exception as e:
                    error_msg = str(e)[:50]
                    msg = f"    ❌ Unexpected error: {error_msg}..."
                    print(ctext(msg, Fore.RED))
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
    # Shorthand combined flags for convenience (e.g., `syncz -cu`)
    parser.add_argument('-cu', '--sync-upload', dest='sync_upload', action='store_true',
                        help='Shorthand for -c --upload (run sync and auto-upload orphans)')
    parser.add_argument('-cd', '--sync-delete', dest='sync_delete', action='store_true',
                        help='Shorthand for -c --delete (run sync and auto-delete orphans)')
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
        # Handle combined shorthand flags first
        if args.sync_upload or args.sync_delete:
            # Validate conflicting flags
            if args.sync_upload and args.sync_delete:
                msg = ("❌ Error: Cannot use both -cu/--sync-upload and "
                       "-cd/--sync-delete together")
                print(ctext(msg, Fore.RED))
                sys.exit(1)

            if args.sync_upload:
                print(ctext("🤖 SyncZ Auto-Upload Mode (-cu)", Fore.CYAN))
                msg = "   All orphaned files will be automatically uploaded"
                print(ctext(msg, Fore.CYAN))
                do_sync(auto_upload=True, auto_delete=False)
                return

            if args.sync_delete:
                print(ctext("🤖 SyncZ Auto-Delete Mode (-cd)", Fore.CYAN))
                msg = ("   All orphaned files will be automatically moved "
                       "to deleted folder")
                print(ctext(msg, Fore.CYAN))
                do_sync(auto_upload=False, auto_delete=True)
                return

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
