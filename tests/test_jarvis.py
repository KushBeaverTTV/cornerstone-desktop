#!/usr/bin/env python3
"""Unit tests for Cornerstone Jarvis helpers (speech sanitizer, step summaries)."""
import importlib.util
import os
import sys

DAEMON_PATH = os.path.expanduser("~/.local/share/cornerstone-jarvis/jarvisd.py")
spec = importlib.util.spec_from_file_location("jarvisd", DAEMON_PATH)
jarvisd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jarvisd)

assert "I've shown the code on screen" in jarvisd.strip_for_speech("Here:\n```bash\nls -la\n```\nDone.")
assert jarvisd.strip_for_speech("Check [shell.json](file:///tmp/a) and `VRAM 28%`!") == "Check shell.json and VRAM 28%!"
assert jarvisd.summarize_step({"step_type": "run_command"}) == "Running command…"
assert jarvisd.summarize_step({"step_type": "agent_response"}) == "Responding…"
assert jarvisd.summarize_step({"step_type": "user_input"}) == ""

print("jarvisd unit tests: PASS")
