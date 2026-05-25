from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _disable_prepared_stmt_cache(url: str) -> str:
    """Append SQLAlchemy asyncpg dialect param prepared_statement_cache_size=0
    via URL query string — it is a dialect __init__ kwarg, not a create_engine
    kwarg, so it has to ride along on the URL when we use create_async_engine.
    """
    if "+asyncpg" not in url or "prepared_statement_cache_size" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}prepared_statement_cache_size=0"


engine = create_async_engine(
    _disable_prepared_stmt_cache(settings.DATABASE_URL),
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
    #   1. asyncpg driver-side LRU cache  → statement_cache_size=0 (connect_args)
    #   2. SQLAlchemy asyncpg dialect cache → prepared_statement_cache_size=0
    #      (dialect __init__ kwarg; passed via URL query string above)
    # Both are no-ops when connecting directly to Postgres (dev / Compose).
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
