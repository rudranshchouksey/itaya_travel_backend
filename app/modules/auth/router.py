from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import SessionDep, TokenDep, get_current_active_user
from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.modules.auth.models import RevokedToken
from app.modules.auth.schemas import LogoutPayload, RefreshPayload, Token, TokenPayload
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserRead

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, session: SessionDep):
    # Check if user exists by email
    stmt = select(User).where(User.email == user_in.email)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    # Check if user exists by username
    stmt = select(User).where(User.username == user_in.username)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )

    user = User(
        email=user_in.email,
        username=user_in.username,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        profile_image_url=user_in.profile_image_url,
        password_hash=get_password_hash(user_in.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
):
    # form_data.username will contain the email
    stmt = select(User).where(User.email == form_data.username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(payload: RefreshPayload, session: SessionDep):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        decoded = jwt.decode(
            payload.refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        token_data = TokenPayload(**decoded)
        if token_data.type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
    except jwt.PyJWTError:
        raise credentials_exception

    # Check if refresh token is revoked
    stmt_revoked = select(RevokedToken).where(
        RevokedToken.token == payload.refresh_token
    )
    result_revoked = await session.execute(stmt_revoked)
    if result_revoked.scalar_one_or_none():
        raise credentials_exception

    user_id = token_data.sub
    if not user_id:
        raise credentials_exception

    # Generate new tokens
    access_token = create_access_token(user_id)
    refresh_token_new = create_refresh_token(user_id)

    # Optional: revoke old refresh token for refresh token rotation
    if token_data.exp:
        revoked = RevokedToken(
            token=payload.refresh_token,
            expires_at=datetime.fromtimestamp(token_data.exp, tz=UTC),
        )
        session.add(revoked)
        await session.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_new,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    access_token: TokenDep,
    payload: LogoutPayload,
    session: SessionDep,
):
    # We revoke both the access token and the provided refresh token
    try:
        decoded_access = jwt.decode(
            access_token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        exp_access = decoded_access.get("exp")
        if exp_access:
            revoked_access = RevokedToken(
                token=access_token,
                expires_at=datetime.fromtimestamp(exp_access, tz=UTC),
            )
            session.add(revoked_access)
    except jwt.PyJWTError:
        pass

    try:
        decoded_refresh = jwt.decode(
            payload.refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        exp_refresh = decoded_refresh.get("exp")
        if exp_refresh:
            revoked_refresh = RevokedToken(
                token=payload.refresh_token,
                expires_at=datetime.fromtimestamp(exp_refresh, tz=UTC),
            )
            session.add(revoked_refresh)
    except jwt.PyJWTError:
        pass

    await session.commit()
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserRead)
async def get_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user
