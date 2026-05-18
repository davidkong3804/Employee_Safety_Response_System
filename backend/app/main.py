from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.modules.auth.router import router as auth_router
from app.modules.events.router import router as events_router
from app.modules.notifications.router import router as notifications_router
from app.modules.reports.router import router as reports_router
from app.modules.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema creation and demo seeding are NOT done here — running them on
    # every pod startup races across replicas. They run once via the
    # init job / `python -m app.init_db` (see docs/deployment.md).
    yield

    await engine.dispose()


app = FastAPI(
    title="Employee Safety & Response System",
    description="企業營運緊急事件安全回報系統",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(reports_router)
app.include_router(users_router)
app.include_router(notifications_router)


@app.get("/health")
async def health_check():
    """Liveness probe — process is up. Must stay cheap and dependency-free."""
    return {"status": "healthy"}


@app.get("/health/ready")
async def readiness_check(response: Response):
    """Readiness probe — only report ready when the database is reachable,
    so Kubernetes keeps traffic off a pod that cannot serve requests."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not ready", "reason": "database unreachable"}
