"""BM25 倒排索引.

基于 rank_bm25 库实现,支持:
- 中英文混合分词
- 文档 ID / 来源 / 元数据保留
- Pickle 持久化
- 增量添加文档

设计取舍:
- 中文按字符切分(简单可靠,适合 Resume 项目)
- 不引入 jieba 等中文分词库(零依赖)
- 适合 1000~10000 文档规模
"""
import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Plus, BM25Okapi


_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
_PUNCT_PATTERN = re.compile(r"[^\w\s\u4e00-\u9fff]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def tokenize_chinese(text: str) -> list[str]:
    """中文按字符切分,每个汉字 1 个 token.

    示例: '小度智能' → ['小', '度', '智', '能']
    """
    return list(_CJK_PATTERN.findall(text))


def tokenize(text: str) -> list[str]:
    """中英文混合分词.

    策略:
    1. 转小写
    2. 去除标点
    3. 沿 CJK 边界切分(每个 CJK 字符单独成 token)
    4. 非 CJK 段(英文/数字)按原整体成 token(>1 字符)

    示例:
        "小度智能音箱WiFi" → ['小','度','智','能','音','箱','wifi']
        "iPhone 15 Pro" → ['iphone', '15', 'pro']
    """
    if not text:
        return []
    text = text.lower()
    text = _PUNCT_PATTERN.sub(" ", text)

    tokens: list[str] = []
    current_word: list[str] = []

    def flush_word() -> None:
        if current_word:
            word = "".join(current_word)
            if len(word) > 1:
                tokens.append(word)
            current_word.clear()

    for char in text:
        if _CJK_PATTERN.match(char):
            flush_word()
            tokens.append(char)
        elif char.isspace():
            flush_word()
        else:
            current_word.append(char)
    flush_word()

    return tokens


@dataclass
class _Doc:
    """内部文档表示."""
    id: str
    text: str
    tokens: list[str]
    metadata: dict = field(default_factory=dict)


class BM25Index:
    """BM25 倒排索引封装."""

    def __init__(self, k1: float = 1.5, b: float = 0.75, delta: float = 1.0, algorithm: str = "plus"):
        """初始化.

        Args:
            k1: BM25 参数,词频饱和度(1.2~2.0)
            b: BM25 参数,长度归一化(0~1)
            delta: BM25Plus 参数,避免零 IDF 边界
            algorithm: 'plus' (推荐,避免小语料零分) / 'okapi'
        """
        self.k1 = k1
        self.b = b
        self.delta = delta
        self.algorithm = algorithm
        self._docs: list[_Doc] = []
        self._bm25 = None

    def add_documents(self, documents: list[dict]) -> None:
        """添加文档(增量).

        Args:
            documents: [{"id": str, "text": str, ...metadata}, ...]
        """
        new_docs = []
        for doc in documents:
            text = doc.get("text", "")
            tokens = tokenize(text)
            if not tokens:
                continue
            metadata = {k: v for k, v in doc.items() if k not in ("id", "text")}
            new_docs.append(_Doc(
                id=doc.get("id", str(len(self._docs) + len(new_docs))),
                text=text,
                tokens=tokens,
                metadata=metadata,
            ))
        self._docs.extend(new_docs)
        self._bm25 = None

    def _ensure_bm25(self):
        if self._bm25 is None and self._docs:
            corpus = [d.tokens for d in self._docs]
            if self.algorithm == "plus":
                self._bm25 = BM25Plus(corpus, k1=self.k1, b=self.b, delta=self.delta)
            else:
                self._bm25 = BM25Okapi(corpus, k1=self.k1, b=self.b)
        return self._bm25

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """BM25 检索.

        Args:
            query: 查询字符串
            top_k: 返回前 K 个

        Returns:
            [{"id", "text", "score", **metadata}, ...] 按分数降序
        """
        if not self._docs:
            return []
        bm25 = self._ensure_bm25()
        if bm25 is None:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = bm25.get_scores(query_tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            {
                "id": self._docs[idx].id,
                "text": self._docs[idx].text,
                "score": float(score),
                **self._docs[idx].metadata,
            }
            for idx, score in ranked
            if score > 0
        ]

    def clear(self) -> None:
        """清空索引."""
        self._docs = []
        self._bm25 = None

    def size(self) -> int:
        return len(self._docs)

    def save(self, path: Path) -> None:
        """持久化到文件."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "k1": self.k1,
                "b": self.b,
                "delta": self.delta,
                "algorithm": self.algorithm,
                "docs": self._docs,
            }, f)

    def load(self, path: Path) -> None:
        """从文件加载."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.k1 = data.get("k1", 1.5)
        self.b = data.get("b", 0.75)
        self.delta = data.get("delta", 1.0)
        self.algorithm = data.get("algorithm", "plus")
        self._docs = data["docs"]
        self._bm25 = None
