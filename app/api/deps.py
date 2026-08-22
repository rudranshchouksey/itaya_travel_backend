import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import ALGORITHM
from app.modules.auth.models import RevokedToken
from app.modules.auth.schemas import TokenPayload
from app.modules.users.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

TokenDep = Annotated[str, Depends(oauth2_scheme)]
SessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(session: SessionDep, token: TokenDep) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
        if token_data.type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
    except (jwt.PyJWTError, ValidationError):
        raise credentials_exception

    stmt_revoked = select(RevokedToken).where(RevokedToken.token == token)
    result_revoked = await session.execute(stmt_revoked)
    if result_revoked.scalar_one_or_none():
        raise credentials_exception

    user_id = token_data.sub
    if not user_id:
        raise credentials_exception

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise credentials_exception

    from sqlalchemy.orm import selectinload

    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_uuid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
