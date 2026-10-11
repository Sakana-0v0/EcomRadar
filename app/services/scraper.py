import asyncio
import httpx
from typing import AsyncGenerator

async def scrape_urls(urls: list[str], timeout: float = 5.0) -> dict[str, str]:
    """Asynchronously fetch multiple URLs concurrently, return {url: content}"""
    async def fetch_one(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
        try:
            response = await client.get(url, timeout=timeout)
            response.raise_for_status()
            text = response.text
            text = _clean_html(text)
            return url, text
        except Exception as e:
            return url, ""

    def _clean_html(text: str) -> str:
        import re
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    async with httpx.AsyncClient() as client:
        tasks = [fetch_one(client, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {url: content for url, content in results if isinstance(content, str)}
