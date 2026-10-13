"""BM25 倒排索引单元测试."""
import pytest

from app.services.retrieval.bm25_index import BM25Index, tokenize, tokenize_chinese


class TestTokenize:
    def test_tokenize_chinese_splits_cjk(self):
        """中文按字符切分."""
        tokens = tokenize_chinese("小度智能音箱")
        assert "小" in tokens
        assert "度" in tokens
        assert "智" in tokens

    def test_tokenize_lowers_and_strips(self):
        tokens = tokenize("Hello World!")
        assert "hello" in tokens
        assert "world" in tokens
        assert "!" not in "".join(tokens)

    def test_tokenize_combines_chinese_and_english(self):
        tokens = tokenize("iPhone 15 Pro")
        assert "iphone" in tokens
        assert "15" in tokens
        assert "pro" in tokens


class TestBM25Index:
    def test_empty_index_returns_no_results(self):
        idx = BM25Index()
        results = idx.search("query", top_k=5)
        assert results == []

    def test_add_documents_indexes_them(self):
        idx = BM25Index()
        idx.add_documents([
            {"id": "1", "text": "小度智能音箱蓝牙WiFi语音控制", "source": "jd"},
            {"id": "2", "text": "天猫精灵蓝牙音响", "source": "tmall"},
        ])
        results = idx.search("小度", top_k=5)
        assert len(results) >= 1
        assert results[0]["id"] == "1"
        assert results[0]["score"] > 0

    def test_search_returns_relevant_doc_higher(self):
        idx = BM25Index()
        idx.add_documents([
            {"id": "doc1", "text": "apple banana cherry"},
            {"id": "doc2", "text": "apple fruit sweet"},
            {"id": "doc3", "text": "vegetable carrot potato"},
        ])
        results = idx.search("apple", top_k=3)
        assert results[0]["id"] in ("doc1", "doc2")
        assert results[-1]["id"] == "doc3"

    def test_search_respects_top_k(self):
        idx = BM25Index()
        for i in range(20):
            idx.add_documents([{"id": str(i), "text": f"测试文档 {i} 内容", "source": "test"}])
        results = idx.search("测试", top_k=5)
        assert len(results) == 5

    def test_search_chinese_keyword(self):
        idx = BM25Index()
        idx.add_documents([
            {"id": "1", "text": "小度智能音箱旗舰版", "source": "jd"},
            {"id": "2", "text": "小米手机充电器", "source": "jd"},
            {"id": "3", "text": "天猫精灵语音助手", "source": "tmall"},
        ])
        results = idx.search("智能音箱", top_k=3)
        assert results[0]["id"] == "1"
        assert all(r["id"] != "2" for r in results[:2])

    def test_search_returns_empty_for_irrelevant_query(self):
        idx = BM25Index()
        idx.add_documents([
            {"id": "1", "text": "小度智能音箱", "source": "jd"},
        ])
        results = idx.search("完全没有关系的关键词 xyz123", top_k=5)
        assert all(r["score"] == 0 for r in results)

    def test_source_metadata_preserved(self):
        idx = BM25Index()
        idx.add_documents([
            {"id": "1", "text": "测试商品", "source": "jd", "category": "智能音箱"},
        ])
        results = idx.search("测试", top_k=1)
        assert results[0]["source"] == "jd"
        assert results[0]["category"] == "智能音箱"

    def test_clear_resets_index(self):
        idx = BM25Index()
        idx.add_documents([{"id": "1", "text": "测试", "source": "x"}])
        idx.clear()
        assert idx.search("测试") == []

    def test_persistence_save_and_load(self, tmp_path):
        idx = BM25Index()
        idx.add_documents([
            {"id": "1", "text": "测试商品A", "source": "jd"},
            {"id": "2", "text": "测试商品B", "source": "tmall"},
        ])
        save_path = tmp_path / "bm25.pkl"
        idx.save(save_path)

        new_idx = BM25Index()
        new_idx.load(save_path)
        results = new_idx.search("测试", top_k=2)
        assert len(results) == 2
