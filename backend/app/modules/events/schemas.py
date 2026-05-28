from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EventCreate(BaseModel):
    title: str
    description: str | None = None
    event_type: Literal["earthquake", "fire", "flood", "security", "other"]
    severity: Literal["low", "medium", "high", "critical"]
    facility: list[str] | None = None


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    status: Literal["active", "closed"] | None = None


class EventResponse(BaseModel):
    id: str
    title: str
    description: str | None
    event_type: str
    severity: str
    status: str
    facility: list[str] | None
    created_by: str
    created_at: datetime
    closed_at: datetime | None

    class Config:
        from_attributes = True
