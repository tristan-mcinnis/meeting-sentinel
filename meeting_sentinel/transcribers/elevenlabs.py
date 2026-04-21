"""ElevenLabs Scribe transcriber."""

from __future__ import annotations

import os
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None


API_URL = "https://api.elevenlabs.io/v1/speech-to-text"


class ElevenLabsTranscriber:
    def __init__(
        self,
        model: str = "scribe_v1",
        language: str | None = None,
        diarize: bool = True,
    ):
        if requests is None:
            raise RuntimeError(
                "The `requests` package is required for ElevenLabs. Install with: pip install requests"
            )
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY not set. Get a key at https://elevenlabs.io "
                "and export it in your shell."
            )
        self.model = model
        self.language = language
        self.diarize = diarize

    def transcribe(self, audio_path: Path) -> str:
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "application/octet-stream")}
            data = {
                "model_id": self.model,
                "diarize": "true" if self.diarize else "false",
                "timestamps_granularity": "word",
            }
            if self.language:
                data["language_code"] = self.language

            print(f"Uploading {audio_path.name} to ElevenLabs...")
            resp = requests.post(
                API_URL,
                headers={"xi-api-key": self.api_key},
                data=data,
                files=files,
                timeout=1800,
            )

        if resp.status_code != 200:
            raise RuntimeError(f"ElevenLabs error {resp.status_code}: {resp.text}")

        payload = resp.json()
        return self._format(payload)

    def _format(self, payload: dict) -> str:
        words = payload.get("words") or []
        if not words:
            return payload.get("text", "")

        lines: list[str] = []
        current_speaker = None
        current: list[str] = []
        turn_start: float | None = None

        def flush() -> None:
            if not current:
                return
            parts: list[str] = []
            if turn_start is not None:
                parts.append(f"[{_ts(turn_start)}]")
            if current_speaker is not None:
                parts.append(f"Speaker {current_speaker}:")
            parts.append("".join(current).strip())
            line = " ".join(p for p in parts if p)
            if line.strip():
                lines.append(line)

        for w in words:
            text = w.get("text", "")
            start = w.get("start")
            speaker = w.get("speaker_id")
            if speaker != current_speaker:
                flush()
                current_speaker = speaker
                current = []
                turn_start = start
            current.append(text if w.get("type") == "spacing" else text)
        flush()
        return "\n\n".join(lines)


def _ts(seconds: float) -> str:
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
