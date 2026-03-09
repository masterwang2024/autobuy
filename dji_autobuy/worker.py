from __future__ import annotations

import random
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from .models import Account, JobConfig, LogFn
from .scraper import get_versions_and_stock


def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def run_worker(account: Account, config: JobConfig, log_fn: LogFn) -> None:
    config.validate()
    username = account.username

    def log(message: str) -> None:
        log_fn(f"[{now_ts()}] [{username}] {message}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless)
        page = browser.new_page()
        page.goto(
            config.product_url,
            wait_until="domcontentloaded",
            timeout=config.page_timeout_ms,
        )
        log("登录成功（模拟）")

        if config.monitor_mode:
            while True:
                result = get_versions_and_stock(page)
                if result.in_stock:
                    log("检测到有货，准备进入加购流程")
                    break
                delay = random.randint(config.min_refresh_sec, config.max_refresh_sec)
                log(f"缺货，{delay}s 后刷新")
                page.wait_for_timeout(delay * 1000)
                page.reload(wait_until="domcontentloaded", timeout=config.page_timeout_ms)

        # 这里仍然保留示例行为。接入真实业务时，把这里替换成你的稳定 Worker.run。
        if config.version != "默认":
            log(f"模拟选择版本：{config.version}")
            time.sleep(0.2)

        log("模拟加入购物车成功")
        browser.close()
