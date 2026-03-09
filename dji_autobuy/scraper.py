from __future__ import annotations

import re

from playwright.sync_api import Page, sync_playwright

from .models import PreloadResult

VERSION_SELECTOR = "section:has-text('选你所需') button, section:has-text('选你所需') a"
PURCHASE_KEYWORDS = re.compile("开始选购|购买|立即购买|加入购物车")


def get_versions_and_stock(page: Page) -> PreloadResult:
    versions: list[str] = []
    in_stock = False

    try:
        locs = page.locator(VERSION_SELECTOR)
        for index in range(locs.count()):
            text = locs.nth(index).inner_text().strip()
            if text and text not in versions:
                versions.append(text)
    except Exception:
        pass

    try:
        button = page.get_by_text(PURCHASE_KEYWORDS).first
        in_stock = button.is_visible(timeout=2000)
    except Exception:
        pass

    return PreloadResult(versions=versions, in_stock=in_stock)


def preload_product(url: str, timeout_ms: int = 30000) -> PreloadResult:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        result = get_versions_and_stock(page)
        browser.close()
        return result
