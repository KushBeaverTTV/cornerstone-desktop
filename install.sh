#!/usr/bin/env bash
# Link the Cornerstone desktop tools into place. Safe to run again.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.local/bin ~/.local/share ~/.config/systemd/user \
         ~/.config/google-chrome/NativeMessagingHosts \
         ~/.config/chromium/NativeMessagingHosts
for f in "$here"/bin/*; do ln -sfn "$f" ~/.local/bin/"$(basename "$f")"; done
ln -sfn ~/.local/bin/omarchy-dictation-cornerstone ~/.local/bin/cornerstone
[ -e ~/.local/share/muse-agent ] || ln -s "$here/muse-agent" ~/.local/share/muse-agent
mkdir -p ~/.local/share/cornerstone-jarvis
ln -sfn "$here/jarvis/jarvisd.py" ~/.local/share/cornerstone-jarvis/jarvisd.py
ext_id="$(cat "$here/muse-agent/ext-id.txt")"
for host_dir in ~/.config/google-chrome/NativeMessagingHosts ~/.config/chromium/NativeMessagingHosts; do
  cat > "$host_dir/com.kushbeaverttv.muse_usage.json" <<JSON
{"name":"com.kushbeaverttv.muse_usage","description":"Saves Muse quota numbers for the Omarchy bar",
 "path":"$HOME/.local/share/muse-agent/usage-host.py","type":"stdio",
 "allowed_origins":["chrome-extension://$ext_id/"]}
JSON
done
for u in "$here"/systemd/*; do cp -rn "$u" ~/.config/systemd/user/; done
systemctl --user daemon-reload
echo "Installed. Plugins live in their own repos (cornerstone-*)."
