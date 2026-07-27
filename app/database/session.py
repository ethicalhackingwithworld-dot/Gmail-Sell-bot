"""
Database Session Configuration
Async SQLAlchemy setup with SQLite/PostgreSQL support
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, QueuePool
from app.config import settings
import structlog
from typing import AsyncGenerator

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


# Create engine based on environment
if settings.ENVIRONMENT == "development":
    # SQLite for development
    engine: AsyncEngine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        poolclass=NullPool,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL for production
    engine: AsyncEngine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        poolclass=QueuePool,
        pool_size=50,
        max_overflow=100,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency
    Usage: async for db in get_db():
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")


async def close_db() -> None:
    """Close database connections"""
    await engine.dispose()
    logger.info("Database connections closed")
