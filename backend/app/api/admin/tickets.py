import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.tenant import get_tenant_id
from app.models.customer import Customer
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


async def _resolve_assigned_names(db: AsyncSession, tickets: list) -> dict[uuid.UUID, str]:
    """Build a map of user_id -> display name for assigned_to fields."""
    assigned_ids = {t.assigned_to for t in tickets if t.assigned_to}
    if not assigned_ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(assigned_ids)))
    return {u.id: u.full_name or u.username for u in result.scalars().all()}


@router.get("/counts")
async def ticket_counts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(
        select(func.count()).select_from(Ticket).where(
            Ticket.owner_id == tid,
            Ticket.status.in_(["open", "in_progress"]),
        )
    )
    return {"open": result.scalar() or 0}


@router.get("/", response_model=list[TicketResponse])
async def list_tickets(
    ticket_status: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = Query(None),
    assigned_to: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    query = select(Ticket).where(Ticket.owner_id == tid)

    if ticket_status:
        query = query.where(Ticket.status == ticket_status)
    if priority:
        query = query.where(Ticket.priority == priority)
    if assigned_to:
        query = query.where(Ticket.assigned_to == assigned_to)

    query = query.order_by(Ticket.created_at.desc())
    result = await db.execute(query)
    tickets = result.scalars().all()
    name_map = await _resolve_assigned_names(db, tickets)
    responses = []
    for t in tickets:
        resp = TicketResponse.model_validate(t)
        resp.customer_name = t.customer.full_name if t.customer else None
        resp.assigned_to_name = name_map.get(t.assigned_to) if t.assigned_to else None
        responses.append(resp)
    return responses


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    ticket = Ticket(
        customer_id=body.customer_id,
        subject=body.subject,
        priority=body.priority,
        status=TicketStatus.open,
        owner_id=tid,
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
        owner_id=tid,
    )
    db.add(message)
    await db.flush()
    await db.refresh(ticket)
    resp = TicketResponse.model_validate(ticket)
    resp.customer_name = ticket.customer.full_name if ticket.customer else None
    return resp


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id, Ticket.owner_id == tid))
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Resolve sender names for messages
    sender_ids = {m.sender_id for m in ticket.messages}
    name_map: dict[uuid.UUID, str] = {}
    if sender_ids:
        users_result = await db.execute(select(User).where(User.id.in_(sender_ids)))
        for u in users_result.scalars().all():
            name_map[u.id] = u.full_name or u.username
        customers_result = await db.execute(select(Customer).where(Customer.id.in_(sender_ids)))
        for c in customers_result.scalars().all():
            name_map[c.id] = c.full_name

    # Resolve assigned_to name
    assigned_name = None
    if ticket.assigned_to:
        assigned_result = await db.execute(select(User).where(User.id == ticket.assigned_to))
        assigned_user = assigned_result.scalar_one_or_none()
        if assigned_user:
            assigned_name = assigned_user.full_name or assigned_user.username

    resp = TicketResponse.model_validate(ticket)
    resp.customer_name = ticket.customer.full_name if ticket.customer else None
    resp.assigned_to_name = assigned_name
    for msg in resp.messages:
        msg.sender_name = name_map.get(msg.sender_id)
    return resp


@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: uuid.UUID,
    body: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id, Ticket.owner_id == tid))
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
    # Resolve assigned_to name
    assigned_name = None
    if ticket.assigned_to:
        assigned_result = await db.execute(select(User).where(User.id == ticket.assigned_to))
        au = assigned_result.scalar_one_or_none()
        if au:
            assigned_name = au.full_name or au.username
    resp = TicketResponse.model_validate(ticket)
    resp.customer_name = ticket.customer.full_name if ticket.customer else None
    resp.assigned_to_name = assigned_name
    return resp


@router.post("/{ticket_id}/messages", response_model=TicketMessageResponse, status_code=status.HTTP_201_CREATED)
async def add_ticket_message(
    ticket_id: uuid.UUID,
    body: TicketMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id, Ticket.owner_id == tid))
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    message = TicketMessage(
        ticket_id=ticket_id,
        sender_type="staff",
        sender_id=current_user.id,
        message=body.message,
        owner_id=tid,
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)
    resp = TicketMessageResponse.model_validate(message)
    resp.sender_name = current_user.full_name or current_user.username
    return resp
