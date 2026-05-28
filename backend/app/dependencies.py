import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import cache_get_json, cache_set_json
from app.config import settings
from app.database import get_db
from app.modules.users.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

USER_PROFILE_TTL = 600


async def _get_user_by_id(user_id: str, db: AsyncSession) -> User | None:
    cache_key = f"user:profile:{user_id}"
    cached_user = await cache_get_json(cache_key)
    if cached_user is not None:
        if "id" in cached_user and isinstance(cached_user["id"], str):
            cached_user["id"] = uuid.UUID(cached_user["id"])
        if (
            "manager_id" in cached_user
            and cached_user["manager_id"] is not None
            and isinstance(cached_user["manager_id"], str)
        ):
            cached_user["manager_id"] = uuid.UUID(cached_user["manager_id"])
        return User(**cached_user, password_hash="")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is not None:
        user_dict = {
            "id": str(user.id),
            "employee_id": user.employee_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "department": user.department,
            "facility": user.facility,
            "phone": user.phone,
            "manager_id": str(user.manager_id) if user.manager_id else None,
            "is_active": user.is_active,
        }
        await cache_set_json(cache_key, user_dict, ttl_seconds=USER_PROFILE_TTL)
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await _get_user_by_id(user_id, db)
    if user is None:
        raise credentials_exception
    return user


async def get_optional_user(
    token: str | None = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if token is None:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    return await _get_user_by_id(user_id, db)


def require_role(*roles: str):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker
