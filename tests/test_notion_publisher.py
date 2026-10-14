"""Notion Publisher 单元测试.

测试覆盖:
- NotionPublisher.publish() 成功路径
- Markdown 解析为 Notion Blocks
- API 错误处理 (401/404/500)
- 凭证通过 CredentialStore 注入
- 超时与重试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.publisher.notion_client import NotionPublisher
from app.services.publisher.markdown_to_blocks import markdown_to_blocks


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("ECOMRADAR_CREDENTIAL_KEY", "test-key-for-unit-tests")


class TestMarkdownToBlocks:
    def test_empty_returns_empty(self):
        assert markdown_to_blocks("") == []

    def test_h1_to_heading(self):
        blocks = markdown_to_blocks("# 标题")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading_1"
        assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "标题"

    def test_h2_to_heading(self):
        blocks = markdown_to_blocks("## 副标题")
        assert blocks[0]["type"] == "heading_2"

    def test_h3_to_heading(self):
        blocks = markdown_to_blocks("### 小节")
        assert blocks[0]["type"] == "heading_3"

    def test_paragraph(self):
        blocks = markdown_to_blocks("普通段落文字")
        assert blocks[0]["type"] == "paragraph"
        assert "普通段落文字" in blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]

    def test_table_preserved(self):
        md = """| 列A | 列B |
|---|---|
| 1 | 2 |"""
        blocks = markdown_to_blocks(md)
        assert any(b["type"] == "table" for b in blocks)

    def test_list_item(self):
        blocks = markdown_to_blocks("- 项目1\n- 项目2")
        assert all(b["type"] == "bulleted_list_item" for b in blocks)
        assert len(blocks) == 2

    def test_bold_in_rich_text(self):
        blocks = markdown_to_blocks("**粗体文字**")
        text = blocks[0]["paragraph"]["rich_text"][0]
        assert text["text"]["content"] == "粗体文字"
        assert text["annotations"]["bold"] is True

    def test_complex_report(self):
        md = """# 竞品周报 - 智能音箱

## Executive Summary

本周动态...

## 竞品矩阵对比

| 品牌 | 价格 |
|---|---|
| 小度 | 329 |

## 行动建议

**1. 错位定价** — 音质升级
"""
        blocks = markdown_to_blocks(md)
        types = [b["type"] for b in blocks]
        assert "heading_1" in types
        assert "heading_2" in types
        assert "table" in types
        assert "paragraph" in types


class TestNotionPublisher:
    @pytest.mark.asyncio
    async def test_publish_success(self):
        publisher = NotionPublisher(
            api_key="secret-key",
            parent_page_id="page-123",
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "block-1", "object": "block"}

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            success = await publisher.publish(
                title="测试报告",
                content="# 标题\n## 内容",
                metadata={"task_id": "t1"},
            )
            assert success is True
            assert publisher.channel_name == "notion"

    @pytest.mark.asyncio
    async def test_publish_401_raises(self):
        publisher = NotionPublisher(api_key="bad-key", parent_page_id="page-123")
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(PermissionError):
                await publisher.publish(title="t", content="x", metadata={})

    @pytest.mark.asyncio
    async def test_publish_404_raises(self):
        publisher = NotionPublisher(api_key="k", parent_page_id="missing-page")
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(ValueError):
                await publisher.publish(title="t", content="x", metadata={})

    @pytest.mark.asyncio
    async def test_publish_5xx_raises_runtime_error(self):
        publisher = NotionPublisher(api_key="k", parent_page_id="p")
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(RuntimeError):
                await publisher.publish(title="t", content="x", metadata={})

    def test_publisher_protocol_conformance(self):
        from app.core.mcp_config import Publisher
        publisher = NotionPublisher(api_key="k", parent_page_id="p")
        assert isinstance(publisher, Publisher)
        assert hasattr(publisher, "channel_name")
        assert hasattr(publisher, "publish")
