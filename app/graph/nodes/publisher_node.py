"""Publisher Node - 集成 Notion + 飞书 + 凭证管理.

凭证注入策略:
- 优先从 CredentialStore 加载 (Phase 6)
- Fallback: 环境变量
- 凭证永远不出现在日志/错误信息中
"""
import os
from typing import Optional

from app.graph.state import GraphState
from app.core.logging import get_logger
from app.core.checkpointer import Checkpoint, get_checkpointer
from app.services.security.credential_store import (
    CredentialStore,
    EncryptedCredential,
)

logger = get_logger(__name__)


def _mask_key(key: str) -> str:
    """凭证脱敏 (用于日志)."""
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


async def _load_notion_credential(
    tenant_id: str,
    store: Optional[CredentialStore] = None,
) -> Optional[EncryptedCredential]:
    """从 CredentialStore 加载 Notion 凭证."""
    if store is None:
        try:
            store = CredentialStore.create(backend="memory")
        except Exception:
            return None
    return await store.load(tenant_id, "notion")


async def _load_feishu_credential(
    tenant_id: str,
    store: Optional[CredentialStore] = None,
) -> Optional[EncryptedCredential]:
    """从 CredentialStore 加载飞书凭证."""
    if store is None:
        try:
            store = CredentialStore.create(backend="memory")
        except Exception:
            return None
    return await store.load(tenant_id, "feishu")


async def publisher_node(state: GraphState) -> GraphState:
    """Publisher Node - 推送到 Notion + 飞书.

    输入: 合格报告 + task_id + tenant_id
    输出: published_channels (list[str])

    凭证策略:
    1. 从 CredentialStore 加载 (按 tenant_id 隔离)
    2. 失败时回退到环境变量
    3. 凭证永远脱敏后再日志
    """
    report = state.get("report", "")
    task_id = state.get("task_id", f"task_{id(state)}")
    tenant_id = state.get("tenant_id", "anonymous")
    category = state.get("report_category", "未指定")

    if not report:
        return {
            "published_channels": [],
            "is_degraded": True,
            "error_messages": state.get("error_messages", []) + ["Publisher: empty report"],
        }

    published_channels: list[str] = []

    try:
        from app.core.mcp_config import register_publisher
        from app.services.publisher.notion_client import NotionPublisher
        from app.services.publisher.feishu_client import FeishuPublisher

        notion_cred = await _load_notion_credential(tenant_id)
        if notion_cred and notion_cred.extra.get("parent_page_id"):
            try:
                notion = NotionPublisher(
                    api_key=notion_cred.api_key,
                    parent_page_id=notion_cred.extra["parent_page_id"],
                )
                ok = await notion.publish(
                    title=f"EcomRadar - {category}",
                    content=report,
                    metadata={"task_id": task_id, "tenant_id": tenant_id},
                )
                if ok:
                    published_channels.append("notion")
                    logger.info(
                        "notion published",
                        extra={"node": "publisher", "key": _mask_key(notion_cred.api_key)},
                    )
            except Exception as e:
                logger.warning(
                    f"notion publish failed: {type(e).__name__}",
                    extra={"node": "publisher"},
                )
        else:
            env_key = os.environ.get("NOTION_API_KEY", "")
            env_page = os.environ.get("NOTION_PARENT_PAGE_ID", "")
            if env_key and env_page:
                try:
                    notion = NotionPublisher(api_key=env_key, parent_page_id=env_page)
                    if await notion.publish(
                        title=f"EcomRadar - {category}",
                        content=report,
                        metadata={"task_id": task_id},
                    ):
                        published_channels.append("notion")
                except Exception as e:
                    logger.warning(
                        f"notion env publish failed: {type(e).__name__}",
                        extra={"node": "publisher"},
                    )

        feishu_cred = await _load_feishu_credential(tenant_id)
        if feishu_cred and feishu_cred.extra.get("folder_token"):
            try:
                feishu = FeishuPublisher(
                    app_id=feishu_cred.api_key,
                    app_secret=feishu_cred.extra.get("app_secret", ""),
                    folder_token=feishu_cred.extra["folder_token"],
                )
                if await feishu.publish(
                    title=f"EcomRadar - {category}",
                    content=report,
                    metadata={"task_id": task_id},
                ):
                    published_channels.append("feishu")
            except Exception as e:
                logger.warning(
                    f"feishu publish failed: {type(e).__name__}",
                    extra={"node": "publisher"},
                )
        else:
            env_app_id = os.environ.get("FEISHU_APP_ID", "")
            env_app_secret = os.environ.get("FEISHU_APP_SECRET", "")
            env_folder = os.environ.get("FEISHU_FOLDER_TOKEN", "")
            if env_app_id and env_app_secret and env_folder:
                try:
                    feishu = FeishuPublisher(
                        app_id=env_app_id,
                        app_secret=env_app_secret,
                        folder_token=env_folder,
                    )
                    if await feishu.publish(
                        title=f"EcomRadar - {category}",
                        content=report,
                        metadata={"task_id": task_id},
                    ):
                        published_channels.append("feishu")
                except Exception as e:
                    logger.warning(
                        f"feishu env publish failed: {type(e).__name__}",
                        extra={"node": "publisher"},
                    )

        try:
            checkpoint_store = get_checkpointer(backend="memory")
            await checkpoint_store.save(Checkpoint(
                task_id=task_id,
                node_name="publisher",
                state={**state, "published_channels": published_channels},
            ))
        except Exception:
            pass

        logger.info(
            "publisher completed",
            extra={"node": "publisher", "channels": published_channels},
        )
        return {"published_channels": published_channels}

    except Exception as e:
        logger.error("publisher failed", extra={"node": "publisher", "error": str(e)})
        return {
            "published_channels": [],
            "is_degraded": True,
            "error_messages": state.get("error_messages", []) + [f"Publisher: {str(e)}"],
        }
