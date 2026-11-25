#!/usr/bin/env python3
"""Cornerstone Jarvis daemon: hands-free wake word ('Hey Jarvis'), local GPU STT,
streaming default-agent (agy) runner, and local Piper British TTS voice replies.

State is published atomically to ~/.local/state/cornerstone-jarvis/state.json for
cornerstone.island to observe via FileView. Commands arrive over a local UNIX socket
at ~/.local/state/cornerstone-jarvis/jarvis.sock.
"""
import json
import math
import os
import re
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave

import numpy as np

HOME = os.path.expanduser("~")
DATA_DIR = os.path.join(HOME, ".local", "share", "cornerstone-jarvis")
CONF_DIR = os.path.join(HOME, ".config", "omarchy", "cornerstone-jarvis")
STATE_DIR = os.path.join(HOME, ".local", "state", "cornerstone-jarvis")
STATE_PATH = os.path.join(STATE_DIR, "state.json")
CONF_PATH = os.path.join(CONF_DIR, "config.json")
SOCK_PATH = os.path.join(STATE_DIR, "jarvis.sock")
VOICE_MODEL = os.path.join(DATA_DIR, "models", "en_GB-alan-medium.onnx")
DICTATION_BIN = os.path.join(HOME, ".local", "bin", "omarchy-dictation-cornerstone")
WORK_DIR = os.path.join(HOME, "Work") if os.path.isdir(os.path.join(HOME, "Work")) else HOME

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # 80 ms @ 16 kHz (native openWakeWord frame)
CHUNK_BYTES = CHUNK_SAMPLES * 2

DEFAULT_CONFIG = {
    "wakeEnabled": True,
    "ttsEnabled": True,
    "wakeThreshold": 0.55,
    "silenceSeconds": 1.35,
    "maxListenSeconds": 18.0,
    "threadTtlSeconds": 900,
    "speechRmsThreshold": 380,
}

QUIET_STREAMS = (
    "cornerstone-jarvis", "cornerstone-dictation",
    "gsr-default_output", "default_output", "gsr-app",
    "peak", "monitor", "cava", "easyeffects",
)

VOICE_FRAMING = (
    "[Cornerstone Jarvis — Omarchy Dynamic Island voice & quick-ask mode. "
    "The user is speaking or quick-typing from the desktop notch. "
    "Respond concisely in 1-3 short, natural sentences unless asked for detail. "
    "Avoid markdown tables, raw file paths, or long code blocks in spoken answers.]\n\n"
)


def strip_for_speech(text: str) -> str:
    """Turn an agent markdown reply into clean, natural spoken English."""
    if not text:
        return ""
    s = re.sub(r"```[\s\S]*?```", " I've shown the code on screen. ", text)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"file://\S+", "", s)
    s = re.sub(r"[*_#~>|]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 480:
        cut = s[:480]
        last = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        s = cut[: last + 1] if last > 120 else cut.rstrip() + "."
    return s


def summarize_step(step: dict) -> str:
    """Produce a short human-readable status line from an agy stream-json step_update."""
    st = str(step.get("step_type") or "").lower()
    if not st or st == "user_input":
        return ""
    if "think" in st or "plan" in st:
        return "Thinking…"
    if "command" in st or "shell" in st or "terminal" in st:
        return "Running command…"
    if "search" in st or "grep" in st or "find" in st or "web" in st:
        return "Searching…"
    if "read" in st or "view" in st or "list" in st:
        return "Checking files…"
    if "write" in st or "edit" in st or "replace" in st:
        return "Making changes…"
    if "agent_response" in st:
        return "Responding…"
    return st.replace("_", " ").capitalize() + "…"


def active_external_mic_app() -> str:
    """Return the app name of another active microphone recorder (e.g. Discord, OBS), or ''."""
    try:
        out = subprocess.check_output(["pactl", "list", "source-outputs"], text=True, timeout=1.5)
    except Exception:
        return ""
    blocks = out.split("Source Output #")[1:]
    for blk in blocks:
        if "Corked: yes" in blk:
            continue
        m_app = re.search(r'application\.name\s*=\s*"([^"]+)"', blk)
        m_media = re.search(r'media\.name\s*=\s*"([^"]+)"', blk)
        app = (m_app.group(1) if m_app else "").strip()
        media = (m_media.group(1) if m_media else "").strip()
        combined = f"{app} {media}".lower()
        if not combined.strip():
            continue
        if any(q in combined for q in QUIET_STREAMS):
            continue
        return app or media
    return ""


def generate_chime(path: str, freqs: list, dur: float = 0.085, vol: float = 0.22):
    """Synthesize a crisp, pleasant two-tone chime WAV (no external assets needed)."""
    sr = 24000
    frames = []
    for f in freqs:
        n = int(sr * dur)
        for i in range(n):
            t = i / sr
            env = math.sin(math.pi * (i / n)) ** 1.4
            val = math.sin(2.0 * math.pi * f * t) * env * vol
            frames.append(int(max(-1.0, min(1.0, val)) * 32767))
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack("<" + "h" * len(frames), *frames))


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except Exception:
        pass
    return cfg


def save_config(cfg: dict):
    os.makedirs(CONF_DIR, exist_ok=True)
    tmp = CONF_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONF_PATH)


def preferred_mic_target() -> str:
    """Honor Cornerstone Audio's pinned mic for 'Cornerstone' if set."""
    pins = os.path.join(HOME, ".config", "omarchy", "audio-mic-pins.json")
    try:
        with open(pins, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            val = data.get("Cornerstone") or data.get("Jarvis") or ""
            return str(val).strip()
    except Exception:
        pass
    return ""


class JarvisDaemon:
    def __init__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        os.makedirs(CONF_DIR, exist_ok=True)
        self.cfg = load_config()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()

        # Audio chimes
        self.chime_start = os.path.join(STATE_DIR, "chime-start.wav")
        self.chime_done = os.path.join(STATE_DIR, "chime-done.wav")
        generate_chime(self.chime_start, [587.33, 880.0], dur=0.075, vol=0.20)
        generate_chime(self.chime_done, [880.0, 659.25], dur=0.07, vol=0.16)

        self.state = {
            "phase": "idle",
            "wakeEnabled": bool(self.cfg.get("wakeEnabled", True)),
            "wakeGated": False,
            "wakeGateReason": "",
            "ttsEnabled": bool(self.cfg.get("ttsEnabled", True)),
            "conversationId": "",
            "prompt": "",
            "statusLine": "",
            "reply": "",
            "error": "",
            "startedAt": 0.0,
            "updatedAt": time.time(),
            "level": 0.0,
            "turnCount": 0,
            "wakeReady": False,
            "ttsReady": os.path.isfile(VOICE_MODEL),
        }
        self._last_thread_at = 0.0
        self._listen_stop = threading.Event()
        self._active_agent_proc = None
        self._active_tts_proc = None
        self._worker_thread = None
        self._wake_model = None
        self._piper_voice = None
        self._piper_lock = threading.Lock()
        self._wake_cooldown_until = 0.0
        self._publish_state()

    def _publish_state(self):
        with self.lock:
            self.state["updatedAt"] = time.time()
            payload = json.dumps(self.state, ensure_ascii=False)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, STATE_PATH)

    def _update(self, **kwargs):
        with self.lock:
            self.state.update(kwargs)
        self._publish_state()

    def _play_chime(self, path: str):
        if os.path.isfile(path) and shutil.which("pw-play"):
            try:
                subprocess.Popen(
                    ["pw-play", "--media-name", "cornerstone-jarvis-cue", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def _load_wake_model(self):
        if self._wake_model is not None:
            return self._wake_model
        try:
            import openwakeword
            paths = openwakeword.get_pretrained_model_paths()
            jarvis = [p for p in paths if "hey_jarvis" in os.path.basename(p).lower()]
            if not jarvis:
                return None
            self._wake_model = openwakeword.Model(wakeword_model_paths=jarvis, vad_threshold=0.5)
            self._update(wakeReady=True)
            return self._wake_model
        except Exception as e:
            sys.stderr.write(f"openWakeWord init failed: {e}\n")
            self._update(wakeReady=False)
            return None

    def _load_piper(self):
        with self._piper_lock:
            if self._piper_voice is not None:
                return self._piper_voice
            if not os.path.isfile(VOICE_MODEL):
                return None
            try:
                from piper import PiperVoice
                self._piper_voice = PiperVoice.load(VOICE_MODEL)
                self._update(ttsReady=True)
                return self._piper_voice
            except Exception as e:
                sys.stderr.write(f"Piper init failed: {e}\n")
                self._update(ttsReady=False)
                return None

    def _pw_record_cmd(self, out_target: str, fmt: str = "raw") -> list:
        cmd = [
            "pw-record",
            "--rate", str(SAMPLE_RATE),
            "--channels", "1",
            "--format", "s16",
            "-P", '{ media.name = "cornerstone-jarvis" application.name = "cornerstone-jarvis" }',
        ]
        target = preferred_mic_target()
        if target:
            cmd += ["--target", target]
        if fmt == "raw":
            cmd += ["--raw", out_target]
        else:
            cmd += [out_target]
        return cmd

    def stop_active(self):
        """Cancel listening, agent generation, or TTS playback cleanly."""
        self._listen_stop.set()
        with self.lock:
            ap = self._active_agent_proc
            tp = self._active_tts_proc
            self._active_agent_proc = None
            self._active_tts_proc = None
        for p in (tp, ap):
            if p and p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=1.5)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
        with self.lock:
            cur = self.state["phase"]
        if cur in ("listening", "transcribing", "thinking", "speaking"):
            self._update(
                phase="reply" if self.state.get("reply") else "idle",
                statusLine="",
                level=0.0,
            )

    def _speak(self, text: str):
        with self.lock:
            if not self.state.get("ttsEnabled"):
                return
        spoken = strip_for_speech(text)
        if not spoken:
            return
        voice = self._load_piper()
        if voice is None:
            return
        self._update(phase="speaking", statusLine="Speaking…")
        wav_path = os.path.join(STATE_DIR, "tts-reply.wav")
        try:
            with wave.open(wav_path, "wb") as wf:
                voice.synthesize_wav(spoken, wf)
            proc = subprocess.Popen(
                ["pw-play", "--media-name", "cornerstone-jarvis-tts", wav_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            with self.lock:
                self._active_tts_proc = proc
            proc.wait()
        except Exception as e:
            sys.stderr.write(f"TTS error: {e}\n")
        finally:
            with self.lock:
                self._active_tts_proc = None
                still_speaking = self.state["phase"] == "speaking"
            if still_speaking:
                self._update(phase="reply", statusLine="")

    def _run_agent(self, prompt: str):
        prompt = prompt.strip()
        if not prompt:
            self._update(phase="idle", statusLine="")
            return
        now = time.time()
        ttl = float(self.cfg.get("threadTtlSeconds", 900))
        with self.lock:
            conv_id = self.state.get("conversationId") or ""
            if conv_id and (now - self._last_thread_at) > ttl:
                conv_id = ""
                self.state["conversationId"] = ""
                self.state["turnCount"] = 0
            turn = int(self.state.get("turnCount") or 0)

        full_prompt = (VOICE_FRAMING + prompt) if not conv_id else prompt
        cmd = [
            "agy",
            "--dangerously-skip-permissions",
            "--output-format", "stream-json",
            f"--print={full_prompt}",
        ]
        if conv_id:
            cmd += ["--conversation", conv_id]

        self._update(
            phase="thinking",
            prompt=prompt,
            statusLine="Thinking…",
            error="",
            startedAt=now,
            level=0.0,
        )

        streamed = []
        final_reply = ""
        new_conv_id = conv_id
        err_msg = ""

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=WORK_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            with self.lock:
                self._active_agent_proc = proc

            for raw_line in proc.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                kind = ev.get("event")
                if kind == "init":
                    cid = ev.get("conversation_id") or ""
                    if cid:
                        new_conv_id = cid
                        self._update(conversationId=cid)
                elif kind == "step_update":
                    su = ev.get("step_update") or {}
                    cid = su.get("conversation_id") or ""
                    if cid:
                        new_conv_id = cid
                    delta = su.get("text_delta")
                    if delta:
                        streamed.append(delta)
                        self._update(reply="".join(streamed).strip(), statusLine="Responding…")
                    else:
                        label = summarize_step(su)
                        if label:
                            self._update(statusLine=label)
                elif kind == "result":
                    res = ev.get("result") or {}
                    cid = res.get("conversation_id") or ""
                    if cid:
                        new_conv_id = cid
                    resp = res.get("response")
                    if resp:
                        final_reply = str(resp).strip()
                    if res.get("status") not in (None, "SUCCESS"):
                        err_msg = str(res.get("error") or res.get("status"))

            stderr_tail = (proc.stderr.read() or "").strip()
            rc = proc.wait()
            with self.lock:
                was_cancelled = self._active_agent_proc is None
                self._active_agent_proc = None

            if was_cancelled:
                return

            reply = final_reply or "".join(streamed).strip()
            if rc != 0 and not reply:
                err_msg = err_msg or (stderr_tail.splitlines()[-1] if stderr_tail else f"agy exited {rc}")
                self._update(phase="error", error=err_msg, statusLine="")
                return

            self._last_thread_at = time.time()
            self._update(
                phase="reply",
                conversationId=new_conv_id,
                reply=reply,
                statusLine="",
                error="",
                turnCount=turn + 1,
            )
            self._speak(reply)
        except Exception as e:
            with self.lock:
                self._active_agent_proc = None
            self._update(phase="error", error=str(e), statusLine="")

    def _transcribe_wav(self, wav_path: str) -> str:
        # Prefer Cornerstone's already-loaded GPU STT pipeline (types nothing).
        if os.path.isfile(DICTATION_BIN):
            try:
                r = subprocess.run(
                    [DICTATION_BIN, "transcribe-file", wav_path],
                    capture_output=True, text=True, timeout=60,
                )
                txt = (r.stdout or "").strip()
                if r.returncode == 0 and txt:
                    return txt
            except Exception as e:
                sys.stderr.write(f"transcribe-file error: {e}\n")
        return ""

    def _capture_and_ask(self, from_wake: bool = False):
        self._listen_stop.clear()
        self._play_chime(self.chime_start)
        self._update(
            phase="listening",
            statusLine="Listening…" if not from_wake else "Hey Jarvis — listening…",
            error="",
            startedAt=time.time(),
            level=0.0,
        )

        pcm_chunks = []
        speech_started = False
        speech_started_at = 0.0
        last_speech_at = time.time()
        started_at = time.time()
        max_sec = float(self.cfg.get("maxListenSeconds", 18.0))
        sil_sec = float(self.cfg.get("silenceSeconds", 1.35))
        rms_thresh = float(self.cfg.get("speechRmsThreshold", 380))
        last_level_push = 0.0

        proc = None
        try:
            proc = subprocess.Popen(
                self._pw_record_cmd("-", fmt="raw"),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            fd = proc.stdout.fileno()
            while not self.stop_event.is_set() and not self._listen_stop.is_set():
                rlist, _, _ = select.select([fd], [], [], 0.1)
                now = time.time()
                if now - started_at >= max_sec:
                    break
                if not rlist:
                    continue
                data = os.read(fd, CHUNK_BYTES)
                if not data:
                    break
                pcm_chunks.append(data)
                if len(data) >= 2:
                    arr = np.frombuffer(data[: (len(data) // 2) * 2], dtype=np.int16).astype(np.float32)
                    rms = float(np.sqrt(np.mean(arr * arr))) if arr.size else 0.0
                    norm = min(1.0, rms / 4500.0)
                    if rms >= rms_thresh:
                        if not speech_started:
                            speech_started = True
                            speech_started_at = now
                        last_speech_at = now
                    if now - last_level_push >= 0.12:
                        last_level_push = now
                        self._update(level=round(norm, 2))
                # Auto-end after silence once the user has started speaking,
                # or give up after 5s of pure silence from a wake-word trigger.
                if speech_started and (now - speech_started_at) >= 0.5 and (now - last_speech_at) >= sil_sec:
                    break
                if from_wake and not speech_started and (now - started_at) >= 5.0:
                    break
        except Exception as e:
            sys.stderr.write(f"Listen error: {e}\n")
        finally:
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

        self._play_chime(self.chime_done)
        raw_pcm = b"".join(pcm_chunks)
        if len(raw_pcm) < SAMPLE_RATE * 2 * 0.25:
            self._update(phase="reply" if self.state.get("reply") else "idle", statusLine="", level=0.0)
            return

        wav_path = os.path.join(STATE_DIR, "utterance.wav")
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(raw_pcm)

        self._update(phase="transcribing", statusLine="Transcribing…", level=0.0)
        text = self._transcribe_wav(wav_path)
        # Strip accidental leading wake-phrase echo if STT caught the tail of "Hey Jarvis"
        text = re.sub(r"^(hey[\s,]+jarvis|jarvis)[\s,.:!?-]+", "", text, flags=re.I).strip()
        if not text:
            self._update(
                phase="reply" if self.state.get("reply") else "idle",
                statusLine="",
                error="" if from_wake else "Didn't catch anything",
            )
            return
        self._run_agent(text)

    def trigger_listen(self, from_wake: bool = False):
        with self.lock:
            phase = self.state["phase"]
        if phase == "listening":
            # Second press stops recording immediately and sends what was captured.
            self._listen_stop.set()
            return
        if phase in ("transcribing", "thinking", "speaking"):
            self.stop_active()
            time.sleep(0.1)
        t = threading.Thread(target=self._capture_and_ask, args=(from_wake,), daemon=True)
        self._worker_thread = t
        t.start()

    def trigger_ask(self, text: str):
        text = str(text or "").strip()
        if not text:
            return
        with self.lock:
            phase = self.state["phase"]
        if phase in ("listening", "transcribing", "thinking", "speaking"):
            self.stop_active()
            time.sleep(0.05)
        t = threading.Thread(target=self._run_agent, args=(text,), daemon=True)
        self._worker_thread = t
        t.start()

    def set_wake(self, mode: str) -> bool:
        with self.lock:
            cur = bool(self.state["wakeEnabled"])
            nxt = (not cur) if mode == "toggle" else (mode == "on")
            self.cfg["wakeEnabled"] = nxt
            save_config(self.cfg)
        self._update(wakeEnabled=nxt)
        return nxt

    def set_tts(self, mode: str) -> bool:
        with self.lock:
            cur = bool(self.state["ttsEnabled"])
            nxt = (not cur) if mode == "toggle" else (mode == "on")
            self.cfg["ttsEnabled"] = nxt
            save_config(self.cfg)
        if not nxt and self.state.get("phase") == "speaking":
            self.stop_active()
        self._update(ttsEnabled=nxt)
        return nxt

    def reset_thread(self):
        self.stop_active()
        self._last_thread_at = 0.0
        self._update(
            phase="idle",
            conversationId="",
            prompt="",
            reply="",
            statusLine="",
            error="",
            turnCount=0,
            level=0.0,
        )

    def _wake_loop(self):
        """Always-on CPU wake-word listener ('Hey Jarvis'), auto-gated during Discord/OBS mic use."""
        proc = None
        last_gate_check = 0.0
        buf = bytearray()

        def close_proc():
            nonlocal proc, buf
            buf.clear()
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            proc = None

        while not self.stop_event.is_set():
            with self.lock:
                enabled = bool(self.state["wakeEnabled"])
                phase = self.state["phase"]

            busy = phase in ("listening", "transcribing", "thinking", "speaking")
            now = time.time()

            if not enabled or busy:
                close_proc()
                if not enabled and self.state.get("wakeGated"):
                    self._update(wakeGated=False, wakeGateReason="")
                time.sleep(0.25)
                continue

            if now - last_gate_check >= 2.0:
                last_gate_check = now
                blocker = active_external_mic_app()
                gated = bool(blocker)
                if gated != self.state.get("wakeGated") or blocker != self.state.get("wakeGateReason"):
                    self._update(wakeGated=gated, wakeGateReason=blocker)

            if self.state.get("wakeGated"):
                close_proc()
                time.sleep(0.4)
                continue

            model = self._load_wake_model()
            if model is None:
                time.sleep(5.0)
                continue

            if proc is None or proc.poll() is not None:
                try:
                    proc = subprocess.Popen(
                        self._pw_record_cmd("-", fmt="raw"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                    )
                    buf.clear()
                    model.reset()
                except Exception as e:
                    sys.stderr.write(f"Wake pw-record failed: {e}\n")
                    time.sleep(2.0)
                    continue

            fd = proc.stdout.fileno()
            rlist, _, _ = select.select([fd], [], [], 0.25)
            if not rlist:
                continue
            chunk = os.read(fd, CHUNK_BYTES)
            if not chunk:
                close_proc()
                time.sleep(0.5)
                continue
            buf.extend(chunk)
            while len(buf) >= CHUNK_BYTES:
                frame = bytes(buf[:CHUNK_BYTES])
                del buf[:CHUNK_BYTES]
                pcm = np.frombuffer(frame, dtype=np.int16)
                scores = model.predict(pcm)
                best = max(scores.values()) if scores else 0.0
                if best >= float(self.cfg.get("wakeThreshold", 0.55)) and time.time() >= self._wake_cooldown_until:
                    self._wake_cooldown_until = time.time() + 3.0
                    close_proc()
                    self.trigger_listen(from_wake=True)
                    break

        close_proc()

    def handle_command(self, raw: str) -> dict:
        try:
            req = json.loads(raw)
        except Exception:
            req = {"cmd": raw.strip()}
        cmd = str(req.get("cmd") or "").strip().lower()
        arg = req.get("arg")
        if cmd == "listen":
            self.trigger_listen(from_wake=False)
            return {"ok": True, "phase": self.state["phase"]}
        if cmd == "ask":
            self.trigger_ask(str(arg or ""))
            return {"ok": True}
        if cmd == "stop":
            self.stop_active()
            return {"ok": True}
        if cmd == "reset":
            self.reset_thread()
            return {"ok": True}
        if cmd == "wake":
            val = self.set_wake(str(arg or "toggle"))
            return {"ok": True, "wakeEnabled": val}
        if cmd == "tts":
            val = self.set_tts(str(arg or "toggle"))
            return {"ok": True, "ttsEnabled": val}
        if cmd == "status":
            with self.lock:
                return {"ok": True, "state": dict(self.state)}
        if cmd == "ping":
            return {"ok": True}
        return {"ok": False, "error": f"unknown command: {cmd}"}

    def serve(self):
        if os.path.exists(SOCK_PATH):
            try:
                os.unlink(SOCK_PATH)
            except OSError:
                pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(SOCK_PATH)
        os.chmod(SOCK_PATH, 0o600)
        srv.listen(16)
        srv.settimeout(0.5)

        wake_thread = threading.Thread(target=self._wake_loop, daemon=True)
        wake_thread.start()

        # Pre-warm Piper model in background so first reply speaks instantly.
        threading.Thread(target=self._load_piper, daemon=True).start()

        def _sig(_signum, _frame):
            self.stop_event.set()

        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)

        try:
            while not self.stop_event.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with conn:
                    conn.settimeout(2.0)
                    try:
                        data = conn.recv(65536).decode("utf-8", errors="replace")
                        resp = self.handle_command(data)
                        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    except Exception as e:
                        try:
                            conn.sendall((json.dumps({"ok": False, "error": str(e)}) + "\n").encode("utf-8"))
                        except Exception:
                            pass
        finally:
            self.stop_active()
            srv.close()
            try:
                os.unlink(SOCK_PATH)
            except OSError:
                pass


if __name__ == "__main__":
    JarvisDaemon().serve()
