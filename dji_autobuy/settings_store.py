from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def _default_settings_path() -> Path:
    return Path.home() / ".autobuy" / "settings.json"


@dataclass
class StoredAccount:
    username: str
    password: str
    enabled: bool = True


@dataclass
class StoredTask:
    name: str
    url: str
    version: str = "默认"
    monitor_mode: bool = False
    enabled: bool = True
    account_usernames: list[str] | None = None


@dataclass
class AppSettings:
    accounts: list[StoredAccount] | None = None
    tasks: list[StoredTask] | None = None
    headless: bool = False
    max_workers: int = 3
    min_refresh_sec: int = 15
    max_refresh_sec: int = 60
    max_refresh_attempts: int = 120
    max_monitor_minutes: int = 120
    retry_count: int = 0

    def normalized_accounts(self) -> list[StoredAccount]:
        if not self.accounts:
            return []
        return self.accounts

    def normalized_tasks(self) -> list[StoredTask]:
        if not self.tasks:
            return []
        return self.tasks


def load_settings(path: Path | None = None) -> AppSettings:
    settings_path = path or _default_settings_path()
    if not settings_path.exists():
        return AppSettings()
    try:
        data: dict[str, Any] = json.loads(settings_path.read_text(encoding="utf-8"))
        accounts_raw = data.get("accounts") or []
        tasks_raw = data.get("tasks") or []
        accounts = [StoredAccount(**item) for item in accounts_raw]
        tasks = [StoredTask(**item) for item in tasks_raw]
        return AppSettings(
            accounts=accounts,
            tasks=tasks,
            headless=bool(data.get("headless", False)),
            max_workers=int(data.get("max_workers", 3)),
            min_refresh_sec=int(data.get("min_refresh_sec", 15)),
            max_refresh_sec=int(data.get("max_refresh_sec", 60)),
            max_refresh_attempts=int(data.get("max_refresh_attempts", 120)),
            max_monitor_minutes=int(data.get("max_monitor_minutes", 120)),
            retry_count=int(data.get("retry_count", 0)),
        )
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
