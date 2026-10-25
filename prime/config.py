from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    home: Path
    api_key: str
    base_url: str
    model: str
    vision_model: str = "nvidia/Nemotron-3.5-Super-VL"
    speech_model: str = ""         # e.g. nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning on a dedicated Nebius endpoint
    speech_base_url: str = ""      # defaults to base_url (Token Factory)
    speech_api_key: str = ""       # a Serverless Endpoint's own token; defaults to api_key

    @property
    def db_path(self) -> Path:
        return self.home / "prime.db"

    @property
    def ics_path(self) -> Path:
        return self.home / "calendar.ics"


def load_settings() -> Settings:
    _load_dotenv()
    home = Path(os.environ.get("PRIME_HOME", Path.home() / ".prime")).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    return Settings(
        home=home,
        api_key=os.environ.get("NEBIUS_API_KEY", ""),
        base_url=os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"),
        model=os.environ.get("PRIME_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
        vision_model=os.environ.get("PRIME_VISION_MODEL", "nvidia/Nemotron-3.5-Super-VL"),
        speech_model=os.environ.get("PRIME_SPEECH_MODEL", ""),
        speech_base_url=os.environ.get("PRIME_SPEECH_BASE_URL", ""),
        speech_api_key=os.environ.get("PRIME_SPEECH_API_KEY", ""),
    )
