from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.core.auth import (
    Principal,
    create_access_token,
    get_current_principal,
    hash_password,
    verify_password,
)
from app.core.config import Settings, get_runtime_settings
from app.core.models import UserAccount
from app.db.base import new_uuid, utcnow
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

RoleLiteral = Literal["VIEWER", "WAREHOUSE", "DISPATCHER", "WEBHOOK_INGESTOR", "ADMIN"]


class UserRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: RoleLiteral = "DISPATCHER"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: str
    active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    role: str


class PrincipalResponse(BaseModel):
    username: str
    role: str
    auth_method: str
    authenticated: bool
    auth_enabled: bool


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegisterRequest,
    request: Request,
    settings: Settings = Depends(get_runtime_settings),
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    """Register a user (bootstrapping first account, ADMIN, or dev auth_enabled=False)."""
    user_count = int((await session.execute(select(func.count(UserAccount.id)))).scalar_one() or 0)
    actor = "bootstrap"

    if user_count > 0 and settings.auth_enabled:
        principal = await get_current_principal(request, settings)
        if principal.role.upper() != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only ADMIN users can register additional accounts.",
            )
        actor = principal.username

    clean_username = payload.username.strip().lower()
    existing = await session.execute(
        select(UserAccount).where(UserAccount.username == clean_username)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{clean_username}' already exists.",
        )

    user = UserAccount(
        id=new_uuid(),
        username=clean_username,
        role=payload.role,
        password_hash=hash_password(payload.password),
        active=True,
        created_at=utcnow(),
    )
    session.add(user)
    await session.flush()

    await record_audit_event(
        session,
        entity_type="user",
        entity_id=user.id,
        action="USER_REGISTERED",
        actor=actor,
        previous_state=None,
        new_state=user.role,
        details={"username": user.username, "role": user.role},
    )
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login_user(
    payload: LoginRequest,
    settings: Settings = Depends(get_runtime_settings),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate credentials and issue an HS256 JWT access token."""
    clean_username = payload.username.strip().lower()
    result = await session.execute(
        select(UserAccount).where(UserAccount.username == clean_username)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token(
        subject=user.username,
        role=user.role,
        secret=settings.auth_secret_key,
        ttl_minutes=settings.auth_token_ttl_minutes,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.auth_token_ttl_minutes * 60,
        username=user.username,
        role=user.role,
    )


@router.get("/me", response_model=PrincipalResponse)
async def get_me(
    principal: Principal = Depends(get_current_principal),
    settings: Settings = Depends(get_runtime_settings),
) -> PrincipalResponse:
    """Return the active authenticated or development caller identity."""
    return PrincipalResponse(
        username=principal.username,
        role=principal.role,
        auth_method=principal.auth_method,
        authenticated=principal.authenticated,
        auth_enabled=settings.auth_enabled,
    )
