"""
Public endpoint exposing client.config.json to the frontend — no
auth required, this is just branding/labels, not sensitive data.
"""

from fastapi import APIRouter

from app.core.client_config import client_config

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/")
async def get_config():
    return client_config
