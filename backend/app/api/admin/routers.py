import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.router import Router
from app.models.user import User
from app.schemas.router import RouterCreate, RouterResponse, RouterStatusResponse, RouterUpdate
from app.services.mikrotik import get_mikrotik_client, invalidate_client

router = APIRouter(prefix="/routers", tags=["routers"])


@router.get("/", response_model=list[RouterResponse])
async def list_routers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Router).order_by(Router.created_at))
    return result.scalars().all()


@router.post("/", response_model=RouterResponse, status_code=status.HTTP_201_CREATED)
async def create_router(
    body: RouterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    r = Router(**body.model_dump())
    db.add(r)
    await db.flush()
    await db.refresh(r)
    return r


@router.get("/{router_id}", response_model=RouterResponse)
async def get_router(
    router_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Router).where(Router.id == router_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")
    return r


@router.put("/{router_id}", response_model=RouterResponse)
async def update_router(
    router_id: uuid.UUID,
    body: RouterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Router).where(Router.id == router_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(r, field, value)

    invalidate_client(str(router_id))
    await db.flush()
    await db.refresh(r)
    return r


@router.delete("/{router_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_router(
    router_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Router).where(Router.id == router_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")
    r.is_active = False
    invalidate_client(str(router_id))
    await db.flush()


@router.get("/{router_id}/status", response_model=RouterStatusResponse)
async def get_router_status(
    router_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Router).where(Router.id == router_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")

    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    try:
        identity = await client.get_identity()
        resources = await client.get_resources()
        sessions = await client.get_active_sessions()
        return RouterStatusResponse(
            id=r.id,
            name=r.name,
            connected=True,
            identity=identity,
            uptime=resources.get("uptime", ""),
            cpu_load=resources.get("cpu-load", "0"),
            free_memory=int(resources.get("free-memory", 0)),
            total_memory=int(resources.get("total-memory", 0)),
            active_sessions=len(sessions),
            version=resources.get("version", ""),
        )
    except Exception as e:
        return RouterStatusResponse(id=r.id, name=r.name, connected=False, error=str(e))
