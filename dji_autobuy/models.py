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
    min_refresh_sec: int = 15
    max_refresh_sec: int = 60
    page_timeout_ms: int = 30000

    def validate(self) -> None:
        if not self.product_url.strip():
            raise ValueError("URL 不能为空")
        if self.min_refresh_sec <= 0 or self.max_refresh_sec <= 0:
            raise ValueError("刷新间隔必须是正数")
        if self.min_refresh_sec > self.max_refresh_sec:
            raise ValueError("最小刷新间隔不能大于最大刷新间隔")


@dataclass
class PreloadResult:
    versions: list[str] = field(default_factory=list)
    in_stock: bool = False
