import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.tenant import get_tenant_id
from app.models.router import Router
from app.models.voucher import Voucher, VoucherStatus
from app.models.user import User
from app.schemas.voucher import VoucherGenerate, VoucherResponse
from app.services.mikrotik import get_mikrotik_client

router = APIRouter(prefix="/vouchers", tags=["vouchers"])


def generate_voucher_code() -> str:
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"NL-{part1}-{part2}"


@router.get("/hotspot-profiles")
async def get_hotspot_profiles(
    router_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Fetch hotspot user profiles from a MikroTik router."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    mt_router = result.scalar_one_or_none()
    if not mt_router:
        raise HTTPException(status_code=404, detail="Router not found")

    try:
        client = get_mikrotik_client(str(mt_router.id), mt_router.url, mt_router.username, mt_router.password)
        resp = await client._request("GET", "ip/hotspot/user/profile")
        profiles = resp.json()
        return [
            {
                "name": p.get("name"),
                "rate_limit": p.get("rate-limit", ""),
                "session_timeout": p.get("session-timeout", ""),
                "shared_users": p.get("shared-users", "1"),
            }
            for p in profiles
        ]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch hotspot profiles: {e}")


@router.get("/", response_model=list[VoucherResponse])
async def list_vouchers(
    voucher_status: VoucherStatus | None = Query(None, alias="status"),
    batch_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    query = select(Voucher).where(Voucher.owner_id == tid)

    if voucher_status:
        query = query.where(Voucher.status == voucher_status)
    if batch_id:
        query = query.where(Voucher.batch_id == batch_id)

    query = query.order_by(Voucher.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/generate", response_model=list[VoucherResponse], status_code=status.HTTP_201_CREATED)
async def generate_vouchers(
    body: VoucherGenerate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Generate a batch of vouchers for hotspot access."""
    tid = uuid.UUID(tenant_id)

    # Verify router belongs to tenant
    result = await db.execute(select(Router).where(Router.id == body.router_id, Router.owner_id == tid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Router not found")

    batch_id = uuid.uuid4().hex[:8].upper()
    vouchers = []

    for _ in range(body.count):
        for _attempt in range(10):
            code = generate_voucher_code()
            existing = await db.execute(select(Voucher).where(Voucher.code == code))
            if existing.scalar_one_or_none() is None:
                break
        else:
            raise HTTPException(status_code=500, detail="Failed to generate unique voucher code")

        voucher = Voucher(
            code=code,
            router_id=body.router_id,
            hotspot_profile=body.hotspot_profile,
            duration_hours=body.duration_hours,
            status=VoucherStatus.unused,
            batch_id=batch_id,
            owner_id=tid,
        )
        db.add(voucher)
        vouchers.append(voucher)

    await db.flush()
    for v in vouchers:
        await db.refresh(v)

    return vouchers


@router.post("/redeem")
async def redeem_voucher(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Redeem a voucher code — creates a hotspot user on MikroTik. No auth required (captive portal use)."""
    code = body.get("code", "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Voucher code required")

    result = await db.execute(select(Voucher).where(Voucher.code == code))
    voucher = result.scalar_one_or_none()

    if voucher is None:
        raise HTTPException(status_code=404, detail="Invalid voucher code")
    if voucher.status != VoucherStatus.unused:
        raise HTTPException(status_code=400, detail=f"Voucher is {voucher.status.value}")

    # Get router to create hotspot user
    rt_result = await db.execute(select(Router).where(Router.id == voucher.router_id))
    mt_router = rt_result.scalar_one_or_none()
    if not mt_router:
        raise HTTPException(status_code=500, detail="Router not found for this voucher")

    now = datetime.now(timezone.utc)
    voucher.activated_at = now
    voucher.expires_at = now + timedelta(hours=voucher.duration_hours)
    voucher.status = VoucherStatus.active

    # Create hotspot user on MikroTik
    try:
        client = get_mikrotik_client(str(mt_router.id), mt_router.url, mt_router.username, mt_router.password)
        await client._request("PUT", "ip/hotspot/user", json={
            "name": voucher.code,
            "password": voucher.code,
            "profile": voucher.hotspot_profile,
            "limit-uptime": f"{voucher.duration_hours}h",
        })
    except Exception as e:
        # Rollback voucher status if MikroTik fails
        voucher.status = VoucherStatus.unused
        voucher.activated_at = None
        voucher.expires_at = None
        await db.flush()
        raise HTTPException(status_code=502, detail=f"Failed to create hotspot user: {e}")

    await db.flush()
    await db.refresh(voucher)
    return {
        "status": "active",
        "code": voucher.code,
        "profile": voucher.hotspot_profile,
        "expires_at": voucher.expires_at.isoformat(),
        "message": f"Connected! Your access expires in {voucher.duration_hours} hours.",
    }


@router.delete("/{voucher_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_voucher(
    voucher_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Revoke a voucher (only if unused)."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Voucher).where(Voucher.id == voucher_id, Voucher.owner_id == tid))
    voucher = result.scalar_one_or_none()

    if voucher is None:
        raise HTTPException(status_code=404, detail="Voucher not found")
    if voucher.status != VoucherStatus.unused:
        raise HTTPException(status_code=400, detail="Only unused vouchers can be revoked")

    voucher.status = VoucherStatus.revoked
    await db.flush()
