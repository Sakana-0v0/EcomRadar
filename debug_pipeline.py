"""调试脚本：直接调用各节点，绕过 HTTP 层"""
import asyncio
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.graph.state import GraphState
from app.graph.nodes.scraper_node import scraper_node
from app.graph.nodes.extractor_node import extractor_node
from app.graph.nodes.rag_node import rag_node
from app.graph.nodes.writer_node import writer_node
from app.graph.nodes.evaluator_node import evaluator_node


def print_state(label, state):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    print(f"{'='*60}")
    for k, v in state.items():
        if isinstance(v, str) and len(v) > 200:
            print(f"  {k}: {v[:200]}...")
        elif isinstance(v, list) and v and isinstance(v[0], str):
            print(f"  {k}: [{len(v)} items] {str(v[0])[:100]}...")
        else:
            print(f"  {k}: {v}")


async def debug_pipeline(urls: list[str]):
    """逐步执行整条链路"""
    state: GraphState = {
        "urls": urls,
        "scraped_content": {},
        "chunks": [],
        "context_docs": [],
        "report": "",
        "quality_score": 0,
        "retry_count": 0,
        "is_degraded": False,
        "error_messages": [],
    }
    print_state("Initial", state)

    # Step 1: Scraper
    print("\n[运行] Scraper Node...")
    state.update(await scraper_node(state))
    print_state("After Scraper", state)
    if not state["scraped_content"]:
        print("[STOP] 抓取失败，请检查 URL")
        return

    # Step 2: Extractor
    print("\n[运行] Extractor Node...")
    state.update(extractor_node(state))
    print_state("After Extractor", state)

    # Step 3: RAG
    print("\n[运行] RAG Node...")
    state.update(await rag_node(state))
    print_state("After RAG", state)

    # Step 4: Writer
    print("\n[运行] Writer Node...")
    state.update(await writer_node(state))
    print_state("After Writer", state)

    # Step 5: Evaluator
    print("\n[运行] Evaluator Node...")
    state.update(evaluator_node(state))
    print_state("After Evaluator", state)


if __name__ == "__main__":
    import sys
    test_urls = sys.argv[1:] if len(sys.argv) > 1 else ["https://example.com"]
    asyncio.run(debug_pipeline(test_urls))
