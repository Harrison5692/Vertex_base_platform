from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, auth, config, items, transactions
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(items.router)
app.include_router(transactions.router)


@app.get("/health")
async def health():
    """Simple liveness check — useful for deployment/uptime monitoring."""
    return {"status": "ok", "environment": settings.environment}
