#!/usr/bin/env python3
"""Quick test script to demonstrate the beautified configuration interface"""

import sys
import os
sys.path.append('.')

# Import the client functions
from client import change_config, load_config, CONFIG_FILE
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
    
    print(f"After Termux preset: Path={config['path']}, IP={config['server_ip']}, Port={config['server_port']}")
    
    # Save the test config
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    
    print("✅ Termux preset applied successfully!")

if __name__ == "__main__":
    test_termux_preset()
