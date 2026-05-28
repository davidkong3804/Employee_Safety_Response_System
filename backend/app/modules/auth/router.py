import asyncio
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserProfile
from app.modules.users.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Run bcrypt verification in the default thread pool so the asyncio
    event loop stays responsive. bcrypt.checkpw is deliberately CPU-heavy
    (~100-300ms per call); a synchronous call inside an async route
    serialises every other request on the same worker behind it, which is
    why high-concurrency login tests bottlenecked to ~4 req/s per pod.
    Offloading via asyncio.to_thread lets the worker handle other I/O
    while bcrypt runs on a thread."""
    return await asyncio.to_thread(
        bcrypt.checkpw,
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def hash_password(password: str) -> str:
    """Synchronous on purpose — only called during user creation / seeding,
    not on the login hot path, so event-loop blocking is acceptable."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(settings.BCRYPT_ROUNDS)).decode("utf-8")


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode = {"sub": user_id, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.employee_id == data.employee_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not await verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect employee ID or password",
        )
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserProfile(
        id=str(current_user.id),
        employee_id=current_user.employee_id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        department=current_user.department,
        facility=current_user.facility,
        phone=current_user.phone,
    )
