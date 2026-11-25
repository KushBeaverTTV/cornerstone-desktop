#!/usr/bin/env python3
"""Chrome native-messaging host: saves the Muse quota numbers the add-on read,
for the Omarchy bar widget. Validates everything; writes one small JSON file."""
import json, os, shutil, struct, subprocess, sys, time

OUT = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "muse-widget", "usage.json")

def read_msg():
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:
        return None
    n = struct.unpack("<I", raw)[0]
    if n > 4096:
        return None
    return json.loads(sys.stdin.buffer.read(n).decode("utf-8"))

def reply(obj):
    b = json.dumps(obj).encode()
    sys.stdout.buffer.write(struct.pack("<I", len(b)) + b)
    sys.stdout.buffer.flush()

def clean(d):
    out = {}
    if isinstance(d.get("weeklyPct"), (int, float)) and 0 <= d["weeklyPct"] <= 100:
        out["weeklyPct"] = round(float(d["weeklyPct"]), 1)
    if isinstance(d.get("sessionPct"), (int, float)) and 0 <= d["sessionPct"] <= 100:
        out["sessionPct"] = round(float(d["sessionPct"]), 1)
    if isinstance(d.get("extraTokens"), (int, float)) and 0 <= d["extraTokens"] < 1e15:
        out["extraTokens"] = float(d["extraTokens"])
    for k, lim in (("resetText", 48), ("sessionResetText", 48), ("extraText", 40), ("plan", 24)):
        v = d.get(k)
        if isinstance(v, str):
            v = "".join(c for c in v if c.isprintable())[:lim].strip()
            if v:
                out[k] = v
    return out

def notify_shell():
    exe = shutil.which("omarchy-shell")
    if not exe:
        return
    try:
        subprocess.Popen([exe, "muse", "refresh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def main():
    msg = read_msg()
    if not isinstance(msg, dict):
        return
    new = clean(msg)
    if not new:
        reply({"ok": False}); return
    try:
        with open(OUT) as f:
            old = json.load(f)
    except Exception:
        old = {}
    merged = {**old, **new, "updated": int(time.time())}
    peaks = [float(old.get("extraPeak", 0)), float(old.get("extraTokens", 0)), float(merged.get("extraTokens", 0))]
    if max(peaks) > 0:
        merged["extraPeak"] = max(peaks)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(merged, f)
    os.replace(tmp, OUT)
    notify_shell()
    reply({"ok": True})

if __name__ == "__main__":
    main()
