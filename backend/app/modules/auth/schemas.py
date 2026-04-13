from pydantic import BaseModel


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: str
    employee_id: str
    name: str
    email: str
    role: str
    department: str | None
    facility: str | None
    phone: str | None

    class Config:
        from_attributes = True
