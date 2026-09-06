from __future__ import annotations

import asyncio
import json
import urllib.parse

from ...typing import AsyncResult, Messages
from ..base_provider import AsyncGeneratorProvider, ProviderModelMixin
from ...providers.response import SearchResults
from ...requests.cdp import CDPSession
from ... import debug
from ..helper import get_last_user_message


class GoogleSearch(AsyncGeneratorProvider, ProviderModelMixin):
    label = "Google Search"
    url = "https://google.com"
    working = True
    supports_native_tools = True
    default_model = "search"

    @classmethod
    async def create_async_generator(
        cls,
        model: str,
        messages: Messages,
        **kwargs,
    ) -> AsyncResult:
        query = get_last_user_message(messages)
        search_url = f"{cls.url}/search?q={urllib.parse.quote_plus(query)}"

        debug.log(f"Google Search: Starting CDPSession for query: {query}")
        session = CDPSession(headless=False)
        await session.start()

        try:
            await session.navigate(search_url)

            await session.click_accept_button()

            # Wait for Google search results page to load
            for _ in range(30):
                try:
                    has_results = await session.evaluate_js(
                        "document.querySelectorAll('div.g, h3').length > 0"
                    )
                    if has_results:
                        break
                except Exception:
                    pass
                await asyncio.sleep(1)

            # Extract search results from the DOM
            results_json = await session.evaluate_js(
                """
                (() => {
                    const results = [];
                    const items = document.querySelectorAll('h3');
                    items.forEach(item => {
                        const linkEl = item.parentElement;
                        const title = item.innerText || '';
                        const link = linkEl.href  ? new URL(linkEl.href || '/') : null;
                        if (link) link.searchParams.delete("srsltid")
                        let parentEl = linkEl.parentElement.parentElement.parentElement;
                        let snippetEl = null;
                        while (parentEl) {
                            if (parentEl.nextElementSibling)
                            snippetEl = parentEl.nextElementSibling.querySelector("div div:not(:has(a, svg)) span:not(:has(div, span, a, svg)):not(:empty)");
                            if (snippetEl) break;
                            parentEl = parentEl.parentElement;
                        }
                        const snippet = snippetEl ? snippetEl.innerText : '';
                        if (title && link) {
                            results.push({ title, link: link.toString(), snippet });
                        }
                    });
                    return JSON.stringify(results);
                })()
                """
            )

            results = json.loads(results_json) if results_json else []

            if not results:
                raise RuntimeError("No search results found.")
            yield SearchResults(results)
        finally:
            await session.close()
