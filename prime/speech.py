"""Voice input helpers. Transcription itself is LLM.transcribe (Nemotron 3 Nano Omni on Nebius).

The page records 16 kHz mono WAV; the audio passes through in memory and is never stored.
"""
from __future__ import annotations

import io
import wave

MAX_BYTES = 4 * 1024 * 1024          # about two minutes of 16 kHz mono 16-bit audio


def seconds_of(wav: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(wav)) as w:
            return w.getnframes() / w.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError):
        return None
