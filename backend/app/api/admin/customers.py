import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.tenant import get_tenant_id
from app.models.customer import Customer, CustomerStatus
from app.models.disconnect_log import DisconnectAction, DisconnectLog, DisconnectReason
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.notification import Notification
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate
from app.services.audit import log_action
from app.services.mikrotik import get_client_for_customer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: CustomerStatus | None = Query(None, alias="status"),
    search: str | None = Query(None),
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
    await db.refresh(customer)

    # Auto-provision PPPoE secret on MikroTik with plan profile
    try:
        client, _ = await get_client_for_customer(db, customer)
        if client:
            plan = customer.plan
            profile = "default"
            if plan:
                profile_name = f"{plan.download_mbps}M-{plan.upload_mbps}M"
                rate_limit = f"{plan.upload_mbps}M/{plan.download_mbps}M"
                profile = await client.ensure_profile(profile_name, rate_limit)

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

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)

    await db.flush()
    await db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
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

    customer.status = CustomerStatus.terminated
    await db.flush()


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
                await client.disable_secret(customer.mikrotik_secret_id)
                response = {"detail": "PPPoE secret disabled"}
        except Exception as e:
            response = {"detail": f"MikroTik error: {e}"}
    logger.info(f"Customer {customer.id} status changed to disconnected")

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
    if customer.mikrotik_secret_id:
        try:
            client, _ = await get_client_for_customer(db, customer)
            if client:
                await client.enable_secret(customer.mikrotik_secret_id)
                if customer.plan:
                    profile_name = f"{customer.plan.download_mbps}M-{customer.plan.upload_mbps}M"
                    rate_limit = f"{customer.plan.upload_mbps}M/{customer.plan.download_mbps}M"
                    await client.ensure_profile(profile_name, rate_limit)
                    await client.update_secret(customer.mikrotik_secret_id, {"profile": profile_name})
                response = {"detail": "PPPoE secret enabled + plan profile restored"}
        except Exception as e:
            response = {"detail": f"MikroTik error: {e}"}
    logger.info(f"Customer {customer.id} status changed to active")

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
                response = {"detail": f"Profile changed to {throttle_name}"}
        except Exception as e:
            response = {"detail": f"MikroTik error: {e}"}
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
                profile_name = f"{new_plan.download_mbps}M-{new_plan.upload_mbps}M"
                rate_limit = f"{new_plan.upload_mbps}M/{new_plan.download_mbps}M"
                await client.ensure_profile(profile_name, rate_limit)
                await client.update_secret(customer.mikrotik_secret_id, {"profile": profile_name})
                mt_result = {"detail": f"Profile changed to {profile_name}"}
        except Exception as e:
            mt_result = {"detail": f"MikroTik error: {e}"}

    await log_action(db, current_user.id, "customer.change_plan", "customer", customer.id, details=f"new_plan={new_plan.name}", owner_id=tid)
    return {"status": "plan_changed", "new_plan": new_plan.name, "mikrotik": mt_result}


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
