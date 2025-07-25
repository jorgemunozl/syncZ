#!/bin/bash

# SyncZ Installation Script for Termux
# This script sets up SyncZ on Android devices using Termux

echo "🚀 Setting up SyncZ for Termux..."

# Update package lists
echo "📦 Updating packages..."
pkg update -y

# Install required packages
echo "🐍 Installing Python and dependencies..."
pkg install -y python git

# Install Python requirements
echo "📚 Installing Python packages..."
pip install requests

# Setup storage access
echo "📱 Setting up storage access..."
echo "Please allow storage permissions when prompted."
termux-setup-storage

# Create sync directory
echo "📁 Creating sync directory..."
mkdir -p ~/syncz-data

echo "✅ SyncZ setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit client.py to set the correct SERVER_IP"
echo "2. Edit the 'path' variable to point to your desired sync directory"
echo "3. Run: python client.py"
echo ""
echo "💡 Tip: Your Android storage is available at:"
echo "   Internal storage: ~/storage/shared"
echo "   SD card: ~/storage/external-1"
