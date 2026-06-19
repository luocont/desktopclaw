"""Bing search backend using Playwright browser automation."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote

from loguru import logger

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright

    from desktopclaw.config.schema import WebSearchConfig

PLAYWRIGHT_INSTALL_HINT = (
    "Playwright is not installed. Run: pip install \"desktopclaw[web-search]\" "
    "&& playwright install chromium"
)

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class SearchResult:
    """A single Bing web search result."""

    title: str
    url: str
    snippet: str


def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


async def _collect_result_items(page: Page, parse_timeout_ms: int = 15000) -> list:
    """Collect SERP result nodes; prefer attached over visible."""
    selectors = (
        "#b_results li.b_algo",
        "ol#b_results li.b_algo",
        "li.b_algo",
    )
    timeout_sec = parse_timeout_ms / 1000

    for sel in selectors:
        try:
            await page.wait_for_selector(sel, state="attached", timeout=timeout_sec)
            items = await page.query_selector_all(sel)
            if items:
                logger.debug("BingSearch: found {} items via {!r}", len(items), sel)
                return items
        except Exception:
            continue

    for _ in range(5):
        await asyncio.sleep(0.5)
        items = await page.query_selector_all("li.b_algo")
        if items:
            logger.debug("BingSearch: found {} items after poll", len(items))
            return items

    return []


async def parse_bing_results(page: Page) -> list[SearchResult]:
    """Parse Bing search results from the current page DOM."""
    results: list[SearchResult] = []
    items = await _collect_result_items(page)

    if not items:
        snippet = (await page.content())[:500]
        logger.debug("BingSearch: no result items; page snippet: {}", snippet)
        raise RuntimeError("No Bing search results found in DOM")

    for item in items:
        try:
            title_el = await item.query_selector("h2 > a")
            if not title_el:
                continue

            title = (await title_el.inner_text()).strip()
            if not title:
                title = (await title_el.text_content() or "").strip()
            url = (await title_el.get_attribute("href") or "").strip()
            if not title or not url:
                continue

            desc_el = await item.query_selector(".b_caption p")
            if not desc_el:
                desc_el = await item.query_selector("p.b_lineclamp2")
            snippet = ""
            if desc_el:
                snippet = (await desc_el.inner_text()).strip()
                if not snippet:
                    snippet = (await desc_el.text_content() or "").strip()

            results.append(SearchResult(title=title, url=url, snippet=snippet))
        except Exception:
            continue

    return results


async def is_captcha_page(page: Page) -> bool:
    """Detect Bing captcha / verification pages."""
    url = page.url.lower()
    if "identity/verification" in url or "/captcha" in url:
        return True

    for selector in (
        "#turnstile-widget",
        "input[name='cf-turnstile-response']",
        "#captcha",
        ".captcha",
    ):
        el = await page.query_selector(selector)
        if el:
            return True

    return False


class BingSearchBackend:
    """Playwright-backed Bing search with browser context reuse."""

    def __init__(self, config: WebSearchConfig, proxy: str | None = None):
        self._config = config
        self._proxy = proxy
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0.0

    async def start(self) -> None:
        """Lazy-start Playwright browser and context."""
        if self._context is not None:
            return

        if not _playwright_available():
            raise RuntimeError(PLAYWRIGHT_INSTALL_HINT)

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        launch_kwargs: dict = {
            "headless": self._config.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        if self._proxy:
            launch_kwargs["proxy"] = {"server": self._proxy}

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        await self._create_context()
        logger.debug("BingSearchBackend: browser started (headless={})", self._config.headless)

    async def close(self) -> None:
        """Release Playwright browser and context."""
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.debug("BingSearchBackend: context close error: {}", e)
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.debug("BingSearchBackend: browser close error: {}", e)
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.debug("BingSearchBackend: playwright stop error: {}", e)
            self._playwright = None

    async def search(self, query: str, count: int) -> list[SearchResult]:
        """Execute a Bing search and return structured results."""
        async with self._lock:
            await self._throttle()
            return await asyncio.wait_for(
                self._search_with_retries(query, count),
                timeout=self._config.timeout_s,
            )

    async def _throttle(self) -> None:
        """Enforce minimum interval between searches with jitter."""
        min_interval = self._config.min_interval_s
        if min_interval <= 0:
            return

        jitter = min_interval * 0.3
        required_gap = min_interval + random.uniform(-jitter, jitter)
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < required_gap:
            await asyncio.sleep(required_gap - elapsed)
        self._last_request_time = time.monotonic()

    async def _search_with_retries(self, query: str, count: int) -> list[SearchResult]:
        max_attempts = max(1, self._config.max_retries + 1)
        last_error: str | None = None

        for attempt in range(max_attempts):
            try:
                await self.start()
                results = await self._search_once(query, count)
                if results:
                    return results[:count]
                last_error = "No results parsed from Bing search page"
                logger.warning(
                    "BingSearch: empty results (attempt {}/{}), query={!r}",
                    attempt + 1,
                    max_attempts,
                    query,
                )
            except asyncio.TimeoutError:
                last_error = f"Search timed out after {self._config.timeout_s}s"
                logger.error("BingSearch: timeout, query={!r}", query)
            except Exception as e:
                last_error = str(e) or f"{type(e).__name__}"
                if PLAYWRIGHT_INSTALL_HINT in last_error:
                    raise RuntimeError(last_error) from e
                logger.error("BingSearch: attempt {}/{} failed: {}", attempt + 1, max_attempts, last_error)

            if attempt < max_attempts - 1:
                err_lower = (last_error or "").lower()
                if "captcha" in err_lower or "verification" in err_lower:
                    await self._recreate_context()
                elif attempt == 0:
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                else:
                    await self._recreate_context()
                    await asyncio.sleep(random.uniform(1.0, 2.0))

        raise RuntimeError(last_error or "Bing search failed")

    async def _search_once(self, query: str, count: int) -> list[SearchResult]:
        if not self._context:
            raise RuntimeError("Browser context not initialized")

        page = await self._context.new_page()
        try:
            params = {
                "q": query,
                "count": count,
                "setlang": "zh-CN",
                "mkt": "zh-CN",
            }
            query_str = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
            full_url = f"{self._config.base_url}?{query_str}"

            await page.goto(full_url, wait_until="load", timeout=30000)
            await asyncio.sleep(random.uniform(0.8, 2.0))

            accept_btn = await page.query_selector("#bnp_btn_accept")
            if accept_btn:
                await accept_btn.click()
                try:
                    await page.wait_for_load_state("load", timeout=10000)
                except Exception:
                    await asyncio.sleep(1.0)

            try:
                await page.wait_for_selector(
                    "#b_results, ol#b_results",
                    state="attached",
                    timeout=15000,
                )
            except Exception:
                logger.debug("BingSearch: #b_results not attached yet, will poll in parser")

            first_result = await page.query_selector("li.b_algo")
            if first_result:
                try:
                    await first_result.scroll_into_view_if_needed()
                except Exception:
                    pass
            await asyncio.sleep(random.uniform(0.3, 0.8))

            if await is_captcha_page(page):
                raise RuntimeError(
                    "Bing captcha or verification triggered. "
                    "Reduce search frequency or configure a proxy."
                )

            return await parse_bing_results(page)
        finally:
            await page.close()

    async def _create_context(self) -> None:
        if not self._browser:
            raise RuntimeError("Browser not initialized")

        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        await self._context.add_init_script(STEALTH_SCRIPT)

    async def _recreate_context(self) -> None:
        """Destroy and recreate browser context (e.g. after captcha)."""
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        await self._create_context()
