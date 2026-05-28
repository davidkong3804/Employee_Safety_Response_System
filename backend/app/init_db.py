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
    # --- Transaction 1: schema changes (columns + type conversion + backfill) ---
    # Keep these together so they succeed or fail atomically. Index creation is
    # in a separate transaction below so a failed index never rolls back the
    # column adds that the app depends on at runtime.
    async with engine.begin() as conn:
        # 1. Add the snapshot columns if missing
        await conn.execute(
            text("""
            ALTER TABLE safety_reports
                ADD COLUMN IF NOT EXISTS manager_id_snapshot UUID,
                ADD COLUMN IF NOT EXISTS department_snapshot VARCHAR(100),
                ADD COLUMN IF NOT EXISTS facility_snapshot VARCHAR(50)
        """)
        )

        # 2. Ensure events.facility is VARCHAR(50)[] (ARRAY), not scalar VARCHAR.
        #    Clusters created before the ARRAY change store facility as a plain
        #    string in PostgreSQL array-literal notation (e.g. '{Fab14,Fab18}').
        #    Casting via `::character varying(50)[]` re-parses the literal into
        #    a proper multi-element array; ARRAY[facility] would instead wrap it
        #    in a single-element array, corrupting the data.
        await conn.execute(
            text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name  = 'events'
                      AND column_name = 'facility'
                      AND data_type   = 'character varying'
                ) THEN
                    ALTER TABLE events
                        ALTER COLUMN facility TYPE character varying(50)[]
                        USING CASE WHEN facility IS NULL THEN NULL
                                   ELSE facility::character varying(50)[]
                              END;
                END IF;
            END $$
        """)
        )

        # 2b. Repair rows that were already migrated with the incorrect ARRAY[facility]
        #     wrapping (produces a 1-element array whose only element is an array-literal
        #     string like '{Fab14,Fab18}'). Re-parse those by casting the inner string.
        await conn.execute(
            text("""
            UPDATE events
            SET    facility = (facility[1])::character varying(50)[]
            WHERE  facility IS NOT NULL
              AND  array_length(facility, 1) = 1
              AND  facility[1] LIKE '{%}'
        """)
        )

        # 3. Backfill historical rows from current user values.
        result = await conn.execute(
            text("""
            UPDATE safety_reports sr
            SET manager_id_snapshot = u.manager_id,
                department_snapshot = u.department,
                facility_snapshot   = u.facility
            FROM users u
            WHERE sr.user_id = u.id
              AND sr.manager_id_snapshot IS NULL
              AND sr.department_snapshot IS NULL
              AND sr.facility_snapshot IS NULL
        """)
        )
        backfilled = result.rowcount if result.rowcount is not None else 0

    # --- Transaction 2: performance indexes (each isolated so one failure ---
    # doesn't roll back the others or the schema changes above).
    _indexes = [
        # event list ORDER BY (status ASC, created_at DESC)
        (
            "idx_events_status_created",
            """
            CREATE INDEX IF NOT EXISTS idx_events_status_created
                ON events (status ASC, created_at DESC)
        """,
        ),
        # ARRAY containment operator (@>) for facility scoping; requires GIN.
        (
            "idx_events_facility_gin",
            """
            CREATE INDEX IF NOT EXISTS idx_events_facility_gin
                ON events USING GIN (facility)
        """,
        ),
        # stats GROUP BY (event_id, status)
        (
            "idx_safety_reports_event_status",
            """
            CREATE INDEX IF NOT EXISTS idx_safety_reports_event_status
                ON safety_reports (event_id, status)
        """,
        ),
        # submit_report / my-report look up by (event_id, user_id) — hot path.
        # Also acts as a de-facto uniqueness enforcer (one row per user per event).
        (
            "idx_safety_reports_event_user",
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_safety_reports_event_user
                ON safety_reports (event_id, user_id)
        """,
        ),
    ]
    for name, sql in _indexes:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
        except Exception as exc:
            print(f"⚠️  Could not create index {name}: {exc}")

    print(f"✅ Pending migrations applied (org-snapshot columns; backfilled {backfilled} rows; indexes ensured).")


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
