import requests
import os


def run_upload_test():
    """
    Tests the file upload functionality of the SyncZ server.
    """
    server_url = "http://localhost:8000/upload"
    test_file_name = "test_upload.txt"
    test_file_content = "This is a test file for upload."
    
    # Create a dummy file to upload
    with open(test_file_name, "w") as f:
        f.write(test_file_content)
        
    file_path = os.path.abspath(test_file_name)
    mtime = os.path.getmtime(file_path)
    relpath = os.path.basename(file_path)

    print("--- Running Upload Test ---")
    print(f"Server URL: {server_url}")
    print(f"File: {file_path}")
    print(f"MTime: {mtime}")
    print(f"Relpath: {relpath}")

    try:
        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'application/octet-stream'),
                'mtime': (None, str(mtime)),
                'relpath': (None, relpath)
            }
            
            response = requests.post(server_url, files=files, timeout=10)
            
            print("\n--- Server Response ---")
            print(f"Status Code: {response.status_code}")
            print(f"Response Text: {response.text}")
            
            if response.status_code == 200:
                print("\n✅ Upload test successful!")
            else:
                print("\n❌ Upload test failed.")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ An error occurred: {e}")
    finally:
        # Clean up the dummy file
        if os.path.exists(test_file_name):
            os.remove(test_file_name)
        print("\n--- Test Finished ---")


if __name__ == "__main__":
    run_upload_test()
