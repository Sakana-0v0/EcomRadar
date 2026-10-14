"""FastAPI 应用入口.

Phase 6: 集成多租户中间件 + 限流中间件.
"""
from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.logging import setup_logging
from app.middleware import TenantMiddleware, RateLimitMiddleware

setup_logging()

app = FastAPI(
    title="EcomRadar",
    description="多智能体电商竞品监控研报系统",
    version="0.6.0",
)

app.add_middleware(RateLimitMiddleware, limit=10, window_seconds=60.0)
app.add_middleware(TenantMiddleware, required=True)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "EcomRadar",
        "version": "0.6.0",
        "description": "多智能体电商竞品监控研报系统",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
