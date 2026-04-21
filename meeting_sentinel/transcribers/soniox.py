"""Soniox transcriber — cloud STT with speaker diarization."""

from __future__ import annotations

import os
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None


API_BASE = "https://api.soniox.com/v1"
MODEL = "stt-async-v3"


class SonioxTranscriber:
    def __init__(
        self,
        languages: list[str] | None = None,
        diarization: bool = True,
        timestamps: bool = True,
        model: str = MODEL,
    ):
        if requests is None:
            raise RuntimeError(
                "The `requests` package is required for Soniox. Install with: pip install requests"
            )
        self.api_key = os.environ.get("SONIOX_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "SONIOX_API_KEY not set. Get a key at https://console.soniox.com "
                "and export it in your shell."
            )
        self.languages = languages or ["en"]
        self.diarization = diarization
        self.timestamps = timestamps
        self.model = model

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def transcribe(self, audio_path: Path) -> str:
        file_id = self._upload(audio_path)
        transcription_id = self._create_job(file_id)
        self._poll(transcription_id)
        transcript = self._fetch_transcript(transcription_id)
        return self._format(transcript)

    def _upload(self, audio_path: Path) -> str:
        with open(audio_path, "rb") as f:
            resp = requests.post(
                f"{API_BASE}/files",
                headers=self._headers(),
                files={"file": (audio_path.name, f)},
            )
        if resp.status_code != 201:
            raise RuntimeError(f"Upload failed: {resp.text}")
        return resp.json()["id"]

    def _create_job(self, file_id: str) -> str:
        payload = {
            "model": self.model,
            "file_id": file_id,
            "enable_speaker_diarization": self.diarization,
            "enable_language_identification": True,
        }
        if self.languages:
            payload["language_hints"] = self.languages

        resp = requests.post(
            f"{API_BASE}/transcriptions",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code != 201:
            raise RuntimeError(f"Job creation failed: {resp.text}")
        return resp.json()["id"]

    def _poll(self, transcription_id: str, max_wait: float = 3600.0) -> None:
        url = f"{API_BASE}/transcriptions/{transcription_id}"
        start = time.time()
        dots = 0
        while True:
            resp = requests.get(url, headers=self._headers())
            if resp.status_code != 200:
                raise RuntimeError(f"Status check failed: {resp.text}")
            data = resp.json()
            status = data.get("status")
            if status == "completed":
                print()
                return
            if status == "error":
                raise RuntimeError(f"Soniox error: {data.get('error_message', 'unknown')}")
            if time.time() - start > max_wait:
                raise TimeoutError(f"Transcription exceeded {max_wait}s")
            print(".", end="", flush=True)
            dots += 1
            if dots % 50 == 0:
                print()
            time.sleep(2)

    def _fetch_transcript(self, transcription_id: str) -> dict:
        resp = requests.get(
            f"{API_BASE}/transcriptions/{transcription_id}/transcript",
            headers=self._headers(),
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Transcript fetch failed: {resp.text}")
        return resp.json()

    def _format(self, transcript: dict) -> str:
        tokens = transcript.get("tokens", [])
        if not tokens:
            return transcript.get("text", "")

        lines: list[str] = []
        current_speaker = None
        current_parts: list[str] = []
        turn_start_ms: int | None = None

        def flush() -> None:
            if not current_parts:
                return
            parts: list[str] = []
            if self.timestamps and turn_start_ms is not None:
                parts.append(f"[{_ts(turn_start_ms)}]")
            if current_speaker is not None:
                parts.append(f"Speaker {current_speaker}:")
            parts.append("".join(current_parts).strip())
            line = " ".join(p for p in parts if p)
            if line.strip():
                lines.append(line)

        for tok in tokens:
            text = tok.get("text", "")
            start_ms = tok.get("start_ms", 0)
            speaker = tok.get("speaker")
            if speaker != current_speaker:
                flush()
                current_speaker = speaker
                current_parts = []
                turn_start_ms = start_ms
            current_parts.append(text)
        flush()
        return "\n\n".join(lines)


def _ts(ms: int) -> str:
    total = ms // 1000
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
