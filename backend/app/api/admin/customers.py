import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.customer import Customer, CustomerStatus
from app.models.disconnect_log import DisconnectAction, DisconnectLog, DisconnectReason
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate
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
):
    query = select(Customer)
    count_query = select(func.count(Customer.id))

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
):
    customer = Customer(**body.model_dump())
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

    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
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
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
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
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
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
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
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
    )
    db.add(log)
    await db.flush()
    return {"status": "disconnected", "gateway_response": response}


@router.post("/{customer_id}/reconnect", status_code=200)
async def reconnect_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
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
    )
    db.add(log)
    await db.flush()
    return {"status": "reconnected", "gateway_response": response}


@router.post("/{customer_id}/throttle", status_code=200)
async def throttle_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
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
    )
    db.add(log)
    await db.flush()
    return {"status": "throttled", "gateway_response": response}


@router.post("/{customer_id}/change-plan", status_code=200)
async def change_plan(
    customer_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change a customer's plan with instant MikroTik speed update."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    new_plan_id = body.get("plan_id")
    if not new_plan_id:
        raise HTTPException(status_code=400, detail="plan_id required")

    from app.models.plan import Plan
    plan_result = await db.execute(select(Plan).where(Plan.id == new_plan_id))
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

    return {"status": "plan_changed", "new_plan": new_plan.name, "mikrotik": mt_result}
