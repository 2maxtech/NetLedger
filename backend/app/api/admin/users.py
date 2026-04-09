import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.core.tenant import get_tenant_id
from app.core.security import hash_password
from app.models.user import PERMISSION_MODULES, STAFF_ROLES, User, UserRole
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/system/users", tags=["users"])


@router.get("/permissions")
async def list_permissions():
    """Return available permission modules for staff configuration."""
    return [{"key": k, "label": v} for k, v in PERMISSION_MODULES.items()]

# --- Super Admin: Organizations endpoint ---
org_router = APIRouter(prefix="/system/organizations", tags=["organizations"])


@org_router.get("/", response_model=list[UserResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.super_admin)),
):
    """List all registered ISP operators (users with role=admin)."""
    result = await db.execute(
        select(User).where(User.role == UserRole.admin).order_by(User.created_at.desc())
    )
    return result.scalars().all()


@router.get("/", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(User).where(User.owner_id == tid).order_by(User.created_at))
    return result.scalars().all()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    existing = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        permissions=body.permissions if body.role in STAFF_ROLES else [],
        owner_id=tid,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    # Super admin can update any user; regular admin only their own staff
    if current_user.role == UserRole.super_admin:
        result = await db.execute(select(User).where(User.id == user_id))
    else:
        result = await db.execute(select(User).where(User.id == user_id, User.owner_id == tid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
    tenant_id: str = Depends(get_tenant_id),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    tid = uuid.UUID(tenant_id)
    if current_user.role == UserRole.super_admin:
        result = await db.execute(select(User).where(User.id == user_id))
    else:
        result = await db.execute(select(User).where(User.id == user_id, User.owner_id == tid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Super admin deleting an org: cascade delete all tenant data
    if current_user.role == UserRole.super_admin and user.role == UserRole.admin:
        from app.models.ticket import TicketMessage, Ticket
        from app.models.payment import Payment
        from app.models.invoice import Invoice
        from app.models.voucher import Voucher
        from app.models.expense import Expense
        from app.models.audit_log import AuditLog
        from app.models.ip_pool import IPPool
        from app.models.disconnect_log import DisconnectLog
        from app.models.notification import Notification
        from app.models.app_setting import AppSetting
        from app.models.customer import Customer
        from app.models.plan import Plan
        from app.models.router import Area, Router

        uid = user.id
        await db.execute(select(TicketMessage).where(TicketMessage.owner_id == uid).execution_options(synchronize_session="fetch"))
        from sqlalchemy import delete as sa_delete
        await db.execute(sa_delete(TicketMessage).where(TicketMessage.owner_id == uid))
        await db.execute(sa_delete(Ticket).where(Ticket.owner_id == uid))
        await db.execute(sa_delete(Payment).where(Payment.owner_id == uid))
        await db.execute(sa_delete(Invoice).where(Invoice.owner_id == uid))
        await db.execute(sa_delete(Voucher).where(Voucher.owner_id == uid))
        await db.execute(sa_delete(Expense).where(Expense.owner_id == uid))
        await db.execute(sa_delete(AuditLog).where(AuditLog.owner_id == uid))
        await db.execute(sa_delete(IPPool).where(IPPool.owner_id == uid))
        await db.execute(sa_delete(DisconnectLog).where(DisconnectLog.owner_id == uid))
        await db.execute(sa_delete(Notification).where(Notification.owner_id == uid))
        await db.execute(sa_delete(AppSetting).where(AppSetting.owner_id == uid))
        await db.execute(sa_delete(Customer).where(Customer.owner_id == uid))
        await db.execute(sa_delete(Plan).where(Plan.owner_id == uid))
        await db.execute(sa_delete(Area).where(Area.owner_id == uid))
        await db.execute(sa_delete(Router).where(Router.owner_id == uid))
        await db.execute(sa_delete(User).where(User.owner_id == uid))
        await db.delete(user)
        await db.flush()
    else:
        # Regular admin deleting staff: just deactivate
        user.is_active = False
        await db.flush()
