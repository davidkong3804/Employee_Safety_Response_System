from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://app:devpassword@localhost:5432/safety_response"
    READ_DATABASE_URL: str | None = None
    REDIS_URL: str = "redis://localhost:6379"
    JWT_SECRET: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Database connection pool — tuned per-pod so that
    # replicas x (DB_POOL_SIZE + DB_MAX_OVERFLOW) stays under Postgres max_connections.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    class Config:
        env_file = ".env"


settings = Settings()
