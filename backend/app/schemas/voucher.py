import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.voucher import VoucherStatus


class VoucherGenerate(BaseModel):
    plan_id: uuid.UUID
    duration_days: int
    count: int = 1


class VoucherRedeem(BaseModel):
    code: str
    customer_id: uuid.UUID


class VoucherResponse(BaseModel):
    id: uuid.UUID
    code: str
    plan_id: uuid.UUID
    duration_days: int
    status: VoucherStatus
    customer_id: uuid.UUID | None
    activated_at: datetime | None
    expires_at: datetime | None
    batch_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
