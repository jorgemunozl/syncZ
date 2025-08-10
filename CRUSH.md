# CRUSH.md for SyncZ Project

## How to Build/Run/Lint/Test

### 🚀 **Recommended Usage:**
- **Unified Interface:** `python syncz` (beautiful menu with all options)
- **Quick Server:** `python syncz -s` (direct server launch with beautiful interface)  
- **Auto Setup:** `bash syncz_setup.sh` (handles environment and dependencies)
- **From Any Directory:** `syncz` commands work from anywhere after setup

### 🔧 **Direct Script Usage:**
- **Client (unified menu):** `python client.py`
- **Server (beautiful interface):** `python run_server.py`
- **Note:** Direct scripts should be run from the project directory

### 📦 **Dependencies:**
- **Auto-install:** Dependencies installed automatically by `syncz_setup.sh`
- **Manual install:** `pip install requests colorama`
- **Virtual Environment:** Automatically managed by setup script
- **Environment Check:** `syncz` commands check dependencies automatically

### 🧪 **Testing:**
- **Manual testing:** Launch server and client, test sync operations
- **Network testing:** Test between different devices on same network
- **No automated tests:** Currently manual testing only

---

**Note:** This file helps maintain consistency and quality standards for the SyncZ project. The focus is on providing a beautiful, professional, and user-friendly experience across all platforms.
