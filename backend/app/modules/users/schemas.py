from pydantic import BaseModel


class UserCreate(BaseModel):
    employee_id: str
    name: str
    email: str
    password: str
    role: str
    department: str | None = None
    facility: str | None = None
    phone: str | None = None
    manager_id: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None
    department: str | None = None
    facility: str | None = None
    phone: str | None = None
    manager_id: str | None = None
    is_active: bool | None = None


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
