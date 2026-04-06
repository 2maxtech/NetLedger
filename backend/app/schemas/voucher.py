import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.voucher import VoucherStatus


class VoucherGenerate(BaseModel):
    router_id: uuid.UUID
    hotspot_profile: str
    duration_hours: int
    count: int = 1


class VoucherResponse(BaseModel):
    id: uuid.UUID
    code: str
    router_id: uuid.UUID
    hotspot_profile: str
    duration_hours: int
    status: VoucherStatus
    activated_at: datetime | None
    expires_at: datetime | None
    batch_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
