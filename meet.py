#!/usr/bin/env python3
"""
meet — Meeting Sentinel CLI

Records meeting audio on macOS via BlackHole + ffmpeg, then transcribes
using your chosen provider (Soniox, ElevenLabs, or local Whisper).

Commands:
    meet setup              First-run config (paths + transcription provider)
    meet start [-n NAME]    Start recording
    meet stop               Stop recording and transcribe
    meet watch              Daemon — auto-prompts when meeting apps open
    meet transcribe FILE    Transcribe an existing audio file
    meet status             Show current recording state
    meet devices            List available audio input devices
    meet unprocessed        List transcripts with no matching notes file
    meet config             Print active config and paths
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from meeting_sentinel.config import (
    CONFIG_PATH,
    STATE_PATH,
    Config,
    load_config,
    run_setup_wizard,
)
from meeting_sentinel.transcribers import get_transcriber


MEETING_APPS_DEFAULT = ["zoom.us", "Microsoft Teams", "WeChat", "FaceTime"]
POLL_INTERVAL = 15


def _ensure_dirs(cfg: Config) -> None:
    cfg.recordings_dir.mkdir(parents=True, exist_ok=True)
    cfg.transcripts_dir.mkdir(parents=True, exist_ok=True)


def _require_config() -> Config:
    cfg = load_config()
    if cfg is None:
        print("No config found. Running first-run setup...\n")
        cfg = run_setup_wizard()
    return cfg


# ────────────────── state ──────────────────

def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _clear_state() -> None:
    if STATE_PATH.exists():
        STATE_PATH.unlink()


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _is_recording() -> bool:
    state = _load_state()
    pid = state.get("pid")
    return bool(pid and _process_alive(pid))


# ────────────────── devices ──────────────────

def _list_devices_output() -> str:
    result = subprocess.run(
        ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    )
    return result.stderr


def _find_device_index(name: str, output: str | None = None) -> str | None:
    out = output or _list_devices_output()
    in_audio = False
    for line in out.split("\n"):
        if "AVFoundation audio devices:" in line:
            in_audio = True
            continue
        if in_audio and name in line:
            for part in line.split("["):
                part = part.strip()
                if part and part[0].isdigit():
                    return part.split("]")[0]
    return None


# ────────────────── notifications ──────────────────

def _show_dialog(message: str, buttons: list[str] | None = None) -> str | None:
    buttons = buttons or ["OK"]
    btn_str = ", ".join(f'"{b}"' for b in buttons)
    script = (
        f'display dialog "{message}" '
        f"buttons {{{btn_str}}} default button \"{buttons[-1]}\" "
        f"with icon note"
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            for part in result.stdout.strip().split(","):
                if "button returned:" in part:
                    return part.split("button returned:")[1].strip()
        return None
    except subprocess.TimeoutExpired:
        return None


def _notify(title: str, message: str) -> None:
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _app_running(name: str) -> bool:
    return subprocess.run(["pgrep", "-xi", name], capture_output=True).returncode == 0


# ────────────────── commands ──────────────────

def cmd_setup(args) -> int:
    run_setup_wizard()
    return 0


def cmd_config(args) -> int:
    cfg = load_config()
    if cfg is None:
        print("No config found. Run: meet setup")
        return 1
    print(f"Config file:        {CONFIG_PATH}")
    print(f"Recordings dir:     {cfg.recordings_dir}")
    print(f"Transcripts dir:    {cfg.transcripts_dir}")
    print(f"Transcriber:        {cfg.transcriber}")
    if cfg.transcriber_options:
        print(f"Transcriber opts:   {cfg.transcriber_options}")
    print(f"Blackhole device:   {cfg.blackhole_device}")
    print(f"Mic device:         {cfg.mic_device}")
    print(f"Meeting apps:       {', '.join(cfg.meeting_apps)}")
    return 0


def cmd_start(args) -> int:
    cfg = _require_config()

    if _is_recording():
        state = _load_state()
        print(f"Already recording: {state.get('name', 'unknown')}")
        print("Run `meet stop` first.")
        return 1

    _ensure_dirs(cfg)

    devices_output = _list_devices_output()
    mic_index = _find_device_index(cfg.mic_device, devices_output)
    bh_index = _find_device_index(cfg.blackhole_device, devices_output)

    if mic_index is None and bh_index is None:
        print("No audio input devices found. Run `meet devices` to debug.")
        return 1

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    name = args.name or f"meeting-{timestamp}"
    audio_file = cfg.recordings_dir / f"{name}.m4a"

    if mic_index and bh_index:
        cmd = [
            "ffmpeg",
            "-f", "avfoundation", "-i", f"none:{mic_index}",
            "-f", "avfoundation", "-i", f"none:{bh_index}",
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest[aout]",
            "-map", "[aout]",
            "-c:a", "aac", "-b:a", "128k",
            "-y", str(audio_file),
        ]
        print("Recording mic + system audio (mixed)")
    elif mic_index:
        cmd = [
            "ffmpeg",
            "-f", "avfoundation", "-i", f"none:{mic_index}",
            "-c:a", "aac", "-b:a", "128k",
            "-y", str(audio_file),
        ]
        print("Recording mic only (BlackHole not found)")
    else:
        cmd = [
            "ffmpeg",
            "-f", "avfoundation", "-i", f"none:{bh_index}",
            "-c:a", "aac", "-b:a", "128k",
            "-y", str(audio_file),
        ]
        print("Recording system audio only (mic not found)")

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    _save_state({
        "pid": proc.pid,
        "audio_file": str(audio_file),
        "started_at": datetime.datetime.now().isoformat(),
        "name": name,
    })

    print(f"Recording started: {audio_file.name}")
    _notify("Meeting Sentinel", f"Recording: {name}")
    return 0


def cmd_stop(args) -> int:
    cfg = _require_config()
    state = _load_state()
    pid = state.get("pid")
    audio_file = state.get("audio_file")

    if not pid or not audio_file:
        print("No active recording.")
        return 1

    try:
        os.kill(pid, signal.SIGINT)
        time.sleep(2)
        if _process_alive(pid):
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
    except OSError:
        pass

    audio_path = Path(audio_file)
    _clear_state()

    if not audio_path.exists() or audio_path.stat().st_size < 1024:
        print("Recording file missing or too small. Nothing to transcribe.")
        return 1

    size_mb = audio_path.stat().st_size / 1024 / 1024
    print(f"Recording stopped: {audio_path.name} ({size_mb:.1f} MB)")

    if args.no_transcribe:
        print("Skipping transcription (--no-transcribe).")
        return 0

    return _transcribe(cfg, audio_path)


def cmd_transcribe(args) -> int:
    cfg = _require_config()
    _ensure_dirs(cfg)
    audio_path = Path(args.file).expanduser().resolve()
    if not audio_path.exists():
        print(f"File not found: {audio_path}")
        return 1
    return _transcribe(cfg, audio_path)


def _transcribe(cfg: Config, audio_path: Path) -> int:
    try:
        transcriber = get_transcriber(cfg.transcriber, cfg.transcriber_options)
    except Exception as e:
        print(f"Failed to load transcriber '{cfg.transcriber}': {e}")
        print(f"Audio preserved at: {audio_path}")
        return 1

    transcript_file = cfg.transcripts_dir / f"{audio_path.stem}-transcript.txt"
    print(f"\nTranscribing via {cfg.transcriber}...")

    try:
        text = transcriber.transcribe(audio_path)
    except Exception as e:
        print(f"\nTranscription failed: {e}")
        print(f"Audio preserved at: {audio_path}")
        return 1

    if not text or not text.strip():
        print("\nTranscription returned empty result.")
        print(f"Audio preserved at: {audio_path}")
        return 1

    transcript_file.write_text(text, encoding="utf-8")
    print(f"\nTranscript saved: {transcript_file}")
    _notify("Meeting Sentinel", f"Transcript ready: {transcript_file.name}")
    return 0


def cmd_watch(args) -> int:
    cfg = _require_config()
    apps = cfg.meeting_apps or MEETING_APPS_DEFAULT
    print(f"Meeting Sentinel watching (every {POLL_INTERVAL}s)")
    print(f"Apps: {', '.join(apps)}")
    print("Ctrl+C to stop.\n")

    was_in_meeting = any(_app_running(app) for app in apps)
    if was_in_meeting:
        print("Meeting app already running — waiting for a new session.\n")

    while True:
        try:
            in_meeting = any(_app_running(app) for app in apps)

            if in_meeting and not was_in_meeting and not _is_recording():
                choice = _show_dialog(
                    "Meeting app detected.\\nStart recording?",
                    ["Skip", "Record"],
                )
                if choice == "Record":
                    class _A:
                        name = None
                    cmd_start(_A())

            elif not in_meeting and was_in_meeting and _is_recording():
                choice = _show_dialog(
                    "Meeting app closed.\\nStop recording and transcribe?",
                    ["Keep Recording", "Stop & Transcribe"],
                )
                if choice == "Stop & Transcribe":
                    class _B:
                        no_transcribe = False
                    cmd_stop(_B())

            was_in_meeting = in_meeting
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopped.")
            break

    return 0


def cmd_status(args) -> int:
    state = _load_state()
    if not state or not state.get("pid"):
        print("No active recording.")
        return 0

    pid = state["pid"]
    if not _process_alive(pid):
        print("Stale state (process not running). Cleaning up.")
        _clear_state()
        return 0

    started = state.get("started_at", "")
    try:
        start_time = datetime.datetime.fromisoformat(started)
        elapsed = datetime.datetime.now() - start_time
        mins = int(elapsed.total_seconds() // 60)
        secs = int(elapsed.total_seconds() % 60)
        dur = f"{mins}m {secs}s"
    except (ValueError, TypeError):
        dur = "unknown"

    print("Recording in progress")
    print(f"  Name:     {state.get('name', 'unknown')}")
    print(f"  File:     {state.get('audio_file', 'unknown')}")
    print(f"  Duration: {dur}")
    print(f"  PID:      {pid}")
    return 0


def cmd_devices(args) -> int:
    cfg = load_config()
    bh_name = cfg.blackhole_device if cfg else "BlackHole 2ch"

    result = subprocess.run(
        ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    )
    in_audio = False
    print("Audio devices:\n")
    for line in result.stderr.split("\n"):
        if "AVFoundation audio devices:" in line:
            in_audio = True
            continue
        if in_audio:
            if line.strip() and "[" not in line:
                break
            if "[" in line:
                clean = line.split("] ", 1)[-1] if "] " in line else line
                print(f"  {clean.strip()}")

    idx = _find_device_index(bh_name)
    print()
    if idx:
        print(f"{bh_name} found at index [{idx}]")
    else:
        print(f"'{bh_name}' not found.")
        print("Install BlackHole: https://existential.audio/blackhole/")
    return 0


def cmd_unprocessed(args) -> int:
    cfg = _require_config()
    _ensure_dirs(cfg)
    raw = sorted(cfg.transcripts_dir.glob("*-transcript.txt"))
    if not raw:
        print("No raw transcripts found.")
        return 0
    print(f"{len(raw)} transcript(s) in {cfg.transcripts_dir}:\n")
    for t in raw:
        size_kb = t.stat().st_size / 1024
        print(f"  {t.name}  ({size_kb:.0f} KB)")
    return 0


# ────────────────── main ──────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="meet",
        description="Meeting Sentinel — record and transcribe meetings on macOS",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Run first-run setup wizard")
    sub.add_parser("config", help="Show active configuration")

    p_start = sub.add_parser("start", help="Start recording")
    p_start.add_argument("-n", "--name", help="Recording name")

    p_stop = sub.add_parser("stop", help="Stop recording and transcribe")
    p_stop.add_argument("--no-transcribe", action="store_true", help="Skip transcription")

    sub.add_parser("watch", help="Watch for meeting apps and auto-prompt")
    sub.add_parser("status", help="Show current recording state")
    sub.add_parser("devices", help="List audio devices")
    sub.add_parser("unprocessed", help="List transcripts in the transcripts dir")

    p_tx = sub.add_parser("transcribe", help="Transcribe an existing audio file")
    p_tx.add_argument("file", help="Path to audio file")

    args = parser.parse_args()

    handlers = {
        "setup": cmd_setup,
        "config": cmd_config,
        "start": cmd_start,
        "stop": cmd_stop,
        "watch": cmd_watch,
        "status": cmd_status,
        "devices": cmd_devices,
        "unprocessed": cmd_unprocessed,
        "transcribe": cmd_transcribe,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
