"""Tests for Bing Playwright web search."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from desktopclaw.agent.tools.bing_search import (
    BingSearchBackend,
    PLAYWRIGHT_INSTALL_HINT,
    SearchResult,
    is_captcha_page,
    parse_bing_results,
)
from desktopclaw.agent.tools.web import WebSearchTool
from desktopclaw.config.schema import WebSearchConfig


@pytest.mark.asyncio
async def test_parse_bing_results_extracts_title_url_snippet() -> None:
    page = AsyncMock()
    page.wait_for_selector = AsyncMock()

    title_el = AsyncMock()
    title_el.inner_text = AsyncMock(return_value="Example Title")
    title_el.get_attribute = AsyncMock(return_value="https://example.com/page")

    desc_el = AsyncMock()
    desc_el.inner_text = AsyncMock(return_value="Example snippet text")

    item = AsyncMock()
    item.query_selector = AsyncMock(side_effect=lambda sel: {
        "h2 > a": title_el,
        ".b_caption p": desc_el,
        "p.b_lineclamp2": None,
    }.get(sel))

    page.query_selector_all = AsyncMock(return_value=[item])

    results = await parse_bing_results(page)

    assert len(results) == 1
    assert results[0].title == "Example Title"
    assert results[0].url == "https://example.com/page"
    assert results[0].snippet == "Example snippet text"


@pytest.mark.asyncio
async def test_parse_bing_results_poll_when_wait_fails() -> None:
    page = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=TimeoutError("visible timeout"))

    title_el = AsyncMock()
    title_el.inner_text = AsyncMock(return_value="Poll Title")
    title_el.get_attribute = AsyncMock(return_value="https://poll.example.com")

    item = AsyncMock()
    item.query_selector = AsyncMock(side_effect=lambda sel: title_el if sel == "h2 > a" else None)

    page.query_selector_all = AsyncMock(return_value=[item])
    page.content = AsyncMock(return_value="<html></html>")

    results = await parse_bing_results(page)
    assert len(results) == 1
    assert results[0].title == "Poll Title"


@pytest.mark.asyncio
async def test_parse_bing_results_fallback_snippet_selector() -> None:
    page = AsyncMock()
    page.wait_for_selector = AsyncMock()

    title_el = AsyncMock()
    title_el.inner_text = AsyncMock(return_value="Title")
    title_el.get_attribute = AsyncMock(return_value="https://example.com")

    lineclamp_el = AsyncMock()
    lineclamp_el.inner_text = AsyncMock(return_value="Lineclamp snippet")

    item = AsyncMock()

    async def query_selector(sel: str):
        if sel == "h2 > a":
            return title_el
        if sel == ".b_caption p":
            return None
        if sel == "p.b_lineclamp2":
            return lineclamp_el
        return None

    item.query_selector = query_selector
    page.query_selector_all = AsyncMock(return_value=[item])

    results = await parse_bing_results(page)
    assert results[0].snippet == "Lineclamp snippet"


@pytest.mark.asyncio
async def test_is_captcha_page_detects_verification_url() -> None:
    page = AsyncMock()
    page.url = "https://www.bing.com/identity/verification"
    page.query_selector = AsyncMock(return_value=None)
    assert await is_captcha_page(page) is True


@pytest.mark.asyncio
async def test_is_captcha_page_detects_turnstile_widget() -> None:
    page = AsyncMock()
    page.url = "https://cn.bing.com/search?q=test"
    page.query_selector = AsyncMock(side_effect=lambda sel: MagicMock() if sel == "#turnstile-widget" else None)
    assert await is_captcha_page(page) is True


def test_web_search_config_defaults() -> None:
    config = WebSearchConfig()
    assert config.max_results == 5
    assert config.base_url == "https://cn.bing.com/search"
    assert config.headless is True
    assert config.timeout_s == 30
    assert config.min_interval_s == 3.0
    assert config.max_retries == 1


@pytest.mark.asyncio
async def test_web_search_tool_formats_results() -> None:
    backend = AsyncMock()
    backend.search = AsyncMock(return_value=[
        SearchResult(title="A", url="https://a.com", snippet="Snippet A"),
        SearchResult(title="B", url="https://b.com", snippet=""),
    ])
    tool = WebSearchTool(backend=backend, max_results=5)

    result = await tool.execute(query="test query", count=2)

    assert "Results for: test query" in result
    assert "1. A" in result
    assert "https://a.com" in result
    assert "Snippet A" in result
    assert "2. B" in result
    backend.search.assert_awaited_once_with("test query", 2)


@pytest.mark.asyncio
async def test_web_search_tool_playwright_not_installed_message() -> None:
    backend = BingSearchBackend(config=WebSearchConfig(), proxy=None)
    tool = WebSearchTool(backend=backend)

    with patch("desktopclaw.agent.tools.bing_search._playwright_available", return_value=False):
        result = await tool.execute(query="hello")

    assert "Playwright is not installed" in result
    assert "web-search" in result


@pytest.mark.asyncio
async def test_bing_search_backend_throttle_waits() -> None:
    import time

    config = WebSearchConfig(min_interval_s=0.2)
    backend = BingSearchBackend(config=config)
    backend._last_request_time = time.monotonic()

    start = time.monotonic()
    await backend._throttle()
    elapsed = time.monotonic() - start

    assert elapsed >= 0.14  # 0.2s minus max 30% jitter


@pytest.mark.asyncio
async def test_bing_search_backend_captcha_raises_and_retries() -> None:
    config = WebSearchConfig(max_retries=1, min_interval_s=0)
    backend = BingSearchBackend(config=config)
    backend._context = AsyncMock()
    backend._browser = AsyncMock()

    page = AsyncMock()
    page.url = "https://cn.bing.com/search?q=test"
    page.goto = AsyncMock()
    page.evaluate = AsyncMock()
    page.close = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)

    backend._context.new_page = AsyncMock(return_value=page)
    backend._create_context = AsyncMock()
    backend._recreate_context = AsyncMock()

    with patch("desktopclaw.agent.tools.bing_search.is_captcha_page", new=AsyncMock(return_value=True)):
        with pytest.raises(RuntimeError, match="captcha"):
            await backend._search_with_retries("test", 5)

    backend._recreate_context.assert_awaited_once()
