# EcomRadar 多渠道推送配置指南

本文档说明如何为 EcomRadar 配置 Notion / 飞书推送凭证。

## ⚠️ 安全原则

1. **绝不**在聊天/代码/提交中明文分享 API key
2. **绝不**把 `.env` 文件提交到 git (已在 `.gitignore` 中)
3. 凭证通过 `CredentialStore` 加密存储 (Fernet AES-256)
4. Master Key (`ECOMRADAR_CREDENTIAL_KEY`) 一旦丢失, 所有已加密凭证不可恢复

## 📋 前置准备

### 1. 生成 Master Key (一次性)

```bash
# 方式 1: openssl
openssl rand -base64 32

# 方式 2: Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

将输出结果保存到安全位置(如 1Password/Bitwarden), 然后:

```bash
export ECOMRADAR_CREDENTIAL_KEY="<your-32-byte-base64>"
```

或在 `.env` 文件中设置(同样要妥善保管)。

### 2. 复制环境变量模板

```bash
cp .env.example .env
# 编辑 .env 填入真实值
```

---

## 📘 Notion 集成

### 步骤 1: 创建 Integration

1. 访问 https://www.notion.so/profile/integrations
2. 点击 **+ New integration**
3. 填写:
   - Name: `EcomRadar`
   - Logo: (可选)
   - Associated workspace: 选择你的 workspace
4. **Capabilities** 勾选:
   - ✅ Read content
   - ✅ Update content
   - ✅ Insert content
5. 点击 **Submit**
6. 复制 **Internal Integration Secret** (以 `ntn_` 开头)

### 步骤 2: 授权页面

1. 在 Notion 中创建一个父页面 (例: "竞品周报")
2. 点击页面右上角 `···` → **+ Add connections**
3. 搜索 `EcomRadar` 并添加
4. 从页面 URL 末尾复制 32 字符作为 `NOTION_PARENT_PAGE_ID`

### 步骤 3: 配置 EcomRadar

**方式 A: 环境变量 (生产推荐)**
```bash
export NOTION_API_KEY="ntn_xxxxxxxx"
export NOTION_PARENT_PAGE_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

**方式 B: CredentialStore (本地开发)**
```bash
python -m scripts.setup_credentials add notion
# 按提示输入 tenant_id / api_key / page_id
```

### 步骤 4: 测试

```bash
python -m pytest tests/test_notion_publisher.py -v
```

---

## 📗 飞书集成

### 步骤 1: 创建企业自建应用

1. 访问 https://open.feishu.cn/app
2. 点击 **创建企业自建应用**
3. 填写:
   - 应用名称: `EcomRadar`
   - 应用描述: `竞品监控研报推送`
4. 进入应用详情

### 步骤 2: 配置权限

**权限管理** 页面, 搜索并添加:
- ✅ `docs:document:create` (创建文档)
- ✅ `docs:document:update` (更新文档, 用于后续追加内容)
- ✅ `drive:file:upload` (上传图片, 后续扩展用)

### 步骤 3: 创建应用版本并发布

1. **应用发布** → **版本管理与发布**
2. 创建版本 → 填写版本号和说明
3. 申请发布 (企业内部应用通常自动通过)
4. 回到 **凭证与基础信息**, 复制:
   - **App ID**: `cli_xxxxxxxx`
   - **App Secret**: 点击"查看"获取

### 步骤 4: 获取 Folder Token

1. 在飞书云空间创建一个目标文件夹 (例: "竞品报告")
2. 打开该文件夹
3. 从 URL 末尾获取 folder_token (例: `fldcnXXXXXXXX`)

### 步骤 5: 配置 EcomRadar

**方式 A: 环境变量**
```bash
export FEISHU_APP_ID="cli_xxxxxxxx"
export FEISHU_APP_SECRET="xxxxxxxxxxxxxxxx"
export FEISHU_FOLDER_TOKEN="fldcnxxxxxxxx"
```

**方式 B: CredentialStore**
```bash
python -m scripts.setup_credentials add feishu
# 按提示输入
```

### 步骤 6: 测试

```bash
python -m pytest tests/test_feishu_publisher.py -v
```

---

## 🧪 端到端测试

启动服务后, 触发一次完整流程:

```bash
# 1. 启动 Qdrant + Redis (可选)
docker-compose up -d qdrant

# 2. 启动 EcomRadar
uvicorn app.main:app --reload

# 3. 触发报告生成
curl -X POST http://localhost:8000/api/v1/report/generate \
  -H "X-Tenant-ID: tenant_1" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://item.jd.com/100012345678.html"]}'

# 4. 审批后恢复 (HITL)
curl -X POST http://localhost:8000/api/v1/report/{task_id}/resume \
  -H "X-Tenant-ID: tenant_1" \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'

# 5. 检查 Notion/飞书 是否收到新页面
```

---

## 🔒 安全检查清单

- [ ] `.env` 文件不在 git 中 (`.gitignore` 已包含)
- [ ] `ECOMRADAR_CREDENTIAL_KEY` 已生成并安全存储
- [ ] Notion Integration Token 不在聊天/截图中明文出现
- [ ] 飞书 App Secret 不在聊天/截图中明文出现
- [ ] 生产环境使用环境变量而非 CredentialStore (便于密钥管理)
- [ ] 定期轮换 Master Key (季度或半年)

---

## ❓ 常见问题

**Q: 凭证加密后能恢复吗?**
A: 可以,只要 Master Key 不丢失。Fernet 是对称加密。

**Q: 多个 tenant 如何隔离?**
A: 每个 tenant 有独立的 CredentialStore key (tenant_id:provider), 凭证物理隔离。

**Q: Notion/飞书 推送失败怎么办?**
A: Publisher Node 失败时降级 (不中断流程), 错误信息在 `error_messages` 字段中。可通过 `/api/v1/report/{task_id}/status` 查询。

**Q: 如何轮换 Master Key?**
A: 需要重新加密所有已存储的凭证。当前未提供自动化脚本, 建议:
1. 备份现有凭证
2. 生成新 Master Key
3. 重新运行 `setup_credentials add`
