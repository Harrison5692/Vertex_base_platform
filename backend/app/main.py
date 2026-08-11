from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import items
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items.router)


@app.get("/health")
async def health():
    """Simple liveness check — useful for deployment/uptime monitoring."""
    return {"status": "ok", "environment": settings.environment}
