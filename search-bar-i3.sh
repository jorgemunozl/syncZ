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
cat > "$SCRIPT_PATH" <<'EOF_SCRIPT'
#!/usr/bin/env bash
# Top-of-screen dmenu launcher for PDFs; supports page jump via ':12' or '-P 12'.
set -euo pipefail
DIR="${1:-$HOME/zoteroReference/}"
DMENU=${DMENU:-dmenu}
DMENU_ARGS=${DMENU_ARGS:-"-i -p pdf:"}  # single-line, minimal, top bar is default

# Collect PDF list (prefer fd; fallback to find). Output relative paths.
if command -v fd >/dev/null 2>&1; then
  mapfile -t files < <(fd -H -t f -e pdf . "$DIR")
else
  mapfile -t files < <(cd "$DIR" && find . -type f -iname '*.pdf' -printf '%P\n')
fi

# Build display -> path map; show only basenames; disambiguate duplicates with parent dir
declare -A count
for f in "${files[@]}"; do base="${f##*/}"; ((count["$base"]++)) || true; done

mapfile -t lines < <(
  for f in "${files[@]}"; do
    base="${f##*/}"
    if (( count["$base"] > 1 )); then
      parent="${f%/*}"; [[ "$parent" = "." || -z "$parent" ]] && parent="/"
      printf '%s — %s\t%s\n' "$base" "$parent" "$DIR/${f#./}"
    else
      printf '%s\t%s\n' "$base" "$DIR/${f#./}"
    fi
  done | sort -u
)

# Present menu of display names only (dmenu prints selection or typed input)
choice=$(printf '%s\n' "${lines[@]}" | cut -f1 | eval "$DMENU $DMENU_ARGS -p 'pdf (append :12 or -P 12):'") || exit 0
[[ -n "$choice" ]] || exit 0

line="$choice"
file_display="$line"; page=""
# If the user appended a page suffix (when using Tab to paste), strip & parse it
if [[ "$line" =~ (.*)[[:space:]]-P[[:space:]]*([0-9-]+)$ ]]; then
  file_display="${BASH_REMATCH[1]}"; page="${BASH_REMATCH[2]}"
elif [[ "$line" =~ (.*)[:#]([0-9-]+)$ ]]; then
  file_display="${BASH_REMATCH[1]}"; page="${BASH_REMATCH[2]}"
fi
file_display="${file_display%"${file_display##*[![:space:]]}"}"  # rtrim

# Map display -> absolute path
abs_path=$(printf '%s\n' "${lines[@]}" | awk -v sel="$file_display" -F '\t' '($1==sel){print $2; exit}') || true
[[ -n "$abs_path" ]] || exit 1

# Launch zathura (jump to page if provided)
if [[ -n "$page" ]]; then
  exec zathura -P "$page" "$abs_path"
else
  exec zathura "$abs_path"
fi
EOF_SCRIPT

chmod +x "$SCRIPT_PATH"

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
