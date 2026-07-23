from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from core.config import settings

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key: str = Security(api_key_header)):
    expected_key = getattr(settings, "LEGALLENS_API_KEY", "")
    if expected_key:
        if not api_key or api_key != expected_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API Key"
            )
    return api_key
