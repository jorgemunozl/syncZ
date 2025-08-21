import http.server
import socketserver
from datetime import datetime

class TestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] POST request received for {self.path}")
        
        try:
            # Log headers
            print("Headers:")
            for header, value in self.headers.items():
                print(f"  {header}: {value}")
            
            # Read content length
            content_length = int(self.headers.get('Content-Length', 0))
            print(f"Content-Length: {content_length}")
            
            if content_length > 0:
                # Read a small portion of the body for debugging
                sample_size = min(content_length, 500)
                body_sample = self.rfile.read(sample_size)
                print(f"Body sample ({sample_size} bytes):")
                print(body_sample[:200])
                
                # Read the rest if needed
                if content_length > sample_size:
                    remaining = self.rfile.read(content_length - sample_size)
                    print(f"Read additional {len(remaining)} bytes")
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK - Test server received request')
            
            print("Response sent successfully")
            
        except Exception as e:
            print(f"Error handling request: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error: {str(e)}".encode())
            except:
                print("Failed to send error response")

def main():
    PORT = 8000
    
    class ReuseAddrTCPServer(socketserver.TCPServer):
        allow_reuse_address = True
    
    print(f"Starting test server on port {PORT}...")
    
    with ReuseAddrTCPServer(('0.0.0.0', PORT), TestHandler) as httpd:
        try:
            print("Test server is ready!")
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping test server...")

if __name__ == "__main__":
    main()
