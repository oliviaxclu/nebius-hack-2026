"""Thin client for NVIDIA Nemotron served by Nebius Token Factory (OpenAI-compatible API).

Every request is redacted first and written to the local audit table, so the user can see
exactly what left their device.
"""
from __future__ import annotations

import base64
import json
import re
import sqlite3
from datetime import datetime

from .config import Settings
from .privacy import Redactor


class LLM:
    def __init__(self, settings: Settings, conn: sqlite3.Connection, redactor: Redactor, client=None):
        self.settings = settings
        self.conn = conn
        self.redactor = redactor
        if client is None:
            if not settings.api_key:
                raise RuntimeError("NEBIUS_API_KEY is not set. Copy .env.example to .env and add your key.")
            from openai import OpenAI  # lazy import so tests don't need network libs

            client = OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        self.client = client

    def _audit(self, purpose: str, payload: dict, model: str | None = None) -> None:
        blob = json.dumps(payload, ensure_ascii=False)
        self.conn.execute(
            "INSERT INTO llm_audit(ts, model, purpose, sent, n_chars) VALUES (?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), model or self.settings.model, purpose, blob, len(blob)),
        )
        self.conn.commit()

    def chat(self, messages: list[dict], tools: list[dict] | None = None, purpose: str = "chat"):
        safe = self.redactor.redact_obj(messages)
        payload = {"model": self.settings.model, "messages": safe}
        if tools:
            payload["tools"] = tools
        self._audit(purpose, {"messages": safe, "n_tools": len(tools or [])})
        resp = self.client.chat.completions.create(temperature=0.2, **payload)
        return resp.choices[0].message

    def vision(self, prompt: str, images: list[str], purpose: str = "vision", subject: str = "your hands and pen") -> str:
        """A text prompt plus a few images (data URLs). Only the text is redacted: running redaction over base64 could
        corrupt an image. The audit log records how many frames were sent and their size, never the frames.
        No low max_tokens: Super-VL reasons before it answers and returns nothing if the budget runs out."""
        text = self.redactor.redact_obj(prompt)
        kb = round(sum(len(u) for u in images) * 3 / 4 / 1024)
        note = f"{len(images)} cropped frame{'s' if len(images) != 1 else ''} of {subject}, about {kb} KB, not stored"
        self._audit(purpose, {"messages": [{"role": "user", "content": [{"type": "text", "text": text}, {"type": "image", "note": note}]}],
                              "n_tools": 0}, model=self.settings.vision_model)
        resp = self.client.chat.completions.create(
            model=self.settings.vision_model, temperature=0,
            messages=[{"role": "user", "content": [{"type": "text", "text": text}] +
                       [{"type": "image_url", "image_url": {"url": u}} for u in images]}])
        return resp.choices[0].message.content or ""

    def transcribe(self, wav: bytes, seconds: float | None = None, purpose: str = "speech") -> str:
        """Speech to text with Nemotron 3 Nano Omni (audio in, text out), with reasoning off as NVIDIA recommends for
        transcription. The audio is sent as an audio_url part (the format on the model card) and is never stored: the
        audit log records only that a clip of about N seconds was sent."""
        if not self.settings.speech_model:
            raise RuntimeError("No speech model is configured (PRIME_SPEECH_MODEL).")
        client = self.client
        if self.settings.speech_base_url and self.settings.speech_base_url != self.settings.base_url:   # a dedicated endpoint elsewhere
            from openai import OpenAI
            client = OpenAI(base_url=self.settings.speech_base_url, api_key=self.settings.speech_api_key or self.settings.api_key)
        note = f"[a voice clip of about {seconds:.0f} seconds, not stored]" if seconds else "[a voice clip, not stored]"
        self._audit(purpose, {"messages": [{"role": "user", "content": note}], "n_tools": 0}, model=self.settings.speech_model)
        url = "data:audio/wav;base64," + base64.b64encode(wav).decode()
        resp = client.chat.completions.create(
            model=self.settings.speech_model, temperature=0,
            messages=[{"role": "user", "content": [{"type": "audio_url", "audio_url": {"url": url}},
                                                   {"type": "text", "text": "Transcribe this audio. Reply with only the words spoken."}]}],
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        return re.sub(r"<think>.*?</think>", "", resp.choices[0].message.content or "", flags=re.S).strip()

    def ping(self) -> str:
        msg = self.chat([{"role": "user", "content": "Reply with exactly: ok"}], purpose="healthcheck")
        return (msg.content or "").strip()

    def list_models(self) -> list[str]:
        return sorted(m.id for m in self.client.models.list().data)
