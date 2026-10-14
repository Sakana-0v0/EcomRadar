"""Publisher Node 集成测试.

验证:
- 无凭证时优雅降级 (published_channels = [])
- 凭证存储路径下成功推送
- 多租户隔离
- 错误处理 (无日志泄露凭证)
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.graph.nodes.publisher_node import publisher_node, _mask_key
from app.services.security.credential_store import (
    CredentialStore,
    EncryptedCredential,
)


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("ECOMRADAR_CREDENTIAL_KEY", "test-key-for-unit-tests")


class TestMaskKey:
    def test_short_key_returns_asterisks(self):
        assert _mask_key("") == "***"
        assert _mask_key("abc") == "***"

    def test_normal_key_masks_middle(self):
        masked = _mask_key("secret-key-12345678")
        assert masked.startswith("secr")
        assert masked.endswith("5678")
        assert "..." in masked


class TestPublisherNode:
    @pytest.mark.asyncio
    async def test_empty_report_returns_degraded(self):
        state = {
            "task_id": "t1",
            "tenant_id": "tenant_1",
            "report": "",
            "report_category": "测试",
            "scraped_content": {},
            "chunks": [],
            "context_docs": [],
            "quality_score": 0,
            "retry_count": 0,
            "is_degraded": False,
            "error_messages": [],
        }
        result = await publisher_node(state)
        assert result["is_degraded"] is True
        assert result["published_channels"] == []

    @pytest.mark.asyncio
    async def test_no_credentials_returns_empty(self):
        state = {
            "task_id": "t1",
            "tenant_id": "tenant_no_creds",
            "report": "# 报告\n## 内容",
            "report_category": "测试",
            "scraped_content": {},
            "chunks": [],
            "context_docs": [],
            "quality_score": 80,
            "retry_count": 1,
            "is_degraded": False,
            "error_messages": [],
        }
        result = await publisher_node(state)
        assert "notion" not in result.get("published_channels", [])
        assert "feishu" not in result.get("published_channels", [])

    @pytest.mark.asyncio
    async def test_credential_store_path_publishes_to_notion(self):
        store = CredentialStore.create(backend="memory")
        await store.save(EncryptedCredential(
            tenant_id="tenant_1",
            provider="notion",
            api_key="notion-secret-key-1234",
            extra={"parent_page_id": "page-abc-123"},
        ))

        with patch(
            "app.graph.nodes.publisher_node._load_notion_credential",
            new=AsyncMock(return_value=await store.load("tenant_1", "notion")),
        ):
            with patch(
                "app.services.publisher.notion_client.NotionPublisher.publish",
                new=AsyncMock(return_value=True),
            ):
                state = {
                    "task_id": "t1",
                    "tenant_id": "tenant_1",
                    "report": "# 报告\n## 内容",
                    "report_category": "智能音箱",
                    "scraped_content": {},
                    "chunks": [],
                    "context_docs": [],
                    "quality_score": 85,
                    "retry_count": 1,
                    "is_degraded": False,
                    "error_messages": [],
                }
                result = await publisher_node(state)
                assert "notion" in result["published_channels"]

    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        """不同 tenant 使用不同凭证."""
        store = CredentialStore.create(backend="memory")
        await store.save(EncryptedCredential(
            tenant_id="tenant_A",
            provider="notion",
            api_key="A-secret-key",
            extra={"parent_page_id": "page-A"},
        ))
        await store.save(EncryptedCredential(
            tenant_id="tenant_B",
            provider="notion",
            api_key="B-secret-key",
            extra={"parent_page_id": "page-B"},
        ))

        cred_A = await store.load("tenant_A", "notion")
        cred_B = await store.load("tenant_B", "notion")
        assert cred_A.api_key == "A-secret-key"
        assert cred_B.api_key == "B-secret-key"
        assert cred_A.api_key != cred_B.api_key

    @pytest.mark.asyncio
    async def test_publisher_failure_does_not_crash_pipeline(self):
        """Publisher 失败不应中断流程 (降级)."""
        with patch(
            "app.graph.nodes.publisher_node._load_notion_credential",
            new=AsyncMock(side_effect=Exception("store error")),
        ):
            with patch(
                "app.services.publisher.feishu_client.FeishuPublisher.publish",
                new=AsyncMock(side_effect=Exception("network")),
            ):
                state = {
                    "task_id": "t1",
                    "tenant_id": "tenant_X",
                    "report": "# 报告",
                    "report_category": "测试",
                    "scraped_content": {},
                    "chunks": [],
                    "context_docs": [],
                    "quality_score": 80,
                    "retry_count": 1,
                    "is_degraded": False,
                    "error_messages": [],
                }
                result = await publisher_node(state)
                assert "error_messages" in result
                assert result.get("is_degraded") is True
