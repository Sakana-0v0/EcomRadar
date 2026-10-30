"""FastAPI 应用入口.

Phase 6: 集成多租户中间件 + 限流中间件.
Phase 10: 挂载前端 Dashboard (frontend/dist).
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router as v1_router
from app.core.logging import setup_logging
from app.middleware import TenantMiddleware, RateLimitMiddleware

setup_logging()

app = FastAPI(
    title="EcomRadar",
    description="多智能体电商竞品监控研报系统",
    version="0.7.0",
)

app.add_middleware(RateLimitMiddleware, limit=10, window_seconds=60.0)
app.add_middleware(TenantMiddleware, required=True)

app.include_router(v1_router, prefix="/api/v1")


# ---------- 前端 Dashboard (可选, 需先构建 frontend) ----------
_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/", include_in_schema=False)
    async def dashboard():
        from fastapi.responses import FileResponse
        return FileResponse(_FRONTEND_DIST / "index.html")
else:

    @app.get("/", include_in_schema=False)
    async def dashboard_placeholder():
        return {
            "name": "EcomRadar",
            "version": "0.7.0",
            "description": "多智能体电商竞品监控研报系统",
            "hint": "前端未构建, 请运行: cd frontend && npm install && npm run build",
        }


@app.get("/api/v1/meta", include_in_schema=False)
async def meta():
    """前端构建信息."""
    return {
        "frontend_built": _FRONTEND_DIST.exists(),
        "version": "0.7.0",
        "nodes": 6,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
