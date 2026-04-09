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
from app.core.tenant import get_tenant_id
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.schemas.billing import (
    BulkActionResponse,
    BulkInvoiceDeleteRequest,
    BulkInvoiceIdsRequest,
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
from app.services.audit import log_action
from app.api.admin.settings import get_branding_settings
from app.services.pdf import generate_invoice_pdf
from app.utils.csv_export import make_csv_response

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
    format: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    query = select(Invoice).where(Invoice.owner_id == tid)
    count_query = select(func.count(Invoice.id)).where(Invoice.owner_id == tid)

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

    if format == "csv":
        query = query.order_by(Invoice.issued_at.desc())
        result = await db.execute(query)
        invoices = result.scalars().all()
        rows = [
            {
                "customer_name": inv.customer.full_name if inv.customer else "",
                "amount": str(inv.amount),
                "status": inv.status.value,
                "due_date": inv.due_date.isoformat() if inv.due_date else "",
                "paid_date": inv.paid_at.isoformat() if inv.paid_at else "",
                "created_at": inv.created_at.isoformat() if inv.created_at else "",
            }
            for inv in invoices
        ]
        return make_csv_response(rows, "invoices.csv")

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


# --- Bulk invoice action endpoints (must be before /invoices/{invoice_id}) ---


@router.post("/invoices/bulk/mark-paid", response_model=BulkActionResponse)
async def bulk_mark_paid(
    body: BulkInvoiceIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.billing)),
    tenant_id: str = Depends(get_tenant_id),
):
    """Mark multiple invoices as paid with today's date and create payment records."""
    from app.models.payment import PaymentMethod

    tid = uuid.UUID(tenant_id)
    success = 0
    failed = 0
    errors = []

    for inv_id in body.invoice_ids:
        try:
            result = await db.execute(
                select(Invoice).where(Invoice.id == inv_id, Invoice.owner_id == tid)
            )
            invoice = result.scalar_one_or_none()
            if not invoice:
                failed += 1
                errors.append({"invoice_id": str(inv_id), "error": "Invoice not found"})
                continue
            if invoice.status == InvoiceStatus.paid:
                failed += 1
                errors.append({"invoice_id": str(inv_id), "error": "Invoice already paid"})
                continue

            # Calculate remaining balance
            pay_result = await db.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice.id)
            )
            total_paid = pay_result.scalar() or Decimal("0")
            remaining = invoice.amount - total_paid

            if remaining > Decimal("0"):
                await billing_service.record_payment(
                    db=db,
                    invoice_id=invoice.id,
                    amount=remaining,
                    method=PaymentMethod.cash,
                    reference=f"bulk-paid-{date.today().isoformat()}",
                    received_by=current_user.id,
                    owner_id=tid,
                )
            else:
                # Already fully paid by payments, just update status
                invoice.status = InvoiceStatus.paid
                invoice.paid_at = datetime.now(timezone.utc)

            await log_action(
                db, current_user.id, "invoice.bulk_mark_paid",
                "invoice", invoice.id,
                details=f"customer={invoice.customer_id} amount={invoice.amount}",
                owner_id=tid,
            )
            success += 1
        except Exception as e:
            failed += 1
            errors.append({"invoice_id": str(inv_id), "error": str(e)})

    await db.flush()
    return BulkActionResponse(success=success, failed=failed, errors=errors)


@router.post("/invoices/bulk/delete", response_model=BulkActionResponse)
async def bulk_delete_invoices(
    body: BulkInvoiceDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
    tenant_id: str = Depends(get_tenant_id),
):
    """Delete multiple invoices. Requires admin password confirmation. Cannot delete paid invoices."""
    from app.core.security import verify_password

    if not body.password or not verify_password(body.password, current_user.password_hash):
        raise HTTPException(status_code=403, detail="Incorrect password")

    tid = uuid.UUID(tenant_id)
    success = 0
    failed = 0
    errors = []

    for inv_id in body.invoice_ids:
        try:
            result = await db.execute(
                select(Invoice).where(Invoice.id == inv_id, Invoice.owner_id == tid)
            )
            invoice = result.scalar_one_or_none()
            if not invoice:
                failed += 1
                errors.append({"invoice_id": str(inv_id), "error": "Invoice not found"})
                continue
            if invoice.status == InvoiceStatus.paid:
                failed += 1
                errors.append({"invoice_id": str(inv_id), "error": "Cannot delete paid invoice"})
                continue

            # Delete related payments and notifications
            from sqlalchemy import delete as sql_delete
            await db.execute(sql_delete(Payment).where(Payment.invoice_id == invoice.id))
            await db.execute(sql_delete(Notification).where(Notification.customer_id == invoice.customer_id, Notification.owner_id == tid))
            await db.delete(invoice)
            await log_action(db, current_user.id, "invoice.bulk_delete", "invoice", inv_id, details=f"amount={invoice.amount}", owner_id=tid)
            success += 1
        except Exception as e:
            failed += 1
            errors.append({"invoice_id": str(inv_id), "error": str(e)})

    await db.flush()
    return BulkActionResponse(success=success, failed=failed, errors=errors)


@router.post("/invoices/bulk/send-notification", response_model=BulkActionResponse)
async def bulk_send_invoice_notification(
    body: BulkInvoiceIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Send invoice notifications (email/SMS) for multiple invoices."""
    from app.api.admin.settings import get_template_settings
    from app.services.template_renderer import render_template
    from app.services.billing import _build_payment_url

    tid = uuid.UUID(tenant_id)
    success = 0
    failed = 0
    errors = []

    templates = await get_template_settings(db, tenant_id=tid)

    for inv_id in body.invoice_ids:
        try:
            result = await db.execute(
                select(Invoice).where(Invoice.id == inv_id, Invoice.owner_id == tid)
            )
            invoice = result.scalar_one_or_none()
            if not invoice:
                failed += 1
                errors.append({"invoice_id": str(inv_id), "error": "Invoice not found"})
                continue

            customer = invoice.customer
            if not customer:
                failed += 1
                errors.append({"invoice_id": str(inv_id), "error": "Customer not found for invoice"})
                continue

            plan = invoice.plan
            payment_url = await _build_payment_url(db, invoice, tid)
            tpl_vars = {
                "customer_name": customer.full_name,
                "amount": f"\u20b1{invoice.amount:,.2f}",
                "plan_name": plan.name if plan else "N/A",
                "due_date": invoice.due_date.strftime("%B %d, %Y") if hasattr(invoice.due_date, "strftime") else str(invoice.due_date),
                "due_date_short": invoice.due_date.strftime("%b %d") if hasattr(invoice.due_date, "strftime") else str(invoice.due_date),
                "portal_url": "",
                "payment_url": payment_url,
            }

            # SMS notification
            db.add(Notification(
                customer_id=customer.id,
                type=NotificationType.sms,
                subject="Invoice Notification",
                message=render_template(templates["tpl_invoice_sms"], tpl_vars),
                status=NotificationStatus.pending,
                owner_id=tid,
            ))
            # Email notification if customer has valid email
            if customer.email and not customer.email.endswith("@imported.local"):
                db.add(Notification(
                    customer_id=customer.id,
                    type=NotificationType.email,
                    subject=render_template(templates["tpl_invoice_email_subject"], tpl_vars),
                    message=render_template(templates["tpl_invoice_email_body"], tpl_vars),
                    status=NotificationStatus.pending,
                    owner_id=tid,
                ))
            success += 1
        except Exception as e:
            failed += 1
            errors.append({"invoice_id": str(inv_id), "error": str(e)})

    await db.flush()
    return BulkActionResponse(success=success, failed=failed, errors=errors)


@router.post("/invoices/bulk/download-pdf")
async def bulk_download_pdf(
    body: BulkInvoiceIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Download multiple invoices as a ZIP of PDFs."""
    import io
    import zipfile

    tid = uuid.UUID(tenant_id)
    branding = await get_branding_settings(db, tenant_id=tid)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for inv_id in body.invoice_ids:
            result = await db.execute(
                select(Invoice).where(Invoice.id == inv_id, Invoice.owner_id == tid)
            )
            invoice = result.scalar_one_or_none()
            if not invoice:
                continue
            customer = invoice.customer
            plan = invoice.plan
            payments = invoice.payments or []
            total_paid = sum(p.amount for p in payments)
            pdf_bytes = generate_invoice_pdf(invoice, customer, plan, payments, total_paid, branding=branding)
            customer_name = customer.full_name.replace(" ", "_") if customer else "unknown"
            zf.writestr(f"invoice-{customer_name}-{str(invoice.id)[:8]}.pdf", pdf_bytes)

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="invoices.zip"'},
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.owner_id == tid))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_to_response(invoice)


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.owner_id == tid))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    customer = invoice.customer
    plan = invoice.plan
    payments = invoice.payments or []
    total_paid = sum(p.amount for p in payments)

    branding = await get_branding_settings(db, tenant_id=tid)
    pdf_bytes = generate_invoice_pdf(invoice, customer, plan, payments, total_paid, branding=branding)

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
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    if body.customer_id:
        result = await db.execute(select(Customer).where(Customer.id == body.customer_id, Customer.owner_id == tid))
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        invoice = await billing_service.generate_invoice(db, customer, date.today().replace(day=1), owner_id=tid)
        return {"generated": 1, "skipped": 0, "invoices": [str(invoice.id)]}
    else:
        result = await billing_service.generate_monthly_invoices(db, owner_id=tid)
        return result


@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: uuid.UUID,
    body: InvoiceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.billing)),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.owner_id == tid))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Track changes for audit log
    changes = []
    if body.status is not None and body.status != invoice.status:
        changes.append(f"status: {invoice.status} -> {body.status}")
        invoice.status = body.status
    if body.amount is not None and body.amount != invoice.amount:
        changes.append(f"amount: {invoice.amount} -> {body.amount}")
        invoice.amount = body.amount
    if body.due_date is not None and body.due_date != invoice.due_date:
        changes.append(f"due_date: {invoice.due_date} -> {body.due_date}")
        invoice.due_date = body.due_date

    await db.flush()
    await db.refresh(invoice)

    if changes:
        await log_action(
            db, current_user.id, "invoice.update",
            "invoice", invoice.id,
            details=f"customer={invoice.customer_id} {', '.join(changes)}",
            owner_id=tid,
        )

    return _invoice_to_response(invoice)


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.billing)),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.owner_id == tid))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == InvoiceStatus.paid:
        raise HTTPException(status_code=400, detail="Cannot delete a paid invoice")

    # Delete related payments first
    await db.execute(
        select(Payment).where(Payment.invoice_id == invoice.id)
    )
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Payment).where(Payment.invoice_id == invoice.id))
    await db.delete(invoice)
    await db.flush()
    await log_action(db, current_user.id, "invoice.delete", "invoice", invoice_id, details=f"customer={invoice.customer_id} amount={invoice.amount}", owner_id=tid)


# --- Payment endpoints ---

@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    customer_id: uuid.UUID | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    format: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    query = select(Payment).where(Payment.owner_id == tid)
    count_query = select(func.count(Payment.id)).where(Payment.owner_id == tid)

    if customer_id:
        query = query.join(Invoice).where(Invoice.customer_id == customer_id)
        count_query = count_query.join(Invoice).where(Invoice.customer_id == customer_id)
    if from_date:
        query = query.where(Payment.received_at >= datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc))
        count_query = count_query.where(Payment.received_at >= datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc))
    if to_date:
        query = query.where(Payment.received_at <= datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc))
        count_query = count_query.where(Payment.received_at <= datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc))

    if format == "csv":
        query = query.order_by(Payment.received_at.desc())
        result = await db.execute(query)
        payments = result.scalars().all()
        rows = [
            {
                "customer_name": p.invoice.customer.full_name if p.invoice and p.invoice.customer else "",
                "amount": str(p.amount),
                "method": p.method.value,
                "date": p.received_at.isoformat() if p.received_at else "",
            }
            for p in payments
        ]
        return make_csv_response(rows, "payments.csv")

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
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    try:
        payment = await billing_service.record_payment(
            db=db,
            invoice_id=body.invoice_id,
            amount=body.amount,
            method=body.method,
            reference=body.reference_number,
            received_by=current_user.id,
            owner_id=tid,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    inv = payment.invoice
    await log_action(db, current_user.id, "payment.create", "payment", payment.id, details=f"invoice={payment.invoice_id} amount={payment.amount} method={payment.method}", owner_id=tid)
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
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    return await billing_service.get_revenue_summary(db, from_date, to_date, owner_id=tid)


@router.get("/notifications")
async def list_notifications(
    status_filter: NotificationStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    query = select(Notification).where(Notification.owner_id == tid)
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
