"""Qdrant 向量存储服务 — 知识库与任务缓存分离"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.core.config import settings
from app.services.embedding import embed_text
import uuid

_client = None

VECTOR_SIZE = 1024
DISTANCE = Distance.COSINE


def get_client() -> QdrantClient:
    """Get or create Qdrant client singleton."""
    global _client
    if _client is None:
        if settings.qdrant_url:
            _client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
                check_compatibility=False,
            )
        else:
            _client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _client


def _ensure_collection(collection_name: str, payload_index_keys: list[str] | None = None) -> None:
    """确保 collection 存在，不存在则创建.

    Args:
        collection_name: collection 名
        payload_index_keys: 需要建 payload 索引的字段名（用于 filter）
    """
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=DISTANCE),
        )
    # 为 filter 字段创建 payload 索引（Qdrant Cloud 需要显式建索引）
    if payload_index_keys:
        from qdrant_client.models import PayloadSchemaType
        for key in payload_index_keys:
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=key,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass  # 索引可能已存在


def _search(collection_name: str, query_vector: list, top_k: int) -> list[dict]:
    """统一的检索实现"""
    client = get_client()
    if hasattr(client, "query_points"):
        results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
        )
        return [
            {"text": p.payload.get("text", ""), "source": p.payload.get("source", ""), "score": p.score}
            for p in results.points
        ]
    else:
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
        )
        return [
            {"text": r.payload.get("text", ""), "source": r.payload.get("source", ""), "score": r.score}
            for r in results
        ]


async def index_to_knowledge_base(
    chunks: list[str], source: str = "manual", metadata: dict | None = None
) -> int:
    """将文本块写入离线知识库 collection.

    Args:
        chunks: 文本块列表
        source: 来源标识（用于追溯）
        metadata: 额外元数据

    Returns:
        写入的文档数
    """
    if not chunks:
        return 0
    _ensure_collection(settings.qdrant_kb_collection)

    points = []
    for i, chunk in enumerate(chunks):
        vector = await embed_text(chunk)
        payload = {
            "text": chunk,
            "source": source,
            "chunk_index": i,
        }
        if metadata:
            payload.update(metadata)
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload=payload,
        ))

    get_client().upsert(
        collection_name=settings.qdrant_kb_collection,
        points=points,
    )
    return len(points)


async def retrieve_from_knowledge_base(query: str, top_k: int = 5) -> list[dict]:
    """从知识库 collection 检索上下文.

    Returns:
        命中列表，每项含 text/source/score
    """
    try:
        query_vector = await embed_text(query)
        return _search(settings.qdrant_kb_collection, query_vector, top_k)
    except Exception:
        return []


async def index_to_task_cache(
    task_id: str, chunks: list[str], source: str = ""
) -> int:
    """将文本块写入任务级缓存 collection.

    Args:
        task_id: 任务唯一标识（用作 payload 过滤）
        chunks: 文本块列表
        source: 来源

    Returns:
        写入的文档数
    """
    if not chunks:
        return 0
    _ensure_collection(settings.qdrant_cache_collection, payload_index_keys=["task_id"])

    points = []
    for i, chunk in enumerate(chunks):
        vector = await embed_text(chunk)
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "text": chunk,
                "task_id": task_id,
                "source": source,
                "chunk_index": i,
            },
        ))

    get_client().upsert(
        collection_name=settings.qdrant_cache_collection,
        points=points,
    )
    return len(points)


async def retrieve_from_task_cache(
    task_id: str, query: str, top_k: int = 5
) -> list[dict]:
    """从任务缓存检索（仅检索属于该 task_id 的内容）.

    使用 Qdrant 过滤条件实现任务隔离.
    """
    try:
        query_vector = await embed_text(query)
        client = get_client()
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        if hasattr(client, "query_points"):
            results = client.query_points(
                collection_name=settings.qdrant_cache_collection,
                query=query_vector,
                query_filter=Filter(must=[
                    FieldCondition(key="task_id", match=MatchValue(value=task_id))
                ]),
                limit=top_k,
            )
            return [
                {"text": p.payload.get("text", ""), "source": p.payload.get("source", ""), "score": p.score}
                for p in results.points
            ]
        else:
            results = client.search(
                collection_name=settings.qdrant_cache_collection,
                query_vector=query_vector,
                query_filter=Filter(must=[
                    FieldCondition(key="task_id", match=MatchValue(value=task_id))
                ]),
                limit=top_k,
            )
            return [
                {"text": r.payload.get("text", ""), "source": r.payload.get("source", ""), "score": r.score}
                for r in results
            ]
    except Exception:
        return []


async def clear_task_cache(task_id: str) -> int:
    """清理指定任务在 task_cache 中的所有数据.

    Returns:
        删除的文档数（近似值）
    """
    try:
        client = get_client()
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        result = client.delete(
            collection_name=settings.qdrant_cache_collection,
            points_selector=Filter(must=[
                FieldCondition(key="task_id", match=MatchValue(value=task_id))
            ]),
        )
        return 1
    except Exception:
        return 0


def get_collection_stats() -> dict:
    """获取所有 collection 的统计信息（用于诊断）"""
    client = get_client()
    stats = {}
    for name in [settings.qdrant_kb_collection, settings.qdrant_cache_collection]:
        try:
            info = client.get_collection(name)
            stats[name] = {
                "points": info.points_count,
                "vector_size": info.config.params.vectors.size,
                "distance": str(info.config.params.vectors.distance),
            }
        except Exception as e:
            stats[name] = {"error": str(e)}
    return stats
