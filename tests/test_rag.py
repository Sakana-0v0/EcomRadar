import pytest


@pytest.mark.asyncio
async def test_retrieve_from_kb():
    """从知识库检索"""
    from app.services.vector_store import retrieve_from_knowledge_base
    results = await retrieve_from_knowledge_base("什么是人工智能", top_k=3)
    assert isinstance(results, list)
    assert len(results) <= 3
    # 验证返回格式
    if results:
        assert "text" in results[0]
        assert "score" in results[0]


@pytest.mark.asyncio
async def test_index_and_retrieve_task_cache():
    """任务缓存索引 + 检索"""
    from app.services.vector_store import index_to_task_cache, retrieve_from_task_cache, clear_task_cache
    task_id = "test_task_001"
    chunks = ["机器学习是AI的核心技术", "深度学习是机器学习的子领域"]
    count = await index_to_task_cache(task_id, chunks, source="test")
    assert count == 2
    results = await retrieve_from_task_cache(task_id, "深度学习", top_k=3)
    assert len(results) >= 1
    # 任务隔离：另一个 task_id 应该检索不到
    other_results = await retrieve_from_task_cache("other_task", "深度学习", top_k=3)
    assert len(other_results) == 0
    # 清理
    await clear_task_cache(task_id)


@pytest.mark.asyncio
async def test_collection_stats():
    """诊断接口"""
    from app.services.vector_store import get_collection_stats
    stats = get_collection_stats()
    assert "knowledge_base" in stats
    assert "task_cache" in stats
