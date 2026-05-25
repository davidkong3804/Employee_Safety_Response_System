from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    # PgBouncer transaction mode multiplexes many client connections onto a
    # smaller pool of server connections. Two layers of prepared-statement
    # caching must be disabled or two clients sharing a server conn will collide
    # with "prepared statement __asyncpg_stmt_N__ already exists":
    #   1. asyncpg driver-side LRU cache  → statement_cache_size=0
    #   2. SQLAlchemy asyncpg dialect cache → prepared_statement_cache_size=0
    # Both are no-ops when connecting directly to Postgres (dev / Compose).
    prepared_statement_cache_size=0,
    connect_args={"statement_cache_size": 0},
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
