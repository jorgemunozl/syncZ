import http.server
import hashlib
import os
import json
import socketserver
from datetime import datetime

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


def parse_multipart_form_data(boundary, body):
    """Simple multipart/form-data parser"""
    parts = {}
    
    boundary_bytes = b'--' + boundary
    sections = body.split(boundary_bytes)
    
    for section in sections[1:-1]:  # Skip first empty and last boundary parts
        if not section.strip():
            continue
            
        # Find the headers/body separator
        header_end = section.find(b'\r\n\r\n')
        if header_end == -1:
            continue
            
        headers = section[2:header_end].decode('utf-8', errors='ignore')  # Skip leading \r\n
        content = section[header_end + 4:]  # Skip \r\n\r\n
        
        # Remove trailing \r\n if present
        if content.endswith(b'\r\n'):
            content = content[:-2]
        
        # Parse Content-Disposition header
        for line in headers.split('\r\n'):
            if line.lower().startswith('content-disposition:'):
                # Extract name from form-data
                if 'name="' in line:
                    start = line.find('name="') + 6
                    end = line.find('"', start)
                    if end != -1:
                        field_name = line[start:end]
                        
                        # Check if it's a file field
                        if 'filename="' in line:
                            # Extract filename
                            fname_start = line.find('filename="') + 10
                            fname_end = line.find('"', fname_start)
                            filename = line[fname_start:fname_end] if fname_end != -1 else 'unknown'
                            parts[field_name] = {'type': 'file', 'content': content, 'filename': filename}
                        else:
                            # Regular form field
                            parts[field_name] = {'type': 'field', 'content': content.decode('utf-8', errors='ignore')}
                break
    
    return parts


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
                metadata_size = format_file_size(len(data))
                print(ctext(f"✅ Served metadata ({metadata_size})", Fore.GREEN))
            except FileNotFoundError:
                self.send_error(404, "Metadata not found")
                print(ctext("❌ Metadata file not found", Fore.RED))
        else:
            super().do_GET()

    def do_POST(self):
        print(ctext(f"🔄 Received POST request for {self.path}", Fore.MAGENTA))
        
        try:
            if self.path == '/regenerate-metadata':
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
                
            elif self.path == '/upload':
                print(ctext("📤 Processing file upload...", Fore.CYAN))
                
                # Get content type and boundary
                content_type = self.headers.get('Content-Type', '')
                content_length = int(self.headers.get('Content-Length', 0))
                
                print(ctext(f"📋 Content-Type: {content_type}", Fore.BLUE))
                print(ctext(f"📏 Content-Length: {content_length}", Fore.BLUE))
                
                if not content_type.startswith('multipart/form-data'):
                    self.send_error(400, "Expected multipart/form-data")
                    return
                
                # Extract boundary
                boundary_start = content_type.find('boundary=')
                if boundary_start == -1:
                    self.send_error(400, "No boundary found in Content-Type")
                    return
                
                boundary = content_type[boundary_start + 9:].strip().encode()
                print(ctext(f"🔗 Boundary: {boundary.decode()}", Fore.BLUE))
                
                # Read the request body
                body = self.rfile.read(content_length)
                body_size = format_file_size(len(body))
                msg = f"📦 Read {body_size} ({len(body):,} bytes)"
                print(ctext(msg, Fore.BLUE))
                
                # Parse multipart data
                parts = parse_multipart_form_data(boundary, body)
                print(ctext(f"📂 Found parts: {list(parts.keys())}", Fore.BLUE))
                
                # Validate required fields
                if 'file' not in parts:
                    self.send_error(400, "No file field in upload")
                    print(ctext("❌ No file field found", Fore.RED))
                    return
                
                file_part = parts['file']
                if file_part['type'] != 'file':
                    self.send_error(400, "File field is not a file")
                    print(ctext("❌ File field is not a file", Fore.RED))
                    return
                
                filename = file_part['filename']
                file_content = file_part['content']
                
                print(ctext(f"📄 Filename: {filename}", Fore.GREEN))
                file_size_bytes = len(file_content)
                file_size_readable = format_file_size(file_size_bytes)
                msg = (f"💾 File size: {file_size_readable} "
                       f"({file_size_bytes:,} bytes)")
                print(ctext(msg, Fore.GREEN))
                
                # Get optional fields
                mtime = 0
                relpath = None
                
                if 'mtime' in parts and parts['mtime']['type'] == 'field':
                    try:
                        mtime = float(parts['mtime']['content'])
                        print(ctext(f"📅 MTime: {mtime}", Fore.BLUE))
                    except ValueError:
                        print(ctext("⚠️  Invalid mtime, using 0", Fore.YELLOW))
                
                if 'relpath' in parts and parts['relpath']['type'] == 'field':
                    relpath = parts['relpath']['content']
                    print(ctext(f"📁 Relative path: {relpath}", Fore.BLUE))
                
                # Determine file path
                if relpath:
                    # Sanitize path to prevent directory traversal
                    relpath = os.path.normpath(relpath).replace('..', '')
                    filepath = os.path.join(path, relpath)
                    # Create directory if needed
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    final_filename = relpath
                else:
                    final_filename = filename
                    filepath = os.path.join(path, filename)
                
                print(ctext(f"💾 Saving to: {filepath}", Fore.YELLOW))
                
                # Write file
                with open(filepath, 'wb') as f:
                    f.write(file_content)
                
                # Set modification time
                if mtime > 0:
                    os.utime(filepath, (mtime, mtime))
                    print(ctext(f"🕒 Set mtime to {mtime}", Fore.BLUE))
                
                file_size = os.path.getsize(filepath)
                file_size_readable = format_file_size(file_size)
                msg = (f"✅ Upload successful: {final_filename} "
                       f"({file_size_readable})")
                print(ctext(msg, Fore.GREEN))
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Upload successful')
                
            else:
                self.send_error(404, "POST path not supported")
                print(ctext(f"❌ Unsupported POST path: {self.path}", Fore.RED))
                
        except Exception as e:
            print(ctext(f"❌ Error processing request: {e}", Fore.RED))
            import traceback
            traceback.print_exc()
            
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Server error: {str(e)}".encode())
            except:
                print(ctext("❌ Failed to send error response", Fore.RED))


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
    print(ctext("\n🚀 Starting SyncZ Server (Simple Version)...", Fore.GREEN))
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
