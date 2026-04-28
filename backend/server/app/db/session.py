"""
FarmShield Backend — Database Session Management.

Exports:
  - async_engine: the SQLAlchemy async engine
  - AsyncSessionLocal: async session factory
  - Base: declarative base for ORM models
  - get_async_session(): async context manager yielding a session
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


async_engine = create_async_engine(
    settings.db_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_pool_max_overflow,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session. Used as a FastAPI dependency and in services."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
