"""Local Whisper transcriber — runs on the user's Mac, no API key."""

from __future__ import annotations

from pathlib import Path


class WhisperLocalTranscriber:
    def __init__(
        self,
        model: str = "base",
        language: str | None = None,
    ):
        try:
            import whisper  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "openai-whisper is not installed. Install with: pip install openai-whisper\n"
                "(Also requires ffmpeg, which you already have if recording works.)"
            ) from e
        self.model_name = model
        self.language = language
        self._model = None

    def _load_model(self):
        if self._model is None:
            import whisper
            print(f"Loading Whisper model '{self.model_name}' (first run may download weights)...")
            self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, audio_path: Path) -> str:
        model = self._load_model()
        kwargs = {}
        if self.language:
            kwargs["language"] = self.language

        print(f"Transcribing {audio_path.name} with Whisper {self.model_name}...")
        result = model.transcribe(str(audio_path), verbose=False, **kwargs)

        segments = result.get("segments") or []
        if not segments:
            return result.get("text", "").strip()

        lines: list[str] = []
        for seg in segments:
            start = seg.get("start", 0.0)
            text = seg.get("text", "").strip()
            if text:
                lines.append(f"[{_ts(start)}] {text}")
        return "\n".join(lines)


def _ts(seconds: float) -> str:
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
