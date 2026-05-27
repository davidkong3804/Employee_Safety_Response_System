from typing import Literal
from pydantic import BaseModel, field_validator


def format_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 12 and digits.startswith("8869"):
        digits = "0" + digits[3:]
    if len(digits) == 10 and digits.startswith("09"):
        return f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
    return phone


class UserCreate(BaseModel):
    employee_id: str
    name: str
    email: str
    password: str
    role: Literal["employee", "manager", "admin"]
    department: str | None = None
    facility: str | None = None
    phone: str | None = None
    manager_id: str | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return format_phone(v)


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    role: Literal["employee", "manager", "admin"] | None = None
    department: str | None = None
    facility: str | None = None
    phone: str | None = None
    manager_id: str | None = None
    is_active: bool | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return format_phone(v)


class UserResponse(BaseModel):
    id: str
    employee_id: str
    name: str
    email: str
    role: str
    department: str | None
    facility: str | None
    phone: str | None
    manager_id: str | None
    is_active: bool

    class Config:
        from_attributes = True
