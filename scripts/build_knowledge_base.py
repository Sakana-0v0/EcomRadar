"""离线知识库构建脚本.

用法:
  python scripts/build_knowledge_base.py --file data/kb_sources/articles.json
  python scripts/build_knowledge_base.py --urls https://example.com/article1,https://example.com/article2

输入数据格式 (JSON Lines):
  {"text": "...", "source": "research_report_2024", "metadata": {"author": "...", "year": 2024}}
"""
import asyncio
import argparse
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.services.vector_store import index_to_knowledge_base, get_collection_stats
from app.services.scraper import scrape_urls
from app.services.chunker import chunk_text


async def build_from_file(file_path: str):
    """从 JSONL 文件构建知识库"""
    total_chunks = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[跳过] 第 {line_no} 行 JSON 错误: {e}")
                continue

            text = item.get("text", "")
            source = item.get("source", f"line_{line_no}")
            metadata = item.get("metadata", {})

            if not text:
                continue

            chunks = chunk_text(text)
            count = await index_to_knowledge_base(chunks, source=source, metadata=metadata)
            total_chunks += count
            print(f"[{line_no}] {source}: {len(chunks)} chunks -> {count} indexed")

    return total_chunks


async def build_from_urls(urls: list[str]):
    """从 URL 列表构建知识库"""
    total_chunks = 0
    scraped = await scrape_urls(urls)
    for url, content in scraped.items():
        if not content:
            print(f"[跳过] {url}: 抓取为空")
            continue
        chunks = chunk_text(content)
        count = await index_to_knowledge_base(chunks, source=url)
        total_chunks += count
        print(f"[OK] {url}: {len(chunks)} chunks -> {count} indexed")
    return total_chunks


async def show_stats():
    print("\n=== 当前 collection 状态 ===")
    stats = get_collection_stats()
    for name, info in stats.items():
        print(f"  {name}: {info}")


async def main():
    parser = argparse.ArgumentParser(description="构建知识库")
    parser.add_argument("--file", help="JSONL 文件路径")
    parser.add_argument("--urls", help="逗号分隔的 URL 列表")
    parser.add_argument("--stats", action="store_true", help="仅查看 collection 状态")
    args = parser.parse_args()

    if args.stats:
        await show_stats()
        return

    if not args.file and not args.urls:
        parser.print_help()
        return

    total = 0
    if args.file:
        print(f"=== 从文件构建: {args.file} ===")
        total += await build_from_file(args.file)
    if args.urls:
        urls = [u.strip() for u in args.urls.split(",") if u.strip()]
        print(f"\n=== 从 URL 构建: {len(urls)} 个 ===")
        total += await build_from_urls(urls)

    print(f"\n=== 完成: 共写入 {total} 个文档 ===")
    await show_stats()


if __name__ == "__main__":
    asyncio.run(main())
