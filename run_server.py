import cgi
import io
import http.server
import hashlib
import os
import json
import socketserver

METADATA_PATH = 'file_list.json'
path = "/home/jorge/zoteroReference"
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
            raw_body = self.rfile.read(content_length)
            fp = io.BytesIO(raw_body)
            environ = {
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': self.headers.get('Content-Type'),
                'CONTENT_LENGTH': str(content_length),
            }

            form = cgi.FieldStorage(
                fp=fp,
                headers=self.headers,
                environ=environ,
                keep_blank_values=True
            )

            if 'file' not in form or not form['file'].filename:
                self.send_error(400, "No file field")
                return

            fileitem = form['file']
            mtime = float(form.getvalue('mtime', '0'))
            # Accept relpath for recursive upload
            relpath = form.getvalue('relpath')
            if relpath:
                # Sanitize relpath to prevent directory traversal
                relpath = os.path.normpath(relpath).replace('..', '')
                filepath = os.path.join(path, relpath)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                filename = relpath
            else:
                filename = os.path.basename(fileitem.filename)
                filepath = os.path.join(path, filename)

            with open(filepath, 'wb') as f:
                f.write(fileitem.file.read())
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