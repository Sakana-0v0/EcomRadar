"""轻量多信号 Reranker.

为什么不用 BGE-Reranker / Cohere Rerank:
- BGE 模型 ~1GB,下载耗时长
- 离线场景无 GPU 加速
- 多信号融合在中小语料上效果接近

融合的 4 个信号:
1. token_overlap: 查询-文档 Jaccard 相似度 (0~1)
2. length_score: 长度得分(适中最佳) (0~1)
3. position_score: 位置偏置(早出略高) (0.5~1)
4. bm25_signal: 归一化后的 BM25 分数 (0~1)

最终: 0.4*token + 0.2*length + 0.1*position + 0.3*bm25 (可调)
"""
import math
from dataclasses import dataclass
from typing import Optional

from app.services.retrieval.bm25_index import tokenize


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard 相似度 = |A ∩ B| / |A ∪ B|."""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    if not union:
        return 0.0
    return len(intersection) / len(union)


def length_score(text_length: int, optimal: int = 200, tolerance: float = 0.7) -> float:
    """长度得分: 越接近 optimal 分数越高.

    Args:
        text_length: 文档字符数
        optimal: 理想长度
        tolerance: 容差比例

    Returns:
        0~1 分数
    """
    if text_length <= 0:
        return 0.0
    ratio = text_length / optimal
    if ratio <= 1.0:
        return max(0.3, ratio)
    excess = ratio - 1.0
    return max(0.3, 1.0 - excess * tolerance)


def position_score(position: int, total: int) -> float:
    """位置得分: 早期略高(线性衰减 0.5~1)."""
    if total <= 1:
        return 1.0
    decay = 0.5 * (position / max(1, total - 1))
    return 1.0 - decay


def _min_max_norm(values: list[float]) -> list[float]:
    if not values:
        return []
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        return [0.0 for _ in values]
    return [(v - min_v) / (max_v - min_v) for v in values]


@dataclass
class RerankSignals:
    """单文档重排序信号."""
    token_overlap: float
    length_score: float
    position_score: float
    bm25_signal: float

    def to_dict(self) -> dict:
        return {
            "token_overlap": self.token_overlap,
            "length_score": self.length_score,
            "position_score": self.position_score,
            "bm25_signal": self.bm25_signal,
        }


def compute_rerank_signals(
    query: str,
    doc: str,
    bm25_score: float,
    position: int,
    total: int,
    optimal_length: int = 200,
) -> dict:
    """计算单文档的所有重排序信号.

    Returns:
        {"token_overlap", "length_score", "position_score", "bm25_signal"} 字典
    """
    query_tokens = set(tokenize(query))
    doc_tokens = set(tokenize(doc))
    return RerankSignals(
        token_overlap=jaccard_similarity(query_tokens, doc_tokens),
        length_score=length_score(len(doc), optimal=optimal_length),
        position_score=position_score(position, total),
        bm25_signal=max(0.0, min(1.0, bm25_score)),
    ).to_dict()


class LightweightReranker:
    """轻量多信号 Reranker."""

    def __init__(
        self,
        token_weight: float = 0.4,
        bm25_weight: float = 0.3,
        length_weight: float = 0.2,
        position_weight: float = 0.1,
        optimal_length: int = 200,
    ):
        """初始化.

        Args:
            token_weight: 词重叠权重
            bm25_weight: BM25 分数权重
            length_weight: 长度得分权重
            position_weight: 位置偏置权重
            optimal_length: 理想长度

        Note:
            权重会自动归一化到和为 1.0(若传入权重之和不为 1)
        """
        total = token_weight + bm25_weight + length_weight + position_weight
        if total > 0:
            self.weights = {
                "token": token_weight / total,
                "bm25": bm25_weight / total,
                "length": length_weight / total,
                "position": position_weight / total,
            }
        else:
            self.weights = {"token": 0.4, "bm25": 0.3, "length": 0.2, "position": 0.1}
        self.optimal_length = optimal_length

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: Optional[int] = None,
    ) -> list[dict]:
        """对候选列表重排序.

        Args:
            query: 查询字符串
            candidates: 候选文档列表 (需含 'text' 字段)
            top_k: 限制返回数量,None 全部返回

        Returns:
            重排序后的列表,每项新增 'rerank_score' 和 'rerank_signals' 字段
        """
        if not candidates:
            return []

        total = len(candidates)
        bm25_scores = [c.get("score", 0.0) for c in candidates]
        bm25_norm = _min_max_norm(bm25_scores)

        ranked: list[dict] = []
        for idx, candidate in enumerate(candidates):
            signals = compute_rerank_signals(
                query=query,
                doc=candidate.get("text", ""),
                bm25_score=bm25_norm[idx],
                position=idx,
                total=total,
                optimal_length=self.optimal_length,
            )
            final = (
                self.weights["token"] * signals["token_overlap"]
                + self.weights["bm25"] * signals["bm25_signal"]
                + self.weights["length"] * signals["length_score"]
                + self.weights["position"] * signals["position_score"]
            )
            ranked.append({
                **candidate,
                "rerank_score": final,
                "rerank_signals": signals,
            })

        ranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        if top_k is not None:
            ranked = ranked[:top_k]
        return ranked
