"""One-shot database initializer.

Creates all tables and (optionally) loads demo data. This is intentionally
NOT run on application startup: with multiple backend replicas, doing it per
pod races on DDL and seeding. Run it exactly once — as the Kubernetes init
job, a Docker Compose init service, or locally:

    python -m app.init_db            # create tables only
    python -m app.init_db --seed     # create tables + load demo data

Seeding is idempotent: it is skipped if any user already exists. Setting the
SEED_DEMO_DATA env var to a truthy value is equivalent to passing --seed.
"""
import asyncio
import os
import sys

from app.database import Base, engine

# Importing the models registers them on Base.metadata so create_all sees them.
from app.modules.events.models import Event  # noqa: F401
from app.modules.notifications.models import Reminder  # noqa: F401
from app.modules.reports.models import SafetyReport  # noqa: F401
from app.modules.users.models import User  # noqa: F401


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created (existing tables left untouched).")


async def run(seed: bool) -> None:
    await create_tables()
    if seed:
        from app.seed import seed_data
        await seed_data()
    await engine.dispose()


def _seed_requested() -> bool:
    if "--seed" in sys.argv[1:]:
        return True
    return os.environ.get("SEED_DEMO_DATA", "").lower() in {"1", "true", "yes"}


if __name__ == "__main__":
    asyncio.run(run(seed=_seed_requested()))
