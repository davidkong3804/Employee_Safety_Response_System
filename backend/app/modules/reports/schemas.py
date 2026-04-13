from datetime import datetime

from pydantic import BaseModel


class ReportSubmit(BaseModel):
    status: str  # "safe" or "need_help"
    message: str | None = None


class ReportResponse(BaseModel):
    id: str
    event_id: str
    user_id: str
    user_name: str
    employee_id: str
    department: str | None
    facility: str | None
    phone: str | None
    status: str | None
    message: str | None
    reported_at: datetime | None

    class Config:
        from_attributes = True


class EventStats(BaseModel):
    total: int
    safe: int
    need_help: int
    unreported: int
    report_rate: float


class DepartmentStats(BaseModel):
    department: str
    total: int
    safe: int
    need_help: int
    unreported: int
