from datetime import datetime

from pydantic import BaseModel


class EventCreate(BaseModel):
    title: str
    description: str | None = None
    event_type: str
    severity: str
    facility: str | None = None


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    status: str | None = None


class EventResponse(BaseModel):
    id: str
    title: str
    description: str | None
    event_type: str
    severity: str
    status: str
    facility: str | None
    created_by: str
    created_at: datetime
    closed_at: datetime | None

    class Config:
        from_attributes = True
