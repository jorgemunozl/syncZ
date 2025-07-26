#!/usr/bin/env python3
"""
SyncZ Configuration Helper
A simple script to help configure SyncZ for your network setup.
"""

import socket
import os


def get_local_ip():
    """Get the local IP address of this machine."""
    try:
        # Connect to a remote address to determine local IP (LAN)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        return local_ip
    except Exception:
        return "127.0.0.1"

def get_ethernet_ip():
    """Get the Ethernet IP address of this machine (if available)."""
    try:
        import fcntl, struct
        iface = 'eth0'
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', iface[:15].encode('utf-8'))
        )[20:24])
    except Exception:
        return get_local_ip()

def update_client_config(server_ip, sync_path):
    """Update client.py with new configuration."""
    try:
        with open("client.py", "r") as f:
            content = f.read()
        
        # Update SERVER_IP
        content = content.replace(
            'SERVER_IP   = "192.168.43.119"',
            f'SERVER_IP   = "{server_ip}"'
        )
        
        # Update path
        content = content.replace(
            'path="/root/shared/zoteroReference"',
            f'path="{sync_path}"'
        )
        
        with open("client.py", "w") as f:
            f.write(content)
        
        print(f"✅ Updated client.py with SERVER_IP: {server_ip} and path: {sync_path}")
        return True
    except Exception as e:
        print(f"❌ Error updating client.py: {e}")
        return False

def update_server_config(sync_path, port=8000):
    """Update run_server.py with new configuration."""
    try:
        with open("run_server.py", "r") as f:
            content = f.read()
        
        # Update path
        content = content.replace(
            'path = "/home/jorge/zoteroReference"',
            f'path = "{sync_path}"'
        )
        
        # Update PORT if different
        if port != 8000:
            content = content.replace(
                'PORT = 8000',
                f'PORT = {port}'
            )
        
        with open("run_server.py", "w") as f:
            f.write(content)
        
        print(f"✅ Updated run_server.py with path: {sync_path} and port: {port}")
        return True
    except Exception as e:
        print(f"❌ Error updating run_server.py: {e}")
        return False

def main():
    print("🔧 SyncZ Configuration Helper")
    print("=" * 40)
    
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
        else:
            abs_path = input(f"{prompt} (absolute, press Enter for current directory): ").strip()
            return abs_path if abs_path else os.getcwd()

    if choice in ["1", "3"]:
        print("\n🖥️  Server Configuration")
        server_path = get_path("Enter sync directory path for server")
        port = input("Enter server port (press Enter for 8000): ").strip()
        if not port:
            port = 8000
        else:
            try:
                port = int(port)
            except ValueError:
                print("Invalid port, using 8000")
                port = 8000
        if update_server_config(server_path, port):
            print(f"\n🚀 Server ready! Run: python run_server.py")
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
        if update_client_config(server_ip, client_path):
            print(f"\n🔄 Client ready! Run: python client.py")

    print("\n✨ Configuration complete!")
    print("\n📝 Quick Start:")
    print("1. On server device: python run_server.py")
    print("2. On client device: python client.py")

if __name__ == "__main__":
    main()
