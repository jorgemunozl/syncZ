#!/usr/bin/env bash
# One-shot installer for a dmenu + zathura PDF launcher on Ubuntu (GNOME).
# - Installs: dmenu, fd-find, zathura (+ pdf plugin), xdg-utils
# - Creates ~/.local/bin/pdf-onebar (top bar; filenames only; page jump via :12 or -P 12)
# - Sets Zathura as default PDF handler (via xdg-mime)
# - Adds a GNOME custom shortcut: Super+Shift+P

set -euo pipefail

PDF_DIR_DEFAULT="${PDF_DIR_DEFAULT:-$HOME/zoteroReference/}"
KEYBIND='<Super><Shift>p'
CMD_NAME='PDF Onebar'
SCRIPT_PATH="$HOME/.local/bin/pdf-onebar"
BINDING_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/pdf-onebar/"

# --- 1) Packages ----------------------------------------------------------------
if ! command -v apt >/dev/null 2>&1; then
  echo "This script expects Ubuntu/Debian with apt." >&2
  exit 1
fi

# dmenu, fd-find (binary is fdfind), zathura, zathura's poppler backend, and xdg-utils
sudo apt install -y dmenu fd-find zathura zathura-pdf-poppler xdg-utils

# fd-find installs the binary as 'fdfind'; create a convenient 'fd' shim if missing
if ! command -v fd >/dev/null 2>&1 && command -v fdfind >/dev/null 2>&1; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$(command -v fdfind)" "$HOME/.local/bin/fd"
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) : ;;
    *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile" ;;
  esac
fi

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

# --- 4) Add GNOME keyboard shortcut (Custom Shortcuts) --------------------------
if command -v gsettings >/dev/null 2>&1; then
  CURRENT=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings || echo "@as []")
  if [[ "$CURRENT" == "@as []" || "$CURRENT" == "[]" ]]; then
    NEW="['$BINDING_PATH']"
  elif [[ "$CURRENT" == *"$BINDING_PATH"* ]]; then
    NEW="$CURRENT"
  else
    NEW="${CURRENT%]*}, '$BINDING_PATH']"
  fi
  gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$NEW"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$BINDING_PATH" name "$CMD_NAME"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$BINDING_PATH" command "sh -c '$SCRIPT_PATH \"$PDF_DIR_DEFAULT\"'"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$BINDING_PATH" binding "$KEYBIND"
else
  echo "gsettings not found; skipping GNOME keybinding setup." >&2
fi

# --- 5) Summary -----------------------------------------------------------------
echo "\nInstalled: dmenu, fd-find (aka fdfind), zathura(+pdf plugin), xdg-utils."
echo "Script: $SCRIPT_PATH"
echo "PDF folder default: $PDF_DIR_DEFAULT (change by editing the key in the script or pass a path argument)"
echo "Zathura set as default PDF opener (desktop: $DESKTOP_FILE)."
echo "Shortcut: $KEYBIND -> launches '$CMD_NAME' (dmenu top bar)."