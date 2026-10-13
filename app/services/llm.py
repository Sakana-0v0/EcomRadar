import httpx
import os
from app.core.config import settings


async def generate_report(content: str , context: str , retry_count: int ) -> str:
    """调用LLM生成结构化研报"""
    prompt = f"""
你是一个专业的研报撰写助手。请基于以下内容撰写结构化研报。

内容摘要：
{content[:2000]}

上下文参考：
{context[:1000]}

重试次数：{retry_count}

请按以下结构生成研报：
1. # 研究报告
2. ## 核心要点（3-5条）
3. ## 内容摘要（详细分析）
4. ## 影响与趋势分析
5. ## 风险提示
6. ## 展望

要求：内容准确、结构清晰、有深度分析。
"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": settings.llm_model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout = 30.0
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]



   
