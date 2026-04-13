from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.modules.auth.router import hash_password
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        employee_id=user.employee_id,
        name=user.name,
        email=user.email,
        role=user.role,
        department=user.department,
        facility=user.facility,
        phone=user.phone,
        manager_id=str(user.manager_id) if user.manager_id else None,
        is_active=user.is_active,
    )


@router.get("", response_model=list[UserResponse])
async def list_users(
    role: str | None = None,
    facility: str | None = None,
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
):
    query = select(User).order_by(User.name)
    if role:
        query = query.where(User.role == role)
    if facility:
        query = query.where(User.facility == facility)
    if department:
        query = query.where(User.department == department)
    result = await db.execute(query)
    return [_user_to_response(u) for u in result.scalars().all()]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = User(
        employee_id=data.employee_id,
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        department=data.department,
        facility=data.facility,
        phone=data.phone,
        manager_id=UUID(data.manager_id) if data.manager_id else None,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return _user_to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)
    if "manager_id" in update_data and update_data["manager_id"]:
        update_data["manager_id"] = UUID(update_data["manager_id"])
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return _user_to_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.flush()
