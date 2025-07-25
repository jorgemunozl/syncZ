import os
import json
import hashlib
import requests




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

#try with ip = 119

path="/root/shared/zoteroReference"

os.chdir(path)

# IP = input("Enter the ip: ")


SERVER_IP   = "192.168.43.119"   # your laptop’s reserved DHCP/static IP
SERVER_PORT = 8000
BASE_URL    = f"http://{SERVER_IP}:{SERVER_PORT}"

METADATA_URL = f"{BASE_URL}/metadata"
LOCAL_JSON   = "file_list.json"
DOWNLOAD_DIR = "."

def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def load_json(path):
    return json.load(open(path, encoding="utf-8"))

def save_json(path, data):
    json.dump(data, open(path, "w", encoding="utf-8"), indent=2)

# 1. Fetch remote metadata
print("Fetching remote metadata...")
resp = requests.get(METADATA_URL)
resp.raise_for_status()
remote_meta = resp.json()

# 2. Compute local metadata

local_meta = generate_file_list(path)

with open("file_list.json", "w", encoding="utf-8") as f:
        json.dump(local_meta, f, indent=2)

remote_index = {m["name"]: (m["sha256"], m.get("mtime", 0)) for m in remote_meta}
local_index  = {m["name"]: (m["sha256"], m.get("mtime", 0)) for m in local_meta}

to_download = [
    name for name, (remote_hash, remote_mtime) in remote_index.items()
    if (
        name not in local_index or
        #local_index[name][0] != remote_hash or
        local_index[name][1] < remote_mtime  
        )
    ]

    


to_upload = [
    m for m in local_meta
    if (
        m["name"] not in remote_index or
        remote_index.get(m["name"], ("", 0))[0] != m["sha256"] or
        remote_index.get(m["name"], ("", 0))[1] < m["mtime"]  # local is newer
    )
]
for m in to_upload:
    if m["name"]=="file_list.json":
        to_upload.remove(m)

# 4. Download missing/changed
for name in to_download:
    print(f"Downloading {name}...")
    dir_name = os.path.dirname(name)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    dl = requests.get(f"{BASE_URL}/{name}", stream=True)
    dl.raise_for_status()
    with open(name, "wb") as f:
        for chunk in dl.iter_content(4096):
            f.write(chunk)
    orig_mtime = remote_index[name][1]
    os.utime(name, (orig_mtime, orig_mtime))
to_delete = [
    name for name in local_index
    # never delete your metadata file itself
    if name not in remote_index and name != LOCAL_JSON
]

# 5. To delete.
for name in to_delete:
    for d in to_upload:
        if d["name"] == name:
            to_upload.remove(d)
            break
    print(f"Deleting local file {name} (removed on server)...")
    try:
        os.remove(os.path.join(DOWNLOAD_DIR, name))
    except FileNotFoundError:
        pass  # already gone
    except Exception as e:
        print(f"  ! Failed to delete {name}: {e}")


# 5. Upload new/changed (server must implement POST /upload)
for m in to_upload:
    print(f"Uploading {m['name']}...")
    with open(m["name"], "rb") as f:
        files = {"file": f}
        data = {"mtime": str(m["mtime"])}
        upl = requests.post(f"{BASE_URL}/upload", files=files, data=data)
        upl.raise_for_status()

# 6. Update local metadata
print("Sync complete.")
