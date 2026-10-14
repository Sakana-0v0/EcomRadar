"""飞书 Publisher 单元测试."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.publisher.feishu_client import FeishuPublisher


SAMPLE_TOKEN_RESPONSE = {
    "code": 0,
    "msg": "ok",
    "tenant_access_token": "t-xxxxx",
    "expire": 7200,
}

SAMPLE_CREATE_DOC_RESPONSE = {
    "code": 0,
    "msg": "ok",
    "data": {
        "document": {
            "document_id": "doc_new_123",
            "url": "https://example.feishu.cn/docs/doc_new_123",
        }
    },
}


class TestFeishuPublisher:
    @pytest.mark.asyncio
    async def test_publish_creates_new_doc(self):
        publisher = FeishuPublisher(
            app_id="cli_xxx",
            app_secret="secret",
            folder_token="fld_xxx",
        )
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = SAMPLE_TOKEN_RESPONSE
        create_response = MagicMock()
        create_response.status_code = 200
        create_response.json.return_value = SAMPLE_CREATE_DOC_RESPONSE

        with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=[token_response, create_response])):
            success = await publisher.publish(
                title="测试报告",
                content="# 标题\n内容",
                metadata={},
            )
            assert success is True
            assert publisher.channel_name == "feishu"
            assert publisher.last_doc_id == "doc_new_123"

    @pytest.mark.asyncio
    async def test_token_failure_raises(self):
        publisher = FeishuPublisher(
            app_id="bad", app_secret="bad", folder_token="fld",
        )
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"code": 10003, "msg": "invalid app_id"}

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=token_response)):
            with pytest.raises(PermissionError):
                await publisher.publish(title="t", content="c", metadata={})

    @pytest.mark.asyncio
    async def test_create_doc_failure_raises(self):
        publisher = FeishuPublisher(
            app_id="cli_xxx", app_secret="secret", folder_token="fld_xxx",
        )
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = SAMPLE_TOKEN_RESPONSE
        create_response = MagicMock()
        create_response.status_code = 200
        create_response.json.return_value = {"code": 99991663, "msg": "folder not found"}

        with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=[token_response, create_response])):
            with pytest.raises(ValueError):
                await publisher.publish(title="t", content="c", metadata={})

    def test_publisher_protocol_conformance(self):
        from app.core.mcp_config import Publisher
        publisher = FeishuPublisher(
            app_id="cli_xxx", app_secret="secret", folder_token="fld_xxx",
        )
        assert isinstance(publisher, Publisher)
        assert publisher.channel_name == "feishu"

    def test_credentials_required(self):
        with pytest.raises(ValueError):
            FeishuPublisher(app_id="", app_secret="", folder_token="")
