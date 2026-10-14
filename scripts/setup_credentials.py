"""凭证设置脚本 - 交互式添加 Notion/飞书 凭证.

⚠️ 重要安全提示:
- 不要在代码或聊天中明文分享 API key
- 推荐方式: 通过环境变量 (生产) 或 CredentialStore (本地)
- 此脚本加密存储到本地文件, master key 从环境变量 ECOMRADAR_CREDENTIAL_KEY 读取

用法:
    export ECOMRADAR_CREDENTIAL_KEY="your-master-key-here"
    python -m scripts.setup_credentials add notion
    python -m scripts.setup_credentials add feishu
    python -m scripts.setup_credentials list
"""
import asyncio
import getpass
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def cmd_add_notion():
    from app.services.security.credential_store import (
        CredentialStore, EncryptedCredential,
    )
    try:
        store = CredentialStore.create(backend="memory")
    except ValueError as e:
        print(f"错误: {e}")
        print("请先设置 ECOMRADAR_CREDENTIAL_KEY 环境变量")
        return

    tenant_id = input("Tenant ID: ").strip()
    api_key = getpass.getpass("Notion API Key (输入隐藏): ").strip()
    parent_page_id = input("Parent Page ID: ").strip()

    asyncio.run(store.save(EncryptedCredential(
        tenant_id=tenant_id,
        provider="notion",
        api_key=api_key,
        extra={"parent_page_id": parent_page_id},
    )))
    print(f"已保存 Notion 凭证: tenant={tenant_id}")


def cmd_add_feishu():
    from app.services.security.credential_store import (
        CredentialStore, EncryptedCredential,
    )
    try:
        store = CredentialStore.create(backend="memory")
    except ValueError as e:
        print(f"错误: {e}")
        return

    tenant_id = input("Tenant ID: ").strip()
    app_id = getpass.getpass("Feishu App ID: ").strip()
    app_secret = getpass.getpass("Feishu App Secret (输入隐藏): ").strip()
    folder_token = input("Folder Token: ").strip()

    asyncio.run(store.save(EncryptedCredential(
        tenant_id=tenant_id,
        provider="feishu",
        api_key=app_id,
        extra={"app_secret": app_secret, "folder_token": folder_token},
    )))
    print(f"已保存飞书凭证: tenant={tenant_id}")


def cmd_list():
    print("\n已配置的租户 (从环境变量读取):")
    print(f"  NOTION_API_KEY: {'已设置' if os.environ.get('NOTION_API_KEY') else '未设置'}")
    print(f"  NOTION_PARENT_PAGE_ID: {'已设置' if os.environ.get('NOTION_PARENT_PAGE_ID') else '未设置'}")
    print(f"  FEISHU_APP_ID: {'已设置' if os.environ.get('FEISHU_APP_ID') else '未设置'}")
    print(f"  FEISHU_APP_SECRET: {'已设置' if os.environ.get('FEISHU_APP_SECRET') else '未设置'}")
    print(f"  FEISHU_FOLDER_TOKEN: {'已设置' if os.environ.get('FEISHU_FOLDER_TOKEN') else '未设置'}")
    print(f"  ECOMRADAR_CREDENTIAL_KEY: {'已设置' if os.environ.get('ECOMRADAR_CREDENTIAL_KEY') else '未设置'}")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m scripts.setup_credentials add notion")
        print("  python -m scripts.setup_credentials add feishu")
        print("  python -m scripts.setup_credentials list")
        return

    cmd = sys.argv[1]
    if cmd == "add" and len(sys.argv) > 2:
        if sys.argv[2] == "notion":
            cmd_add_notion()
        elif sys.argv[2] == "feishu":
            cmd_add_feishu()
        else:
            print(f"未知 provider: {sys.argv[2]}")
    elif cmd == "list":
        cmd_list()
    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
