#!/usr/bin/env python3
"""Test actual upload to server"""

import os
import sys
import requests
sys.path.insert(0, '.')

from client import UploadFileWithProgress, print_progress

def test_real_upload():
    # Create a test file
    with open("real_test.txt", "w") as f:
        f.write("This is a real upload test\n")
    
    try:
        print("Testing real upload to server...")
        
        filename = "real_test.txt"
        def upload_progress_callback(path, transferred, total):
            print_progress(filename, transferred, total)
        
        wrapper = UploadFileWithProgress("real_test.txt", callback=upload_progress_callback)
        
        try:
            files = {"file": wrapper}
            data = {"mtime": "1234567890"}
            
            print("Making POST request...")
            response = requests.post("http://localhost:8000/upload", files=files, data=data, timeout=30)
            
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text}")
            
            if response.status_code == 200:
                print("✅ Upload successful!")
            else:
                print(f"❌ Upload failed with status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Upload request failed: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            wrapper.close()
            
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        if os.path.exists("real_test.txt"):
            os.remove("real_test.txt")

if __name__ == "__main__":
    test_real_upload()
