from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://app:devpassword@localhost:5432/safety_response"
    READ_DATABASE_URL: str | None = None
    REDIS_URL: str = "redis://localhost:6379"
    JWT_SECRET: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    BCRYPT_ROUNDS: int = 12

    # Database connection pool — tuned per-pod so that
    # replicas x (DB_POOL_SIZE + DB_MAX_OVERFLOW) stays under Postgres max_connections.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Rate limiter settings (action: limit / window-seconds). The defaults
    # match the original hard-coded values; override via env vars during a
    # planned load test so Locust doesn't get rate-limited at its own
    # synthetic request volume:
    #   RATE_LIMIT_REPORT_LIMIT=5000 RATE_LIMIT_REPORT_WINDOW=10
    #   RATE_LIMIT_REMIND_LIMIT=1000 RATE_LIMIT_REMIND_WINDOW=60
    # Production defaults stay low to prevent abuse.
    RATE_LIMIT_REPORT_LIMIT: int = 5
    RATE_LIMIT_REPORT_WINDOW: int = 10
    RATE_LIMIT_REMIND_LIMIT: int = 3
    RATE_LIMIT_REMIND_WINDOW: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
