import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import STAFF_ROLES, User, UserRole

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


def require_role(*roles):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        # super_admin has access to everything
        if current_user.role == UserRole.super_admin:
            return current_user
        # Check if role matches (support both string and enum)
        allowed = {r.value if isinstance(r, UserRole) else r for r in roles}
        if current_user.role.value not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return role_checker


def require_permission(*perms: str):
    """Check module-level permissions. Admins bypass; staff must have the permission."""
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        # super_admin and admin have all permissions
        if current_user.role in (UserRole.super_admin, UserRole.admin):
            return current_user
        # Staff roles: check permissions list
        user_perms = current_user.permissions or []
        if not any(p in user_perms for p in perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource",
            )
        return current_user
    return checker
