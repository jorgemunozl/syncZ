#!/usr/bin/env bash
# One-shot installer for a dmenu + zathura PDF launcher on Arch Linux (i3).
# - Installs: dmenu, fd, zathura (+ pdf plugin), xdg-utils
# - Creates ~/.local/bin/pdf-onebar (top bar; filenames only; page jump via :12 or -P 12)
# - Sets Zathura as default PDF handler (via xdg-mime)
# - Adds an i3 keybinding: $mod+Shift+P

set -euo pipefail

PDF_DIR_DEFAULT="${PDF_DIR_DEFAULT:-$HOME/zoteroReference/}"
CMD_NAME='PDF Onebar'
SCRIPT_PATH="$HOME/.local/bin/pdf-onebar"
I3_CFG_MAIN="$HOME/.config/i3/config"
I3_CFG_FALLBACK="$HOME/.i3/config"
KEY_COMBO='bindsym $mod+Shift+p exec --no-startup-id'

# --- 1) Packages ----------------------------------------------------------------
if ! command -v pacman >/dev/null 2>&1; then
  echo "This script expects Arch Linux (pacman)." >&2
  exit 1
fi

sudo pacman -S --needed --noconfirm dmenu fd zathura zathura-pdf-poppler xdg-utils

# --- 2) Install the launcher script --------------------------------------------
mkdir -p "$(dirname "$SCRIPT_PATH")"
if [[ -f "$(dirname "$0")/pdf-onebar" ]]; then
  install -m 0755 "$(dirname "$0")/pdf-onebar" "$SCRIPT_PATH"
else
  echo "pdf-onebar not found next to this script; please ensure it's present." >&2
  exit 1
fi

# --- 3) Make Zathura the default PDF opener ------------------------------------
DESKTOP_FILE="org.pwmt.zathura.desktop"
if [[ ! -f "/usr/share/applications/$DESKTOP_FILE" ]]; then
  DESKTOP_FILE="zathura.desktop"
fi
xdg-mime default "$DESKTOP_FILE" application/pdf || true

# --- 4) Add i3 keybinding -------------------------------------------------------
# Choose the active i3 config
I3_CONFIG=""
if [[ -f "$I3_CFG_MAIN" ]]; then I3_CONFIG="$I3_CFG_MAIN"; fi
if [[ -z "$I3_CONFIG" && -f "$I3_CFG_FALLBACK" ]]; then I3_CONFIG="$I3_CFG_FALLBACK"; fi
if [[ -z "$I3_CONFIG" ]]; then
  # Create a minimal config if none exists
  mkdir -p "$(dirname "$I3_CFG_MAIN")"
  I3_CONFIG="$I3_CFG_MAIN"
  cat > "$I3_CONFIG" <<'EOF_I3CFG'
# Minimal i3 config (auto-generated)
set $mod Mod4
font pango:monospace 10
bindsym $mod+Return exec --no-startup-id xterm
bindsym $mod+d exec --no-startup-id dmenu_run
bindsym $mod+Shift+e exec --no-startup-id i3-nagbar -t warning -m 'Exit i3?' -b 'yes' 'i3-msg exit'
EOF_I3CFG
fi

# Append our launcher binding if absent
if ! grep -q "pdf-onebar" "$I3_CONFIG" 2>/dev/null; then
  printf "\n# %s\n%s %q %q\n" "$CMD_NAME" "$KEY_COMBO" "$SCRIPT_PATH" "$PDF_DIR_DEFAULT" >> "$I3_CONFIG"
fi

# Ask i3 to reload the config if running
if command -v i3-msg >/dev/null 2>&1; then
  i3-msg -q reload || true
fi

# --- 5) Summary -----------------------------------------------------------------
echo "\nInstalled: dmenu, fd, zathura(+pdf plugin), xdg-utils."
echo "Script: $SCRIPT_PATH"
echo "PDF folder default: $PDF_DIR_DEFAULT (change by editing the key in the script or pass a path argument)"
echo "Zathura set as default PDF opener (desktop: $DESKTOP_FILE)."
echo "i3 binding added: \$mod+Shift+P (edit in $I3_CONFIG)."
