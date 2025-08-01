
import os
import json
import hashlib
import requests

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
    COLOR_ENABLED = True
except ImportError:
    COLOR_ENABLED = False

def ctext(text, color):
    if COLOR_ENABLED:
        return color + text + Style.RESET_ALL
    return text

def sha256sum(filename):
    h = hashlib.sha256()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def generate_file_list(root):
    rows = []
    for dirpath, _, files in os.walk(root):
        for name in files:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if rel == 'file_list.json':
                continue
            rows.append({
                'name': rel,
                'sha256': sha256sum(full),
                'mtime': os.path.getmtime(full)
            })
    return rows

def load_config(config_file, default_path, default_ip, default_port):
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'path': default_path,
        'server_ip': default_ip,
        'server_port': default_port
    }

def save_config(config_file, config):
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

def prompt_for_path(default_path):
    print(ctext('\n--- Sync Directory Setup ---', Fore.CYAN))
    path = input(ctext(f"Enter sync directory path (press Enter for '{default_path}'): ", Fore.YELLOW)).strip()
    return path if path else default_path

def prompt_for_ip(default_ip):
    print(ctext('\n--- Network Type ---', Fore.CYAN))
    print(ctext('1. LAN (WiFi/Local Network)', Fore.YELLOW))
    print(ctext('2. Ethernet (Wired, between two PCs)', Fore.YELLOW))
    net_choice = input(ctext('Are you connecting over LAN or Ethernet? (1 for LAN, 2 for Ethernet) [1]: ', Fore.YELLOW)).strip()
    if net_choice == '2':
        print(ctext('You selected Ethernet. Make sure both PCs are connected via cable and on the same network.', Fore.GREEN))
    else:
        print(ctext('You selected LAN (WiFi/Local Network). Make sure both devices are on the same WiFi or LAN.', Fore.GREEN))
    ip = input(ctext(f"Enter server IP address (LAN or Ethernet, press Enter for '{default_ip}'): ", Fore.YELLOW)).strip()
    return ip if ip else default_ip

def prompt_for_port(default_port):
    port = input(ctext(f"Enter server port (press Enter for '{default_port}'): ", Fore.YELLOW)).strip()
    if not port:
        return default_port
    try:
        return int(port)
    except ValueError:
        print(ctext('Invalid port, using default.', Fore.RED))
        return default_port

def main():
    CONFIG_FILE = 'config.json'
    DEFAULT_PATH = '/root/shared/zoteroReference'
    DEFAULT_SERVER_IP = '192.168.43.119'
    DEFAULT_SERVER_PORT = 8000

    print(ctext('\n==============================', Fore.CYAN))
    print(ctext('   SyncZ Interactive Client   ', Fore.GREEN))
    print(ctext('==============================\n', Fore.CYAN))

    config = load_config(CONFIG_FILE, DEFAULT_PATH, DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT)
    config['path'] = prompt_for_path(config.get('path', DEFAULT_PATH))
    config['server_ip'] = prompt_for_ip(config.get('server_ip', DEFAULT_SERVER_IP))
    config['server_port'] = prompt_for_port(config.get('server_port', DEFAULT_SERVER_PORT))
    save_config(CONFIG_FILE, config)
    print(ctext(f"\nConfiguration saved to {CONFIG_FILE}.", Fore.YELLOW))
    print(ctext(f"Using path: {config['path']}", Fore.YELLOW))
    print(ctext(f"Server: {config['server_ip']}:{config['server_port']}", Fore.YELLOW))

    print(ctext('\n--- Starting Sync Process ---\n', Fore.CYAN))
    os.chdir(config['path'])
    base_url = f"http://{config['server_ip']}:{config['server_port']}"
    metadata_url = f"{base_url}/metadata"
    local_json = 'file_list.json'
    download_dir = '.'

    print(ctext('Fetching remote metadata...', Fore.BLUE))
    resp = requests.get(metadata_url)
    resp.raise_for_status()
    remote_meta = resp.json()

    local_meta = generate_file_list(config['path'])
    with open(local_json, 'w', encoding='utf-8') as f:
        json.dump(local_meta, f, indent=2)

    remote_index = {m['name']: (m['sha256'], m.get('mtime', 0)) for m in remote_meta}
    local_index = {m['name']: (m['sha256'], m.get('mtime', 0)) for m in local_meta}

    to_download = [
        name for name, (remote_hash, remote_mtime) in remote_index.items()
        if name not in local_index or local_index[name][1] < remote_mtime
    ]

    to_upload = [
        m for m in local_meta
        if (
            m['name'] not in remote_index or
            remote_index.get(m['name'], ('', 0))[0] != m['sha256'] or
            remote_index.get(m['name'], ('', 0))[1] < m['mtime']
        )
    ]
    to_upload = [m for m in to_upload if m['name'] != 'file_list.json']

    for name in to_download:
        print(ctext(f"Downloading {name}...", Fore.MAGENTA))
        dir_name = os.path.dirname(name)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        dl = requests.get(f"{base_url}/{name}", stream=True)
        dl.raise_for_status()
        with open(name, 'wb') as f:
            for chunk in dl.iter_content(4096):
                f.write(chunk)
        orig_mtime = remote_index[name][1]
        os.utime(name, (orig_mtime, orig_mtime))

    to_delete = [name for name in local_index if name not in remote_index and name != local_json]
    for name in to_delete:
        for d in to_upload:
            if d['name'] == name:
                to_upload.remove(d)
                break
        print(ctext(f"Deleting local file {name} (removed on server)...", Fore.RED))
        try:
            os.remove(os.path.join(download_dir, name))
        except FileNotFoundError:
            pass
        except Exception as e:
            print(ctext(f"  ! Failed to delete {name}: {e}", Fore.RED))

    for m in to_upload:
        print(ctext(f"Uploading {m['name']}...", Fore.GREEN))
        with open(m['name'], 'rb') as f:
            files = {'file': f}
            data = {'mtime': str(m['mtime'])}
            upl = requests.post(f"{base_url}/upload", files=files, data=data)
            upl.raise_for_status()

    print(ctext('\nSync complete.\n', Fore.GREEN))

if __name__ == '__main__':
    main()
    for m in to_upload[:]:
        if m["name"] == "file_list.json":
            to_upload.remove(m)

    for name in to_download:
        print(ctext(f"Downloading {name}...", Fore.MAGENTA))
        dir_name = os.path.dirname(name)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        dl = requests.get(f"{base_url}/{name}", stream=True)
        dl.raise_for_status()
        with open(name, "wb") as f:
            for chunk in dl.iter_content(4096):
                f.write(chunk)
        orig_mtime = remote_index[name][1]
        os.utime(name, (orig_mtime, orig_mtime))

    to_delete = [
        name for name in local_index
        if name not in remote_index and name != local_json
    ]
    for name in to_delete:
        for d in to_upload:
            if d["name"] == name:
                to_upload.remove(d)
                break
        print(ctext(f"Deleting local file {name} (removed on server)...", Fore.RED))
        try:
            os.remove(os.path.join(download_dir, name))
        except FileNotFoundError:
            pass
        except Exception as e:
            print(ctext(f"  ! Failed to delete {name}: {e}", Fore.RED))

    for m in to_upload:
        print(ctext(f"Uploading {m['name']}...", Fore.GREEN))
        with open(m["name"], "rb") as f:
            files = {"file": f}
            data = {"mtime": str(m["mtime"])}
            upl = requests.post(f"{base_url}/upload", files=files, data=data)
            upl.raise_for_status()

    print(ctext("\nSync complete.\n", Fore.GREEN))
