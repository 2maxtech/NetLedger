import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.tenant import get_tenant_id
from app.models.plan import Plan
from app.models.user import User
from app.schemas.plan import PlanCreate, PlanResponse, PlanUpdate
from app.models.router import Router
from app.services.mikrotik import get_mikrotik_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/", response_model=list[PlanResponse])
async def list_plans(
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    query = select(Plan).where(Plan.owner_id == tid)
    if active_only:
        query = query.where(Plan.is_active == True)
    query = query.order_by(Plan.monthly_price)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    plan = Plan(**body.model_dump())
    plan.owner_id = uuid.UUID(tenant_id)
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Plan).where(Plan.id == plan_id, Plan.owner_id == tid))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    body: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Plan).where(Plan.id == plan_id, Plan.owner_id == tid))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    old_download = plan.download_mbps
    old_upload = plan.upload_mbps

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    await db.flush()
    await db.refresh(plan)

    # Sync to MikroTik if speeds changed — iterate tenant's routers
    if plan.download_mbps != old_download or plan.upload_mbps != old_upload:
        old_profile = f"{old_download}M-{old_upload}M"
        new_profile = f"{plan.download_mbps}M-{plan.upload_mbps}M"
        new_rate = f"{plan.upload_mbps}M/{plan.download_mbps}M"

        routers_result = await db.execute(
            select(Router).where(Router.owner_id == tid, Router.is_active == True)
        )
        tenant_routers = routers_result.scalars().all()

        for r in tenant_routers:
            try:
                client = get_mikrotik_client(
                    router_id=str(r.id), url=r.url,
                    user=r.username, password=r.password,
                )
                await client.ensure_profile(new_profile, new_rate)

                secrets = await client.get_secrets()
                for s in secrets:
                    if s.get("profile") == old_profile:
                        await client.update_secret(s[".id"], {"profile": new_profile})
                logger.info(f"Plan '{plan.name}' synced on router {r.name}: {old_profile} → {new_profile}")
            except Exception as e:
                logger.warning(f"MikroTik profile sync failed on router {r.name} for plan {plan.id}: {e}")

    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Plan).where(Plan.id == plan_id, Plan.owner_id == tid))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.is_active = False
    await db.flush()
