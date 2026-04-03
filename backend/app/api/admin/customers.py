import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.customer import Customer, CustomerStatus
from app.models.disconnect_log import DisconnectAction, DisconnectLog, DisconnectReason
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate
from app.services import gateway

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

    try:
        response = await gateway.disconnect_customer(str(customer.id), customer.pppoe_username)
    except Exception:
        response = {"detail": "Gateway unreachable, session may still be active"}

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

    try:
        response = await gateway.reconnect_customer(str(customer.id), customer.pppoe_username)
    except Exception:
        response = {"detail": "Gateway unreachable"}

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

    try:
        response = await gateway.throttle_customer(
            str(customer.id), customer.pppoe_username,
            settings.THROTTLE_DOWNLOAD_MBPS, settings.THROTTLE_UPLOAD_KBPS,
        )
    except Exception:
        response = {"detail": "Gateway unreachable"}

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
