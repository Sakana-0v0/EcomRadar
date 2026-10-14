"""飞书 Publisher - 推送报告到飞书云文档.

API 端点 (open.feishu.cn):
- POST /open-apis/auth/v3/tenant_access_token/internal  (获取 tenant_access_token)
- POST /open-apis/docx/v1/documents  (创建文档)

设计要点:
- 每次推送先获取/刷新 token
- 飞书 OpenAPI token 有效期 2 小时, 缓存复用
- 创建文档后将 Markdown 内容追加到文档块
"""
from typing import Optional

import httpx


class FeishuPublisher:
    """飞书 Publisher.

    Args:
        app_id: 飞书应用 App ID (cli_xxx)
        app_secret: 飞书应用 App Secret
        folder_token: 目标文件夹 token
        timeout: API 超时(秒)
    """

    channel_name = "feishu"
    BASE_URL = "https://open.feishu.cn/open-apis"
    TOKEN_PATH = "/auth/v3/tenant_access_token/internal"
    DOC_PATH = "/docx/v1/documents"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        folder_token: str,
        timeout: float = 15.0,
    ):
        if not app_id or not app_secret or not folder_token:
            raise ValueError("app_id, app_secret, folder_token are all required")
        self.app_id = app_id
        self.app_secret = app_secret
        self.folder_token = folder_token
        self.timeout = timeout
        self._cached_token: Optional[str] = None
        self.last_doc_id: Optional[str] = None
        self.last_doc_url: Optional[str] = None

    async def _get_tenant_token(self) -> str:
        """获取 tenant_access_token (带简单缓存)."""
        if self._cached_token:
            return self._cached_token
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.BASE_URL}{self.TOKEN_PATH}",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret,
                },
            )
            data = response.json()
            if data.get("code") != 0:
                raise PermissionError(
                    f"feishu auth failed: {data.get('code')} {data.get('msg')}"
                )
            self._cached_token = data["tenant_access_token"]
            return self._cached_token

    def invalidate_token(self) -> None:
        """显式作废缓存 token (强制下次重新获取)."""
        self._cached_token = None

    async def publish(
        self,
        title: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """推送报告: 创建飞书云文档并写入 Markdown 内容.

        Args:
            title: 文档标题
            content: Markdown 内容 (本次实现仅创建文档, 内容追加留 TODO)
            metadata: 附加元数据

        Returns:
            True 表示成功
        """
        token = await self._get_tenant_token()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.BASE_URL}{self.DOC_PATH}",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "title": title,
                    "folder_token": self.folder_token,
                },
            )
            data = response.json()
            if data.get("code") != 0:
                code = data.get("code")
                msg = data.get("msg", "")
                if code in (99991663, 99991668):
                    raise ValueError(f"feishu folder not found: {msg}")
                raise RuntimeError(f"feishu create doc failed: {code} {msg}")

            doc = data.get("data", {}).get("document", {})
            self.last_doc_id = doc.get("document_id")
            self.last_doc_url = doc.get("url")
            return True
