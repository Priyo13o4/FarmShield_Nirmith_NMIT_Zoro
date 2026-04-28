"""
FarmShield Backend — Authentication.

Exports `require_auth` — a FastAPI Security dependency.
When AUTH_ENABLED=true: validates Bearer API key against settings.API_KEY.
When AUTH_ENABLED=false: no-op with zero overhead.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

# auto_error=False so we get None instead of a 403 when no header is present
_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> None:
    """
    Validate the Authorization: Bearer <key> header.

    Raises HTTPException 401 when AUTH_ENABLED=true and the key is
    missing or incorrect. Is a complete no-op when AUTH_ENABLED=false.
    """
    if not settings.auth_enabled:
        return  # No-op — zero overhead

    if credentials is None or credentials.credentials != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
