import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.invoice import InvoiceStatus
from app.models.payment import PaymentMethod


# --- Invoice schemas ---

class InvoiceResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    plan_id: uuid.UUID
    amount: Decimal
    due_date: date
    status: InvoiceStatus
    paid_at: datetime | None
    issued_at: datetime
    created_at: datetime
    customer_name: str | None = None
    plan_name: str | None = None
    total_paid: Decimal | None = None

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


class InvoiceGenerateRequest(BaseModel):
    customer_id: uuid.UUID | None = None


class InvoiceUpdateRequest(BaseModel):
    status: InvoiceStatus | None = None
    amount: Decimal | None = None


# --- Payment schemas ---

class PaymentCreate(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal
    method: PaymentMethod
    reference_number: str | None = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    method: PaymentMethod
    reference_number: str | None
    received_by: uuid.UUID | None
    received_at: datetime
    created_at: datetime
    customer_name: str | None = None
    invoice_amount: Decimal | None = None

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int
    page: int
    page_size: int


# --- Report schemas ---

class RevenueSummary(BaseModel):
    total_billed: Decimal
    total_collected: Decimal
    total_outstanding: Decimal
    collection_rate: float


# --- Bulk action schemas ---

class BulkInvoiceIdsRequest(BaseModel):
    invoice_ids: list[uuid.UUID]


class BulkActionResponse(BaseModel):
    success: int
    failed: int
    errors: list[dict] = []
