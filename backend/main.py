import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from routers import agents

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(
    title="Research Assistant API",
    description="Backend de apoio à revisão de literatura científica.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/agents", tags=["agents"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
