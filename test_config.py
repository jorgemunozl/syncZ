#!/usr/bin/env python3
"""Quick test script to demonstrate the beautified configuration interface"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import the client functions
from syncz.client import change_config, load_config, CONFIG_FILE
import json

def test_termux_preset():
    """Test the Termux preset functionality"""
    print("Testing Termux preset application...")
    
    # Load current config
    config = load_config()
    print(f"Before: Path={config.get('path')}, IP={config.get('server_ip')}, Port={config.get('server_port')}")
    
    # Apply Termux preset manually to show the result
    config["path"] = "/root/shared/zoteroReference"
    config["server_ip"] = "192.168.43.119"
    config["server_port"] = 8000
    config["port"] = config["server_port"]
    
    print(f"After Termux preset: Path={config['path']}, IP={config['server_ip']}, Port={config['server_port']}")
    
    # Save the test config
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    
    print("✅ Termux preset applied successfully!")

if __name__ == "__main__":
    test_termux_preset()
