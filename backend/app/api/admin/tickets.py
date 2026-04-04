import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.ticket import Ticket, TicketMessage, TicketPriority, TicketStatus
from app.models.user import User
from app.schemas.ticket import (
    TicketCreate,
    TicketMessageCreate,
    TicketMessageResponse,
    TicketResponse,
    TicketUpdate,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/", response_model=list[TicketResponse])
async def list_tickets(
    ticket_status: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = Query(None),
    assigned_to: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Ticket)

    if ticket_status:
        query = query.where(Ticket.status == ticket_status)
    if priority:
        query = query.where(Ticket.priority == priority)
    if assigned_to:
        query = query.where(Ticket.assigned_to == assigned_to)

    query = query.order_by(Ticket.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = Ticket(
        customer_id=body.customer_id,
        subject=body.subject,
        priority=body.priority,
        status=TicketStatus.open,
    )
    db.add(ticket)
    await db.flush()
    await db.refresh(ticket)

    # Add first message
    message = TicketMessage(
        ticket_id=ticket.id,
        sender_type="staff",
        sender_id=current_user.id,
        message=body.message,
    )
    db.add(message)
    await db.flush()
    await db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: uuid.UUID,
    body: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)

    # Set resolved_at when status transitions to resolved
    if body.status == TicketStatus.resolved and ticket.resolved_at is None:
        ticket.resolved_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/messages", response_model=TicketMessageResponse, status_code=status.HTTP_201_CREATED)
async def add_ticket_message(
    ticket_id: uuid.UUID,
    body: TicketMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    message = TicketMessage(
        ticket_id=ticket_id,
        sender_type="staff",
        sender_id=current_user.id,
        message=body.message,
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)
    return message
