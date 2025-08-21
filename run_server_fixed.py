import http.server
import hashlib
import os
import json
import socketserver
import cgi
from datetime import datetime
from urllib.parse import parse_qs

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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
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
        print(ctext(f"🔄 Received POST request for {self.path}", Fore.MAGENTA))
        
        if self.path == '/regenerate-metadata':
            try:
                print(ctext("🔄 Client requested metadata regeneration...", Fore.YELLOW))
                data = generate_file_list(os.getcwd())
                with open("file_list.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "status": "success",
                    "message": f"Metadata regenerated with {len(data)} files",
                    "file_count": len(data)
                }
                self.wfile.write(json.dumps(response).encode())
                print(ctext(f"✅ Regenerated metadata with {len(data)} files", Fore.GREEN))
            except Exception as e:
                print(ctext(f"❌ Failed to regenerate metadata: {e}", Fore.RED))
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "status": "error",
                    "message": f"Failed to regenerate metadata: {str(e)}"
                }
                self.wfile.write(json.dumps(response).encode())
                
        elif self.path == '/upload':
            try:
                print(ctext("📤 Processing file upload...", Fore.CYAN))
                
                # Use cgi.FieldStorage for robust multipart parsing
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        'REQUEST_METHOD': 'POST',
                        'CONTENT_TYPE': self.headers['Content-Type'],
                    }
                )
                
                print(ctext(f"📋 Form fields: {list(form.keys())}", Fore.BLUE))
                
                # Extract file
                if 'file' not in form:
                    self.send_error(400, "No file field in upload")
                    print(ctext("❌ No file field found", Fore.RED))
                    return
                    
                fileitem = form['file']
                if not fileitem.filename:
                    self.send_error(400, "No filename provided")
                    print(ctext("❌ No filename provided", Fore.RED))
                    return
                
                # Extract metadata
                mtime = 0
                relpath = None
                
                if 'mtime' in form:
                    try:
                        mtime = float(form['mtime'].value)
                        print(ctext(f"📅 MTime: {mtime}", Fore.BLUE))
                    except (ValueError, AttributeError):
                        print(ctext("⚠️  Invalid mtime, using 0", Fore.YELLOW))
                
                if 'relpath' in form:
                    relpath = form['relpath'].value
                    print(ctext(f"📁 Relative path: {relpath}", Fore.BLUE))
                
                # Determine file path
                if relpath:
                    # Sanitize path to prevent directory traversal
                    relpath = os.path.normpath(relpath).replace('..', '')
                    filepath = os.path.join(path, relpath)
                    # Create directory if needed
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    filename = relpath
                else:
                    filename = fileitem.filename
                    filepath = os.path.join(path, filename)
                
                print(ctext(f"💾 Saving to: {filepath}", Fore.YELLOW))
                
                # Write file
                with open(filepath, 'wb') as f:
                    if hasattr(fileitem, 'file'):
                        # fileitem.file is the actual file object
                        while True:
                            chunk = fileitem.file.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                    else:
                        # Fallback: write the value directly
                        f.write(fileitem.value)
                
                # Set modification time
                if mtime > 0:
                    os.utime(filepath, (mtime, mtime))
                    print(ctext(f"🕒 Set mtime to {mtime}", Fore.BLUE))
                
                file_size = os.path.getsize(filepath)
                print(ctext(f"✅ Upload successful: {filename} ({file_size} bytes)", Fore.GREEN))
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Upload successful')
                
            except Exception as e:
                print(ctext(f"❌ Upload failed: {e}", Fore.RED))
                import traceback
                traceback.print_exc()
                
                try:
                    self.send_response(500)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(f"Upload failed: {str(e)}".encode())
                except:
                    pass  # Connection might be broken
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


def main():
    print(ctext("\n🚀 Starting SyncZ Server (Fixed Version)...", Fore.GREEN))
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
