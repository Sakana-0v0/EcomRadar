"""Notion Publisher - 推送报告到 Notion 页面.

API 端点:
- POST /v1/blocks/{parent_id}/children  (添加子块)

认证: Bearer token (Internal Integration Secret)
"""
from typing import Optional

import httpx

from app.services.publisher.markdown_to_blocks import markdown_to_blocks


class NotionPublisher:
    """Notion Publisher 实现.

    Args:
        api_key: Notion Internal Integration Secret (从环境变量或 CredentialStore 注入)
        parent_page_id: 父页面 ID (新内容会作为子块添加)
        timeout: API 超时(秒)
    """

    channel_name = "notion"
    BASE_URL = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"

    def __init__(
        self,
        api_key: str,
        parent_page_id: str,
        timeout: float = 15.0,
    ):
        if not api_key:
            raise ValueError("api_key is required for NotionPublisher")
        if not parent_page_id:
            raise ValueError("parent_page_id is required for NotionPublisher")
        self.api_key = api_key
        self.parent_page_id = parent_page_id
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def publish(
        self,
        title: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """推送报告到 Notion.

        Args:
            title: 报告标题(将成为第一个 H1 块)
            content: Markdown 格式的报告内容
            metadata: 附加元数据(可选)

        Returns:
            True 表示成功

        Raises:
            PermissionError: 401/403 (API key 无效)
            ValueError: 404 (页面不存在) / 400 (请求格式错误)
            RuntimeError: 5xx (服务端错误) / 网络错误
        """
        full_md = f"# {title}\n\n{content}" if title else content
        blocks = markdown_to_blocks(full_md)
        if not blocks:
            blocks = [{
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": "(empty report)"}}]},
            }]

        payload = {"children": blocks[:100]}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/blocks/{self.parent_page_id}/children",
                    headers=self._headers(),
                    json=payload,
                )
            except httpx.TimeoutException as e:
                raise RuntimeError(f"Notion API timeout: {e}") from e
            except httpx.HTTPError as e:
                raise RuntimeError(f"Notion API network error: {e}") from e

            if response.status_code in (200, 201):
                return True
            if response.status_code in (401, 403):
                raise PermissionError(
                    f"Notion auth failed: {response.status_code} {response.text[:200]}"
                )
            if response.status_code == 404:
                raise ValueError(
                    f"Notion page not found: {self.parent_page_id}"
                )
            if response.status_code == 400:
                raise ValueError(
                    f"Notion bad request: {response.text[:200]}"
                )
            raise RuntimeError(
                f"Notion API error: {response.status_code} {response.text[:200]}"
            )
