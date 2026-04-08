import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.tenant import get_tenant_id
from app.models.customer import Customer
from app.models.router import Area
from app.models.user import User
from app.schemas.router import AreaCreate, AreaResponse, AreaUpdate

router = APIRouter(prefix="/areas", tags=["areas"])


@router.get("/", response_model=list[AreaResponse])
async def list_areas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Area).where(Area.owner_id == tid).order_by(Area.name))
    return result.scalars().all()


@router.post("/", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
async def create_area(
    body: AreaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    a = Area(**body.model_dump())
    a.owner_id = uuid.UUID(tenant_id)
    db.add(a)
    await db.flush()
    await db.refresh(a)
    return a


@router.put("/{area_id}", response_model=AreaResponse)
async def update_area(
    area_id: uuid.UUID,
    body: AreaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Area).where(Area.id == area_id, Area.owner_id == tid))
    a = result.scalar_one_or_none()
    if a is None:
        raise HTTPException(status_code=404, detail="Area not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(a, field, value)

    await db.flush()
    await db.refresh(a)
    return a


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_area(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Area).where(Area.id == area_id, Area.owner_id == tid))
    a = result.scalar_one_or_none()
    if a is None:
        raise HTTPException(status_code=404, detail="Area not found")
    # Unlink customers referencing this area to avoid FK violation
    await db.execute(
        Customer.__table__.update().where(Customer.area_id == area_id).values(area_id=None)
    )
    await db.delete(a)
    await db.flush()
