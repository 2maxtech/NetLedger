import logging
import uuid as uuid_mod
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.customer import Customer, CustomerStatus
from app.models.disconnect_log import DisconnectAction, DisconnectLog, DisconnectReason
from app.models.invoice import Invoice, InvoiceStatus
from app.models.app_setting import AppSetting
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.models.payment import Payment
from app.api.admin.settings import get_template_settings, get_payment_settings
from app.services.template_renderer import render_template

logger = logging.getLogger(__name__)


async def _build_payment_url(db: AsyncSession, invoice: "Invoice", tenant_id) -> str:
    """Build a payment URL for an invoice if PayMongo is configured for the tenant."""
    if not invoice.payment_token:
        return ""
    pay_settings = await get_payment_settings(db, tenant_id=tenant_id)
    if not pay_settings.get("paymongo_secret_key"):
        return ""
    return f"{settings.BASE_URL}/pay/{invoice.payment_token}"


async def generate_invoice(db: AsyncSession, customer: Customer, billing_period: date, owner_id: uuid_mod.UUID | None = None) -> Invoice:
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
    due_day = min(customer.billing_due_day or settings.BILLING_DUE_DAY, 28)
    due_date = billing_period.replace(day=due_day)

    # Prorate first invoice: if customer signed up mid-cycle, charge only for days used
    # Skip proration for imported customers (they're existing subscribers)
    amount = plan.monthly_price
    is_imported = customer.email and customer.email.endswith("@imported.local")
    signup_date = customer.created_at.date() if customer.created_at else None
    if not is_imported and signup_date and signup_date.year == billing_period.year and signup_date.month == billing_period.month:
        # First invoice — prorate from signup day to end of month
        import calendar
        days_in_month = calendar.monthrange(billing_period.year, billing_period.month)[1]
        days_used = days_in_month - signup_date.day + 1
        if days_used < days_in_month:
            amount = (plan.monthly_price * Decimal(str(days_used)) / Decimal(str(days_in_month))).quantize(Decimal("0.01"))

    invoice = Invoice(
        customer_id=customer.id,
        plan_id=plan.id,
        amount=amount,
        due_date=due_date,
        status=InvoiceStatus.pending,
        issued_at=datetime.now(timezone.utc),
        owner_id=owner_id or customer.owner_id,
    )
    db.add(invoice)
    await db.flush()
    await db.refresh(invoice)

    # Create email + SMS notifications for the invoice
    try:
        oid = owner_id or customer.owner_id
        if amount > Decimal("0"):
            # Get portal slug for customer portal link
            portal_line = ""
            portal_sms = ""
            slug_result = await db.execute(
                select(AppSetting).where(AppSetting.key == "portal_slug", AppSetting.owner_id == oid)
            )
            slug_setting = slug_result.scalar_one_or_none()
            if slug_setting and slug_setting.value:
                portal_url = f"{settings.BASE_URL}/portal/{slug_setting.value}"
                portal_line = f"\nView your account: {portal_url}\n"
                portal_sms = f" View account: {portal_url}"

            # Build payment URL if PayMongo is configured
            payment_url = await _build_payment_url(db, invoice, oid)

            # Load notification templates
            templates = await get_template_settings(db, tenant_id=oid)
            tpl_vars = {
                "customer_name": customer.full_name,
                "amount": f"₱{amount:,.2f}",
                "plan_name": plan.name,
                "due_date": due_date.strftime("%B %d, %Y"),
                "due_date_short": due_date.strftime("%b %d"),
                "portal_url": portal_line.strip() if portal_line else "",
                "payment_url": payment_url,
            }

            # Email notification
            db.add(Notification(
                customer_id=customer.id,
                type=NotificationType.email,
                subject=render_template(templates["tpl_invoice_email_subject"], tpl_vars),
                message=render_template(templates["tpl_invoice_email_body"], tpl_vars),
                status=NotificationStatus.pending,
                owner_id=oid,
            ))
            # SMS notification
            db.add(Notification(
                customer_id=customer.id,
                type=NotificationType.sms,
                subject="Invoice Generated",
                message=render_template(templates["tpl_invoice_sms"], tpl_vars),
                status=NotificationStatus.pending,
                owner_id=oid,
            ))
    except Exception as e:
        logger.error(f"Failed to create invoice notifications for {customer.id}: {e}")

    return invoice


async def generate_monthly_invoices(db: AsyncSession, owner_id: uuid_mod.UUID | None = None) -> dict:
    """Generate invoices for all active/suspended customers for the current month."""
    today = date.today()
    billing_period = today.replace(day=1)

    query = select(Customer).where(
        Customer.status.in_([CustomerStatus.active, CustomerStatus.suspended]),
        Customer.plan_id.isnot(None),
    )
    if owner_id is not None:
        query = query.where(Customer.owner_id == owner_id)
    result = await db.execute(query)
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

            await generate_invoice(db, cust, billing_period, owner_id=owner_id)
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
    skip_network: bool = False,
    owner_id: uuid_mod.UUID | None = None,
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
        owner_id=owner_id or invoice.owner_id,
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
                if not skip_network:
                    if customer.mikrotik_secret_id:
                        from app.services.mikrotik import get_client_for_customer
                        try:
                            client, _ = await get_client_for_customer(db, customer)
                            if client:
                                await client.enable_secret(customer.mikrotik_secret_id)
                                if customer.plan:
                                    profile_name = customer.plan.name
                                    rate_limit = f"{customer.plan.upload_mbps}M/{customer.plan.download_mbps}M"
                                    await client.ensure_profile(
                                        profile_name, rate_limit,
                                        local_address=customer.plan.local_address,
                                        remote_address=customer.plan.remote_address,
                                        dns_server=customer.plan.dns_server,
                                        parent_queue=customer.plan.parent_queue,
                                    )
                                    await client.update_secret(customer.mikrotik_secret_id, {"profile": profile_name})
                                try:
                                    await client.enable_user_queues(customer.pppoe_username)
                                except Exception as qe:
                                    logger.warning(f"Enable shadow queues failed for {customer.id}: {qe}")
                        except Exception as e:
                            logger.error(f"MikroTik enable failed for {customer.id}: {e}")
                    else:
                        logger.warning(f"Customer {customer.id} has no mikrotik_secret_id, skipping")

                    # Remove NAT redirect (browser notification no longer needed)
                    try:
                        from app.services.nat_redirect import remove_redirect_for_customer
                        await remove_redirect_for_customer(db, customer)
                    except Exception as e:
                        logger.warning(f"NAT redirect removal failed for {customer.id}: {e}")

                customer.status = CustomerStatus.active
                log = DisconnectLog(
                    customer_id=customer.id,
                    action=DisconnectAction.reconnect,
                    reason=DisconnectReason.non_payment,
                    performed_by=None,
                    performed_at=datetime.now(timezone.utc),
                    owner_id=customer.owner_id,
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


async def _get_tenant_billing_cfg(db: AsyncSession, tenant_id) -> dict:
    """Get tenant-specific billing settings, with global fallback."""
    from app.models.app_setting import AppSetting
    defaults = {
        "billing_throttle_days_after_due": str(settings.BILLING_THROTTLE_DAYS_AFTER_DUE),
        "billing_disconnect_days_after_due": str(settings.BILLING_DISCONNECT_DAYS_AFTER_DUE),
        "billing_terminate_days_after_due": str(settings.BILLING_TERMINATE_DAYS_AFTER_DUE),
    }
    if tenant_id:
        result = await db.execute(
            select(AppSetting).where(
                AppSetting.key.in_(defaults.keys()),
                AppSetting.owner_id == tenant_id,
            )
        )
        for s in result.scalars().all():
            defaults[s.key] = s.value
    return {
        "throttle": int(defaults["billing_throttle_days_after_due"]),
        "disconnect": int(defaults["billing_disconnect_days_after_due"]),
        "terminate": int(defaults["billing_terminate_days_after_due"]),
    }


async def process_graduated_disconnect(db: AsyncSession, skip_network: bool = False) -> dict:
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

    # Cache tenant configs
    _cfg_cache: dict = {}

    for inv in invoices:
        customer = inv.customer
        days_overdue = (today - inv.due_date).days

        # Get tenant-specific settings
        tid = str(inv.owner_id) if inv.owner_id else None
        if tid not in _cfg_cache:
            _cfg_cache[tid] = await _get_tenant_billing_cfg(db, inv.owner_id)
        cfg = _cfg_cache[tid]

        try:
            # Throttle: customer is active and overdue enough
            if (
                days_overdue >= cfg["throttle"]
                and customer.status == CustomerStatus.active
            ):
                if not skip_network:
                    if customer.mikrotik_secret_id:
                        from app.services.mikrotik import get_client_for_customer
                        try:
                            client, _ = await get_client_for_customer(db, customer)
                            if client:
                                throttle_name = f"{settings.THROTTLE_DOWNLOAD_MBPS}M-throttle"
                                throttle_rate = f"{settings.THROTTLE_UPLOAD_KBPS}k/{settings.THROTTLE_DOWNLOAD_MBPS}M"
                                await client.ensure_profile(throttle_name, throttle_rate)
                                await client.update_secret(customer.mikrotik_secret_id, {"profile": throttle_name})
                                try:
                                    await client.disable_user_queues(customer.pppoe_username)
                                except Exception as qe:
                                    logger.warning(f"Disable shadow queues failed for {customer.id}: {qe}")
                                await client.kick_session(customer.pppoe_username)
                        except Exception as e:
                            logger.error(f"MikroTik throttle failed for {customer.id}: {e}")
                    else:
                        logger.warning(f"Customer {customer.id} has no mikrotik_secret_id, skipping")

                    # Add NAT redirect so customer's browser shows payment notice
                    try:
                        from app.services.nat_redirect import add_redirect_for_customer
                        await add_redirect_for_customer(db, customer)
                    except Exception as e:
                        logger.warning(f"NAT redirect add failed for {customer.id}: {e}")

                customer.status = CustomerStatus.suspended
                db.add(DisconnectLog(
                    customer_id=customer.id,
                    action=DisconnectAction.throttle,
                    reason=DisconnectReason.non_payment,
                    performed_by=None,
                    performed_at=datetime.now(timezone.utc),
                    owner_id=customer.owner_id,
                ))
                throttled += 1

            # Disconnect: customer is suspended and overdue enough
            elif (
                days_overdue >= cfg["disconnect"]
                and customer.status == CustomerStatus.suspended
            ):
                if not skip_network:
                    if customer.mikrotik_secret_id:
                        from app.services.mikrotik import get_client_for_customer
                        try:
                            client, _ = await get_client_for_customer(db, customer)
                            if client:
                                try:
                                    await client.disable_user_queues(customer.pppoe_username)
                                except Exception as qe:
                                    logger.warning(f"Disable shadow queues failed for {customer.id}: {qe}")
                                await client.disable_secret(customer.mikrotik_secret_id)
                                await client.kick_session(customer.pppoe_username)
                        except Exception as e:
                            logger.error(f"MikroTik disconnect failed for {customer.id}: {e}")
                    else:
                        logger.warning(f"Customer {customer.id} has no mikrotik_secret_id, skipping")

                customer.status = CustomerStatus.disconnected
                db.add(DisconnectLog(
                    customer_id=customer.id,
                    action=DisconnectAction.disconnect,
                    reason=DisconnectReason.non_payment,
                    performed_by=None,
                    performed_at=datetime.now(timezone.utc),
                    owner_id=customer.owner_id,
                ))
                disconnected += 1

            # Flag for termination
            elif days_overdue >= cfg["terminate"]:
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
        # Build payment URL if PayMongo is configured
        payment_url = await _build_payment_url(db, inv, customer.owner_id)

        # Load templates for this customer's tenant
        templates = await get_template_settings(db, tenant_id=customer.owner_id)
        tpl_vars = {
            "customer_name": customer.full_name,
            "amount": f"₱{inv.amount}",
            "due_date": str(inv.due_date),
            "due_date_short": inv.due_date.strftime("%b %d") if hasattr(inv.due_date, 'strftime') else str(inv.due_date),
            "portal_url": "",
            "payment_url": payment_url,
        }
        notification = Notification(
            customer_id=customer.id,
            type=NotificationType.sms,
            subject="Payment Reminder",
            message=render_template(templates["tpl_reminder_sms"], tpl_vars),
            status=NotificationStatus.pending,
            owner_id=customer.owner_id,
        )
        db.add(notification)

    await db.flush()
    return len(invoices)


async def get_revenue_summary(db: AsyncSession, start_date: date, end_date: date, owner_id: uuid_mod.UUID | None = None) -> dict:
    """Get revenue summary for a date range."""
    invoice_filters = [
        Invoice.issued_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc),
        Invoice.issued_at <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc),
        Invoice.status != InvoiceStatus.void,
    ]
    if owner_id is not None:
        invoice_filters.append(Invoice.owner_id == owner_id)

    billed_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(and_(*invoice_filters))
    )
    total_billed = billed_result.scalar() or Decimal("0")

    payment_filters = [
        Payment.received_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc),
        Payment.received_at <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc),
    ]
    if owner_id is not None:
        payment_filters.append(Payment.owner_id == owner_id)

    collected_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(and_(*payment_filters))
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
