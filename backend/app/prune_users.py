"""One-shot pruner: delete auto-generated load-test employees that fall
outside the current LOAD_TEST_MAX_EMPLOYEES cap.

Why this exists
---------------
`seed.py` is intentionally additive — it never deletes rows. After lowering
`LOAD_TEST_MAX_EMPLOYEES` (e.g. 15000 → 500 for a demo), the surplus
accounts and all their child rows (safety_reports, reminders) keep sitting
in the DB. This script removes them so the cluster's user count matches
the seed config.

What it deletes
---------------
Users where ALL of these hold:
  - role = 'employee'
  - employee_id matches '^E\\d+$'  (skip A001 / M001 / non-standard IDs)
  - numeric suffix > LOAD_TEST_MAX_EMPLOYEES

Hand-crafted demo accounts (A001–A003, M001–M005, E001–E030) are never
touched because either their role is not 'employee' or their suffix is
within the cap.

What it does NOT delete
-----------------------
  - Any admin or manager
  - Events
  - Reports / reminders belonging to users that survive the prune

Order matters: FKs on safety_reports.user_id and reminders.user_id are
plain references (no ON DELETE CASCADE), so we delete child rows first.

Usage
-----
    python -m app.prune_users           # dry-run: prints what would be deleted
    python -m app.prune_users --apply   # actually delete
"""

import asyncio
import re
import sys

from sqlalchemy import delete, select

from app.database import async_session, engine
from app.modules.notifications.models import Reminder
from app.modules.reports.models import SafetyReport
from app.modules.users.models import User
from app.seed import LOAD_TEST_MAX_EMPLOYEES

_EMP_ID_RE = re.compile(r"^E(\d+)$")


async def find_surplus_user_ids(session) -> list:
    """Return UUIDs of employees whose numeric suffix > cap."""
    rows = (await session.execute(select(User.id, User.employee_id).where(User.role == "employee"))).all()
    surplus = []
    for uid, eid in rows:
        m = _EMP_ID_RE.match(eid or "")
        if not m:
            continue
        if int(m.group(1)) > LOAD_TEST_MAX_EMPLOYEES:
            surplus.append(uid)
    return surplus


async def prune(apply: bool) -> None:
    async with async_session() as session:
        surplus_ids = await find_surplus_user_ids(session)
        if not surplus_ids:
            print(f"✅ Nothing to prune — no employees exceed E{LOAD_TEST_MAX_EMPLOYEES:04d}.")
            return

        print(f"Found {len(surplus_ids)} employee accounts beyond E{LOAD_TEST_MAX_EMPLOYEES:04d}.")

        if not apply:
            print("Dry-run only — pass --apply to actually delete.")
            print("Run with --apply to remove these users plus their safety_reports and reminders.")
            return

        # Order: children first (no ON DELETE CASCADE on the FKs).
        rem = await session.execute(delete(Reminder).where(Reminder.user_id.in_(surplus_ids)))
        rep = await session.execute(delete(SafetyReport).where(SafetyReport.user_id.in_(surplus_ids)))
        usr = await session.execute(delete(User).where(User.id.in_(surplus_ids)))
        await session.commit()

        print(f"✅ Pruned: {usr.rowcount} users, " f"{rep.rowcount} safety_reports, " f"{rem.rowcount} reminders.")


async def main(apply: bool) -> None:
    try:
        await prune(apply=apply)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    apply_flag = "--apply" in sys.argv[1:]
    asyncio.run(main(apply=apply_flag))
