import io
import http.server
import hashlib
import os
import json
import socketserver
from datetime import datetime
from email.parser import BytesParser
from email.policy import default as email_default_policy

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


# --- Configuration ---
CONFIG_FILE = "config.json"
DEFAULT_PATH = "/home/jorge/zoteroReference"
DEFAULT_PORT = 8000

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "path": DEFAULT_PATH,
        "port": DEFAULT_PORT
    }

def get_primary_ip():
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


def show_server_config():
    """Display current server configuration with beautiful formatting"""
    config = load_config()
    print(ctext("\n" + "=" * 50, Fore.CYAN))
    print(ctext("           SYNCZ SERVER CONFIGURATION", Fore.GREEN))
    print(ctext("=" * 50, Fore.CYAN))
    local_ip = get_primary_ip()
    print(ctext("🖥️  Local IP: ", Fore.YELLOW) + ctext(local_ip, Fore.WHITE))
    print(ctext("📁 Sync Path: ", Fore.YELLOW) + ctext(f"{config.get('path', DEFAULT_PATH)}", Fore.WHITE))
    print(ctext("🔌 Server Port: ", Fore.YELLOW) + ctext(f"{config.get('port', DEFAULT_PORT)}", Fore.WHITE))
    print(ctext("🌐 Server IP: ", Fore.YELLOW) + ctext("0.0.0.0 (all interfaces)", Fore.WHITE))
    print(ctext("=" * 50, Fore.CYAN))


config = load_config()
path = config.get("path", DEFAULT_PATH)
PORT = config.get("port", DEFAULT_PORT)
METADATA_PATH = 'file_list.json'
os.chdir(path)

class SyncHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        """Override to add colored logging"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = format % args
        if "GET" in message:
            print(ctext(f"📥 [{timestamp}] {message}", Fore.BLUE))
        elif "POST" in message:
            print(ctext(f"📤 [{timestamp}] {message}", Fore.GREEN))
        else:
            print(ctext(f"ℹ️  [{timestamp}] {message}", Fore.CYAN))
    
    def do_GET(self):
        if self.path == '/metadata':
            try:
                with open(METADATA_PATH, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                print(ctext(f"✅ Served metadata ({len(data)} bytes)", Fore.GREEN))
            except FileNotFoundError:
                self.send_error(404, "Metadata not found")
                print(ctext("❌ Metadata file not found", Fore.RED))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/upload':
            content_length = int(self.headers.get('Content-Length', 0))
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error(400, "Content-Type must be multipart/form-data")
                return
            boundary = content_type.split("boundary=")[-1].encode()
            raw_body = self.rfile.read(content_length)
            # Parse multipart using email.parser
            msg = BytesParser(policy=email_default_policy).parsebytes(
                b'Content-Type: ' + content_type.encode() + b'\r\n\r\n' + raw_body
            )
            fileitem = None
            mtime = 0
            relpath = None
            for part in msg.iter_parts():
                cd = part.get('Content-Disposition', '')
                if 'form-data' in cd:
                    params = {}
                    for param in cd.split(';'):
                        if '=' in param:
                            k, v = param.strip().split('=', 1)
                            params[k] = v.strip('"')
                    if params.get('name') == 'file':
                        fileitem = part
                        filename = params.get('filename', 'uploaded_file')
                    elif params.get('name') == 'mtime':
                        mtime = float(part.get_content().strip())
                    elif params.get('name') == 'relpath':
                        relpath = part.get_content().strip()
            if not fileitem:
                self.send_error(400, "No file field")
                return
            if relpath:
                relpath = os.path.normpath(relpath).replace('..', '')
                filepath = os.path.join(path, relpath)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                filename = relpath
            else:
                filename = filename if 'filename' in locals() else 'uploaded_file'
                filepath = os.path.join(path, filename)
            with open(filepath, 'wb') as f:
                f.write(fileitem.get_payload(decode=True))
            if mtime:
                os.utime(filepath, (mtime, mtime))
            print(ctext(f"📁 Uploaded: {filename} ({os.path.getsize(filepath)} bytes)", Fore.GREEN))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_error(404, "POST path not supported")
            print(ctext(f"❌ Unsupported POST path: {self.path}", Fore.RED))


def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


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
            full = os.path.join(dirpath, fname)
            rows.append({
                "name": os.path.relpath(full, root_dir).replace("\\", "/"),
                "sha256": sha256sum(full),
                "mtime": os.path.getmtime(full)
            })
    return rows

PORT = 8000
path = "/home/jorge/zoteroReference"


def main():
    print(ctext("\n🚀 Starting SyncZ Server...", Fore.GREEN))
    show_server_config()
    
    try:
        os.chdir(path)
        print(ctext(f"\n📂 Changed to directory: {path}", Fore.BLUE))
    except Exception as e:
        print(ctext(f"❌ Failed to change to directory {path}: {e}", Fore.RED))
        return
    
    print(ctext("\n📋 Generating file metadata...", Fore.YELLOW))
    data = generate_file_list(path)
    with open("file_list.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(ctext(f"✅ Generated file_list.json with {len(data)} files", Fore.GREEN))

    Handler = SyncHandler

    class ReuseAddrTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.should_shutdown = False

    local_ip = get_primary_ip()
    print(ctext(f"\n🌐 Server starting on all interfaces, port {PORT}...", Fore.CYAN))
    print(ctext("=" * 50, Fore.CYAN))
    print(ctext("🟢 SyncZ Server is READY!", Fore.GREEN))
    print(ctext("🔗 Access from clients:", Fore.YELLOW))
    print(ctext(f"   📱 Local: http://localhost:{PORT}", Fore.WHITE))
    print(ctext(f"   🌍 Network: http://{local_ip}:{PORT}", Fore.WHITE))
    print(ctext("⌨️  Press Ctrl+C to stop the server", Fore.YELLOW))
    print(ctext("=" * 50, Fore.CYAN))

    with ReuseAddrTCPServer(('0.0.0.0', PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(ctext("\n\n🛑 Shutting down server gracefully...", Fore.YELLOW))
            print(ctext("👋 SyncZ Server stopped. Goodbye!", Fore.GREEN))


if __name__ == "__main__":
    main()