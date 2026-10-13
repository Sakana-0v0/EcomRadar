"""清理旧 collection + 初始化新架构（kb + cache）"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.services.vector_store import get_client, _ensure_collection
from app.core.config import settings


def cleanup_and_init():
    client = get_client()

    print("=== 清理旧数据 ===")
    old_collections = ["reports", "hello_agents_vectors", "rag_knowledge_base"]
    for name in old_collections:
        try:
            client.delete_collection(name)
            print(f"  [DEL] {name}")
        except Exception as e:
            print(f"  [SKIP] {name}: {e}")

    print("\n=== 初始化新 collection ===")
    _ensure_collection(settings.qdrant_kb_collection)
    _ensure_collection(settings.qdrant_cache_collection, payload_index_keys=["task_id"])

    print(f"  [CREATE] {settings.qdrant_kb_collection} (vector_size=1024)")
    print(f"  [CREATE] {settings.qdrant_cache_collection} (vector_size=1024, task_id indexed)")

    print("\n=== 当前状态 ===")
    for name in [settings.qdrant_kb_collection, settings.qdrant_cache_collection]:
        try:
            info = client.get_collection(name)
            print(f"  {name}: {info.points_count} points")
        except Exception as e:
            print(f"  {name}: ERROR {e}")


if __name__ == "__main__":
    cleanup_and_init()
