"""Metadata Filter + Semantic Dedup 单元测试."""
import pytest

from app.services.retrieval.metadata_filter import MetadataFilter, FilterCriteria
from app.services.retrieval.semantic_dedup import (
    deduplicate_by_jaccard,
    deduplicate_by_simhash,
    simhash,
)


SAMPLE_DOCS = [
    {"id": "1", "text": "小度智能音箱", "platform": "jd", "category": "智能音箱", "timestamp": 100},
    {"id": "2", "text": "天猫精灵蓝牙", "platform": "tmall", "category": "智能音箱", "timestamp": 200},
    {"id": "3", "text": "小米手机充电器", "platform": "jd", "category": "手机配件", "timestamp": 150},
    {"id": "4", "text": "苹果笔记本", "platform": "jd", "category": "电脑", "timestamp": 180},
    {"id": "5", "text": "小度智能音箱 旗舰版", "platform": "jd", "category": "智能音箱", "timestamp": 300},
]


class TestMetadataFilter:
    def test_no_filter_returns_all(self):
        f = MetadataFilter()
        result = f.filter(SAMPLE_DOCS)
        assert len(result) == 5

    def test_filter_by_single_platform(self):
        f = MetadataFilter()
        result = f.filter(SAMPLE_DOCS, FilterCriteria(platform="jd"))
        assert len(result) == 4
        assert all(d["platform"] == "jd" for d in result)

    def test_filter_by_category(self):
        f = MetadataFilter()
        result = f.filter(SAMPLE_DOCS, FilterCriteria(category="智能音箱"))
        assert len(result) == 3

    def test_filter_by_multiple_platforms(self):
        f = MetadataFilter()
        result = f.filter(SAMPLE_DOCS, FilterCriteria(platform=["jd", "tmall"]))
        assert len(result) == 5

    def test_filter_by_timestamp_range(self):
        f = MetadataFilter()
        result = f.filter(SAMPLE_DOCS, FilterCriteria(min_timestamp=150, max_timestamp=200))
        assert len(result) == 3
        assert all(150 <= d["timestamp"] <= 200 for d in result)

    def test_combined_filter(self):
        f = MetadataFilter()
        result = f.filter(
            SAMPLE_DOCS,
            FilterCriteria(platform="jd", category="智能音箱"),
        )
        assert len(result) == 2
        assert all(d["platform"] == "jd" and d["category"] == "智能音箱" for d in result)

    def test_filter_excludes_empty_results(self):
        f = MetadataFilter()
        result = f.filter(SAMPLE_DOCS, FilterCriteria(platform="nonexistent"))
        assert result == []

    def test_empty_doc_list(self):
        f = MetadataFilter()
        assert f.filter([]) == []


class TestFilterCriteria:
    def test_criteria_with_no_constraints(self):
        c = FilterCriteria()
        assert c.platform is None
        assert c.category is None


class TestDeduplicateByJaccard:
    def test_no_duplicates_returns_all(self):
        docs = [
            {"id": "1", "text": "完全不同的内容 abc"},
            {"id": "2", "text": "完全无关的文本 xyz"},
        ]
        result = deduplicate_by_jaccard(docs, threshold=0.7)
        assert len(result) == 2

    def test_identical_text_merged(self):
        docs = [
            {"id": "1", "text": "小度智能音箱旗舰版"},
            {"id": "2", "text": "小度智能音箱旗舰版"},
        ]
        result = deduplicate_by_jaccard(docs, threshold=0.7)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_high_overlap_merged(self):
        docs = [
            {"id": "1", "text": "小度智能音箱 旗舰版 蓝牙WiFi 语音控制"},
            {"id": "2", "text": "小度智能音箱 旗舰版 蓝牙WiFi 语音控制 升级款"},
        ]
        result = deduplicate_by_jaccard(docs, threshold=0.7)
        assert len(result) == 1

    def test_preserves_higher_score(self):
        docs = [
            {"id": "1", "text": "小度智能音箱旗舰版", "score": 0.5},
            {"id": "2", "text": "小度智能音箱旗舰版", "score": 0.9},
        ]
        result = deduplicate_by_jaccard(docs, threshold=0.7)
        assert len(result) == 1
        assert result[0]["id"] == "2"

    def test_threshold_sensitivity(self):
        docs = [
            {"id": "1", "text": "小度智能音箱蓝牙"},
            {"id": "2", "text": "小度智能音箱蓝牙WiFi"},
        ]
        strict = deduplicate_by_jaccard(docs, threshold=0.95)
        loose = deduplicate_by_jaccard(docs, threshold=0.5)
        assert len(strict) == 2
        assert len(loose) == 1

    def test_empty_input(self):
        assert deduplicate_by_jaccard([]) == []


class TestSimHash:
    def test_identical_text_same_hash(self):
        text = "小度智能音箱旗舰版"
        h1 = simhash(text)
        h2 = simhash(text)
        assert h1 == h2

    def test_similar_text_close_hash(self):
        h1 = simhash("小度智能音箱旗舰版")
        h2 = simhash("小度智能音箱旗舰版 升级")
        diff = bin(h1 ^ h2).count("1")
        assert diff <= 10


class TestDeduplicateBySimHash:
    def test_similar_text_merged(self):
        docs = [
            {"id": "1", "text": "小度智能音箱旗舰版蓝牙WiFi"},
            {"id": "2", "text": "小度智能音箱旗舰版蓝牙WiFi 升级"},
        ]
        result = deduplicate_by_simhash(docs, threshold=5)
        assert len(result) <= 2
