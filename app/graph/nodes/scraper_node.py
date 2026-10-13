from app.graph.state import GraphState
from app.services.scraper import scrape_urls


async def scraper_node(state: GraphState) -> GraphState:
    urls = state.get("urls", [])
    error_messages = []
    try:
        scraped = await scrape_urls(urls)
    except Exception as e:
        scraped = {}
        error_messages.append(f"Scraper error: {str(e)}")
    
    return {
        "scraped_content": scraped,
        "error_messages": state.get("error_messages", []) + error_messages
    }