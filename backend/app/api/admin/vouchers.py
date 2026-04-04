import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.voucher import Voucher, VoucherStatus
from app.models.user import User
from app.schemas.voucher import VoucherGenerate, VoucherRedeem, VoucherResponse

router = APIRouter(prefix="/vouchers", tags=["vouchers"])


def generate_voucher_code() -> str:
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"NL-{part1}-{part2}"


@router.get("/", response_model=list[VoucherResponse])
async def list_vouchers(
    voucher_status: VoucherStatus | None = Query(None, alias="status"),
    batch_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Voucher)

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
):
    """Generate a batch of vouchers with random codes."""
    batch_id = uuid.uuid4().hex[:8].upper()
    vouchers = []

    for _ in range(body.count):
        # Ensure unique code
        for _attempt in range(10):
            code = generate_voucher_code()
            existing = await db.execute(select(Voucher).where(Voucher.code == code))
            if existing.scalar_one_or_none() is None:
                break
        else:
            raise HTTPException(status_code=500, detail="Failed to generate unique voucher code")

        voucher = Voucher(
            code=code,
            plan_id=body.plan_id,
            duration_days=body.duration_days,
            status=VoucherStatus.unused,
            batch_id=batch_id,
        )
        db.add(voucher)
        vouchers.append(voucher)

    await db.flush()
    for v in vouchers:
        await db.refresh(v)

    return vouchers


@router.post("/redeem", response_model=VoucherResponse)
async def redeem_voucher(
    body: VoucherRedeem,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Redeem a voucher for a customer."""
    result = await db.execute(select(Voucher).where(Voucher.code == body.code))
    voucher = result.scalar_one_or_none()

    if voucher is None:
        raise HTTPException(status_code=404, detail="Voucher not found")
    if voucher.status != VoucherStatus.unused:
        raise HTTPException(status_code=400, detail=f"Voucher is {voucher.status.value}, cannot redeem")

    now = datetime.now(timezone.utc)
    voucher.customer_id = body.customer_id
    voucher.activated_at = now
    voucher.expires_at = now + timedelta(days=voucher.duration_days)
    voucher.status = VoucherStatus.active

    await db.flush()
    await db.refresh(voucher)
    return voucher


@router.delete("/{voucher_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_voucher(
    voucher_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke a voucher (only if unused)."""
    result = await db.execute(select(Voucher).where(Voucher.id == voucher_id))
    voucher = result.scalar_one_or_none()

    if voucher is None:
        raise HTTPException(status_code=404, detail="Voucher not found")
    if voucher.status != VoucherStatus.unused:
        raise HTTPException(status_code=400, detail="Only unused vouchers can be revoked")

    voucher.status = VoucherStatus.revoked
    await db.flush()
