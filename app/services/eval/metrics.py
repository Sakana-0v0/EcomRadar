"""评测指标核心库.

支持的指标:
- exact_match (EM): 字符串完全匹配 (case/space/punct 不敏感)
- f1_score: 字符级 F1 (中英文混合友好)
- rouge_l: 最长公共子序列 F1 (摘要类任务)
- latency stats: P50/P95/mean/min/max

所有指标统一通过 MetricResult 暴露,便于聚合与报告.
"""
import re
import string
from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional


_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def _normalize_text(text: str) -> str:
    """归一化: 转小写 + 去标点 + 合并空白."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s\u4e00-\u9fff]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def exact_match(prediction: str, reference: str) -> bool:
    """完全匹配 (归一化后)."""
    return _normalize_text(prediction) == _normalize_text(reference)


def tokenize_for_f1(text: str) -> list[str]:
    """F1 用分词: 中英文混合.

    中文按 2-gram 切分 (避免单字过细, 也比字符级更准)
    英文按空格切分
    """
    if not text:
        return []
    text = text.lower()
    text = re.sub(r"[^\w\s\u4e00-\u9fff]+", " ", text)
    tokens: list[str] = []
    for chunk in text.split():
        if not chunk:
            continue
        if _CJK_PATTERN.search(chunk):
            for i in range(len(chunk) - 1):
                tokens.append(chunk[i:i + 2])
            if len(chunk) == 1:
                tokens.append(chunk)
        else:
            tokens.append(chunk)
    return tokens


def f1_score(prediction: str, reference: str) -> float:
    """字符级 F1 (中英文混合)."""
    pred_tokens = tokenize_for_f1(prediction)
    ref_tokens = tokenize_for_f1(reference)
    if not pred_tokens or not ref_tokens:
        return 0.0

    from collections import Counter
    pred_counter = Counter(pred_tokens)
    ref_counter = Counter(ref_tokens)
    common = pred_counter & ref_counter
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0

    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def _lcs_length(a: list, b: list) -> int:
    """最长公共子序列长度."""
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            if a[i] == b[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i + 1][j], dp[i][j + 1])
    return dp[m][n]


def rouge_l_score(prediction: str, reference: str) -> float:
    """ROUGE-L (Longest Common Subsequence F1)."""
    pred_tokens = tokenize_for_f1(prediction)
    ref_tokens = tokenize_for_f1(reference)
    if not pred_tokens or not ref_tokens:
        return 0.0
    lcs = _lcs_length(pred_tokens, ref_tokens)
    if lcs == 0:
        return 0.0
    precision = lcs / len(pred_tokens)
    recall = lcs / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


@dataclass
class LatencyStats:
    """延迟统计."""
    count: int = 0
    p50: float = 0.0
    p95: float = 0.0
    mean: float = 0.0
    min: float = 0.0
    max: float = 0.0
    median: float = 0.0


def _percentile(sorted_values: list[float], p: float) -> float:
    """线性插值百分位."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def compute_latency_stats(latencies_ms: Iterable[float]) -> LatencyStats:
    """计算延迟百分位统计."""
    values = sorted(latencies_ms)
    if not values:
        return LatencyStats()
    total = sum(values)
    return LatencyStats(
        count=len(values),
        p50=_percentile(values, 0.5),
        p95=_percentile(values, 0.95),
        mean=total / len(values),
        min=values[0],
        max=values[-1],
        median=_percentile(values, 0.5),
    )


@dataclass
class MetricResult:
    """单个指标结果."""
    name: str
    value: float
    count: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
