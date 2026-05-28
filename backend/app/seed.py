import random
import uuid as _uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import insert as sa_insert
from sqlalchemy import select

from app.database import async_session
from app.modules.events.models import Event
from app.modules.reports.models import SafetyReport
from app.modules.users.models import User

DEFAULT_PASSWORD = bcrypt.hashpw("password123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# Capacity planning: load tests run up to LOAD_TEST_MAX_EMPLOYEES concurrent
# virtual users. The first 30 employees (E001–E030) are hand-crafted demo
# data; the rest are auto-generated test accounts (E0031–E{N}). Bump this
# number if stress tests need more capacity — both seed.py and locustfile.py
# should stay in sync.
LOAD_TEST_MAX_EMPLOYEES = 15000


async def seed_data():
    """Idempotent demo seed.

    Old behaviour ("if any user exists, return") meant that any later
    expansion of the seed (e.g. adding the E0031–E1000 load-test cohort)
    could never apply to an already-seeded cluster — re-running the
    db-init Job was a no-op.

    New behaviour:
      1. Look up which employee_ids already exist in the DB.
      2. In every user-creation loop, skip the entries that exist and
         insert the rest.
      3. The events + safety_reports block runs only when no Event row
         exists — so demo events are not duplicated. Filling in the
         placeholder reports for *newly added* users is left to admins
         (create a new event via the API and every active user gets one
         placeholder automatically).
    """
    async with async_session() as session:
        # ---- existing-data snapshot -------------------------------------
        existing_emp_ids = {row[0] for row in (await session.execute(select(User.employee_id))).all()}
        events_already_exist = (await session.execute(select(Event).limit(1))).scalar_one_or_none() is not None

        added_user_count = 0

        # ---- managers ---------------------------------------------------
        manager_data = [
            ("M001", "王建明", "wang.jm@tsmc.com", "manager", "製造一部", "Fab14", "0912-111-001"),
            ("M002", "李淑芬", "lee.sf@tsmc.com", "manager", "製造二部", "Fab14", "0912-111-002"),
            ("M003", "陳志偉", "chen.zw@tsmc.com", "manager", "製造一部", "Fab18", "0912-111-003"),
            ("M004", "張美玲", "chang.ml@tsmc.com", "manager", "設備部", "Fab14", "0912-111-004"),
            ("M005", "劉大偉", "liu.dw@tsmc.com", "manager", "品質部", "Fab18", "0912-111-005"),
        ]
        for eid, name, email, role, dept, facility, phone in manager_data:
            if eid in existing_emp_ids:
                continue
            session.add(
                User(
                    employee_id=eid,
                    name=name,
                    email=email,
                    password_hash=DEFAULT_PASSWORD,
                    role=role,
                    department=dept,
                    facility=facility,
                    phone=phone,
                )
            )
            added_user_count += 1
        await session.flush()

        # Refresh: managers list contains both pre-existing and just-created rows,
        # ordered by employee_id so mgr_idx 0..4 maps to M001..M005 deterministically.
        managers = list(
            (await session.execute(select(User).where(User.role == "manager").order_by(User.employee_id)))
            .scalars()
            .all()
        )

        # ---- admins -----------------------------------------------------
        admin_data = [
            ("A001", "廖唯辰", "liao.wc@tsmc.com", "admin", "資訊部", "Fab14", "0912-222-001"),
            ("A002", "黃正宏", "huang.zh@tsmc.com", "admin", "資訊部", "Fab18", "0912-222-002"),
            ("A003", "林雅婷", "lin.yt@tsmc.com", "admin", "資訊部", "Fab14", "0912-222-003"),
        ]
        for eid, name, email, role, dept, facility, phone in admin_data:
            if eid in existing_emp_ids:
                continue
            session.add(
                User(
                    employee_id=eid,
                    name=name,
                    email=email,
                    password_hash=DEFAULT_PASSWORD,
                    role=role,
                    department=dept,
                    facility=facility,
                    phone=phone,
                )
            )
            added_user_count += 1
        await session.flush()

        admins = list(
            (await session.execute(select(User).where(User.role == "admin").order_by(User.employee_id))).scalars().all()
        )

        # ---- employees E001–E030 (named) -------------------------------
        employee_data = [
            ("E001", "蔡明軒", "tsai.mx@tsmc.com", "製造一部", "Fab14", "0912-333-001", 0),
            ("E002", "吳佳蓉", "wu.jr@tsmc.com", "製造一部", "Fab14", "0912-333-002", 0),
            ("E003", "劉浩倫", "hsu.zh@tsmc.com", "製造一部", "Fab14", "0912-333-003", 0),
            ("E004", "曹斯涵", "cheng.yw@tsmc.com", "製造一部", "Fab14", "0912-333-004", 0),
            ("E005", "周恩傑", "chou.jj@tsmc.com", "製造一部", "Fab14", "0912-333-005", 0),
            ("E006", "楊淑惠", "yang.sh@tsmc.com", "製造二部", "Fab14", "0912-333-006", 1),
            ("E007", "趙建宏", "chao.jh@tsmc.com", "製造二部", "Fab14", "0912-333-007", 1),
            ("E008", "孫雅琪", "sun.yc@tsmc.com", "製造二部", "Fab14", "0912-333-008", 1),
            ("E009", "何明達", "ho.md@tsmc.com", "製造二部", "Fab14", "0912-333-009", 1),
            ("E010", "林志玲", "lin.zl@tsmc.com", "製造二部", "Fab14", "0912-333-010", 1),
            ("E011", "黃建華", "huang.jh@tsmc.com", "製造一部", "Fab18", "0912-333-011", 2),
            ("E012", "王美珍", "wang.mz@tsmc.com", "製造一部", "Fab18", "0912-333-012", 2),
            ("E013", "李宗翰", "lee.zh@tsmc.com", "製造一部", "Fab18", "0912-333-013", 2),
            ("E014", "張雅芳", "chang.yf@tsmc.com", "製造一部", "Fab18", "0912-333-014", 2),
            ("E015", "劉家豪", "liu.jh@tsmc.com", "製造一部", "Fab18", "0912-333-015", 2),
            ("E016", "陳怡君", "chen.yj@tsmc.com", "設備部", "Fab14", "0912-333-016", 3),
            ("E017", "吳宗憲", "wu.zx@tsmc.com", "設備部", "Fab14", "0912-333-017", 3),
            ("E018", "許雅玲", "hsu.yl@tsmc.com", "設備部", "Fab14", "0912-333-018", 3),
            ("E019", "鄭明哲", "cheng.mz@tsmc.com", "設備部", "Fab14", "0912-333-019", 3),
            ("E020", "周雅慧", "chou.yh@tsmc.com", "設備部", "Fab14", "0912-333-020", 3),
            ("E021", "楊建志", "yang.jz@tsmc.com", "品質部", "Fab18", "0912-333-021", 4),
            ("E022", "趙淑芬", "chao.sf@tsmc.com", "品質部", "Fab18", "0912-333-022", 4),
            ("E023", "孫明輝", "sun.mh@tsmc.com", "品質部", "Fab18", "0912-333-023", 4),
            ("E024", "何雅琳", "ho.yl@tsmc.com", "品質部", "Fab18", "0912-333-024", 4),
            ("E025", "林建成", "lin.jc@tsmc.com", "品質部", "Fab18", "0912-333-025", 4),
            ("E026", "黃美華", "huang.mh2@tsmc.com", "製造一部", "Fab14", "0912-333-026", 0),
            ("E027", "王志明", "wang.zm@tsmc.com", "製造二部", "Fab14", "0912-333-027", 1),
            ("E028", "李雅婷", "lee.yt2@tsmc.com", "製造一部", "Fab18", "0912-333-028", 2),
            ("E029", "張家瑋", "chang.jw@tsmc.com", "設備部", "Fab14", "0912-333-029", 3),
            ("E030", "劉淑玲", "liu.sl@tsmc.com", "品質部", "Fab18", "0912-333-030", 4),
        ]
        for eid, name, email, dept, facility, phone, mgr_idx in employee_data:
            if eid in existing_emp_ids:
                continue
            session.add(
                User(
                    employee_id=eid,
                    name=name,
                    email=email,
                    password_hash=DEFAULT_PASSWORD,
                    role="employee",
                    department=dept,
                    facility=facility,
                    phone=phone,
                    manager_id=managers[mgr_idx].id,
                )
            )
            added_user_count += 1
        await session.flush()

        # ---- extra load-test employees E0031 – E{LOAD_TEST_MAX_EMPLOYEES} -
        depts = ["製造一部", "製造二部", "製造一部", "設備部", "品質部"]
        facilits = ["Fab14", "Fab14", "Fab18", "Fab14", "Fab18"]
        for i in range(31, LOAD_TEST_MAX_EMPLOYEES + 1):
            eid = f"E{i:04d}"
            if eid in existing_emp_ids:
                continue
            mgr_idx = (i - 1) % len(managers)
            phone_raw = f"09{i:08d}"
            phone = f"{phone_raw[:4]}-{phone_raw[4:7]}-{phone_raw[7:]}"
            session.add(
                User(
                    employee_id=eid,
                    name=f"測試員工{i:04d}",
                    email=f"test.emp{i:04d}@tsmc.com",
                    password_hash=DEFAULT_PASSWORD,
                    role="employee",
                    department=depts[mgr_idx],
                    facility=facilits[mgr_idx],
                    phone=phone,
                    manager_id=managers[mgr_idx].id,
                )
            )
            added_user_count += 1
        await session.flush()

        # ---- short-circuit if events already exist ---------------------
        if events_already_exist:
            # Top up placeholder reports for any active event that's missing
            # entries for the newly-added users. Without this step a load test
            # against existing events would 404 on submit_report for E0031+.
            # Mirrors the production POST /api/events logic: filter by event
            # facility (NULL = all) and only include is_active users.
            topped_up = 0
            active_events = (await session.execute(select(Event).where(Event.status == "active"))).scalars().all()

            for ev in active_events:
                # Existing user_ids already covered for this event
                existing_uids = {
                    row[0]
                    for row in (
                        await session.execute(select(SafetyReport.user_id).where(SafetyReport.event_id == ev.id))
                    ).all()
                }
                # Target users — fetch with org context so we can snapshot
                # them onto each new placeholder (C6: keeps historical
                # manager/department/facility queries stable).
                users_q = select(
                    User.id,
                    User.manager_id,
                    User.department,
                    User.facility,
                ).where(User.is_active.is_(True))
                if ev.facility:
                    users_q = users_q.where(User.facility.in_(ev.facility))
                target_rows = (await session.execute(users_q)).all()
                target_by_uid = {row[0]: row for row in target_rows}
                target_uids = set(target_by_uid.keys())

                missing = target_uids - existing_uids
                if missing:
                    # Bulk INSERT via Core (executemany) — much faster than
                    # session.add_all() + flush for the ~9k Fab14 top-up case.
                    # Explicit `id` because executemany skips Python-side
                    # column defaults (server_default still fires).
                    await session.execute(
                        sa_insert(SafetyReport),
                        [
                            {
                                "id": _uuid.uuid4(),
                                "event_id": ev.id,
                                "user_id": uid,
                                "manager_id_snapshot": target_by_uid[uid][1],
                                "department_snapshot": target_by_uid[uid][2],
                                "facility_snapshot": target_by_uid[uid][3],
                            }
                            for uid in missing
                        ],
                    )
                    topped_up += len(missing)

            await session.commit()
            print(
                f"✅ Seed: ensured users ({added_user_count} added); "
                f"topped up {topped_up} placeholder reports across "
                f"{len(active_events)} active event(s). Demo events not re-created."
            )
            return

        # ---- fresh-DB only: build demo events + placeholder reports ----
        # Need the full user list (admins + managers + all employees) to
        # generate a placeholder report per user.
        all_users = list((await session.execute(select(User))).scalars().all())

        event1 = Event(
            title="2026-04-13 台南地震警報",
            description="台南地區發生規模5.2地震，請全體員工立即回報安全狀態。",
            event_type="earthquake",
            severity="high",
            status="active",
            facility=["Fab14"],
            created_by=admins[0].id,
        )
        session.add(event1)

        event2 = Event(
            title="2026-03-20 消防演習",
            description="年度消防演習已結束，感謝各位配合。",
            event_type="fire",
            severity="medium",
            status="closed",
            created_by=admins[0].id,
            closed_at=datetime.now(timezone.utc) - timedelta(days=24),
        )
        session.add(event2)
        await session.flush()

        # Event 1 (active): partial reporting — some safe, some need help, many unreported
        random.seed(42)
        for user in all_users:
            # Snapshot org context onto every placeholder (C6).
            report = SafetyReport(
                event_id=event1.id,
                user_id=user.id,
                manager_id_snapshot=user.manager_id,
                department_snapshot=user.department,
                facility_snapshot=user.facility,
            )
            roll = random.random()
            if roll < 0.40:
                report.status = "safe"
                report.reported_at = datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 30))
            elif roll < 0.45:
                report.status = "need_help"
                report.message = random.choice(
                    [
                        "被困在無塵室，需要協助撤離",
                        "腳部受傷，需要醫療支援",
                        "設備傾倒擋住出口，需要救援",
                    ]
                )
                report.reported_at = datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 20))
            session.add(report)

        # Event 2 (closed): almost everyone reported
        for user in all_users:
            report = SafetyReport(
                event_id=event2.id,
                user_id=user.id,
                manager_id_snapshot=user.manager_id,
                department_snapshot=user.department,
                facility_snapshot=user.facility,
            )
            roll = random.random()
            if roll < 0.90:
                report.status = "safe"
                report.reported_at = datetime.now(timezone.utc) - timedelta(days=24, minutes=random.randint(1, 60))
            elif roll < 0.95:
                report.status = "need_help"
                report.message = "演習中模擬受傷情境"
                report.reported_at = datetime.now(timezone.utc) - timedelta(days=24, minutes=random.randint(1, 30))
            session.add(report)

        await session.commit()
        print(f"✅ Demo data seeded successfully! ({added_user_count} users + 2 events + placeholder reports)")
        print("   Login accounts (password: password123):")
        print("   Admin:    A001 (廖唯辰)")
        print("   Manager:  M001 (王建明)")
        print("   Employee: E001 (蔡明軒)")
