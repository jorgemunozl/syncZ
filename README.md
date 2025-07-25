# SyncZ - Cross-Device File Synchronization

SyncZ is a lightweight file synchronization tool designed to keep files synchronized between two devices over a local network. It's particularly useful for synchronizing files between a desktop/laptop and mobile devices using Termux.

## Features

- **Bidirectional sync**: Automatically detects and syncs newer files in both directions
- **Efficient transfer**: Only transfers files that have changed (based on modification time and SHA256 hash)
- **Mobile-friendly**: Works seamlessly with Termux on Android devices
- **Simple HTTP protocol**: Uses standard HTTP for file transfer
- **Automatic cleanup**: Removes files that have been deleted on the remote device

## How It Works

The system consists of two main components:

1. **Server** (`run_server.py`): Runs on one device to serve files and metadata
2. **Client** (`client.py`): Runs on another device to sync with the server

The synchronization process:
1. Server generates metadata (file list with hashes and modification times)
2. Client fetches remote metadata and compares with local files
3. Files are downloaded, uploaded, or deleted as needed to achieve synchronization
4. Both devices end up with identical file sets

## Requirements

- Python 3.6+
- `requests` library
- Network connectivity between devices

### For Mobile Devices (Termux)

Termux is a powerful terminal emulator for Android that provides a Linux environment. To use SyncZ on Android:

1. Install [Termux](https://termux.com/) from F-Droid or GitHub
2. Install Python and required packages:
   ```bash
   pkg update
   pkg install python
   pip install requests
   ```

## Setup

### Server Setup (Device 1)

1. Edit the `path` variable in `run_server.py` to point to your desired sync directory
2. Run the server:
   ```bash
   python run_server.py
   ```
3. The server will start on port 8000 and display the serving address

### Client Setup (Device 2)

1. Edit the following variables in `client.py`:
   - `SERVER_IP`: IP address of the server device
   - `path`: Local directory to sync
2. Run the client:
   ```bash
   python client.py
   ```

## Configuration

### Server Configuration (`run_server.py`)

- `path`: Directory to serve and sync (default: `/home/jorge/zoteroReference`)
- `PORT`: HTTP server port (default: 8000)

### Client Configuration (`client.py`)

- `SERVER_IP`: IP address of the server device
- `SERVER_PORT`: Server port (should match server configuration)
- `path`: Local directory to sync (default: `/root/shared/zoteroReference`)

## Network Setup

1. **Find your server IP**: 
   ```bash
   ip addr show
   # or
   hostname -I
   ```

2. **Ensure devices are on the same network**: Both devices should be connected to the same WiFi network

3. **Configure firewall** (if necessary): Allow incoming connections on port 8000

## Mobile Usage with Termux

Termux provides a full Linux environment on Android, making it perfect for running SyncZ:

### Installing Termux
- **Recommended**: Download from [F-Droid](https://f-droid.org/packages/com.termux/)
- Alternative: Download from [GitHub Releases](https://github.com/termux/termux-app/releases)
- **Note**: Avoid Google Play Store version as it's outdated

### Termux Setup for SyncZ
```bash
# Update packages
pkg update && pkg upgrade

# Install Python and dependencies
pkg install python git

# Install required Python packages
pip install requests

# Clone or download SyncZ
git clone <your-repo-url>
cd syncZ

# Edit configuration
nano client.py  # or use vim/emacs
```

### Storage Access in Termux
To sync files with your Android device's storage:
```bash
# Allow Termux to access device storage
termux-setup-storage

# Your Android storage will be available at:
# ~/storage/shared (Internal storage)
# ~/storage/external-1 (SD card, if available)
```

## Example Use Cases

1. **Zotero Reference Sync**: Keep research papers and references synchronized between desktop and mobile
2. **Document Backup**: Ensure important documents are backed up across devices
3. **Development Files**: Sync code projects between development environments
4. **Media Files**: Keep photos, music, or videos synchronized

## Troubleshooting

### Connection Issues
- Verify both devices are on the same network
- Check IP address configuration
- Ensure firewall allows connections on the specified port
- Test connectivity: `ping <server-ip>`

### Permission Issues
- Ensure Python has read/write permissions for sync directories
- In Termux, use `termux-setup-storage` for broader file access

### File Conflicts
- The system prioritizes newer files based on modification time
- Files are compared using SHA256 hashes for integrity
- Manual intervention may be needed for complex conflicts

## Security Considerations

- This tool is designed for trusted local networks
- No authentication or encryption is implemented
- Consider using VPN for remote synchronization
- Be cautious when exposing the server to external networks

## License

[Add your preferred license here]

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.
