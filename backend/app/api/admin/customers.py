import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.tenant import get_tenant_id
from app.models.bandwidth_usage import BandwidthUsage
from app.models.customer import Customer, CustomerStatus
from app.models.customer_activity import CustomerActivity
from app.models.disconnect_log import DisconnectAction, DisconnectLog, DisconnectReason
from app.models.invoice import Invoice
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.models.payment import Payment
from app.models.pppoe_session import PPPoESession
from app.models.session_traffic import SessionTraffic
from app.models.ticket import Ticket, TicketMessage
from app.models.user import User
from app.schemas.customer import (
    BulkActionResponse,
    BulkChangeStatusRequest,
    BulkCustomerIdsRequest,
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
)
from app.services import billing as billing_service
from app.services.audit import log_action
from app.services.mikrotik import get_client_for_customer
from app.utils.csv_export import make_csv_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: CustomerStatus | None = Query(None, alias="status"),
    search: str | None = Query(None),
    format: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    query = select(Customer).where(Customer.owner_id == tid)
    count_query = select(func.count(Customer.id)).where(Customer.owner_id == tid)

    if status_filter:
        query = query.where(Customer.status == status_filter)
        count_query = count_query.where(Customer.status == status_filter)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Customer.full_name.ilike(search_filter))
            | (Customer.email.ilike(search_filter))
            | (Customer.pppoe_username.ilike(search_filter))
        )
        count_query = count_query.where(
            (Customer.full_name.ilike(search_filter))
            | (Customer.email.ilike(search_filter))
            | (Customer.pppoe_username.ilike(search_filter))
        )

    if format == "csv":
        query = query.order_by(Customer.created_at.desc())
        result = await db.execute(query)
        customers = result.scalars().all()
        rows = [
            {
                "full_name": c.full_name,
                "email": c.email or "",
                "phone": c.phone or "",
                "pppoe_username": c.pppoe_username,
                "plan_name": c.plan.name if c.plan else "",
                "status": c.status.value,
                "area_name": c.area.name if c.area else "",
                "created_at": c.created_at.isoformat() if c.created_at else "",
            }
            for c in customers
        ]
        return make_csv_response(rows, "customers.csv")

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(Customer.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)

    return CustomerListResponse(
        items=result.scalars().all(),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    customer = Customer(**body.model_dump())
    customer.owner_id = uuid.UUID(tenant_id)
    db.add(customer)
    await db.flush()
    await db.refresh(customer, ['plan', 'area'])

    # Auto-provision PPPoE secret on MikroTik with plan profile
    try:
        client, _ = await get_client_for_customer(db, customer)
        if client:
            plan = customer.plan
            profile = "default"
            if plan:
                profile_name = plan.name
                rate_limit = f"{plan.upload_mbps}M/{plan.download_mbps}M"
                profile = await client.ensure_profile(
                    profile_name, rate_limit,
                    local_address=plan.local_address,
                    remote_address=plan.remote_address,
                    dns_server=plan.dns_server,
                    parent_queue=plan.parent_queue,
                )

            secret_id = await client.create_secret(
                name=customer.pppoe_username,
                password=customer.pppoe_password,
                profile=profile,
                caller_id=customer.mac_address,
            )
            customer.mikrotik_secret_id = secret_id
            await db.flush()
            await db.refresh(customer)
    except Exception as e:
        logger.warning(f"MikroTik provisioning failed for {customer.id}: {e}")

    await log_action(db, current_user.id, "customer.create", "customer", customer.id, owner_id=uuid.UUID(tenant_id))
    return customer


# --- Bulk action endpoints (must be before /{customer_id} routes) ---


@router.post("/bulk/generate-invoices", response_model=BulkActionResponse)
async def bulk_generate_invoices(
    body: BulkCustomerIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Generate invoices for multiple customers at once."""
    tid = uuid.UUID(tenant_id)
    billing_period = date.today().replace(day=1)
    success = 0
    failed = 0
    errors = []

    for cid in body.customer_ids:
        try:
            result = await db.execute(
                select(Customer).where(Customer.id == cid, Customer.owner_id == tid)
            )
            customer = result.scalar_one_or_none()
            if not customer:
                failed += 1
                errors.append({"customer_id": str(cid), "error": "Customer not found"})
                continue
            if not customer.plan_id:
                failed += 1
                errors.append({"customer_id": str(cid), "error": "Customer has no plan assigned"})
                continue

            await billing_service.generate_invoice(db, customer, billing_period, owner_id=tid)
            success += 1
        except Exception as e:
            failed += 1
            errors.append({"customer_id": str(cid), "error": str(e)})

    await db.flush()
    return BulkActionResponse(success=success, failed=failed, errors=errors)


@router.post("/bulk/send-reminder", response_model=BulkActionResponse)
async def bulk_send_reminder(
    body: BulkCustomerIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Send payment reminder notifications to multiple customers."""
    from app.api.admin.settings import get_template_settings
    from app.services.template_renderer import render_template

    tid = uuid.UUID(tenant_id)
    success = 0
    failed = 0
    errors = []

    templates = await get_template_settings(db, tenant_id=tid)

    for cid in body.customer_ids:
        try:
            result = await db.execute(
                select(Customer).where(Customer.id == cid, Customer.owner_id == tid)
            )
            customer = result.scalar_one_or_none()
            if not customer:
                failed += 1
                errors.append({"customer_id": str(cid), "error": "Customer not found"})
                continue

            # Find the latest unpaid invoice for this customer
            inv_result = await db.execute(
                select(Invoice).where(
                    Invoice.customer_id == cid,
                    Invoice.status.in_(["pending", "overdue"]),
                ).order_by(Invoice.due_date.desc()).limit(1)
            )
            invoice = inv_result.scalar_one_or_none()
            if not invoice:
                failed += 1
                errors.append({"customer_id": str(cid), "error": "No unpaid invoice found"})
                continue

            tpl_vars = {
                "customer_name": customer.full_name,
                "amount": f"\u20b1{invoice.amount:,.2f}",
                "due_date": str(invoice.due_date),
                "due_date_short": invoice.due_date.strftime("%b %d") if hasattr(invoice.due_date, "strftime") else str(invoice.due_date),
                "portal_url": "",
            }

            # Create SMS reminder
            db.add(Notification(
                customer_id=customer.id,
                type=NotificationType.sms,
                subject="Payment Reminder",
                message=render_template(templates["tpl_reminder_sms"], tpl_vars),
                status=NotificationStatus.pending,
                owner_id=tid,
            ))
            # Create email reminder if customer has valid email
            if customer.email and not customer.email.endswith("@imported.local"):
                db.add(Notification(
                    customer_id=customer.id,
                    type=NotificationType.email,
                    subject=render_template(templates.get("tpl_reminder_email_subject", "Payment Reminder"), tpl_vars),
                    message=render_template(templates.get("tpl_reminder_email_body", "Hi {customer_name}, your bill of {amount} is due on {due_date}."), tpl_vars),
                    status=NotificationStatus.pending,
                    owner_id=tid,
                ))
            success += 1
        except Exception as e:
            failed += 1
            errors.append({"customer_id": str(cid), "error": str(e)})

    await db.flush()
    return BulkActionResponse(success=success, failed=failed, errors=errors)


@router.post("/bulk/change-status", response_model=BulkActionResponse)
async def bulk_change_status(
    body: BulkChangeStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Change status for multiple customers at once."""
    tid = uuid.UUID(tenant_id)
    success = 0
    failed = 0
    errors = []

    for cid in body.customer_ids:
        try:
            result = await db.execute(
                select(Customer).where(Customer.id == cid, Customer.owner_id == tid)
            )
            customer = result.scalar_one_or_none()
            if not customer:
                failed += 1
                errors.append({"customer_id": str(cid), "error": "Customer not found"})
                continue

            old_status = customer.status
            customer.status = body.status
            await log_action(
                db, current_user.id, "customer.bulk_status",
                "customer", customer.id,
                details=f"{old_status.value} -> {body.status.value}",
                owner_id=tid,
            )
            success += 1
        except Exception as e:
            failed += 1
            errors.append({"customer_id": str(cid), "error": str(e)})

    await db.flush()
    return BulkActionResponse(success=success, failed=failed, errors=errors)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    updated_fields = body.model_dump(exclude_unset=True)
    for field, value in updated_fields.items():
        setattr(customer, field, value)

    await db.flush()
    await db.refresh(customer, ['plan'])

    # Sync PPPoE credential / plan changes to MikroTik
    mt_fields = {"pppoe_password", "pppoe_username", "mac_address", "plan_id"}
    if mt_fields & updated_fields.keys() and customer.mikrotik_secret_id:
        try:
            client, _ = await get_client_for_customer(db, customer)
            if client:
                secret_update: dict[str, str] = {}
                if "pppoe_password" in updated_fields:
                    secret_update["password"] = customer.pppoe_password
                if "pppoe_username" in updated_fields:
                    secret_update["name"] = customer.pppoe_username
                if "mac_address" in updated_fields:
                    secret_update["caller-id"] = customer.mac_address or ""
                if "plan_id" in updated_fields and customer.plan:
                    plan = customer.plan
                    profile_name = plan.name
                    rate_limit = f"{plan.upload_mbps}M/{plan.download_mbps}M"
                    await client.ensure_profile(
                        profile_name, rate_limit,
                        local_address=plan.local_address,
                        remote_address=plan.remote_address,
                        dns_server=plan.dns_server,
                        parent_queue=plan.parent_queue,
                    )
                    secret_update["profile"] = profile_name
                if secret_update:
                    await client.update_secret(customer.mikrotik_secret_id, secret_update)
        except Exception as e:
            logger.warning(f"MikroTik sync failed for customer {customer.id}: {e}")

    return customer


@router.post("/{customer_id}/delete", status_code=200)
async def delete_customer(
    customer_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Delete a customer. Requires admin password confirmation."""
    from app.core.security import verify_password

    password = body.get("password", "")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required to confirm deletion")
    if not verify_password(password, current_user.password_hash):
        raise HTTPException(status_code=403, detail="Incorrect password")

    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    username = customer.pppoe_username

    # Remove NAT redirect if any
    try:
        from app.services.nat_redirect import remove_redirect_for_customer
        await remove_redirect_for_customer(db, customer)
    except Exception:
        pass

    # Remove PPPoE secret from MikroTik
    if customer.mikrotik_secret_id:
        try:
            client, _ = await get_client_for_customer(db, customer)
            if client:
                await client.kick_session(customer.pppoe_username)
                await client.delete_secret(customer.mikrotik_secret_id)
        except Exception as e:
            logger.warning(f"MikroTik delete secret failed for {customer.id}: {e}")

    # Clean up related records
    await db.execute(
        Payment.__table__.delete().where(
            Payment.invoice_id.in_(select(Invoice.id).where(Invoice.customer_id == customer_id))
        )
    )
    await db.execute(Invoice.__table__.delete().where(Invoice.customer_id == customer_id))
    await db.execute(DisconnectLog.__table__.delete().where(DisconnectLog.customer_id == customer_id))
    await db.execute(Notification.__table__.delete().where(Notification.customer_id == customer_id))
    # Delete session traffic (via session FK), then PPPoE sessions
    await db.execute(
        SessionTraffic.__table__.delete().where(
            SessionTraffic.session_id.in_(select(PPPoESession.id).where(PPPoESession.customer_id == customer_id))
        )
    )
    await db.execute(PPPoESession.__table__.delete().where(PPPoESession.customer_id == customer_id))
    await db.execute(BandwidthUsage.__table__.delete().where(BandwidthUsage.customer_id == customer_id))
    await db.execute(CustomerActivity.__table__.delete().where(CustomerActivity.customer_id == customer_id))
    # Delete ticket messages (via ticket FK), then tickets
    await db.execute(
        TicketMessage.__table__.delete().where(
            TicketMessage.ticket_id.in_(select(Ticket.id).where(Ticket.customer_id == customer_id))
        )
    )
    await db.execute(Ticket.__table__.delete().where(Ticket.customer_id == customer_id))

    await log_action(db, current_user.id, "customer.delete", "customer", customer.id, details=f"deleted {username}", owner_id=tid)
    await db.delete(customer)
    await db.flush()
    return {"status": "deleted", "username": username}


@router.post("/{customer_id}/disconnect", status_code=200)
async def disconnect_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    response = {"detail": "No MikroTik secret linked"}
    if customer.mikrotik_secret_id:
        try:
            client, _ = await get_client_for_customer(db, customer)
            if client:
                # Disable any per-user simple queue so IP-based traffic (if any) stops
                try:
                    await client.disable_user_queues(customer.pppoe_username)
                except Exception as qe:
                    logger.warning(f"Failed to disable shadow queues for {customer.id}: {qe}")
                await client.disable_secret(customer.mikrotik_secret_id)
                response = {"detail": "PPPoE secret disabled"}
        except Exception as e:
            response = {"detail": f"MikroTik error: {e}"}
    logger.info(f"Customer {customer.id} status changed to disconnected")

    # Remove NAT redirect (disconnected = no session = no traffic)
    try:
        from app.services.nat_redirect import remove_redirect_for_customer
        await remove_redirect_for_customer(db, customer)
    except Exception as e:
        logger.warning(f"NAT redirect removal failed for {customer.id}: {e}")

    customer.status = CustomerStatus.disconnected
    log = DisconnectLog(
        customer_id=customer.id,
        action=DisconnectAction.disconnect,
        reason=DisconnectReason.manual,
        performed_by=current_user.id,
        performed_at=datetime.now(timezone.utc),
        owner_id=tid,
    )
    db.add(log)
    await log_action(db, current_user.id, "customer.disconnect", "customer", customer.id, owner_id=tid)
    await db.flush()
    return {"status": "disconnected", "gateway_response": response}


@router.post("/{customer_id}/reconnect", status_code=200)
async def reconnect_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    response = {"detail": "No MikroTik secret linked"}
    try:
        client, _ = await get_client_for_customer(db, customer)
        if client:
            if customer.mikrotik_secret_id:
                # Try to enable existing secret
                secret = await client.get_secret(customer.mikrotik_secret_id)
                if secret:
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
                    response = {"detail": "PPPoE secret enabled + plan profile restored"}
                else:
                    # Secret was deleted from MikroTik — recreate it
                    customer.mikrotik_secret_id = None

            if not customer.mikrotik_secret_id:
                # No secret — create a new one
                profile = "default"
                if customer.plan:
                    profile_name = customer.plan.name
                    rate_limit = f"{customer.plan.upload_mbps}M/{customer.plan.download_mbps}M"
                    profile = await client.ensure_profile(
                        profile_name, rate_limit,
                        local_address=customer.plan.local_address,
                        remote_address=customer.plan.remote_address,
                        dns_server=customer.plan.dns_server,
                        parent_queue=customer.plan.parent_queue,
                    )
                secret_id = await client.create_secret(
                    name=customer.pppoe_username,
                    password=customer.pppoe_password,
                    profile=profile,
                    caller_id=customer.mac_address,
                )
                customer.mikrotik_secret_id = secret_id
                response = {"detail": f"PPPoE secret recreated + enabled (id={secret_id})"}

            # Re-enable any per-user simple queues we disabled on throttle/disconnect
            try:
                await client.enable_user_queues(customer.pppoe_username)
            except Exception as qe:
                logger.warning(f"Failed to enable shadow queues for {customer.id}: {qe}")
    except Exception as e:
        response = {"detail": f"MikroTik error: {e}"}
    logger.info(f"Customer {customer.id} status changed to active")

    # Remove NAT redirect on reconnect
    try:
        from app.services.nat_redirect import remove_redirect_for_customer
        await remove_redirect_for_customer(db, customer)
    except Exception as e:
        logger.warning(f"NAT redirect removal failed for {customer.id}: {e}")

    customer.status = CustomerStatus.active
    log = DisconnectLog(
        customer_id=customer.id,
        action=DisconnectAction.reconnect,
        reason=DisconnectReason.manual,
        performed_by=current_user.id,
        performed_at=datetime.now(timezone.utc),
        owner_id=tid,
    )
    db.add(log)
    await log_action(db, current_user.id, "customer.reconnect", "customer", customer.id, owner_id=tid)
    await db.flush()
    return {"status": "reconnected", "gateway_response": response}


@router.post("/{customer_id}/throttle", status_code=200)
async def throttle_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    response = {"detail": "No MikroTik secret linked"}
    if customer.mikrotik_secret_id:
        try:
            from app.core.config import settings as throttle_settings
            client, _ = await get_client_for_customer(db, customer)
            if client:
                throttle_name = f"{throttle_settings.THROTTLE_DOWNLOAD_MBPS}M-throttle"
                throttle_rate = f"{throttle_settings.THROTTLE_UPLOAD_KBPS}k/{throttle_settings.THROTTLE_DOWNLOAD_MBPS}M"
                await client.ensure_profile(throttle_name, throttle_rate)
                await client.update_secret(customer.mikrotik_secret_id, {"profile": throttle_name})
                # Disable any per-user simple queue shadowing the throttle profile
                try:
                    await client.disable_user_queues(customer.pppoe_username)
                except Exception as qe:
                    logger.warning(f"Failed to disable shadow queues for {customer.id}: {qe}")
                # Kick the active session so the new profile takes effect on reconnect
                try:
                    await client.kick_session(customer.pppoe_username)
                except Exception as ke:
                    logger.warning(f"Failed to kick session for {customer.id}: {ke}")
                response = {"detail": f"Profile changed to {throttle_name}"}
        except Exception as e:
            response = {"detail": f"MikroTik error: {e}"}
    # Add NAT redirect so customer's browser shows payment notice
    try:
        from app.services.nat_redirect import add_redirect_for_customer
        await add_redirect_for_customer(db, customer)
    except Exception as e:
        logger.warning(f"NAT redirect add failed for {customer.id}: {e}")

    logger.info(f"Customer {customer.id} status changed to suspended")

    customer.status = CustomerStatus.suspended
    log = DisconnectLog(
        customer_id=customer.id,
        action=DisconnectAction.throttle,
        reason=DisconnectReason.manual,
        performed_by=current_user.id,
        performed_at=datetime.now(timezone.utc),
        owner_id=tid,
    )
    db.add(log)
    await log_action(db, current_user.id, "customer.throttle", "customer", customer.id, owner_id=tid)
    await db.flush()
    return {"status": "throttled", "gateway_response": response}


@router.post("/{customer_id}/change-plan", status_code=200)
async def change_plan(
    customer_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Change a customer's plan with instant MikroTik speed update."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    new_plan_id = body.get("plan_id")
    if not new_plan_id:
        raise HTTPException(status_code=400, detail="plan_id required")

    from app.models.plan import Plan
    plan_result = await db.execute(select(Plan).where(Plan.id == new_plan_id, Plan.owner_id == tid))
    new_plan = plan_result.scalar_one_or_none()
    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    old_plan_id = customer.plan_id
    customer.plan_id = new_plan.id
    await db.flush()
    await db.refresh(customer)

    # Update MikroTik profile
    mt_result = {"detail": "No MikroTik secret linked"}
    if customer.mikrotik_secret_id:
        try:
            client, _ = await get_client_for_customer(db, customer)
            if client:
                profile_name = new_plan.name
                rate_limit = f"{new_plan.upload_mbps}M/{new_plan.download_mbps}M"
                await client.ensure_profile(
                    profile_name, rate_limit,
                    local_address=new_plan.local_address,
                    remote_address=new_plan.remote_address,
                    dns_server=new_plan.dns_server,
                    parent_queue=new_plan.parent_queue,
                )
                await client.update_secret(customer.mikrotik_secret_id, {"profile": profile_name})
                mt_result = {"detail": f"Profile changed to {profile_name}"}
        except Exception as e:
            mt_result = {"detail": f"MikroTik error: {e}"}

    await log_action(db, current_user.id, "customer.change_plan", "customer", customer.id, details=f"new_plan={new_plan.name}", owner_id=tid)
    return {"status": "plan_changed", "new_plan": new_plan.name, "mikrotik": mt_result}


@router.get("/{customer_id}/redirect", status_code=200)
async def get_redirect_status(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Check if a NAT redirect rule exists for a customer."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    from app.services.nat_redirect import check_redirect_for_customer
    rule = await check_redirect_for_customer(db, customer)
    return {"active": rule is not None, "rule": rule}


@router.post("/{customer_id}/redirect", status_code=200)
async def add_redirect(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Manually add a NAT redirect for a customer's browser notification."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    from app.services.nat_redirect import add_redirect_for_customer
    success = await add_redirect_for_customer(db, customer)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add redirect. Check that NAT redirect is enabled in Settings and customer has an active session.")

    await log_action(db, current_user.id, "customer.redirect_add", "customer", customer.id, owner_id=tid)
    await db.flush()
    return {"status": "redirect_added"}


@router.delete("/{customer_id}/redirect", status_code=200)
async def remove_redirect(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Manually remove NAT redirect for a customer."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    from app.services.nat_redirect import remove_redirect_for_customer
    await remove_redirect_for_customer(db, customer)

    await log_action(db, current_user.id, "customer.redirect_remove", "customer", customer.id, owner_id=tid)
    await db.flush()
    return {"status": "redirect_removed"}


@router.get("/{customer_id}/history")
async def get_customer_history(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get unified timeline of events for a customer."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.owner_id == tid))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    events = []

    # Invoices
    inv_result = await db.execute(
        select(Invoice).where(Invoice.customer_id == customer_id).order_by(Invoice.issued_at.desc())
    )
    for inv in inv_result.scalars().all():
        events.append({
            "type": "invoice",
            "date": inv.issued_at.isoformat(),
            "title": f"Invoice generated — ₱{inv.amount:,.2f}",
            "detail": f"Plan: {inv.plan.name}" if inv.plan else None,
            "status": inv.status.value,
            "ref_id": str(inv.id),
        })
        if inv.status.value == "paid" and inv.paid_at:
            events.append({
                "type": "invoice_paid",
                "date": inv.paid_at.isoformat(),
                "title": f"Invoice paid — ₱{inv.amount:,.2f}",
                "detail": None,
                "status": "paid",
                "ref_id": str(inv.id),
            })

    # Payments
    pay_result = await db.execute(
        select(Payment).where(
            Payment.invoice_id.in_(select(Invoice.id).where(Invoice.customer_id == customer_id))
        ).order_by(Payment.received_at.desc())
    )
    for p in pay_result.scalars().all():
        events.append({
            "type": "payment",
            "date": p.received_at.isoformat(),
            "title": f"Payment received — ₱{p.amount:,.2f}",
            "detail": f"Method: {p.method.value}" + (f", Ref: {p.reference_number}" if p.reference_number else ""),
            "status": "paid",
            "ref_id": str(p.id),
        })

    # Disconnect logs (throttle, disconnect, reconnect)
    dl_result = await db.execute(
        select(DisconnectLog).where(DisconnectLog.customer_id == customer_id).order_by(DisconnectLog.performed_at.desc())
    )
    action_labels = {"throttle": "Throttled", "disconnect": "Disconnected", "reconnect": "Reconnected"}
    action_statuses = {"throttle": "suspended", "disconnect": "disconnected", "reconnect": "active"}
    for dl in dl_result.scalars().all():
        label = action_labels.get(dl.action.value, dl.action.value)
        events.append({
            "type": "enforcement",
            "date": dl.performed_at.isoformat(),
            "title": f"{label} — {dl.reason.value.replace('_', ' ')}",
            "detail": None,
            "status": action_statuses.get(dl.action.value, dl.action.value),
            "ref_id": str(dl.id),
        })

    # Notifications
    notif_result = await db.execute(
        select(Notification).where(Notification.customer_id == customer_id).order_by(Notification.created_at.desc())
    )
    for n in notif_result.scalars().all():
        events.append({
            "type": "notification",
            "date": (n.sent_at or n.created_at).isoformat(),
            "title": f"{n.type.value.upper()} — {n.subject}",
            "detail": None,
            "status": n.status.value,
            "ref_id": str(n.id),
        })

    # Sort by date descending
    events.sort(key=lambda e: e["date"], reverse=True)

    return {"events": events, "total": len(events)}
