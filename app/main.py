from fastapi import FastAPI
from app.api.v1.router import router as v1_router
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Multi-Agent Report System")

app.include_router(v1_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Multi-Agent Report System API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
