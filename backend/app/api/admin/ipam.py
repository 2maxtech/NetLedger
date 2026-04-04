import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.ip_pool import IPPool
from app.models.user import User

router = APIRouter(prefix="/ipam", tags=["ipam"])


class IPPoolCreate(BaseModel):
    name: str
    router_id: uuid.UUID
    range_start: str
    range_end: str
    subnet: str


class IPPoolResponse(BaseModel):
    id: uuid.UUID
    name: str
    router_id: uuid.UUID
    range_start: str
    range_end: str
    subnet: str

    model_config = {"from_attributes": True}


@router.get("/pools", response_model=list[IPPoolResponse])
async def list_pools(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all IP pools with router info."""
    result = await db.execute(select(IPPool).order_by(IPPool.name))
    return result.scalars().all()


@router.post("/pools", response_model=IPPoolResponse, status_code=status.HTTP_201_CREATED)
async def create_pool(
    body: IPPoolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new IP pool."""
    pool = IPPool(**body.model_dump())
    db.add(pool)
    await db.flush()
    await db.refresh(pool)
    return pool


@router.delete("/pools/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pool(
    pool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an IP pool."""
    result = await db.execute(select(IPPool).where(IPPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(status_code=404, detail="IP pool not found")

    await db.delete(pool)
    await db.flush()
