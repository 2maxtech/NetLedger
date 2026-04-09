import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.tenant import get_tenant_id
from app.models.app_setting import AppSetting
from app.models.customer import Customer
from app.models.plan import Plan
from app.models.router import Router
from app.models.user import STAFF_ROLES, User, UserRole

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status")
async def onboarding_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Return onboarding checklist status for the current tenant."""
    # Staff users skip onboarding entirely
    if current_user.role in STAFF_ROLES:
        return {
            "dismissed": True,
            "completed": 5,
            "total": 5,
            "steps": [],
        }

    tid = uuid.UUID(tenant_id)

    # Check routers
    result = await db.execute(
        select(func.count()).select_from(Router).where(Router.owner_id == tid)
    )
    has_router = result.scalar_one() > 0

    # Check plans
    result = await db.execute(
        select(func.count()).select_from(Plan).where(Plan.owner_id == tid)
    )
    has_plan = result.scalar_one() > 0

    # Check customers
    result = await db.execute(
        select(func.count()).select_from(Customer).where(Customer.owner_id == tid)
    )
    has_customer = result.scalar_one() > 0

    # Check billing config
    result = await db.execute(
        select(AppSetting).where(
            AppSetting.key == "billing_default_due_day",
            AppSetting.owner_id == tid,
        )
    )
    has_billing_config = result.scalar_one_or_none() is not None

    # Check notifications (smtp_host OR sms_api_key)
    result = await db.execute(
        select(AppSetting).where(
            AppSetting.key.in_(["smtp_host", "sms_api_key"]),
            AppSetting.owner_id == tid,
        )
    )
    settings_found = {s.key: s.value for s in result.scalars().all()}
    has_notifications = bool(settings_found.get("smtp_host") or settings_found.get("sms_api_key"))

    # Check dismissed
    result = await db.execute(
        select(AppSetting).where(
            AppSetting.key == "onboarding_dismissed",
            AppSetting.owner_id == tid,
        )
    )
    dismissed_setting = result.scalar_one_or_none()
    dismissed = dismissed_setting is not None and dismissed_setting.value == "true"

    completed = sum([has_router, has_plan, has_customer, has_billing_config, has_notifications])
    total = 5

    return {
        "has_router": has_router,
        "has_plan": has_plan,
        "has_customer": has_customer,
        "has_billing_config": has_billing_config,
        "has_notifications": has_notifications,
        "dismissed": dismissed,
        "completed": completed,
        "total": total,
    }


@router.post("/dismiss")
async def dismiss_onboarding(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Mark onboarding checklist as dismissed for this tenant."""
    tid = uuid.UUID(tenant_id)

    result = await db.execute(
        select(AppSetting).where(
            AppSetting.key == "onboarding_dismissed",
            AppSetting.owner_id == tid,
        )
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = "true"
    else:
        db.add(AppSetting(key="onboarding_dismissed", value="true", owner_id=tid))
    await db.flush()

    return {"status": "dismissed"}
