#!/usr/bin/env bash
# Unified one-shot installer for a dmenu + zathura PDF launcher.
# - Detects environment (GNOME/Ubuntu vs. i3/Arch)
# - Installs dependencies for the chosen environment
# - Installs ~/.local/bin/pdf-onebar
# - Sets Zathura as default PDF handler
# - Adds the appropriate keybinding for GNOME or i3

set -euo pipefail

# --- Script Configuration ---
PDF_DIR_DEFAULT="${PDF_DIR_DEFAULT:-$HOME/zoteroReference/}"
LAUNCHER_CMD_NAME='PDF Onebar'
LAUNCHER_SCRIPT_PATH="$HOME/.local/bin/pdf-onebar"

# --- Environment Detection ---
# Try to auto-detect, but allow user override.
detected_env=""
if command -v gsettings >/dev/null 2>&1 && command -v apt >/dev/null 2>&1; then
    detected_env="gnome"
elif command -v i3 >/dev/null 2>&1 && command -v pacman >/dev/null 2>&1; then
    detected_env="i3"
fi

# --- User Prompt ---
cat << "EOF"

PDF Onebar Launcher Installer
-------------------------------
This script will install a PDF launcher that uses dmenu and zathura.

It needs to know your desktop environment to install the correct
packages and set up the right keyboard shortcut.

(1) GNOME (Ubuntu/Debian-based)
    - Shortcut: Super+Shift+P
    - Packages: dmenu, fd-find, zathura, xdg-utils

(2) i3 (Arch-based)
    - Shortcut: Alt+Shift+P (Mod1+Shift+P)
    - Packages: dmenu, fd, zathura, xdg-utils

EOF

# Prompt user to choose, with auto-detected default
prompt="Choose your environment"
if [[ -n "$detected_env" ]]; then
    prompt+=" (detected: $detected_env, press Enter to confirm)"
fi
prompt+=": "

read -rp "$prompt" choice
choice="${choice:-$detected_env}" # Default to detected if user just hits Enter

# --- Installation Functions ---

install_packages_gnome() {
    echo "▶ Installing packages for GNOME (apt)..."
    
    # Handle zathura PDF backend conflicts
    echo "▶ Checking for zathura PDF backend conflicts..."
    if dpkg -l | grep -q zathura-pdf-mupdf; then
        echo "⚠️  Found zathura-pdf-mupdf installed."
        echo "   zathura-pdf-mupdf and zathura-pdf-poppler conflict with each other."
        echo "   We recommend poppler for better compatibility."
        read -rp "   Remove zathura-pdf-mupdf and install poppler? [Y/n]: " remove_mupdf
        remove_mupdf="${remove_mupdf:-Y}"
        
        if [[ "$remove_mupdf" =~ ^[Yy]$ ]]; then
            sudo apt remove -y zathura-pdf-mupdf
        else
            echo "   Keeping zathura-pdf-mupdf. Skipping poppler installation."
            sudo apt install -y dmenu fd-find zathura xdg-utils
            echo "   NOTE: PDF functionality may be limited with mupdf backend."
            return
        fi
    fi
    
    sudo apt install -y dmenu fd-find zathura zathura-pdf-poppler xdg-utils
    # fd-find installs the binary as 'fdfind'; create a convenient 'fd' shim if missing
    if ! command -v fd >/dev/null 2>&1 && command -v fdfind >/dev/null 2>&1; then
        mkdir -p "$HOME/.local/bin"
        ln -sf "$(command -v fdfind)" "$HOME/.local/bin/fd"
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
            export PATH="$HOME/.local/bin:$PATH" # For current session
            echo "NOTE: fd shim created. Added ~/.local/bin to PATH for future sessions."
        fi
    fi
}

install_packages_i3() {
    echo "▶ Installing packages for i3 (pacman)..."
    
    # Handle zathura PDF backend conflicts for Arch
    echo "▶ Checking for zathura PDF backend conflicts..."
    if pacman -Qq zathura-pdf-mupdf >/dev/null 2>&1; then
        echo "⚠️  Found zathura-pdf-mupdf installed."
        echo "   zathura-pdf-mupdf and zathura-pdf-poppler conflict with each other."
        echo "   We recommend poppler for better compatibility."
        read -rp "   Remove zathura-pdf-mupdf and install poppler? [Y/n]: " remove_mupdf
        remove_mupdf="${remove_mupdf:-Y}"
        
        if [[ "$remove_mupdf" =~ ^[Yy]$ ]]; then
            sudo pacman -R --noconfirm zathura-pdf-mupdf
        else
            echo "   Keeping zathura-pdf-mupdf. Skipping poppler installation."
            sudo pacman -S --needed --noconfirm dmenu fd zathura xdg-utils
            echo "   NOTE: PDF functionality may be limited with mupdf backend."
            return
        fi
    fi
    
    sudo pacman -S --needed --noconfirm dmenu fd zathura zathura-pdf-poppler xdg-utils
}

setup_keybinding_gnome() {
    echo "▶ Setting up GNOME keybinding..."
    local keybind='<Super><Shift>p'
    local binding_path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/pdf-onebar/"
    
    local current_bindings
    current_bindings=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings || echo "@as []")
    
    local new_bindings
    if [[ "$current_bindings" == "@as []" || "$current_bindings" == "[]" ]]; then
        new_bindings="['$binding_path']"
    elif [[ "$current_bindings" == *"$binding_path"* ]]; then
        new_bindings="$current_bindings" # Already there
    else
        new_bindings="${current_bindings%]*}, '$binding_path']"
    fi
    
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$new_bindings"
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$binding_path" name "$LAUNCHER_CMD_NAME"
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$binding_path" command "sh -c '$LAUNCHER_SCRIPT_PATH \"$PDF_DIR_DEFAULT\"'"
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$binding_path" binding "$keybind"
    echo "✅ GNOME shortcut set: $keybind"
}

setup_keybinding_i3() {
    echo "▶ Setting up i3 keybinding..."
    local i3_cfg_main="$HOME/.config/i3/config"
    local i3_cfg_fallback="$HOME/.i3/config"
    local key_combo='bindsym Mod1+Shift+p exec --no-startup-id'

    local i3_config=""
    if [[ -f "$i3_cfg_main" ]]; then 
        i3_config="$i3_cfg_main"
    elif [[ -f "$i3_cfg_fallback" ]]; then 
        i3_config="$i3_cfg_fallback"
    fi
    
    if [[ -z "$i3_config" ]]; then
        echo "❌ WARNING: No i3 config found at:"
        echo "   - $i3_cfg_main"
        echo "   - $i3_cfg_fallback"
        echo ""
        echo "💡 Manual setup required. Add this line to your i3 config:"
        echo "   bindsym Mod1+Shift+p exec --no-startup-id \"$LAUNCHER_SCRIPT_PATH\" \"$PDF_DIR_DEFAULT\""
        echo ""
        echo "   Then reload i3: \$mod+Shift+r"
        return
    fi

    echo "📄 Found i3 config: $i3_config"
    
    if ! grep -q "pdf-onebar" "$i3_config" 2>/dev/null; then
        echo "➕ Adding keybinding to i3 config..."
        printf "\n# %s\n%s %q %q\n" "$LAUNCHER_CMD_NAME" "$key_combo" "$LAUNCHER_SCRIPT_PATH" "$PDF_DIR_DEFAULT" >> "$i3_config"
        echo "✅ i3 binding added to $i3_config (Alt+Shift+P)"
        echo "🔄 Reloading i3 configuration..."
        if command -v i3-msg >/dev/null 2>&1; then
            i3-msg -q reload || echo "⚠️  i3-msg reload failed, manually reload with \$mod+Shift+r"
        else
            echo "💡 Reload i3 manually with \$mod+Shift+r"
        fi
    else
        echo "✅ i3 binding already exists in config."
        echo "🔍 Current binding:"
        grep -A1 -B1 "pdf-onebar" "$i3_config"
    fi
}

# --- Main Execution ---

# 1. Install launcher script
echo "▶ Installing the launcher script to $LAUNCHER_SCRIPT_PATH..."
mkdir -p "$(dirname "$LAUNCHER_SCRIPT_PATH")"
if [[ -f "$(dirname "$0")/pdf-onebar" ]]; then
  install -m 0755 "$(dirname "$0")/pdf-onebar" "$LAUNCHER_SCRIPT_PATH"
else
  echo "❌ ERROR: 'pdf-onebar' script not found in the same directory as this installer." >&2
  exit 1
fi

# 2. Install packages and set up keybindings based on choice
case "$choice" in
    1|g|gnome)
        install_packages_gnome
        setup_keybinding_gnome
        ;;
    2|i|i3)
        install_packages_i3
        setup_keybinding_i3
        ;;
    *)
        echo "❌ Invalid choice. Exiting." >&2
        exit 1
        ;;
esac

# 3. Set Zathura as default
echo "▶ Setting Zathura as the default PDF application..."
DESKTOP_FILE="org.pwmt.zathura.desktop"
if [[ ! -f "/usr/share/applications/$DESKTOP_FILE" ]]; then
  DESKTOP_FILE="zathura.desktop"
fi
xdg-mime default "$DESKTOP_FILE" application/pdf || true
echo "✅ Default PDF handler set."

# --- Summary ---
echo -e "\n🎉 \e[1;32mInstallation Complete!\e[0m"
echo "Launcher script is at: $LAUNCHER_SCRIPT_PATH"
echo "Default PDF folder: $PDF_DIR_DEFAULT"
echo "You can now use your new keyboard shortcut to find and open PDFs."
