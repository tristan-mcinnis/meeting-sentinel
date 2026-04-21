"""Config loading and first-run setup wizard."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_DIR = Path(os.environ.get("MEETING_SENTINEL_HOME", Path.home() / ".config" / "meeting-sentinel"))
CONFIG_PATH = CONFIG_DIR / "config.json"
STATE_PATH = CONFIG_DIR / "state.json"


SUPPORTED_TRANSCRIBERS = ["soniox", "elevenlabs", "whisper-local", "none"]


@dataclass
class Config:
    recordings_dir: Path
    transcripts_dir: Path
    transcriber: str = "soniox"
    transcriber_options: dict = field(default_factory=dict)
    blackhole_device: str = "BlackHole 2ch"
    mic_device: str = "MacBook Pro Microphone"
    meeting_apps: list[str] = field(default_factory=lambda: [
        "zoom.us", "Microsoft Teams", "WeChat", "FaceTime"
    ])

    def to_dict(self) -> dict:
        return {
            "recordings_dir": str(self.recordings_dir),
            "transcripts_dir": str(self.transcripts_dir),
            "transcriber": self.transcriber,
            "transcriber_options": self.transcriber_options,
            "blackhole_device": self.blackhole_device,
            "mic_device": self.mic_device,
            "meeting_apps": self.meeting_apps,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        return cls(
            recordings_dir=Path(data["recordings_dir"]).expanduser(),
            transcripts_dir=Path(data["transcripts_dir"]).expanduser(),
            transcriber=data.get("transcriber", "soniox"),
            transcriber_options=data.get("transcriber_options", {}),
            blackhole_device=data.get("blackhole_device", "BlackHole 2ch"),
            mic_device=data.get("mic_device", "MacBook Pro Microphone"),
            meeting_apps=data.get("meeting_apps", [
                "zoom.us", "Microsoft Teams", "WeChat", "FaceTime"
            ]),
        )


def load_config() -> Config | None:
    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text())
        return Config.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: config at {CONFIG_PATH} is invalid ({e}).")
        return None


def save_config(cfg: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg.to_dict(), indent=2))


def _prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{label}{suffix}: ").strip()
        if raw:
            return raw
        if default is not None:
            return default


def _prompt_choice(label: str, choices: list[str], default: str) -> str:
    opts = " / ".join(c if c != default else f"{c}*" for c in choices)
    while True:
        raw = input(f"{label} ({opts}) [{default}]: ").strip().lower()
        if not raw:
            return default
        if raw in choices:
            return raw
        print(f"Please pick one of: {', '.join(choices)}")


def run_setup_wizard() -> Config:
    """Interactive setup. Overwrites any existing config."""
    print("─" * 60)
    print("  Meeting Sentinel — first-run setup")
    print("─" * 60)
    print()
    print("Audio recordings and text transcripts will be saved to")
    print("folders you choose. Both default to ~/Meetings, which is")
    print("a reasonable choice if you don't have a preference.")
    print()

    home = Path.home()
    default_recordings = home / "Meetings" / "recordings"
    default_transcripts = home / "Meetings" / "transcripts"

    rec = _prompt("Where should audio files be saved?", str(default_recordings))
    tx = _prompt("Where should transcripts be saved?", str(default_transcripts))

    print()
    print("Which transcription provider do you want to use?")
    print("  soniox        — cloud, multilingual, speaker diarization (needs SONIOX_API_KEY)")
    print("  elevenlabs    — cloud, fast, English-leaning (needs ELEVENLABS_API_KEY)")
    print("  whisper-local — runs on your Mac, no cloud, no API key (needs `pip install openai-whisper`)")
    print("  none          — record only, transcribe later with a different tool")
    print()

    provider = _prompt_choice(
        "Provider",
        SUPPORTED_TRANSCRIBERS,
        default="soniox",
    )

    options: dict = {}

    if provider == "soniox":
        langs = _prompt(
            "Language hints (space-separated ISO codes, e.g. 'en zh')",
            "en",
        )
        options["languages"] = langs.split()
        options["diarization"] = True
        options["timestamps"] = True
        if not os.environ.get("SONIOX_API_KEY"):
            print()
            print("  Note: set SONIOX_API_KEY in your shell before running `meet stop`.")
            print("  e.g. add to ~/.zshrc:  export SONIOX_API_KEY='sk-...'")

    elif provider == "elevenlabs":
        model = _prompt("Model id", "scribe_v1")
        options["model"] = model
        lang = _prompt("Language hint (ISO code, or 'auto')", "auto")
        if lang != "auto":
            options["language"] = lang
        options["diarize"] = True
        if not os.environ.get("ELEVENLABS_API_KEY"):
            print()
            print("  Note: set ELEVENLABS_API_KEY in your shell before running `meet stop`.")

    elif provider == "whisper-local":
        model = _prompt_choice(
            "Whisper model",
            ["tiny", "base", "small", "medium", "large", "turbo"],
            default="base",
        )
        options["model"] = model
        lang = _prompt("Language hint (ISO code, or 'auto')", "auto")
        if lang != "auto":
            options["language"] = lang
        print()
        print("  Note: `pip install openai-whisper` before running `meet stop`.")

    print()
    blackhole = _prompt("BlackHole device name (leave default if unsure)", "BlackHole 2ch")
    mic = _prompt("Microphone device name (leave default if unsure)", "MacBook Pro Microphone")

    cfg = Config(
        recordings_dir=Path(rec).expanduser(),
        transcripts_dir=Path(tx).expanduser(),
        transcriber=provider,
        transcriber_options=options,
        blackhole_device=blackhole,
        mic_device=mic,
    )

    cfg.recordings_dir.mkdir(parents=True, exist_ok=True)
    cfg.transcripts_dir.mkdir(parents=True, exist_ok=True)
    save_config(cfg)

    print()
    print("─" * 60)
    print(f"  Config saved to {CONFIG_PATH}")
    print(f"  Recordings  → {cfg.recordings_dir}")
    print(f"  Transcripts → {cfg.transcripts_dir}")
    print(f"  Provider    → {cfg.transcriber}")
    print("─" * 60)
    print()
    print("Next steps:")
    print("  meet devices   # verify BlackHole is detected")
    print("  meet watch     # or: meet start / meet stop")
    print()
    return cfg
