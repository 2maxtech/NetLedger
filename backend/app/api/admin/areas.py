import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.router import Area
from app.models.user import User
from app.schemas.router import AreaCreate, AreaResponse, AreaUpdate

router = APIRouter(prefix="/areas", tags=["areas"])


@router.get("/", response_model=list[AreaResponse])
async def list_areas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Area).order_by(Area.name))
    return result.scalars().all()


@router.post("/", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
async def create_area(
    body: AreaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    a = Area(**body.model_dump())
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
):
    result = await db.execute(select(Area).where(Area.id == area_id))
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
):
    result = await db.execute(select(Area).where(Area.id == area_id))
    a = result.scalar_one_or_none()
    if a is None:
        raise HTTPException(status_code=404, detail="Area not found")
    await db.delete(a)
    await db.flush()
