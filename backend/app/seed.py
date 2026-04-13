import random
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import select

from app.database import async_session
from app.modules.events.models import Event
from app.modules.reports.models import SafetyReport
from app.modules.users.models import User

DEFAULT_PASSWORD = bcrypt.hashpw("password123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed_data():
    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            return

        # --- Create Managers ---
        managers = []
        manager_data = [
            ("M001", "王建明", "wang.jm@tsmc.com", "manager", "製造一部", "Fab14", "0912-111-001"),
            ("M002", "李淑芬", "lee.sf@tsmc.com", "manager", "製造二部", "Fab14", "0912-111-002"),
            ("M003", "陳志偉", "chen.zw@tsmc.com", "manager", "製造一部", "Fab18", "0912-111-003"),
            ("M004", "張美玲", "chang.ml@tsmc.com", "manager", "設備部", "Fab14", "0912-111-004"),
            ("M005", "劉大偉", "liu.dw@tsmc.com", "manager", "品質部", "Fab18", "0912-111-005"),
        ]
        for eid, name, email, role, dept, facility, phone in manager_data:
            m = User(
                employee_id=eid, name=name, email=email,
                password_hash=DEFAULT_PASSWORD, role=role,
                department=dept, facility=facility, phone=phone,
            )
            session.add(m)
            managers.append(m)
        await session.flush()

        # --- Create Admins ---
        admins = []
        admin_data = [
            ("A001", "廖唯辰", "liao.wc@tsmc.com", "admin", "資訊部", "Fab14", "0912-222-001"),
            ("A002", "黃正宏", "huang.zh@tsmc.com", "admin", "資訊部", "Fab18", "0912-222-002"),
            ("A003", "林雅婷", "lin.yt@tsmc.com", "admin", "資訊部", "Fab14", "0912-222-003"),
        ]
        for eid, name, email, role, dept, facility, phone in admin_data:
            a = User(
                employee_id=eid, name=name, email=email,
                password_hash=DEFAULT_PASSWORD, role=role,
                department=dept, facility=facility, phone=phone,
            )
            session.add(a)
            admins.append(a)
        await session.flush()

        # --- Create Employees ---
        employees = []
        employee_data = [
            ("E001", "蔡明軒", "tsai.mx@tsmc.com", "製造一部", "Fab14", "0912-333-001", 0),
            ("E002", "吳佳蓉", "wu.jr@tsmc.com", "製造一部", "Fab14", "0912-333-002", 0),
            ("E003", "許志豪", "hsu.zh@tsmc.com", "製造一部", "Fab14", "0912-333-003", 0),
            ("E004", "鄭雅文", "cheng.yw@tsmc.com", "製造一部", "Fab14", "0912-333-004", 0),
            ("E005", "周俊傑", "chou.jj@tsmc.com", "製造一部", "Fab14", "0912-333-005", 0),
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
            e = User(
                employee_id=eid, name=name, email=email,
                password_hash=DEFAULT_PASSWORD, role="employee",
                department=dept, facility=facility, phone=phone,
                manager_id=managers[mgr_idx].id,
            )
            session.add(e)
            employees.append(e)
        await session.flush()

        all_users = admins + managers + employees

        # --- Create Events ---
        # Event 1: Active earthquake event
        event1 = Event(
            title="2026-04-13 台南地震警報",
            description="台南地區發生規模5.2地震，請全體員工立即回報安全狀態。",
            event_type="earthquake",
            severity="high",
            status="active",
            created_by=admins[0].id,
        )
        session.add(event1)

        # Event 2: Closed fire drill
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

        # --- Create Safety Reports ---
        # Event 1 (active): partial reporting - some safe, some need help, many unreported
        random.seed(42)
        for user in all_users:
            report = SafetyReport(event_id=event1.id, user_id=user.id)
            # ~40% reported safe, ~5% need help, ~55% unreported
            roll = random.random()
            if roll < 0.40:
                report.status = "safe"
                report.reported_at = datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 30))
            elif roll < 0.45:
                report.status = "need_help"
                report.message = random.choice([
                    "被困在無塵室，需要協助撤離",
                    "腳部受傷，需要醫療支援",
                    "設備傾倒擋住出口，需要救援",
                ])
                report.reported_at = datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 20))
            session.add(report)

        # Event 2 (closed): almost everyone reported
        for user in all_users:
            report = SafetyReport(event_id=event2.id, user_id=user.id)
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
        print("✅ Demo data seeded successfully!")
        print("   Login accounts (password: password123):")
        print("   Admin:    A001 (廖唯辰)")
        print("   Manager:  M001 (王建明)")
        print("   Employee: E001 (蔡明軒)")
