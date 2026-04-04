import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.ticket import TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    customer_id: uuid.UUID
    subject: str
    priority: TicketPriority = TicketPriority.medium
    message: str  # initial message


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assigned_to: uuid.UUID | None = None


class TicketMessageCreate(BaseModel):
    message: str


class TicketMessageResponse(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    sender_type: str
    sender_id: uuid.UUID
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    subject: str
    status: TicketStatus
    priority: TicketPriority
    assigned_to: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime
    messages: list[TicketMessageResponse] = []

    model_config = {"from_attributes": True}
