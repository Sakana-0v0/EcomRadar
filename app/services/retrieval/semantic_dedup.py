"""语义去重 (Semantic Deduplication).

两种实现:
1. Jaccard 相似度:基于 token 集合,精确但慢
2. SimHash:局部敏感哈希,O(n) 查重,适合大数据量

设计取舍:
- Jaccard 用于小规模精确去重 (默认)
- SimHash 用于大规模近似去重
- 都保留 score 更高的文档
"""
import hashlib
from typing import Optional

from app.services.retrieval.bm25_index import tokenize


def deduplicate_by_jaccard(
    documents: list[dict],
    threshold: float = 0.7,
) -> list[dict]:
    """Jaccard 相似度去重.

    Args:
        documents: 候选文档列表
        threshold: 相似度阈值,超过则视为重复

    Returns:
        去重后的文档列表(保留 score 更高者)
    """
    if not documents:
        return []

    sorted_docs = sorted(
        documents,
        key=lambda d: d.get("score", 0.0),
        reverse=True,
    )
    kept: list[dict] = []
    kept_tokens: list[set[str]] = []

    for doc in sorted_docs:
        doc_tokens = set(tokenize(doc.get("text", "")))
        is_dup = False
        for existing_tokens in kept_tokens:
            if not doc_tokens and not existing_tokens:
                continue
            if not doc_tokens or not existing_tokens:
                continue
            union = doc_tokens | existing_tokens
            if not union:
                continue
            sim = len(doc_tokens & existing_tokens) / len(union)
            if sim >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(doc)
            kept_tokens.append(doc_tokens)

    return kept


def simhash(text: str, hash_bits: int = 64) -> int:
    """计算文本的 SimHash 指纹.

    Args:
        text: 输入文本
        hash_bits: 哈希位数(默认 64)

    Returns:
        整数哈希值
    """
    tokens = tokenize(text)
    if not tokens:
        return 0

    v = [0] * hash_bits
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(hash_bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= 1 << i
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """两个整数的海明距离(不同 bit 数)."""
    return bin(a ^ b).count("1")


def deduplicate_by_simhash(
    documents: list[dict],
    threshold: int = 5,
) -> list[dict]:
    """SimHash 去重.

    Args:
        documents: 候选文档列表
        threshold: 海明距离阈值,小于等于则视为重复

    Returns:
        去重后的文档列表
    """
    if not documents:
        return []

    sorted_docs = sorted(
        documents,
        key=lambda d: d.get("score", 0.0),
        reverse=True,
    )
    kept: list[dict] = []
    kept_hashes: list[int] = []

    for doc in sorted_docs:
        h = simhash(doc.get("text", ""))
        is_dup = any(
            hamming_distance(h, existing_h) <= threshold
            for existing_h in kept_hashes
        )
        if not is_dup:
            kept.append(doc)
            kept_hashes.append(h)

    return kept
