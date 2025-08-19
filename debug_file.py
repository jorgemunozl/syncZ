#!/usr/bin/env python3
"""
Debug script to investigate why a file keeps being uploaded.
Usage: python3 debug_file.py filename.pdf
"""

import sys
import os
import hashlib
import json
import requests
from datetime import datetime

def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def load_config():
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def debug_file(filename):
    if not os.path.exists(filename):
        print(f"❌ File '{filename}' not found locally")
        return
    
    config = load_config()
    server_ip = config.get("server_ip", "192.168.1.100")
    server_port = config.get("server_port", 8000)
    base_url = f"http://{server_ip}:{server_port}"
    
    print(f"🔍 Debugging file: {filename}")
    print("=" * 50)
    
    # 1. Local file info
    local_stat = os.stat(filename)
    local_mtime = local_stat.st_mtime
    local_size = local_stat.st_size
    local_hash = sha256sum(filename)
    
    print(f"📁 LOCAL FILE INFO:")
    print(f"   Path: {filename}")
    print(f"   Size: {local_size} bytes")
    print(f"   Modified: {datetime.fromtimestamp(local_mtime)}")
    print(f"   MTime (raw): {local_mtime}")
    print(f"   SHA256: {local_hash}")
    print()
    
    # 2. Server metadata
    try:
        print(f"🌐 SERVER METADATA:")
        response = requests.get(f"{base_url}/metadata", timeout=10)
        response.raise_for_status()
        server_meta = response.json()
        
        # Find our file in server metadata
        server_file = None
        for file_info in server_meta:
            if file_info["name"] == filename:
                server_file = file_info
                break
        
        if server_file:
            print(f"   Found on server: YES")
            print(f"   Server SHA256: {server_file['sha256']}")
            print(f"   Server MTime: {server_file['mtime']}")
            print(f"   Server Modified: {datetime.fromtimestamp(server_file['mtime'])}")
            print()
            
            # 3. Comparison
            print(f"🔍 COMPARISON:")
            hash_match = local_hash == server_file['sha256']
            mtime_match = abs(local_mtime - server_file['mtime']) < 1.0  # Allow 1 second difference
            local_newer = local_mtime > server_file['mtime']
            
            print(f"   Hash match: {hash_match} {'✅' if hash_match else '❌'}")
            print(f"   MTime match: {mtime_match} {'✅' if mtime_match else '❌'}")
            print(f"   Local newer: {local_newer} {'🔄' if local_newer else '✅'}")
            print(f"   MTime diff: {local_mtime - server_file['mtime']:.6f} seconds")
            print()
            
            # 4. Sync decision
            print(f"📋 SYNC DECISION:")
            will_upload = (
                not hash_match or 
                local_mtime > server_file['mtime']
            )
            print(f"   Will upload: {will_upload} {'📤' if will_upload else '✅'}")
            
            if will_upload:
                print(f"   Reason: {'Hash mismatch' if not hash_match else 'Local file is newer'}")
        else:
            print(f"   Found on server: NO")
            print(f"   Will upload: YES 📤 (new file)")
            
    except Exception as e:
        print(f"❌ Error getting server metadata: {e}")
        print(f"   Cannot compare with server")
    
    print()
    
    # 5. File content check
    print(f"🔧 FILE ANALYSIS:")
    print(f"   Readable: {os.access(filename, os.R_OK)}")
    print(f"   Writable: {os.access(filename, os.W_OK)}")
    print(f"   In use: {check_file_in_use(filename)}")
    
    # 6. Recommendations
    print()
    print(f"💡 RECOMMENDATIONS:")
    if not os.path.exists(filename):
        print("   - File doesn't exist, check path")
    elif server_file and not hash_match:
        print("   - Hash mismatch indicates file content differs")
        print("   - Check if file is being modified during sync")
        print("   - Verify file isn't corrupted")
    elif server_file and local_newer:
        print("   - Local file is newer, upload is expected")
        print("   - Check if something keeps modifying the file")
    else:
        print("   - File should not be uploading, possible sync bug")

def check_file_in_use(filepath):
    """Check if file might be in use (basic check)"""
    try:
        # Try to open file in exclusive mode
        with open(filepath, 'r+b') as f:
            pass
        return False
    except (IOError, OSError):
        return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 debug_file.py <filename>")
        print("Example: python3 debug_file.py document.pdf")
        sys.exit(1)
    
    filename = sys.argv[1]
    debug_file(filename)
