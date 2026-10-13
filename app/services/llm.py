"""LLM 服务 - 调用大模型生成报告.

Phase 3 升级:
- 新增 generate_competitor_report() 使用竞品周报 Prompt
- 保留 generate_report() 兼容旧调用
- Prompt 模板从 app/prompts/ 目录加载
"""
from pathlib import Path

import httpx

from app.core.config import settings


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """加载 prompt 模板文件."""
    path = _PROMPTS_DIR / name
    return path.read_text(encoding="utf-8")


async def _call_llm(prompt: str, max_tokens: int = 2000) -> str:
    """底层 LLM 调用.

    Args:
        prompt: 完整 prompt
        max_tokens: 最大生成 token 数

    Returns:
        LLM 生成的文本
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": max_tokens,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def generate_competitor_report(
    scraped_content: str,
    context: str,
    retry_count: int = 0,
    category: str = "未指定品类",
    period: str = "本周",
) -> str:
    """生成竞品周报 - 4 段式 Markdown 结构.

    Args:
        scraped_content: 抓取层输出的结构化商品数据
        context: RAG 检索的行业知识
        retry_count: 重试次数(用于 Prompt 调整)
        category: 品类(用于报告标题)
        period: 周期(用于报告标题)

    Returns:
        Markdown 报告文本
    """
    template = _load_prompt("competitor_report.md")
    prompt = (
        template
        .replace("{retry_count}", str(retry_count))
        .replace("{scraped_content}", scraped_content[:6000])
        .replace("{context}", context[:2000])
        .replace("<品类>", category)
        .replace("<品类>", category)
    )
    return await _call_llm(prompt, max_tokens=3000)


async def generate_report(content: str, context: str, retry_count: int) -> str:
    """原 generate_report - 兼容旧调用,委托到竞品周报接口."""
    return await generate_competitor_report(
        scraped_content=content,
        context=context,
        retry_count=retry_count,
    )
