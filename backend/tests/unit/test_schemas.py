"""Unit tests for Pydantic schemas – no database required."""
import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import LoginRequest
from app.modules.events.schemas import EventCreate, EventUpdate
from app.modules.reports.schemas import ReportSubmit
from app.modules.users.schemas import UserCreate, UserUpdate


class TestLoginRequest:
    def test_valid(self):
        req = LoginRequest(employee_id="A001", password="pw")
        assert req.employee_id == "A001"

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(employee_id="A001")

    def test_missing_employee_id_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(password="pw")


class TestEventCreate:
    def test_minimal_valid(self):
        ev = EventCreate(title="Test", event_type="earthquake", severity="high")
        assert ev.description is None

    def test_with_description(self):
        ev = EventCreate(title="T", event_type="fire", severity="low", description="desc")
        assert ev.description == "desc"

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            EventCreate(event_type="earthquake", severity="high")


class TestEventUpdate:
    def test_all_fields_optional(self):
        data = EventUpdate()
        assert data.model_dump(exclude_unset=True) == {}

    def test_partial_update(self):
        data = EventUpdate(status="closed")
        assert data.model_dump(exclude_unset=True) == {"status": "closed"}


class TestReportSubmit:
    def test_safe_status(self):
        r = ReportSubmit(status="safe")
        assert r.status == "safe"
        assert r.message is None

    def test_need_help_with_message(self):
        r = ReportSubmit(status="need_help", message="Trapped")
        assert r.message == "Trapped"

    def test_missing_status_raises(self):
        with pytest.raises(ValidationError):
            ReportSubmit()


class TestUserCreate:
    def test_minimal_valid(self):
        u = UserCreate(
            employee_id="E001",
            name="Alice",
            email="alice@example.com",
            password="pw",
            role="employee",
        )
        assert u.manager_id is None
        assert u.department is None

    def test_all_fields(self):
        u = UserCreate(
            employee_id="M001",
            name="Bob",
            email="bob@example.com",
            password="pw",
            role="manager",
            department="IT",
            facility="Fab14",
            phone="0912345678",
            manager_id="some-uuid",
        )
        assert u.manager_id == "some-uuid"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            UserCreate(employee_id="E001", name="Alice")


class TestUserUpdate:
    def test_all_optional(self):
        u = UserUpdate()
        assert u.model_dump(exclude_unset=True) == {}

    def test_partial(self):
        u = UserUpdate(role="manager", is_active=False)
        dumped = u.model_dump(exclude_unset=True)
        assert dumped["role"] == "manager"
        assert dumped["is_active"] is False
