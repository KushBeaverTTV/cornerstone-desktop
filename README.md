# Cornerstone Desktop

The tools behind the Cornerstone bar plugins on Omarchy, by Kush Beaver
Productionz. Run `./install.sh` to link them into place.

| Path | What it is |
|---|---|
| `bin/omarchy-dictation-cornerstone` (`cornerstone`) | Cornerstone dictation: local Qwen3-ASR with Whisper as referee, Mistral polish, paste. `cornerstone panic` is the emergency stop; recordings stop by themselves after 10 minutes |
| `bin/cornerstone-gpu-watch` | Warns when dictation uses too much GPU or runs slow |
| `bin/app-summon` | One window per app: brings it to your workspace, closes extra copies, or launches it |
| `bin/discord-ctl`, `bin/muse-ctl`, `bin/cornerstone-hq-open` | Window and action helpers for the Discord, Muse and HQ widgets |
| `bin/webapp-chrome` | Opens a URL as a Chrome app window |
| `bin/taskman-end` | End task for Cornerstone Stats: ends every copy of a program, refuses desktop-critical ones |
| `muse-agent/` | Muse quota reader: a Chrome add-on plus its local helper. Load `usage-extension` with Load unpacked in chrome://extensions |
| `systemd/` | User services for the speech servers and the GPU watch |

The plugins themselves: cornerstone-stats, cornerstone-island,
cornerstone-phones, cornerstone-audio, cornerstone-discord, cornerstone-muse,
cornerstone-dictation, cornerstone-hq-widget, cornerstone-gpu,
cornerstone-capture, cornerstone-rig, cornerstone-worktrees, cornerstone-parked.
