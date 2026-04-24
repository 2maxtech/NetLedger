"""Public payment endpoints — no auth required.

GET  /pay/{token}           — invoice summary for payment page
POST /pay/{token}/checkout  — create PayMongo checkout session
GET  /pay/{token}/success   — success redirect info
GET  /pay/{token}/cancel    — cancel redirect info
POST /webhooks/paymongo     — PayMongo webhook receiver
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.app_setting import AppSetting
from app.models.customer import Customer, CustomerStatus
from app.models.disconnect_log import DisconnectAction, DisconnectLog, DisconnectReason
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentMethod
from app.services import paymongo as paymongo_svc
from app.services.audit import log_action

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payment"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_invoice_by_token(db: AsyncSession, token: str) -> Invoice | None:
    """Look up an invoice by its payment_token UUID."""
    try:
        token_uuid = uuid.UUID(token)
    except ValueError:
        return None
    result = await db.execute(
        select(Invoice).where(Invoice.payment_token == token_uuid)
    )
    return result.scalar_one_or_none()


async def _load_tenant_settings(db: AsyncSession, owner_id: uuid.UUID, keys: list[str]) -> dict:
    """Load app_settings for a tenant, returning a dict of key->value."""
    result = await db.execute(
        select(AppSetting).where(
            AppSetting.key.in_(keys),
            AppSetting.owner_id == owner_id,
        )
    )
    return {s.key: s.value for s in result.scalars().all()}


# ---------------------------------------------------------------------------
# GET /pay/{token} — invoice details for payment page
# ---------------------------------------------------------------------------

@router.get("/pay/{token}")
async def get_payment_info(token: str, db: AsyncSession = Depends(get_db)):
    """Return invoice and branding info for the public payment page."""
    invoice = await _get_invoice_by_token(db, token)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == InvoiceStatus.paid:
        return {
            "status": "paid",
            "customer_name": invoice.customer.full_name if invoice.customer else "",
            "amount": float(invoice.amount),
            "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        }
    if invoice.status == InvoiceStatus.void:
        raise HTTPException(status_code=410, detail="Invoice has been voided")

    customer = invoice.customer
    plan = invoice.plan

    # Load branding + fee settings for the tenant
    setting_keys = [
        "company_name", "company_logo_url", "primary_color",
        "paymongo_fee_mode", "paymongo_fee_percent", "paymongo_fee_flat",
        "paymongo_public_key",
    ]
    tenant_settings = await _load_tenant_settings(db, invoice.owner_id, setting_keys)

    fee_mode = tenant_settings.get("paymongo_fee_mode", "pass_to_customer")
    fee_percent = Decimal(tenant_settings.get("paymongo_fee_percent", "2.5"))
    fee_flat = Decimal(tenant_settings.get("paymongo_fee_flat", "15"))

    total, convenience_fee = paymongo_svc.calculate_total(
        invoice.amount, fee_mode, fee_percent, fee_flat,
    )

    return {
        "status": invoice.status.value,
        "customer_name": customer.full_name if customer else "",
        "plan_name": plan.name if plan else "",
        "amount": float(invoice.amount),
        "convenience_fee": float(convenience_fee),
        "total": float(total),
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "company_name": tenant_settings.get("company_name", ""),
        "logo_url": tenant_settings.get("company_logo_url", ""),
        "primary_color": tenant_settings.get("primary_color", "#4f46e5"),
        "paymongo_public_key": tenant_settings.get("paymongo_public_key", ""),
    }


# ---------------------------------------------------------------------------
# POST /pay/{token}/checkout — create PayMongo checkout session
# ---------------------------------------------------------------------------

@router.post("/pay/{token}/checkout")
async def create_checkout(token: str, db: AsyncSession = Depends(get_db)):
    """Create a PayMongo checkout session and return the redirect URL."""
    invoice = await _get_invoice_by_token(db, token)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == InvoiceStatus.paid:
        raise HTTPException(status_code=400, detail="Invoice already paid")
    if invoice.status == InvoiceStatus.void:
        raise HTTPException(status_code=410, detail="Invoice has been voided")

    # Load PayMongo keys + fee settings
    pm_keys = [
        "paymongo_secret_key",
        "paymongo_fee_mode", "paymongo_fee_percent", "paymongo_fee_flat",
    ]
    tenant_settings = await _load_tenant_settings(db, invoice.owner_id, pm_keys)
    secret_key = tenant_settings.get("paymongo_secret_key", "")
    if not secret_key:
        raise HTTPException(status_code=400, detail="Online payments not configured for this provider")

    fee_mode = tenant_settings.get("paymongo_fee_mode", "pass_to_customer")
    fee_percent = Decimal(tenant_settings.get("paymongo_fee_percent", "2.5"))
    fee_flat = Decimal(tenant_settings.get("paymongo_fee_flat", "15"))

    total, convenience_fee = paymongo_svc.calculate_total(
        invoice.amount, fee_mode, fee_percent, fee_flat,
    )

    # Convert to centavos (PayMongo uses integer centavos)
    amount_centavos = int(total * 100)

    customer_name = invoice.customer.full_name if invoice.customer else "Customer"
    plan_name = invoice.plan.name if invoice.plan else "Service"
    description = f"{customer_name} - {plan_name}"

    base_url = settings.BASE_URL
    success_url = f"{base_url}/pay/{token}/success"
    cancel_url = f"{base_url}/pay/{token}/cancel"

    try:
        result = await paymongo_svc.create_checkout_session(
            secret_key=secret_key,
            amount_centavos=amount_centavos,
            description=description,
            reference_number=str(invoice.id),
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as e:
        logger.error(f"PayMongo checkout creation failed for invoice {invoice.id}: {e}")
        raise HTTPException(status_code=502, detail="Failed to create checkout session")

    # Store checkout session ID as a pending payment record
    pending_payment = Payment(
        invoice_id=invoice.id,
        amount=total,
        method=PaymentMethod.online,
        reference_number=result["checkout_session_id"],
        received_at=datetime.now(timezone.utc),
        owner_id=invoice.owner_id,
        paymongo_checkout_id=result["checkout_session_id"],
        convenience_fee=convenience_fee if convenience_fee > 0 else None,
    )
    db.add(pending_payment)

    await log_action(
        db,
        user_id=None,
        action="paymongo_checkout_created",
        entity_type="invoice",
        entity_id=invoice.id,
        details=f"Checkout session {result['checkout_session_id']} created, total={total}",
        owner_id=invoice.owner_id,
    )
    await db.flush()

    return {"checkout_url": result["checkout_url"]}


# ---------------------------------------------------------------------------
# GET /pay/{token}/success and /pay/{token}/cancel
# ---------------------------------------------------------------------------

@router.get("/pay/{token}/success")
async def payment_success(token: str):
    """Success redirect — frontend handles display."""
    return {"status": "success", "token": token}


@router.get("/pay/{token}/cancel")
async def payment_cancel(token: str):
    """Cancel redirect — frontend handles display."""
    return {"status": "cancelled", "token": token}


# ---------------------------------------------------------------------------
# POST /webhooks/paymongo — PayMongo webhook receiver
# ---------------------------------------------------------------------------

@router.post("/webhooks/paymongo")
async def paymongo_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive and process PayMongo webhook events.

    Always returns 200 to PayMongo regardless of processing outcome.
    """
    try:
        raw_body = await request.body()
        signature_header = request.headers.get("paymongo-signature", "")

        # Parse JSON payload
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            logger.error("PayMongo webhook: invalid JSON body")
            return Response(status_code=200)

        event_type = payload.get("data", {}).get("attributes", {}).get("type", "")
        logger.info(f"PayMongo webhook received: {event_type}")

        if event_type != "checkout_session.payment.paid":
            # Not an event we handle — ack and move on
            return Response(status_code=200)

        # Extract checkout session data from the event
        event_data = payload["data"]["attributes"]["data"]
        checkout_attrs = event_data.get("attributes", {})
        checkout_session_id = event_data.get("id", "")
        reference_number = checkout_attrs.get("reference_number", "")

        if not reference_number:
            logger.error(f"PayMongo webhook: no reference_number in checkout session {checkout_session_id}")
            return Response(status_code=200)

        # reference_number is the invoice ID
        try:
            invoice_id = uuid.UUID(reference_number)
        except ValueError:
            logger.error(f"PayMongo webhook: invalid invoice reference_number: {reference_number}")
            return Response(status_code=200)

        # Load the invoice
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
        invoice = result.scalar_one_or_none()
        if not invoice:
            logger.error(f"PayMongo webhook: invoice {invoice_id} not found")
            return Response(status_code=200)

        # Idempotency: if already paid, just ack
        if invoice.status == InvoiceStatus.paid:
            logger.info(f"PayMongo webhook: invoice {invoice_id} already paid, skipping")
            return Response(status_code=200)

        # Verify webhook signature using tenant's webhook secret
        wh_settings = await _load_tenant_settings(
            db, invoice.owner_id, ["paymongo_webhook_secret"]
        )
        webhook_secret = wh_settings.get("paymongo_webhook_secret", "")
        if webhook_secret and signature_header:
            if not paymongo_svc.verify_webhook_signature(raw_body, signature_header, webhook_secret):
                logger.warning(f"PayMongo webhook: signature verification failed for invoice {invoice_id}")
                return Response(status_code=200)

        # Check if we already have a pending payment record from checkout creation
        pay_result = await db.execute(
            select(Payment).where(
                Payment.paymongo_checkout_id == checkout_session_id,
                Payment.invoice_id == invoice.id,
            )
        )
        existing_payment = pay_result.scalar_one_or_none()

        # Load fee settings to calculate convenience_fee
        fee_settings = await _load_tenant_settings(
            db, invoice.owner_id,
            ["paymongo_fee_mode", "paymongo_fee_percent", "paymongo_fee_flat"],
        )
        fee_mode = fee_settings.get("paymongo_fee_mode", "pass_to_customer")
        fee_percent = Decimal(fee_settings.get("paymongo_fee_percent", "2.5"))
        fee_flat = Decimal(fee_settings.get("paymongo_fee_flat", "15"))
        total, convenience_fee = paymongo_svc.calculate_total(
            invoice.amount, fee_mode, fee_percent, fee_flat,
        )

        if existing_payment:
            # Update the pending payment record — it was a placeholder from checkout
            existing_payment.amount = total
            existing_payment.convenience_fee = convenience_fee if convenience_fee > 0 else None
            existing_payment.received_at = datetime.now(timezone.utc)
        else:
            # No pending record (unusual) — create a new one
            payment = Payment(
                invoice_id=invoice.id,
                amount=total,
                method=PaymentMethod.online,
                reference_number=checkout_session_id,
                received_at=datetime.now(timezone.utc),
                owner_id=invoice.owner_id,
                paymongo_checkout_id=checkout_session_id,
                convenience_fee=convenience_fee if convenience_fee > 0 else None,
            )
            db.add(payment)

        # Mark invoice as paid
        invoice.status = InvoiceStatus.paid
        invoice.paid_at = datetime.now(timezone.utc)

        # Auto-reconnect if customer was suspended/disconnected
        cust_result = await db.execute(select(Customer).where(Customer.id == invoice.customer_id))
        customer = cust_result.scalar_one_or_none()

        if customer and customer.status in (CustomerStatus.suspended, CustomerStatus.disconnected):
            # Check for other overdue invoices
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
                # Re-enable on MikroTik
                if customer.mikrotik_secret_id:
                    try:
                        from app.services.mikrotik import get_client_for_customer
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
                                logger.warning(f"Enable shadow queues via webhook failed for {customer.id}: {qe}")
                    except Exception as e:
                        logger.error(f"MikroTik reconnect via webhook failed for {customer.id}: {e}")

                # Remove NAT redirect (browser notification no longer needed)
                try:
                    from app.services.nat_redirect import remove_redirect_for_customer
                    await remove_redirect_for_customer(db, customer)
                except Exception as e:
                    logger.warning(f"NAT redirect removal via webhook failed for {customer.id}: {e}")

                customer.status = CustomerStatus.active
                db.add(DisconnectLog(
                    customer_id=customer.id,
                    action=DisconnectAction.reconnect,
                    reason=DisconnectReason.non_payment,
                    performed_by=None,
                    performed_at=datetime.now(timezone.utc),
                    owner_id=customer.owner_id,
                ))

        await log_action(
            db,
            user_id=None,
            action="paymongo_payment_received",
            entity_type="invoice",
            entity_id=invoice.id,
            details=f"PayMongo checkout {checkout_session_id} paid, amount={total}, fee={convenience_fee}",
            owner_id=invoice.owner_id,
        )
        await db.flush()

        logger.info(f"PayMongo webhook: invoice {invoice_id} marked as paid via {checkout_session_id}")

    except Exception:
        logger.exception("PayMongo webhook processing error")

    # Always return 200 to PayMongo
    return Response(status_code=200)
