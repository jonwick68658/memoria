"""
Dependencies for authentication and rate limiting.
"""

from fastapi import Depends, Header, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from memoria.config import settings
from app.celery_app import redis_client  # Use existing Redis from Celery

# API Key dependency
api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)

async def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key is None or api_key != settings.gateway_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key

# User ID dependency
async def get_user_id(x_user_id: str = Header(..., alias="X-User-Id")):
    if not x_user_id or len(x_user_id) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid User ID"
        )
    return x_user_id

# Rate limiter with Redis
limiter = Limiter(key_func=get_remote_address, default_limits=["100 per minute"], storage_uri="redis://localhost:6379")

# Rate limit dependency
from slowapi import _rate_limit_exceeded_handler
from fastapi import Request

async def rate_limited(request: Request):
    response = await limiter(request)
    if response is not None:
        raise RateLimitExceeded
    return response