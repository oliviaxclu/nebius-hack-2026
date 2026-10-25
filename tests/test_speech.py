import base64
import io
import wave

from fastapi.testclient import TestClient

from prime import db
from prime.config import Settings
from prime.llm import LLM
from prime.privacy import Redactor
from prime.web import create_app
from tests.conftest import TODAY
from tests.fakes import ScriptedClient, text_msg
from tests.test_web import make_client

OMNI = "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning"


def wav(seconds=1.0, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def test_llm_transcribe_sends_audio_to_omni_with_reasoning_off_and_never_stores_it(tmp_path):
    conn = db.connect(tmp_path / "s.db")
    client = ScriptedClient([text_msg("<think>hm</think> Where should I inject today? ")])
    s = Settings(home=tmp_path, api_key="k", base_url="http://x", model="m", speech_model=OMNI)
    clip = wav(2)
    text = LLM(s, conn, Redactor({"name": ["Ray Hale"]}), client=client).transcribe(clip, 2.0)
    req = client.requests[0]
    assert text == "Where should I inject today?" and req["model"] == OMNI
    assert req["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    part = req["messages"][0]["content"][0]
    assert part["type"] == "audio_url" and base64.b64decode(part["audio_url"]["url"].split(",", 1)[1]) == clip   # sent untouched
    row = conn.execute("SELECT model, purpose, sent FROM llm_audit").fetchone()
    assert (row["model"], row["purpose"]) == (OMNI, "speech") and "about 2 seconds" in row["sent"] and "base64" not in row["sent"]


def test_no_speech_model_means_browser_speech(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/api/health").json()["speech"] is False
    assert c.post("/api/transcribe", content=wav(), headers={"Content-Type": "audio/wav"}).status_code == 503


def speech_client(tmp_path, script, **env):
    s = Settings(home=tmp_path, api_key="k", base_url="http://x", model="nvidia/test", speech_model=OMNI)
    def factory(settings, conn, red):
        return LLM(settings, conn, red, client=ScriptedClient(script()))
    return TestClient(create_app(s, llm_factory=factory, root=tmp_path / "w", today=TODAY))


def test_transcribe_route_returns_text_and_lists_the_clip_in_privacy(tmp_path):
    c = speech_client(tmp_path, lambda: [text_msg("Was the low at 3 AM real?")])
    assert c.get("/api/health").json()["speech"] is True
    assert c.post("/api/transcribe", content=wav(3), headers={"Content-Type": "audio/wav"}).json() == {"text": "Was the low at 3 AM real?"}
    call = c.get("/api/audit").json()["calls"][0]
    assert call["purpose"] == "speech" and call["model"] == OMNI and "about 3 seconds" in call["messages"][0]["content"]


def test_transcribe_limits(tmp_path, monkeypatch):
    c = speech_client(tmp_path, lambda: [text_msg("hi")])
    assert c.post("/api/transcribe", content=b"", headers={"Content-Type": "audio/wav"}).status_code == 413
    monkeypatch.setenv("DEMO_MAX_SPEECH_PER_SESSION", "1")
    c = speech_client(tmp_path / "b", lambda: [text_msg("hi")])
    assert c.post("/api/transcribe", content=wav(), headers={"Content-Type": "audio/wav"}).status_code == 200
    assert c.post("/api/transcribe", content=wav(), headers={"Content-Type": "audio/wav"}).status_code == 429


def test_unreachable_model_is_a_502_so_the_page_falls_back(tmp_path):
    def broken():
        def boom(messages):
            raise ConnectionError("down")
        return [boom]
    c = speech_client(tmp_path, broken)
    r = c.post("/api/transcribe", content=wav(), headers={"Content-Type": "audio/wav"})
    assert r.status_code == 502 and "could not be reached" in r.json()["detail"]


def test_a_separate_speech_endpoint_gets_its_own_token(tmp_path, monkeypatch):
    seen = {}
    class FakeOpenAI:
        def __init__(self, base_url, api_key):
            seen.update(base_url=base_url, api_key=api_key)
            self.chat = type("C", (), {"completions": ScriptedClient([text_msg("hello")])})()
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    s = Settings(home=tmp_path, api_key="token-factory-key", base_url="http://tf", model="m", speech_model=OMNI,
                 speech_base_url="https://omni.example/v1", speech_api_key="endpoint-token")
    out = LLM(s, db.connect(tmp_path / "t.db"), Redactor({}), client=ScriptedClient([])).transcribe(wav(), 1.0)
    assert out == "hello" and seen == {"base_url": "https://omni.example/v1", "api_key": "endpoint-token"}
