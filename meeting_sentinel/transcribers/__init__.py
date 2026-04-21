"""Pluggable transcription backends."""

from __future__ import annotations

from typing import Protocol
from pathlib import Path


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> str: ...


def get_transcriber(name: str, options: dict | None = None) -> Transcriber:
    """Factory — returns a transcriber instance by name."""
    options = options or {}
    name = name.lower()

    if name == "soniox":
        from .soniox import SonioxTranscriber
        return SonioxTranscriber(**options)
    if name == "elevenlabs":
        from .elevenlabs import ElevenLabsTranscriber
        return ElevenLabsTranscriber(**options)
    if name in ("whisper-local", "whisper", "local"):
        from .whisper_local import WhisperLocalTranscriber
        return WhisperLocalTranscriber(**options)
    if name == "none":
        raise RuntimeError("Transcriber is set to 'none'. Use `meet stop --no-transcribe` or update config.")
    raise ValueError(f"Unknown transcriber '{name}'. Choices: soniox, elevenlabs, whisper-local, none.")
