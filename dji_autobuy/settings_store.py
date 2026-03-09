from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


def _default_settings_path() -> Path:
    return Path.home() / ".autobuy" / "settings.json"


@dataclass
class AppSettings:
    docx_path: str = ""
    product_url: str = ""
    version: str = "默认"
    headless: bool = False
    max_workers: int = 3
    min_refresh_sec: int = 15
    max_refresh_sec: int = 60
    max_refresh_attempts: int = 120
    max_monitor_minutes: int = 120
    retry_count: int = 0


def load_settings(path: Path | None = None) -> AppSettings:
    settings_path = path or _default_settings_path()
    if not settings_path.exists():
        return AppSettings()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        return AppSettings(**data)
    except Exception:
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> Path:
    settings_path = path or _default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return settings_path
