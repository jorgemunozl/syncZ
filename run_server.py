import io
import http.server
import hashlib
import os
import json
import socketserver


from email.parser import BytesParser
from email.policy import default as email_default_policy


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

config = load_config()
path = config.get("path", DEFAULT_PATH)
PORT = config.get("port", DEFAULT_PORT)
METADATA_PATH = 'file_list.json'
os.chdir(path)

class SyncHandler(http.server.SimpleHTTPRequestHandler):
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
            except FileNotFoundError:
                self.send_error(404, "Metadata not found")
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
            print(f"Saved uploaded file {filename}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_error(404, "POST path not supported")


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
    os.chdir(path)
    data = generate_file_list(path)
    with open("file_list.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Generated file_list.json with {len(data)} items.")

    Handler = SyncHandler

    class ReuseAddrTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.should_shutdown = False

    with ReuseAddrTCPServer(('0.0.0.0', PORT), Handler) as httpd:
        print(f"Serving HTTP and metadata at port {PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down server.")


if __name__ == "__main__":
    main()