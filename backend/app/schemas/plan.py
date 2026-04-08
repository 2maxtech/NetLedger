import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PlanCreate(BaseModel):
    name: str
    download_mbps: int
    upload_mbps: int
    monthly_price: Decimal
    description: str | None = None
    data_cap_gb: int | None = None
    fup_download_mbps: int | None = None
    fup_upload_mbps: int | None = None
    local_address: str | None = None
    remote_address: str | None = None
    dns_server: str | None = None
    parent_queue: str | None = None


class PlanUpdate(BaseModel):
    name: str | None = None
    download_mbps: int | None = None
    upload_mbps: int | None = None
    monthly_price: Decimal | None = None
    description: str | None = None
    is_active: bool | None = None
    data_cap_gb: int | None = None
    fup_download_mbps: int | None = None
    fup_upload_mbps: int | None = None
    local_address: str | None = None
    remote_address: str | None = None
    dns_server: str | None = None
    parent_queue: str | None = None


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    download_mbps: int
    upload_mbps: int
    monthly_price: Decimal
    description: str | None
    is_active: bool
    created_at: datetime
    data_cap_gb: int | None = None
    fup_download_mbps: int | None = None
    fup_upload_mbps: int | None = None
    local_address: str | None = None
    remote_address: str | None = None
    dns_server: str | None = None
    parent_queue: str | None = None

    model_config = {"from_attributes": True}
