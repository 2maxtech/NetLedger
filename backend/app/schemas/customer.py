import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.customer import CustomerStatus
from app.schemas.plan import PlanResponse


class CustomerCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    address: str | None = None
    pppoe_username: str
    pppoe_password: str
    plan_id: uuid.UUID
    mikrotik_secret_id: str | None = None
    mikrotik_queue_id: str | None = None
    mac_address: str | None = None
    router_id: uuid.UUID | None = None
    area_id: uuid.UUID | None = None
    latitude: float | None = None
    longitude: float | None = None


class CustomerUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    pppoe_username: str | None = None
    pppoe_password: str | None = None
    plan_id: uuid.UUID | None = None
    status: CustomerStatus | None = None
    mikrotik_secret_id: str | None = None
    mikrotik_queue_id: str | None = None
    mac_address: str | None = None
    router_id: uuid.UUID | None = None
    area_id: uuid.UUID | None = None
    latitude: float | None = None
    longitude: float | None = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    phone: str
    address: str | None
    pppoe_username: str
    status: CustomerStatus
    plan_id: uuid.UUID
    plan: PlanResponse | None = None
    created_at: datetime
    mikrotik_secret_id: str | None = None
    mikrotik_queue_id: str | None = None
    mac_address: str | None = None
    router_id: uuid.UUID | None = None
    area_id: uuid.UUID | None = None
    latitude: float | None = None
    longitude: float | None = None

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int
