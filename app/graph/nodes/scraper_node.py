from app.graph.state import GraphState
from app.services.scraper import scrape_urls

async def scraper_node(state: GraphState) -> GraphState:
    urls = state.get("urls", [])
    scraped = await scrape_urls(urls)
    return {"scraped_content": scraped}
