# Changelog

All notable changes to SyncZ will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-07-25

### Added
- Initial release of SyncZ
- Bidirectional file synchronization between devices
- HTTP-based file transfer protocol
- SHA256 hash verification for file integrity
- Modification time-based sync decisions
- Support for Termux on Android devices
- Server component (`run_server.py`) for file serving
- Client component (`client.py`) for syncing
- Configuration helper script (`configure.py`)
- Termux setup script (`setup_termux.sh`)
- Comprehensive documentation
- Automatic file cleanup (removes files deleted on remote)
- Support for nested directory structures

### Features
- Efficient sync (only transfers changed files)
- Cross-platform compatibility (Linux, Android via Termux)
- Simple HTTP protocol for easy debugging
- Automatic metadata generation
- Conflict resolution based on modification time
