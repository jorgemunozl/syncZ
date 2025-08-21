#!/usr/bin/env python3
"""Debug script to test upload with requests"""

import os
import sys
sys.path.insert(0, '.')

from client import UploadFileWithProgress, print_progress

def test_upload_with_requests():
    # Create a test file
    test_content = "This is a test file for upload debugging\n" * 10
    with open("debug_test.txt", "w") as f:
        f.write(test_content)
    
    print("Testing upload simulation...")
    
    try:
        # Test the exact same pattern as in client.py
        filename = "debug_test.txt"
        
        def upload_progress_callback(path, transferred, total):
            print_progress(filename, transferred, total)
        
        print("Creating wrapper...")
        wrapper = UploadFileWithProgress("debug_test.txt", callback=upload_progress_callback)
        
        print("Testing wrapper properties...")
        print(f"File size: {len(wrapper)}")
        print(f"File name: {wrapper.name}")
        
        # Test that it can be used like a normal file
        print("Testing file operations...")
        wrapper.seek(0)
        print(f"Position after seek(0): {wrapper.tell()}")
        
        # Read small chunks to trigger progress
        print("Reading file in chunks...")
        total_read = 0
        while True:
            chunk = wrapper.read(50)  # Small chunks
            if not chunk:
                break
            total_read += len(chunk)
        
        print(f"\nTotal read: {total_read} bytes")
        
        # Test if requests would accept this
        try:
            import requests
            print("Testing with requests (dry run)...")
            
            # Reset the wrapper
            wrapper.seek(0)
            
            # This is what would happen in the actual upload
            files = {"file": wrapper}
            data = {"mtime": "123456"}
            
            print("Files dict created successfully")
            print(f"Wrapper in files: {type(files['file'])}")
            
            # Don't actually make the request, just test the setup
            print("Upload setup successful!")
            
        except ImportError:
            print("requests not available, skipping requests test")
        except Exception as e:
            print(f"Requests test failed: {e}")
            import traceback
            traceback.print_exc()
        
        wrapper.close()
        print("Test completed successfully")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        if os.path.exists("debug_test.txt"):
            os.remove("debug_test.txt")

if __name__ == "__main__":
    test_upload_with_requests()
