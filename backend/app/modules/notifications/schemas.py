from datetime import datetime

from pydantic import BaseModel


class ReminderResponse(BaseModel):
    id: str
    event_id: str
    user_id: str
    user_name: str
    employee_id: str
    reminder_count: int
    last_reminded: datetime | None

    class Config:
        from_attributes = True


class ReminderTriggerResponse(BaseModel):
    reminded_count: int
    message: str


class MyReminderItem(BaseModel):
    event_id: str
    event_title: str
    severity: str
    reminder_count: int
    last_reminded: datetime | None
