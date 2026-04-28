"""
FarmShield Backend — FastAPI Dependencies.

Exports:
  - get_db: yields an async DB session for route handlers
  - require_auth: re-exported from core.auth for convenience
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_auth  # noqa: F401 — re-exported
from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async DB session.

    Route handlers receive this via Depends(get_db) and pass it
    to service functions. They never execute queries themselves.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
