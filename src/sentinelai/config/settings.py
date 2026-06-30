from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_SETTINGS_PATH = Path.home() / ".sentinelai" / "config.json"


@dataclass
class AppSettings:
    llm_model: str = "llama3.1:8b"
    python_path: str = ""
    installed_at: str = ""
    version: str = "0.1.0"

    @classmethod
    def load(cls) -> AppSettings:
        if _SETTINGS_PATH.exists():
            try:
                data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
                known = {k for k in cls.__dataclass_fields__}
                return cls(**{k: v for k, v in data.items() if k in known})
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if _SETTINGS_PATH.exists():
            try:
                existing = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        existing.update(asdict(self))
        _SETTINGS_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
