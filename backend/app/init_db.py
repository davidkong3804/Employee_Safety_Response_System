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

from sqlalchemy import text

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


async def apply_pending_migrations() -> None:
    """Ad-hoc, idempotent schema migrations for clusters whose
    safety_reports table predates the org-snapshot columns.

    Why this exists (and why it isn't Alembic yet)
    ----------------------------------------------
    `create_all` only creates *new* tables — it never ALTERs existing
    ones. So adding `manager_id_snapshot` / `department_snapshot` /
    `facility_snapshot` to an existing safety_reports table requires a
    real migration step. Until Alembic is wired up (C5 in
    improvements.md), this function plays that role.

    Every statement is idempotent (ADD COLUMN IF NOT EXISTS / UPDATE
    only where snapshot still NULL), so the Job can run on a fresh
    cluster (no-op) or an existing cluster (adds + backfills).
    """
    async with engine.begin() as conn:
        # 1. Add the snapshot columns if missing
        await conn.execute(text("""
            ALTER TABLE safety_reports
                ADD COLUMN IF NOT EXISTS manager_id_snapshot UUID,
                ADD COLUMN IF NOT EXISTS department_snapshot VARCHAR(100),
                ADD COLUMN IF NOT EXISTS facility_snapshot VARCHAR(50)
        """))
        # 2. Backfill historical rows from current user values. This is the
        #    best snapshot we can synthesise after the fact — going forward,
        #    new placeholders are filled at creation time so they reflect
        #    the org state when the event happened, not later.
        result = await conn.execute(text("""
            UPDATE safety_reports sr
            SET manager_id_snapshot = u.manager_id,
                department_snapshot = u.department,
                facility_snapshot   = u.facility
            FROM users u
            WHERE sr.user_id = u.id
              AND sr.manager_id_snapshot IS NULL
              AND sr.department_snapshot IS NULL
              AND sr.facility_snapshot IS NULL
        """))
        # rowcount may be -1 on some drivers; guard with `or 0`
        backfilled = result.rowcount if result.rowcount is not None else 0
    print(f"✅ Pending migrations applied (org-snapshot columns; backfilled {backfilled} rows).")


async def run(seed: bool) -> None:
    await create_tables()
    await apply_pending_migrations()
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
