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
    active_by_default = True
    supports_native_tools = True
    default_model = "search"
    models = [default_model, "ai-mode"]

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
        except Exception as e:
            await session.close()
            raise e

        # Enable AI mode if the model is like "ai"
        try:
            if model == "ai-mode":
                await session.wait_for_network_idle(idle_time=1, timeout=10.0)
                for _ in range(10):
                    result = await session.evaluate_js("""const b =Array.from(document.querySelectorAll("a, button")).filter(a=>a.textContent.endsWith("KI‑Modus")).pop(); b ? b.click() : null; !!b""")
                    debug.log(f"Google Search: Attempted #{_+1} to enable AI mode, result: {result}")
                    await asyncio.sleep(1)
                    if not result:
                        continue
                    await session.wait_for_network_idle(idle_time=1, timeout=10.0)
                    results = await session.call("Runtime.evaluate", expression="""
    const cyrb53 = (str, seed = 0) => {
    let h1 = 0xdeadbeef ^ seed, h2 = 0x41c6ce57 ^ seed;
    for(let i = 0, ch; i < str.length; i++) {
        ch = str.charCodeAt(i);
        h1 = Math.imul(h1 ^ ch, 2654435761);
        h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1  = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
    h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2  = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
    h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  
    return 4294967296 * (2097151 & h2) + (h1 >>> 0);
};

const result = [];
for (const nodes of Array.from(document.querySelector('[decode-data-ved="1"]').querySelectorAll('*')).map(e=>Array.from(e.childNodes))) {
    for (const node of nodes) {result.push(node)} 
}

const lines = result.map(n=>n.textContent).filter(c=>!c.startsWith('TgQPHd|'));
const keepLines = { };

for (let l of lines) {
    if (l.startsWith('TgQPHd')) continue;
    if (l.startsWith("KI-Antworten können Fehler enthalten.")) break;
    if (!l) continue;

    // Sucht nach n._setImageSrc('ID', 'BASE64_DATEN') und extrahiert die Bilddaten
    const imgMatch = l.match(/_setImageSrc\\([^,]+,\\s*'([^']+)'\\)/);
    if (imgMatch) {
        // Bereinigt eventuelle doppelte Backslashes aus dem Daten-String (z.B. data:image\\/png)
        l = `\\n![](${imgMatch[1]})`;
    }
    const fileMath = l.match(/\\[\\{.+\\]^/);
    if (fileMath) {
        l = l.replace(fileMath[0], '');
    }

    const hash = cyrb53(l);
    keepLines[hash] = l;
}
Object.values(keepLines);
""", returnByValue=True);
                    debug.log(f"Google Search: AI mode results: {results}")
                    if results:
                        for text in results.get("result", {}).get("value", []):
                            yield f"{text}\n"
                        return
            if model == "ai-mode":
                raise RuntimeError("No AI mode results found.")

            # Wait for Google search results page to load
            for _ in range(10):
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
            results = await session.evaluate_js(
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
                    return results;
                })()
                """
            )

            if not results:
                raise RuntimeError("No search results found.")
            yield SearchResults(results)
        finally:
            await session.close()
