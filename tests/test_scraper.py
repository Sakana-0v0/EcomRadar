import pytest

@pytest.mark.asyncio
async def test_scrape_single_url():
    from app.services.scraper import scrape_urls
    result = await scrape_urls(["https://example.com"])
    assert "https://example.com" in result
