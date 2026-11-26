#!/usr/bin/env bash
# Link the Cornerstone desktop tools into place, adapted to this device.
# Safe to run again.
#
# Flags:
#   --plugins      Also install/update all Cornerstone Omarchy plugins
#   --configure    Tailor ~/.config/omarchy/shell.json to this device (implies --plugins)
#   --all-systemd  Copy all desktop-rig systemd drop-ins even on laptops/minimal hosts
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

DO_PLUGINS=0
DO_CONFIGURE=0
ALL_SYSTEMD=0
for arg in "$@"; do
  case "$arg" in
    --plugins) DO_PLUGINS=1 ;;
    --configure) DO_PLUGINS=1; DO_CONFIGURE=1 ;;
    --all-systemd) ALL_SYSTEMD=1 ;;
    -h|--help)
      sed -n '2,9p' "$0"
      exit 0
      ;;
  esac
done

mkdir -p ~/.local/bin ~/.local/share ~/.config/systemd/user ~/.local/share/cornerstone-jarvis

for f in "$here"/bin/*; do
  chmod +x "$f"
  ln -sfn "$f" ~/.local/bin/"$(basename "$f")"
done
ln -sfn ~/.local/bin/omarchy-dictation-cornerstone ~/.local/bin/cornerstone
[ -e ~/.local/share/muse-agent ] || ln -s "$here/muse-agent" ~/.local/share/muse-agent
ln -sfn "$here/jarvis/jarvisd.py" ~/.local/share/cornerstone-jarvis/jarvisd.py

# Register the Muse usage native messaging host for every Chromium-family browser present
ext_id="$(cat "$here/muse-agent/ext-id.txt")"
browser_dirs=(
  "$HOME/.config/google-chrome/NativeMessagingHosts"
  "$HOME/.config/chromium/NativeMessagingHosts"
)
for extra in \
  "$HOME/.config/BraveSoftware/Brave-Browser" \
  "$HOME/.config/vivaldi" \
  "$HOME/.config/microsoft-edge"; do
  [[ -d $extra ]] && browser_dirs+=("$extra/NativeMessagingHosts")
done
for host_dir in "${browser_dirs[@]}"; do
  mkdir -p "$host_dir"
  cat > "$host_dir/com.kushbeaverttv.muse_usage.json" <<JSON
{"name":"com.kushbeaverttv.muse_usage","description":"Saves Muse quota numbers for the Omarchy bar",
 "path":"$HOME/.local/share/muse-agent/usage-host.py","type":"stdio",
 "allowed_origins":["chrome-extension://$ext_id/"]}
JSON
done

# Copy only device-appropriate systemd user units unless --all-systemd is passed
profile_json="$("$here/bin/cornerstone-device" 2>/dev/null || echo '{}')"
has_discrete_gpu="$(printf '%s' "$profile_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(1 if d.get("gpu",{}).get("hasDiscreteVram") else 0)' 2>/dev/null || echo 0)"
has_storage="$(printf '%s' "$profile_json" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(1 if d.get("hardware",{}).get("storageMount") else 0)' 2>/dev/null || echo 0)"

if (( ALL_SYSTEMD )); then
  for u in "$here"/systemd/*; do cp -rn "$u" ~/.config/systemd/user/; done
else
  # Always safe general units
  for u in cornerstone-jarvis.service cornerstone-stt.service; do
    [[ -e "$here/systemd/$u" ]] && cp -rn "$here/systemd/$u" ~/.config/systemd/user/
  done
  # Discrete GPU units only on machines with discrete VRAM
  if (( has_discrete_gpu )); then
    for u in cornerstone-gpu-watch.service cornerstone-gpu-watch.timer cornerstone-stt-gpu.service cornerstone-stt-qwen.service; do
      [[ -e "$here/systemd/$u" ]] && cp -rn "$here/systemd/$u" ~/.config/systemd/user/
    done
  fi
  # /mnt/storage & HQ service drop-ins only when /mnt/storage exists on this PC
  if (( has_storage )); then
    for u in "$here"/systemd/*; do cp -rn "$u" ~/.config/systemd/user/; done
  fi
fi

systemctl --user daemon-reload 2>/dev/null || true

echo "=== Cornerstone Device Profile ==="
"$here/bin/cornerstone-device" --human || true
echo ""

if (( DO_PLUGINS )); then
  sync_args=()
  (( DO_CONFIGURE )) && sync_args+=(--configure)
  "$here/bin/cornerstone-sync" "${sync_args[@]}"
else
  echo "Installed tools. Run 'cornerstone-sync --configure' (or './install.sh --configure') to sync & tailor all Cornerstone bar plugins."
fi
