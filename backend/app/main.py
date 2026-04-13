from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.modules.auth.router import router as auth_router
from app.modules.events.router import router as events_router
from app.modules.notifications.router import router as notifications_router
from app.modules.reports.router import router as reports_router
from app.modules.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed demo data
    from app.seed import seed_data
    await seed_data()

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
    return {"status": "healthy"}
