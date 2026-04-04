import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.notification import Notification, NotificationStatus
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.schemas.billing import (
    InvoiceGenerateRequest,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdateRequest,
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    RevenueSummary,
)
from app.services import billing as billing_service
from app.services.pdf import generate_invoice_pdf

router = APIRouter(prefix="/billing", tags=["billing"])


def _invoice_to_response(inv: Invoice) -> dict:
    total_paid = sum(p.amount for p in inv.payments) if inv.payments else Decimal("0")
    return {
        "id": inv.id,
        "customer_id": inv.customer_id,
        "plan_id": inv.plan_id,
        "amount": inv.amount,
        "due_date": inv.due_date,
        "status": inv.status,
        "paid_at": inv.paid_at,
        "issued_at": inv.issued_at,
        "created_at": inv.created_at,
        "customer_name": inv.customer.full_name if inv.customer else None,
        "plan_name": inv.plan.name if inv.plan else None,
        "total_paid": total_paid,
    }


# --- Invoice endpoints ---

@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    customer_id: uuid.UUID | None = Query(None),
    status_filter: InvoiceStatus | None = Query(None, alias="status"),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Invoice)
    count_query = select(func.count(Invoice.id))

    if customer_id:
        query = query.where(Invoice.customer_id == customer_id)
        count_query = count_query.where(Invoice.customer_id == customer_id)
    if status_filter:
        query = query.where(Invoice.status == status_filter)
        count_query = count_query.where(Invoice.status == status_filter)
    if from_date:
        query = query.where(Invoice.issued_at >= datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc))
        count_query = count_query.where(Invoice.issued_at >= datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc))
    if to_date:
        query = query.where(Invoice.issued_at <= datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc))
        count_query = count_query.where(Invoice.issued_at <= datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(Invoice.issued_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    invoices = result.scalars().all()

    return InvoiceListResponse(
        items=[_invoice_to_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=size,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_to_response(invoice)


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    customer = invoice.customer
    plan = invoice.plan
    payments = invoice.payments or []
    total_paid = sum(p.amount for p in payments)

    pdf_bytes = generate_invoice_pdf(invoice, customer, plan, payments, total_paid)

    filename = f"invoice-{str(invoice.id)[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/invoices/generate", status_code=status.HTTP_200_OK)
async def generate_invoices(
    body: InvoiceGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.billing)),
):
    if body.customer_id:
        result = await db.execute(select(Customer).where(Customer.id == body.customer_id))
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        invoice = await billing_service.generate_invoice(db, customer, date.today().replace(day=1))
        return {"generated": 1, "skipped": 0, "invoices": [str(invoice.id)]}
    else:
        result = await billing_service.generate_monthly_invoices(db)
        return result


@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: uuid.UUID,
    body: InvoiceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.billing)),
):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if body.status is not None:
        invoice.status = body.status
    if body.amount is not None:
        invoice.amount = body.amount

    await db.flush()
    await db.refresh(invoice)
    return _invoice_to_response(invoice)


# --- Payment endpoints ---

@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    customer_id: uuid.UUID | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Payment)
    count_query = select(func.count(Payment.id))

    if customer_id:
        query = query.join(Invoice).where(Invoice.customer_id == customer_id)
        count_query = count_query.join(Invoice).where(Invoice.customer_id == customer_id)
    if from_date:
        query = query.where(Payment.received_at >= datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc))
        count_query = count_query.where(Payment.received_at >= datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc))
    if to_date:
        query = query.where(Payment.received_at <= datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc))
        count_query = count_query.where(Payment.received_at <= datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(Payment.received_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    payments = result.scalars().all()

    items = []
    for p in payments:
        items.append({
            "id": p.id,
            "invoice_id": p.invoice_id,
            "amount": p.amount,
            "method": p.method,
            "reference_number": p.reference_number,
            "received_by": p.received_by,
            "received_at": p.received_at,
            "created_at": p.created_at,
            "customer_name": p.invoice.customer.full_name if p.invoice and p.invoice.customer else None,
            "invoice_amount": p.invoice.amount if p.invoice else None,
        })

    return PaymentListResponse(items=items, total=total, page=page, page_size=size)


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.billing)),
):
    try:
        payment = await billing_service.record_payment(
            db=db,
            invoice_id=body.invoice_id,
            amount=body.amount,
            method=body.method,
            reference=body.reference_number,
            received_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    inv = payment.invoice
    return {
        "id": payment.id,
        "invoice_id": payment.invoice_id,
        "amount": payment.amount,
        "method": payment.method,
        "reference_number": payment.reference_number,
        "received_by": payment.received_by,
        "received_at": payment.received_at,
        "created_at": payment.created_at,
        "customer_name": inv.customer.full_name if inv and inv.customer else None,
        "invoice_amount": inv.amount if inv else None,
    }


# --- Report endpoint ---

@router.get("/reports/summary", response_model=RevenueSummary)
async def revenue_summary(
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.billing)),
):
    return await billing_service.get_revenue_summary(db, from_date, to_date)


@router.get("/notifications")
async def list_notifications(
    status_filter: NotificationStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Notification)
    if status_filter:
        query = query.where(Notification.status == status_filter)
    query = query.order_by(Notification.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    notifications = result.scalars().all()
    return [
        {
            "id": str(n.id),
            "customer_id": str(n.customer_id),
            "type": n.type.value,
            "subject": n.subject,
            "message": n.message,
            "status": n.status.value,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]
