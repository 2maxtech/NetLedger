import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.customer import Customer, CustomerStatus
from app.models.disconnect_log import DisconnectAction, DisconnectLog, DisconnectReason
from app.models.invoice import Invoice, InvoiceStatus
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.models.payment import Payment

logger = logging.getLogger(__name__)


async def generate_invoice(db: AsyncSession, customer: Customer, billing_period: date) -> Invoice:
    """Generate an invoice for a customer. Idempotent — skips if one already exists for the period."""
    result = await db.execute(
        select(Invoice).where(
            and_(
                Invoice.customer_id == customer.id,
                extract("year", Invoice.issued_at) == billing_period.year,
                extract("month", Invoice.issued_at) == billing_period.month,
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    plan = customer.plan
    due_day = min(settings.BILLING_DUE_DAY, 28)
    due_date = billing_period.replace(day=due_day)

    invoice = Invoice(
        customer_id=customer.id,
        plan_id=plan.id,
        amount=plan.monthly_price,
        due_date=due_date,
        status=InvoiceStatus.pending,
        issued_at=datetime.now(timezone.utc),
    )
    db.add(invoice)
    await db.flush()
    await db.refresh(invoice)
    return invoice


async def generate_monthly_invoices(db: AsyncSession) -> dict:
    """Generate invoices for all active/suspended customers for the current month."""
    today = date.today()
    billing_period = today.replace(day=1)

    result = await db.execute(
        select(Customer).where(
            Customer.status.in_([CustomerStatus.active, CustomerStatus.suspended]),
            Customer.plan_id.isnot(None),
        )
    )
    customers = result.scalars().all()

    generated = 0
    skipped = 0
    errors = []

    for cust in customers:
        try:
            existing = await db.execute(
                select(Invoice).where(
                    and_(
                        Invoice.customer_id == cust.id,
                        extract("year", Invoice.issued_at) == billing_period.year,
                        extract("month", Invoice.issued_at) == billing_period.month,
                    )
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            await generate_invoice(db, cust, billing_period)
            generated += 1
        except Exception as e:
            logger.error(f"Failed to generate invoice for customer {cust.id}: {e}")
            errors.append({"customer_id": str(cust.id), "error": str(e)})

    return {"generated": generated, "skipped": skipped, "errors": errors}


async def record_payment(
    db: AsyncSession,
    invoice_id,
    amount: Decimal,
    method,
    reference: str | None,
    received_by=None,
    skip_gateway: bool = False,
) -> Payment:
    """Record a payment against an invoice. Auto-reconnects if fully paid and customer was suspended/disconnected."""
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")

    payment = Payment(
        invoice_id=invoice.id,
        amount=amount,
        method=method,
        reference_number=reference,
        received_by=received_by,
        received_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    await db.flush()

    # Check if invoice is fully paid
    pay_result = await db.execute(
        select(func.sum(Payment.amount)).where(Payment.invoice_id == invoice.id)
    )
    total_paid = pay_result.scalar() or Decimal("0")

    if total_paid >= invoice.amount:
        invoice.status = InvoiceStatus.paid
        invoice.paid_at = datetime.now(timezone.utc)

        # Auto-reconnect if customer was suspended/disconnected and no other overdue invoices
        cust_result = await db.execute(select(Customer).where(Customer.id == invoice.customer_id))
        customer = cust_result.scalar_one_or_none()
        if customer.status in (CustomerStatus.suspended, CustomerStatus.disconnected):
            other_overdue = await db.execute(
                select(Invoice).where(
                    and_(
                        Invoice.customer_id == customer.id,
                        Invoice.id != invoice.id,
                        Invoice.status == InvoiceStatus.overdue,
                    )
                )
            )
            if not other_overdue.scalars().first():
                if not skip_gateway:
                    logger.info(f"Kerio integration pending: reconnect {customer.id}")
                    # Kerio adapter will be wired here

                customer.status = CustomerStatus.active
                log = DisconnectLog(
                    customer_id=customer.id,
                    action=DisconnectAction.reconnect,
                    reason=DisconnectReason.non_payment,
                    performed_by=None,
                    performed_at=datetime.now(timezone.utc),
                )
                db.add(log)

    await db.flush()
    await db.refresh(payment)
    return payment


async def check_overdue_invoices(db: AsyncSession) -> int:
    """Mark pending invoices past due date as overdue."""
    today = date.today()
    result = await db.execute(
        select(Invoice).where(
            and_(
                Invoice.status == InvoiceStatus.pending,
                Invoice.due_date < today,
            )
        )
    )
    invoices = result.scalars().all()
    for inv in invoices:
        inv.status = InvoiceStatus.overdue
    await db.flush()
    return len(invoices)


async def process_graduated_disconnect(db: AsyncSession, skip_gateway: bool = False) -> dict:
    """Apply graduated disconnect enforcement on overdue invoices."""
    today = date.today()
    result = await db.execute(
        select(Invoice).where(Invoice.status == InvoiceStatus.overdue)
    )
    invoices = result.scalars().all()

    throttled = 0
    disconnected = 0
    flagged = 0
    errors = []

    for inv in invoices:
        customer = inv.customer
        days_overdue = (today - inv.due_date).days

        try:
            # Throttle: customer is active and overdue enough
            if (
                days_overdue >= settings.BILLING_THROTTLE_DAYS_AFTER_DUE
                and customer.status == CustomerStatus.active
            ):
                if not skip_gateway:
                    logger.info(f"Kerio integration pending: throttle {customer.id}")
                    # Kerio adapter will be wired here

                customer.status = CustomerStatus.suspended
                db.add(DisconnectLog(
                    customer_id=customer.id,
                    action=DisconnectAction.throttle,
                    reason=DisconnectReason.non_payment,
                    performed_by=None,
                    performed_at=datetime.now(timezone.utc),
                ))
                throttled += 1

            # Disconnect: customer is suspended and overdue enough
            elif (
                days_overdue >= settings.BILLING_DISCONNECT_DAYS_AFTER_DUE
                and customer.status == CustomerStatus.suspended
            ):
                if not skip_gateway:
                    logger.info(f"Kerio integration pending: disconnect {customer.id}")
                    # Kerio adapter will be wired here

                customer.status = CustomerStatus.disconnected
                db.add(DisconnectLog(
                    customer_id=customer.id,
                    action=DisconnectAction.disconnect,
                    reason=DisconnectReason.non_payment,
                    performed_by=None,
                    performed_at=datetime.now(timezone.utc),
                ))
                disconnected += 1

            # Flag for termination
            elif days_overdue >= settings.BILLING_TERMINATE_DAYS_AFTER_DUE:
                flagged += 1

        except Exception as e:
            logger.error(f"Graduated disconnect failed for customer {customer.id}: {e}")
            errors.append({"customer_id": str(customer.id), "error": str(e)})

    await db.flush()
    return {"throttled": throttled, "disconnected": disconnected, "flagged": flagged, "errors": errors}


async def send_billing_reminders(db: AsyncSession) -> int:
    """Create notification records for invoices due in BILLING_REMINDER_DAYS_BEFORE_DUE days."""
    from datetime import timedelta
    today = date.today()
    reminder_date = today + timedelta(days=settings.BILLING_REMINDER_DAYS_BEFORE_DUE)

    result = await db.execute(
        select(Invoice).where(
            and_(
                Invoice.status == InvoiceStatus.pending,
                Invoice.due_date == reminder_date,
            )
        )
    )
    invoices = result.scalars().all()

    for inv in invoices:
        customer = inv.customer
        notification = Notification(
            customer_id=customer.id,
            type=NotificationType.sms,
            subject="Payment Reminder",
            message=f"Hi {customer.full_name}, your bill of ₱{inv.amount} is due on {inv.due_date}. Please pay before the due date to avoid service interruption.",
            status=NotificationStatus.pending,
        )
        db.add(notification)

    await db.flush()
    return len(invoices)


async def get_revenue_summary(db: AsyncSession, start_date: date, end_date: date) -> dict:
    """Get revenue summary for a date range."""
    billed_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            and_(
                Invoice.issued_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                Invoice.issued_at <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc),
                Invoice.status != InvoiceStatus.void,
            )
        )
    )
    total_billed = billed_result.scalar() or Decimal("0")

    collected_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            and_(
                Payment.received_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                Payment.received_at <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc),
            )
        )
    )
    total_collected = collected_result.scalar() or Decimal("0")

    total_outstanding = total_billed - total_collected
    collection_rate = float(total_collected / total_billed * 100) if total_billed > 0 else 0.0

    return {
        "total_billed": total_billed,
        "total_collected": total_collected,
        "total_outstanding": total_outstanding,
        "collection_rate": round(collection_rate, 1),
    }
