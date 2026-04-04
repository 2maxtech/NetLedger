import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.customer import Customer, CustomerStatus
from app.models.disconnect_log import DisconnectLog
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentMethod
from app.models.plan import Plan

API = settings.API_V1_PREFIX


@pytest_asyncio.fixture
async def plan(db_session: AsyncSession) -> Plan:
    p = Plan(
        id=uuid.uuid4(),
        name="Basic 10Mbps",
        download_mbps=10,
        upload_mbps=5,
        monthly_price=Decimal("999.00"),
        is_active=True,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest_asyncio.fixture
async def customer(db_session: AsyncSession, plan: Plan) -> Customer:
    c = Customer(
        id=uuid.uuid4(),
        full_name="Juan Dela Cruz",
        email="juan@test.com",
        phone="09171234567",
        pppoe_username="juan",
        pppoe_password="pass123",
        status=CustomerStatus.active,
        plan_id=plan.id,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest.mark.asyncio
async def test_generate_invoice(db_session: AsyncSession, customer: Customer, plan: Plan):
    from app.services.billing import generate_invoice

    billing_period = date(2026, 4, 1)
    invoice = await generate_invoice(db_session, customer, billing_period)

    assert invoice.customer_id == customer.id
    assert invoice.plan_id == plan.id
    assert invoice.amount == Decimal("999.00")
    assert invoice.due_date == date(2026, 4, settings.BILLING_DUE_DAY)
    assert invoice.status == InvoiceStatus.pending


@pytest.mark.asyncio
async def test_generate_invoice_idempotent(db_session: AsyncSession, customer: Customer, plan: Plan):
    from app.services.billing import generate_invoice

    billing_period = date(2026, 4, 1)
    inv1 = await generate_invoice(db_session, customer, billing_period)
    inv2 = await generate_invoice(db_session, customer, billing_period)

    assert inv1.id == inv2.id

    result = await db_session.execute(select(Invoice))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_generate_monthly_invoices(db_session: AsyncSession, customer: Customer):
    from app.services.billing import generate_monthly_invoices

    result = await generate_monthly_invoices(db_session)

    assert result["generated"] == 1
    assert result["skipped"] == 0


@pytest_asyncio.fixture
async def invoice(db_session: AsyncSession, customer: Customer, plan: Plan) -> Invoice:
    inv = Invoice(
        id=uuid.uuid4(),
        customer_id=customer.id,
        plan_id=plan.id,
        amount=Decimal("999.00"),
        due_date=date(2026, 4, 15),
        status=InvoiceStatus.pending,
        issued_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    db_session.add(inv)
    await db_session.commit()
    await db_session.refresh(inv)
    return inv


@pytest.mark.asyncio
async def test_record_payment_full(db_session: AsyncSession, invoice: Invoice):
    from app.services.billing import record_payment

    payment = await record_payment(
        db=db_session,
        invoice_id=invoice.id,
        amount=Decimal("999.00"),
        method=PaymentMethod.cash,
        reference=None,
        received_by=None,
    )

    assert payment.amount == Decimal("999.00")
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.paid
    assert invoice.paid_at is not None


@pytest.mark.asyncio
async def test_record_payment_partial(db_session: AsyncSession, invoice: Invoice):
    from app.services.billing import record_payment

    await record_payment(
        db=db_session,
        invoice_id=invoice.id,
        amount=Decimal("500.00"),
        method=PaymentMethod.cash,
        reference=None,
        received_by=None,
    )

    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.pending  # not fully paid


@pytest.mark.asyncio
async def test_auto_reconnect_on_full_payment(db_session: AsyncSession, customer: Customer, plan: Plan):
    from app.services.billing import record_payment

    # Make customer disconnected with an overdue invoice
    customer.status = CustomerStatus.disconnected
    inv = Invoice(
        id=uuid.uuid4(),
        customer_id=customer.id,
        plan_id=plan.id,
        amount=Decimal("999.00"),
        due_date=date(2026, 3, 15),
        status=InvoiceStatus.overdue,
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(inv)
    await db_session.commit()

    payment = await record_payment(
        db=db_session,
        invoice_id=inv.id,
        amount=Decimal("999.00"),
        method=PaymentMethod.bank,
        reference="REF123",
        received_by=None,
        skip_gateway=True,
    )

    await db_session.refresh(customer)
    assert customer.status == CustomerStatus.active

    result = await db_session.execute(select(DisconnectLog))
    log = result.scalar_one()
    assert log.action.value == "reconnect"
    assert log.reason.value == "non_payment"


@pytest.mark.asyncio
async def test_check_overdue_invoices(db_session: AsyncSession, customer: Customer, plan: Plan):
    from app.services.billing import check_overdue_invoices

    inv = Invoice(
        id=uuid.uuid4(),
        customer_id=customer.id,
        plan_id=plan.id,
        amount=Decimal("999.00"),
        due_date=date.today() - timedelta(days=1),
        status=InvoiceStatus.pending,
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(inv)
    await db_session.commit()

    count = await check_overdue_invoices(db_session)
    assert count == 1

    await db_session.refresh(inv)
    assert inv.status == InvoiceStatus.overdue


@pytest.mark.asyncio
async def test_graduated_disconnect_throttle(db_session: AsyncSession, customer: Customer, plan: Plan):
    from app.services.billing import process_graduated_disconnect

    days = settings.BILLING_THROTTLE_DAYS_AFTER_DUE
    inv = Invoice(
        id=uuid.uuid4(),
        customer_id=customer.id,
        plan_id=plan.id,
        amount=Decimal("999.00"),
        due_date=date.today() - timedelta(days=days),
        status=InvoiceStatus.overdue,
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(inv)
    await db_session.commit()

    result = await process_graduated_disconnect(db_session, skip_gateway=True)
    assert result["throttled"] == 1

    await db_session.refresh(customer)
    assert customer.status == CustomerStatus.suspended


@pytest.mark.asyncio
async def test_graduated_disconnect_disconnect(db_session: AsyncSession, customer: Customer, plan: Plan):
    from app.services.billing import process_graduated_disconnect

    customer.status = CustomerStatus.suspended
    days = settings.BILLING_DISCONNECT_DAYS_AFTER_DUE
    inv = Invoice(
        id=uuid.uuid4(),
        customer_id=customer.id,
        plan_id=plan.id,
        amount=Decimal("999.00"),
        due_date=date.today() - timedelta(days=days),
        status=InvoiceStatus.overdue,
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(inv)
    await db_session.commit()

    result = await process_graduated_disconnect(db_session, skip_gateway=True)
    assert result["disconnected"] == 1

    await db_session.refresh(customer)
    assert customer.status == CustomerStatus.disconnected


@pytest.mark.asyncio
async def test_graduated_disconnect_idempotent(db_session: AsyncSession, customer: Customer, plan: Plan):
    from app.services.billing import process_graduated_disconnect

    customer.status = CustomerStatus.disconnected
    days = settings.BILLING_DISCONNECT_DAYS_AFTER_DUE
    inv = Invoice(
        id=uuid.uuid4(),
        customer_id=customer.id,
        plan_id=plan.id,
        amount=Decimal("999.00"),
        due_date=date.today() - timedelta(days=days),
        status=InvoiceStatus.overdue,
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(inv)
    await db_session.commit()

    result = await process_graduated_disconnect(db_session, skip_gateway=True)
    assert result["throttled"] == 0
    assert result["disconnected"] == 0


# --- API integration tests ---

@pytest_asyncio.fixture
async def plan_and_customer(client, auth_headers):
    """Create a plan and customer via API, return their IDs."""
    plan_resp = await client.post(
        f"{API}/plans/",
        json={"name": "Test Plan", "download_mbps": 10, "upload_mbps": 5, "monthly_price": "999.00"},
        headers=auth_headers,
    )
    plan_id = plan_resp.json()["id"]

    cust_resp = await client.post(
        f"{API}/customers/",
        json={
            "full_name": "API Test User",
            "email": "apitest@test.com",
            "phone": "09170000000",
            "pppoe_username": "apitest",
            "pppoe_password": "pass123",
            "plan_id": plan_id,
        },
        headers=auth_headers,
    )
    return plan_id, cust_resp.json()["id"]


@pytest.mark.asyncio
async def test_api_generate_invoices(client, auth_headers, plan_and_customer):
    plan_id, customer_id = plan_and_customer

    response = await client.post(
        f"{API}/billing/invoices/generate",
        json={"customer_id": customer_id},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["generated"] == 1


@pytest.mark.asyncio
async def test_api_list_invoices(client, auth_headers, plan_and_customer):
    plan_id, customer_id = plan_and_customer

    await client.post(
        f"{API}/billing/invoices/generate",
        json={"customer_id": customer_id},
        headers=auth_headers,
    )

    response = await client.get(f"{API}/billing/invoices", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_api_record_payment(client, auth_headers, plan_and_customer):
    plan_id, customer_id = plan_and_customer

    await client.post(
        f"{API}/billing/invoices/generate",
        json={"customer_id": customer_id},
        headers=auth_headers,
    )
    inv_resp = await client.get(
        f"{API}/billing/invoices",
        params={"customer_id": customer_id},
        headers=auth_headers,
    )
    invoice_id = inv_resp.json()["items"][0]["id"]

    pay_resp = await client.post(
        f"{API}/billing/payments",
        json={
            "invoice_id": invoice_id,
            "amount": "999.00",
            "method": "cash",
        },
        headers=auth_headers,
    )
    assert pay_resp.status_code == 201
    assert pay_resp.json()["amount"] == "999.00"

    inv_detail = await client.get(f"{API}/billing/invoices/{invoice_id}", headers=auth_headers)
    assert inv_detail.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_api_void_invoice(client, auth_headers, plan_and_customer):
    plan_id, customer_id = plan_and_customer

    await client.post(
        f"{API}/billing/invoices/generate",
        json={"customer_id": customer_id},
        headers=auth_headers,
    )
    inv_resp = await client.get(
        f"{API}/billing/invoices",
        params={"customer_id": customer_id},
        headers=auth_headers,
    )
    invoice_id = inv_resp.json()["items"][0]["id"]

    void_resp = await client.put(
        f"{API}/billing/invoices/{invoice_id}",
        json={"status": "void"},
        headers=auth_headers,
    )
    assert void_resp.status_code == 200
    assert void_resp.json()["status"] == "void"
