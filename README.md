# Cornerstone Desktop

The tools behind the Cornerstone bar plugins on Omarchy, by Kush Beaver
Productionz. Run `./install.sh` to link them into place (or
`./install.sh --configure` to also install/update all Cornerstone plugins and
auto-tailor `~/.config/omarchy/shell.json` to your hardware).

| Path | What it is |
|---|---|
| `bin/cornerstone-device` | Auto-discovers this PC (desktop vs laptop, Apple Silicon / AMD / NVIDIA / Intel GPU, display width, capture backend, browsers, services) and prints a JSON or `--human` profile |
| `bin/cornerstone-sync` | Installs/updates all Cornerstone Omarchy plugins and (`--configure`) tailors `shell.json` for the detected device |
| `bin/cornerstone-capture` | Multi-device screen recording & replay-buffer controller (`gpu-screen-recorder` on supported GPUs, Omarchy `wf-recorder` fallback on Apple Silicon / laptops) |
| `bin/omarchy-dictation-cornerstone` (`cornerstone`) | Cornerstone dictation: local Qwen3-ASR with Whisper as referee, Mistral polish, paste. `cornerstone panic` is the emergency stop; recordings stop by themselves after 10 minutes |
| `bin/cornerstone-jarvis` + `jarvis/jarvisd.py` | Cornerstone Jarvis: hands-free `"Hey Jarvis"` wake word (`openWakeWord`), local GPU STT, streaming `agy` agent bridge, and Piper British TTS voice replies integrated into the Dynamic Island |
| `bin/cornerstone-gpu-watch` | Warns when dictation uses too much GPU or runs slow |
| `bin/app-summon` | One window per app: brings it to your workspace, closes extra copies, or launches it |
| `bin/discord-ctl`, `bin/muse-ctl`, `bin/cornerstone-hq-open` | Window and action helpers for the Discord, Muse and HQ widgets |
| `bin/webapp-chrome` | Opens a URL as an app window in the first installed Chromium-family browser (Chrome, Chromium, Brave, Vivaldi, Edge) |
| `bin/taskman-end` | End task for Cornerstone Stats: ends every copy of a program, refuses desktop-critical ones |
| `muse-agent/` | Muse quota reader: a Chrome/Chromium/Brave add-on plus its local helper. Load `usage-extension` with Load unpacked in `chrome://extensions` |
| `systemd/` | User services installed selectively based on detected hardware (pass `--all-systemd` to copy everything) |

The plugins themselves: cornerstone-stats, cornerstone-island,
cornerstone-phones, cornerstone-audio, cornerstone-discord, cornerstone-muse,
cornerstone-dictation, cornerstone-hq-widget, cornerstone-gpu,
cornerstone-capture, cornerstone-rig, cornerstone-worktrees, cornerstone-parked.
