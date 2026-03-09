from __future__ import annotations

import random
import time
from datetime import datetime
from threading import Event

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .models import Account, JobConfig, LogFn, WorkerResult
from .scraper import get_versions_and_stock


def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _sleep_with_stop(stop_event: Event, seconds: int) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if stop_event.is_set():
            return True
        time.sleep(0.3)
    return stop_event.is_set()


def run_worker(account: Account, config: JobConfig, log_fn: LogFn, stop_event: Event) -> WorkerResult:
    config.validate()
    username = account.username
    started_at = time.time()

    def log(message: str) -> None:
        log_fn(f"[{now_ts()}] [{username}] {message}")

    if stop_event.is_set():
        return WorkerResult(
            username=username,
            ok=False,
            status="cancelled",
            message="任务在启动前已停止",
            error_code="USER_STOP",
        )

    for attempt in range(config.retry_count + 1):
        if stop_event.is_set():
            return WorkerResult(
                username=username,
                ok=False,
                status="cancelled",
                message="任务被手动停止",
                attempts=attempt,
                duration_sec=time.time() - started_at,
                error_code="USER_STOP",
            )
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=config.headless)
                page = browser.new_page()
                page.goto(
                    config.product_url,
                    wait_until="domcontentloaded",
                    timeout=config.page_timeout_ms,
                )
                log("登录成功（模拟）")

                refresh_attempts = 0
                monitor_deadline = started_at + config.max_monitor_minutes * 60
                if config.monitor_mode:
                    while True:
                        if stop_event.is_set():
                            return WorkerResult(
                                username=username,
                                ok=False,
                                status="cancelled",
                                message="监控中被手动停止",
                                attempts=attempt + 1,
                                duration_sec=time.time() - started_at,
                                error_code="USER_STOP",
                            )
                        if time.time() >= monitor_deadline:
                            return WorkerResult(
                                username=username,
                                ok=False,
                                status="timeout",
                                message="监控超时，未检测到库存",
                                attempts=attempt + 1,
                                duration_sec=time.time() - started_at,
                                error_code="MONITOR_TIMEOUT",
                            )
                        if refresh_attempts >= config.max_refresh_attempts:
                            return WorkerResult(
                                username=username,
                                ok=False,
                                status="timeout",
                                message="达到最大刷新次数，未检测到库存",
                                attempts=attempt + 1,
                                duration_sec=time.time() - started_at,
                                error_code="MAX_REFRESH_REACHED",
                            )

                        result = get_versions_and_stock(page)
                        if result.in_stock:
                            log("检测到有货，准备进入加购流程")
                            break
                        delay = random.randint(config.min_refresh_sec, config.max_refresh_sec)
                        refresh_attempts += 1
                        log(f"缺货，第 {refresh_attempts} 次刷新，{delay}s 后重试")
                        if _sleep_with_stop(stop_event, delay):
                            return WorkerResult(
                                username=username,
                                ok=False,
                                status="cancelled",
                                message="等待刷新时被手动停止",
                                attempts=attempt + 1,
                                duration_sec=time.time() - started_at,
                                error_code="USER_STOP",
                            )
                        page.reload(wait_until="domcontentloaded", timeout=config.page_timeout_ms)

                if config.version != "默认":
                    log(f"模拟选择版本：{config.version}")
                    time.sleep(0.2)

                log("模拟加入购物车成功")
                return WorkerResult(
                    username=username,
                    ok=True,
                    status="success",
                    message="加购流程执行完成（模拟）",
                    attempts=attempt + 1,
                    duration_sec=time.time() - started_at,
                )
        except PlaywrightTimeoutError:
            log(f"页面超时，第 {attempt + 1} 次尝试失败")
            if attempt == config.retry_count:
                return WorkerResult(
                    username=username,
                    ok=False,
                    status="failed",
                    message="页面访问超时",
                    attempts=attempt + 1,
                    duration_sec=time.time() - started_at,
                    error_code="PAGE_TIMEOUT",
                )
        except Exception as exc:
            log(f"执行异常，第 {attempt + 1} 次尝试失败：{exc}")
            if attempt == config.retry_count:
                return WorkerResult(
                    username=username,
                    ok=False,
                    status="failed",
                    message=str(exc),
                    attempts=attempt + 1,
                    duration_sec=time.time() - started_at,
                    error_code="WORKER_EXCEPTION",
                )
    return WorkerResult(
        username=username,
        ok=False,
        status="failed",
        message="未知错误",
        attempts=config.retry_count + 1,
        duration_sec=time.time() - started_at,
        error_code="UNKNOWN",
    )
