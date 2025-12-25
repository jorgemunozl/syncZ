#!/usr/bin/env python3
"""
SyncZ Configuration Helper
Updates config.json interactively for server and client settings.
"""

import json
import socket
import os
from pathlib import Path

try:
    from .paths import CONFIG_FILE
except ImportError:  # pragma: no cover - direct execution fallback
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from syncz.paths import CONFIG_FILE

DEFAULT_CONFIG = {
    "path": "/root/shared/zoteroReference",
    "server_ip": "192.168.43.119",
    "server_port": 8000,
}


def normalize_config(config):
    if "server_port" not in config and "port" in config:
        config["server_port"] = config["port"]
    if "port" not in config and "server_port" in config:
        config["port"] = config["server_port"]
    return config


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return normalize_config(json.load(f))
    return DEFAULT_CONFIG.copy()


def save_config(config):
    config = normalize_config(config)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"✅ Saved configuration to {CONFIG_FILE}")


def get_local_ip():
    """Get the local IP address of this machine."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        return local_ip
    except Exception:
        return "127.0.0.1"


def get_ethernet_ip():
    """Get the Ethernet IP address of this machine (if available)."""
    try:
        import fcntl
        import struct
        iface = 'eth0'
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', iface[:15].encode('utf-8'))
        )[20:24])
    except Exception:
        return get_local_ip()


def main():
    print("🔧 SyncZ Configuration Helper")
    print("=" * 40)

    config = load_config()

    print("\n🌐 Network Type Selection:")
    print("1. LAN (WiFi/Local Network)")
    print("2. Ethernet (Wired)")
    net_choice = input("Choose network type (1 for LAN, 2 for Ethernet) [1]: ").strip()
    if net_choice == "2":
        ip_method = get_ethernet_ip
        net_label = "Ethernet"
    else:
        ip_method = get_local_ip
        net_label = "LAN"
    local_ip = ip_method()
    print(f"📡 Detected {net_label} IP address: {local_ip}")

    print("\n🎯 What would you like to configure?")
    print("1. Server (this device will serve files)")
    print("2. Client (this device will sync from server)")
    print("3. Both")
    choice = input("\nEnter your choice (1-3): ").strip()

    print("\n📁 Path Type Selection:")
    print("1. Absolute path (recommended for most setups)")
    print("2. Relative path (relative to this script)")
    path_type = input("Choose path type (1 for absolute, 2 for relative) [1]: ").strip()
    use_relative = (path_type == "2")

    def get_path(prompt):
        if use_relative:
            rel = input(f"{prompt} (relative to this script, press Enter for '.'): ").strip()
            return rel if rel else "."
        abs_path = input(f"{prompt} (absolute, press Enter for current directory): ").strip()
        return abs_path if abs_path else os.getcwd()

    if choice in ["1", "3"]:
        print("\n🖥️  Server Configuration")
        server_path = get_path("Enter sync directory path for server")
        port_input = input("Enter server port (press Enter for 8000): ").strip()
        try:
            port = int(port_input) if port_input else 8000
        except ValueError:
            print("Invalid port, using 8000")
            port = 8000
        config["path"] = server_path
        config["server_port"] = port
        config["port"] = port
        print("\n🚀 Server ready! Run: ./syncz --server")
        print(f"📡 Server will be available at: http://{local_ip}:{port}")

    if choice in ["2", "3"]:
        print("\n💻 Client Configuration")
        if choice == "3":
            server_ip = input(f"Enter server IP address (press Enter for {local_ip}): ").strip()
            if not server_ip:
                server_ip = local_ip
        else:
            server_ip = input("Enter server IP address: ").strip()
            if not server_ip:
                print("❌ Server IP is required for client configuration")
                return
        client_path = get_path("Enter local sync directory path for client")
        config["server_ip"] = server_ip
        config["path"] = client_path
        print("\n🔄 Client ready! Run: ./syncz")

    save_config(config)

    print("\n✨ Configuration complete!")
    print("\n📝 Quick Start:")
    print("1. On server device: ./syncz --server")
    print("2. On client device: ./syncz")


if __name__ == "__main__":
    main()
