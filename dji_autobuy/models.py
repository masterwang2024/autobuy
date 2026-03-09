from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


LogFn = Callable[[str], None]


@dataclass(frozen=True)
class Account:
    username: str
    password: str


@dataclass
class JobConfig:
    product_url: str
    version: str = "默认"
    monitor_mode: bool = False
    headless: bool = False
    max_workers: int = 3
    min_refresh_sec: int = 15
    max_refresh_sec: int = 60
    max_refresh_attempts: int = 120
    max_monitor_minutes: int = 120
    retry_count: int = 0
    page_timeout_ms: int = 30000

    def validate(self) -> None:
        if not self.product_url.strip():
            raise ValueError("URL 不能为空")
        if self.max_workers <= 0:
            raise ValueError("并发数必须大于 0")
        if self.min_refresh_sec <= 0 or self.max_refresh_sec <= 0:
            raise ValueError("刷新间隔必须是正数")
        if self.min_refresh_sec > self.max_refresh_sec:
            raise ValueError("最小刷新间隔不能大于最大刷新间隔")
        if self.max_refresh_attempts <= 0:
            raise ValueError("最大刷新次数必须大于 0")
        if self.max_monitor_minutes <= 0:
            raise ValueError("最大监控时长必须大于 0")
        if self.retry_count < 0:
            raise ValueError("重试次数不能小于 0")


@dataclass
class PreloadResult:
    versions: list[str] = field(default_factory=list)
    in_stock: bool = False


@dataclass
class WorkerResult:
    username: str
    ok: bool
    status: str
    message: str
    attempts: int = 0
    duration_sec: float = 0.0
    error_code: str = ""
