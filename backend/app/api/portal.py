import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.pppoe_session import PPPoESession
from app.models.bandwidth_usage import BandwidthUsage
from app.models.customer_activity import CustomerActivity
from app.models.ticket import Ticket, TicketMessage
from app.api.admin.settings import get_branding_settings
from app.models.app_setting import AppSetting
from app.services.pdf import generate_invoice_pdf

from jose import jwt, JWTError

router = APIRouter(prefix="/portal", tags=["portal"])
security_scheme = HTTPBearer()


def _create_portal_token(customer_id: str) -> str:
    """Create a JWT token for portal customer."""
    from datetime import timedelta
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload = {"sub": customer_id, "type": "portal", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_portal_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    """Dependency: verify portal JWT and return customer."""
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "portal":
            raise HTTPException(status_code=401, detail="Invalid token type")
        customer_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(Customer).where(Customer.id == uuid.UUID(customer_id)))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=401, detail="Customer not found")
    return customer


# --- Tenant slug resolver (public, no auth) ---

@router.get("/tenant/{slug}")
async def resolve_tenant(slug: str, db: AsyncSession = Depends(get_db)):
    """Resolve a portal slug to tenant branding info."""
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "portal_slug", AppSetting.value == slug)
    )
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="Portal not found")
    tenant_id = setting.owner_id
    branding = await get_branding_settings(db, tenant_id=tenant_id)
    return {
        "tenant_id": str(tenant_id),
        "company_name": branding.get("company_name", ""),
        "company_logo_url": branding.get("company_logo_url", ""),
    }


# --- Auth ---

@router.post("/auth/login")
async def portal_login(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    slug = body.get("slug", "").strip()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    # Resolve tenant from slug
    if slug:
        slug_result = await db.execute(
            select(AppSetting).where(AppSetting.key == "portal_slug", AppSetting.value == slug)
        )
        slug_setting = slug_result.scalar_one_or_none()
        if not slug_setting:
            raise HTTPException(status_code=404, detail="Portal not found")
        tenant_id = slug_setting.owner_id
        result = await db.execute(
            select(Customer).where(
                Customer.pppoe_username == username,
                Customer.owner_id == tenant_id,
            )
        )
    else:
        # Fallback: email-based login (backwards compat)
        result = await db.execute(select(Customer).where(Customer.email == username))

    customer = result.scalar_one_or_none()

    if not customer or customer.pppoe_password != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if customer.status == "terminated":
        raise HTTPException(status_code=403, detail="Account terminated")

    token = _create_portal_token(str(customer.id))
    return {
        "access_token": token,
        "customer": {
            "id": str(customer.id),
            "full_name": customer.full_name,
            "email": customer.email,
            "phone": customer.phone,
            "status": customer.status.value,
            "plan_name": customer.plan.name if customer.plan else None,
        },
    }


@router.get("/me")
async def portal_me(customer: Customer = Depends(get_portal_customer)):
    return {
        "id": str(customer.id),
        "full_name": customer.full_name,
        "email": customer.email,
        "phone": customer.phone,
        "address": customer.address,
        "status": customer.status.value,
        "plan": {
            "name": customer.plan.name,
            "download_mbps": customer.plan.download_mbps,
            "upload_mbps": customer.plan.upload_mbps,
            "monthly_price": str(customer.plan.monthly_price),
        } if customer.plan else None,
    }


# --- Dashboard / Overview ---

@router.get("/dashboard")
async def portal_dashboard(
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    # Outstanding balance
    outstanding_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            and_(
                Invoice.customer_id == customer.id,
                Invoice.status.in_([InvoiceStatus.pending, InvoiceStatus.overdue]),
            )
        )
    )
    outstanding = outstanding_result.scalar() or Decimal("0")

    # Active session
    session_result = await db.execute(
        select(PPPoESession).where(
            and_(
                PPPoESession.customer_id == customer.id,
                PPPoESession.ended_at.is_(None),
            )
        ).order_by(PPPoESession.started_at.desc()).limit(1)
    )
    session = session_result.scalar_one_or_none()

    # Recent invoices
    inv_result = await db.execute(
        select(Invoice).where(Invoice.customer_id == customer.id)
        .order_by(Invoice.issued_at.desc()).limit(5)
    )
    recent_invoices = inv_result.scalars().all()

    return {
        "status": customer.status.value,
        "plan": {
            "name": customer.plan.name,
            "download_mbps": customer.plan.download_mbps,
            "upload_mbps": customer.plan.upload_mbps,
            "monthly_price": str(customer.plan.monthly_price),
        } if customer.plan else None,
        "outstanding_balance": str(outstanding),
        "session": {
            "ip_address": session.ip_address,
            "started_at": session.started_at.isoformat(),
            "bytes_in": session.bytes_in,
            "bytes_out": session.bytes_out,
        } if session else None,
        "recent_invoices": [
            {
                "id": str(inv.id),
                "amount": str(inv.amount),
                "due_date": inv.due_date.isoformat(),
                "status": inv.status.value,
            }
            for inv in recent_invoices
        ],
    }


# --- Invoices ---

@router.get("/invoices")
async def portal_invoices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    count_result = await db.execute(
        select(func.count(Invoice.id)).where(Invoice.customer_id == customer.id)
    )
    total = count_result.scalar()

    result = await db.execute(
        select(Invoice).where(Invoice.customer_id == customer.id)
        .order_by(Invoice.issued_at.desc())
        .offset((page - 1) * size).limit(size)
    )
    invoices = result.scalars().all()

    return {
        "items": [
            {
                "id": str(inv.id),
                "amount": str(inv.amount),
                "due_date": inv.due_date.isoformat(),
                "status": inv.status.value,
                "issued_at": inv.issued_at.isoformat(),
                "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
                "plan_name": inv.plan.name if inv.plan else None,
                "total_paid": str(sum(p.amount for p in inv.payments)) if inv.payments else "0",
            }
            for inv in invoices
        ],
        "total": total,
        "page": page,
        "page_size": size,
    }


@router.get("/invoices/{invoice_id}/pdf")
async def portal_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    result = await db.execute(
        select(Invoice).where(
            and_(Invoice.id == invoice_id, Invoice.customer_id == customer.id)
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    payments = invoice.payments or []
    total_paid = sum(p.amount for p in payments)
    branding = await get_branding_settings(db, tenant_id=customer.owner_id)
    pdf_bytes = generate_invoice_pdf(invoice, customer, invoice.plan, payments, total_paid, branding=branding)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="invoice-{str(invoice.id)[:8]}.pdf"'},
    )


# --- Usage ---

@router.get("/usage")
async def portal_usage(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    from datetime import timedelta
    start_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(BandwidthUsage).where(
            and_(
                BandwidthUsage.customer_id == customer.id,
                BandwidthUsage.date >= start_date,
            )
        ).order_by(BandwidthUsage.date.asc())
    )
    usage = result.scalars().all()

    return [
        {
            "date": u.date.isoformat(),
            "bytes_in": u.total_bytes_in,
            "bytes_out": u.total_bytes_out,
            "peak_download_mbps": str(u.peak_download_mbps) if u.peak_download_mbps else "0",
            "peak_upload_mbps": str(u.peak_upload_mbps) if u.peak_upload_mbps else "0",
        }
        for u in usage
    ]


@router.get("/sessions")
async def portal_sessions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    result = await db.execute(
        select(PPPoESession).where(PPPoESession.customer_id == customer.id)
        .order_by(PPPoESession.started_at.desc())
        .offset((page - 1) * size).limit(size)
    )
    sessions = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "ip_address": s.ip_address,
            "mac_address": s.mac_address,
            "started_at": s.started_at.isoformat(),
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "bytes_in": s.bytes_in,
            "bytes_out": s.bytes_out,
        }
        for s in sessions
    ]


# --- Tickets ---

@router.get("/tickets/counts")
async def portal_ticket_counts(
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    from sqlalchemy import func
    result = await db.execute(
        select(func.count()).select_from(Ticket).where(
            Ticket.customer_id == customer.id,
            Ticket.status.in_(["open", "in_progress"]),
        )
    )
    return {"open": result.scalar() or 0}


@router.get("/tickets")
async def portal_get_tickets(
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    result = await db.execute(
        select(Ticket).where(Ticket.customer_id == customer.id).order_by(Ticket.created_at.desc())
    )
    tickets = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "subject": t.subject,
            "status": t.status,
            "priority": t.priority,
            "created_at": t.created_at.isoformat(),
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        }
        for t in tickets
    ]


@router.post("/tickets")
async def portal_create_ticket(
    body: dict,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    ticket = Ticket(
        customer_id=customer.id,
        subject=body["subject"],
        priority=body.get("priority", "medium"),
        owner_id=customer.owner_id,
    )
    db.add(ticket)
    await db.flush()
    await db.refresh(ticket)
    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_type="customer",
        sender_id=customer.id,
        message=body["message"],
        owner_id=customer.owner_id,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(ticket)
    return {
        "id": str(ticket.id),
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat(),
    }


@router.get("/tickets/{ticket_id}")
async def portal_get_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.customer_id == customer.id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Resolve sender names for messages
    sender_ids = {m.sender_id for m in (ticket.messages or [])}
    name_map: dict[uuid.UUID, str] = {}
    if sender_ids:
        from app.models.user import User
        users_result = await db.execute(select(User).where(User.id.in_(sender_ids)))
        for u in users_result.scalars().all():
            name_map[u.id] = u.full_name or u.username
        customers_result = await db.execute(select(Customer).where(Customer.id.in_(sender_ids)))
        for c in customers_result.scalars().all():
            name_map[c.id] = c.full_name

    return {
        "id": str(ticket.id),
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat(),
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "messages": [
            {
                "id": str(m.id),
                "sender_type": m.sender_type,
                "sender_name": name_map.get(m.sender_id),
                "message": m.message,
                "created_at": m.created_at.isoformat(),
            }
            for m in (ticket.messages or [])
        ],
    }


@router.post("/tickets/{ticket_id}/messages")
async def portal_add_message(
    ticket_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_portal_customer),
):
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.customer_id == customer.id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_type="customer",
        sender_id=customer.id,
        message=body["message"],
        owner_id=customer.owner_id,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(ticket)

    # Resolve sender names
    sender_ids = {m.sender_id for m in (ticket.messages or [])}
    name_map: dict[uuid.UUID, str] = {}
    if sender_ids:
        from app.models.user import User
        users_result = await db.execute(select(User).where(User.id.in_(sender_ids)))
        for u in users_result.scalars().all():
            name_map[u.id] = u.full_name or u.username
        customers_result = await db.execute(select(Customer).where(Customer.id.in_(sender_ids)))
        for c in customers_result.scalars().all():
            name_map[c.id] = c.full_name

    return {
        "id": str(ticket.id),
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat(),
        "messages": [
            {
                "id": str(m.id),
                "sender_type": m.sender_type,
                "sender_name": name_map.get(m.sender_id),
                "message": m.message,
                "created_at": m.created_at.isoformat(),
            }
            for m in (ticket.messages or [])
        ],
    }
