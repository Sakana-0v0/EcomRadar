# EcomRadar · 合规与法律风险说明

> 文档目的:明确 EcomRadar 数据采集的合规边界,降低运营与法律风险

---

## 一、合规自检清单(7 项必查)

| 序号 | 自检项 | 实施方式 | 验证命令 |
|------|--------|----------|----------|
| 1 | **robots.txt 优先** | 抓取前先请求 `/robots.txt`,遵守 Disallow 规则 | `curl https://example.com/robots.txt` |
| 2 | **限速 ≤ 1 req/s** | 全局 Semaphore 控制并发,单域名限速 | 配置 `SCRAPER_RATE_LIMIT=1.0` |
| 3 | **不抓个人信息** | 评价用户头像/昵称/手机号等字段过滤 | `product_parser` 显式忽略 |
| 4 | **不绕过技术保护** | 不破解滑块/验证码/JS 加密参数 | Scraper 检测到保护即降级 |
| 5 | **公开数据** | 仅抓无需登录的公开商品详情页 | URL 不含 `login`/`auth` |
| 6 | **数据 24h 清理** | 抓取结果缓存 ≤ 24h,过期自动删除 | 定时任务清理 `data/scraped/` |
| 7 | **不二次分发** | 数据仅用于本地研报生成,不对外传播 | 代码注释 + LICENSE 声明 |

---

## 二、法律风险分级

### 🟢 低风险(简历项目默认)

**场景**:个人非商用,手工触发,抓 3~5 个公开商品页,本地分析后即丢

- ✅ 不涉及商业目的
- ✅ 数据量极小(单次 < 1MB)
- ✅ 不再分发
- ✅ 不抓个人信息
- ✅ 遵守 robots.txt

**法律依据**:
- 《个人信息保护法》第 13 条:个人非商用目的不构成违法
- 《反不正当竞争法》:不以"实质性替代"为目的不构成不正当竞争
- 平台 ToS:违反 ToS 可能被封号,但民事/刑事风险极低

### 🟡 中风险(需谨慎)

**场景**:每天自动抓 100 次,本地存储,作为内部参考

- ⚠️ 违反平台 ToS(可能被封 IP)
- ⚠️ 持续抓取可能被认定为"实质性替代"
- ⚠️ 大量数据本地存储需关注数据安全

**缓解措施**:
- 错峰抓取(避开大促)
- IP 池隔离(避免主业务受影响)
- 数据脱敏(去个人化)

### 🔴 高风险(禁止)

**场景**:持续大规模抓取 + 商业化 + 二次分发

- ❌ 违反《反不正当竞争法》(实质性替代原平台)
- ❌ 违反平台 ToS(可能面临民事诉讼)
- ❌ 涉及《数据安全法》与《个人信息保护法》

**禁止行为**:
- 抓取登录态数据
- 绕过反爬机制(滑块、验证码)
- 抓取后商业转售
- 镜像原平台核心数据

---

## 三、技术合规实施

### 3.1 robots.txt 合规

```python
# app/services/ecomradar/robots_checker.py
import httpx
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


async def is_allowed(url: str, user_agent: str = "EcomRadar") -> bool:
    """检查 URL 是否被 robots.txt 允许抓取."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(robots_url)
            if response.status_code == 200:
                rp = RobotFileParser()
                rp.parse(response.text.splitlines())
                return rp.can_fetch(user_agent, url)
    except Exception:
        pass
    # 拿不到 robots.txt 时保守拒绝
    return False
```

### 3.2 限速配置

```python
# app/core/config.py
class Settings:
    scraper_max_concurrency: int = 5       # 最多 5 个并发
    scraper_rate_limit: float = 1.0         # 1 req/s
    scraper_retry_times: int = 3            # 最多重试 3 次
    scraper_retry_backoff: float = 2.0      # 指数退避基数
```

### 3.3 数据清理

```python
# scripts/cleanup_scraped_data.py
import shutil
from pathlib import Path
from datetime import datetime, timedelta


def cleanup_old_data(directory: Path, max_age_hours: int = 24):
    """清理 24 小时前的抓取数据."""
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    for file in directory.rglob("*.json"):
        if datetime.fromtimestamp(file.stat().st_mtime) < cutoff:
            file.unlink()
```

---

## 四、平台特殊说明

### 京东 (item.jd.com)
- 商品详情页对搜索引擎基本开放
- 价格 / 销量 / DSR 可抓取
- 评价需登录,**不抓**
- 建议:≤ 1 req/s,可加上 `Referer: https://www.jd.com/`

### 淘宝 / 天猫 (detail.tmall.com, item.taobao.com)
- 移动端 (h5.taobao.com) 反爬较弱
- 价格 / SKU / 店铺信息可抓
- 评价默认折叠,需登录,**不抓**
- 建议:≤ 1 req/s,失败时降级到 jina reader

### 拼多多 (mobile.yangkeduo.com)
- 反爬较强,可能触发滑块
- 优先 jina reader 兜底
- 不主动抓评价
- 建议:≤ 0.5 req/s(更保守)

### 抖音电商 (haohuo.jinritemai.com)
- 反爬强,**默认走 jina reader**
- 价格 / 店铺信息可抓
- 直播数据 / 达人数据**不抓**

---

## 五、降级与告警

当检测到以下情况,Scraper 应**自动降级或暂停**:
- 连续 3 个 403/503 响应 → 切换 jina reader
- 触发滑块/CAPTCHA → 跳过该 URL,记录告警
- 限速触发 → 等待 60s 后重试
- 平台公告 ToS 变更 → 暂停相关平台

---

## 六、用户协议(LICENSE 需声明)

```
MIT License

本项目仅用于个人技术验证与学习目的。

禁止行为:
- 商业化使用
- 大规模持续抓取
- 二次分发抓取数据
- 用于实质性替代原平台服务

作者不对因使用本项目产生的任何法律风险负责。
```

---

## 七、版本

- v1.0 · 2026-10-13 · 初版,覆盖 7 项合规自检 + 法律分级 + 平台特殊说明
