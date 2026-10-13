import httpx
from app.core.config import settings

async def embed_text(text: str) -> list[float]:
    """调用 Embedding API 获取向量"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
           f"{settings.embed_base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {settings.embed_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": settings.embed_model_name,
                "input": text[:1000]  # 限制输入长度
            },
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]