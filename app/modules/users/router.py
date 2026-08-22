from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep, get_current_active_user
from app.modules.users.models import User
from app.modules.users.schemas import UserRead, UserUpdate

router = APIRouter()


@router.patch("/me", response_model=UserRead)
async def update_me(
    user_in: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep,
):
    if user_in.email and user_in.email != current_user.email:
        stmt = select(User).where(User.email == user_in.email)
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

    if user_in.username and user_in.username != current_user.username:
        stmt = select(User).where(User.username == user_in.username)
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already taken")

    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user
