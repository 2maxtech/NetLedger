"""Seed a demo tenant with realistic Filipino ISP data.

Called on app startup. Skips silently if the demo user already exists.
"""

import logging
import random
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.security import hash_password
from app.models.customer import Customer, CustomerStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentMethod
from app.models.plan import Plan
from app.models.router import Area, Router
from app.models.user import User, UserRole
from app.models.app_setting import AppSetting

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static seed data
# ---------------------------------------------------------------------------

_PLANS = [
    {"name": "5 Mbps Basic", "download_mbps": 5, "upload_mbps": 5, "monthly_price": Decimal("599.00"), "description": "Entry-level residential plan"},
    {"name": "10 Mbps Standard", "download_mbps": 10, "upload_mbps": 10, "monthly_price": Decimal("799.00"), "description": "Most popular residential plan"},
    {"name": "20 Mbps Premium", "download_mbps": 20, "upload_mbps": 20, "monthly_price": Decimal("1299.00"), "description": "High-speed residential plan"},
    {"name": "50 Mbps Business", "download_mbps": 50, "upload_mbps": 50, "monthly_price": Decimal("1999.00"), "description": "Dedicated business plan"},
]

_AREAS = [
    {"name": "Brgy. San Isidro", "description": "Main coverage area — 120 subscribers"},
    {"name": "Brgy. Maligaya", "description": "Expansion area — 45 subscribers"},
]

# (full_name, pppoe_username, email, phone, plan_index, area_index, status)
_CUSTOMERS = [
    ("Juan dela Cruz",      "juan",     "juan@sample.net",     "09171234501", 1, 0, "active"),
    ("Maria Santos",        "maria",    "maria@sample.net",    "09171234502", 2, 0, "active"),
    ("Pedro Reyes",         "pedro",    "pedro@sample.net",    "09171234503", 0, 0, "active"),
    ("Ana Garcia",          "ana",      "ana@sample.net",      "09171234504", 1, 1, "active"),
    ("Jose Mendoza",        "jose",     "jose@sample.net",     "09171234505", 3, 1, "active"),
    ("Rosa Cruz",           "rosa",     "rosa@sample.net",     "09171234506", 0, 0, "active"),
    ("Carlos Bautista",     "carlos",   "carlos@sample.net",   "09171234507", 2, 0, "active"),
    ("Elena Rivera",        "elena",    "elena@sample.net",    "09171234508", 1, 1, "active"),
    ("Miguel Torres",       "miguel",   "miguel@sample.net",   "09171234509", 1, 0, "active"),
    ("Sofia Ramos",         "sofia",    "sofia@sample.net",    "09171234510", 0, 0, "active"),
    ("Antonio Flores",      "antonio",  "antonio@sample.net",  "09171234511", 2, 1, "suspended"),
    ("Isabella Gutierrez",  "isabella", "isabella@sample.net", "09171234512", 1, 0, "suspended"),
    ("Roberto Navarro",     "roberto",  "roberto@sample.net",  "09171234513", 3, 1, "suspended"),
    ("Carmen Espinoza",     "carmen",   "carmen@sample.net",   "09171234514", 0, 0, "disconnected"),
    ("Luis Villanueva",     "luis",     "luis@sample.net",     "09171234515", 1, 1, "disconnected"),
]

# Invoice statuses for the 15 customers (in order): 8 paid, 4 pending, 3 overdue
_INVOICE_STATUSES = (
    ["paid"] * 8 + ["pending"] * 4 + ["overdue"] * 3
)

_PAYMENT_METHODS = [m for m in PaymentMethod]


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

async def seed_demo_data() -> None:
    """Create the demo tenant if it does not already exist."""
    async with async_session() as db:
        # Check if demo user already exists
        result = await db.execute(select(User).where(User.is_demo == True).limit(1))  # noqa: E712
        if result.scalar_one_or_none() is not None:
            logger.info("Demo user already exists — skipping seed")
            return

        logger.info("Seeding demo data ...")

        # --- Demo user ---
        demo_user = User(
            username="demo",
            email="demo@netledger.app",
            password_hash=hash_password("demo123"),
            full_name="Demo Operator",
            company_name="Sample ISP",
            phone="09170000000",
            role=UserRole.admin,
            is_active=True,
            is_demo=True,
        )
        db.add(demo_user)
        await db.flush()
        owner_id = demo_user.id

        # --- Router ---
        router = Router(
            name="Main Router",
            url="http://192.168.88.1",
            username="admin",
            password="",
            location="NOC — Brgy. San Isidro",
            is_active=True,
            owner_id=owner_id,
        )
        db.add(router)
        await db.flush()

        # --- Areas ---
        area_objs: list[Area] = []
        for area_data in _AREAS:
            area = Area(
                name=area_data["name"],
                description=area_data["description"],
                router_id=router.id,
                owner_id=owner_id,
            )
            db.add(area)
            area_objs.append(area)
        await db.flush()

        # --- Plans ---
        plan_objs: list[Plan] = []
        for plan_data in _PLANS:
            plan = Plan(owner_id=owner_id, **plan_data)
            db.add(plan)
            plan_objs.append(plan)
        await db.flush()

        # --- Customers ---
        customer_objs: list[Customer] = []
        for row in _CUSTOMERS:
            full_name, pppoe_user, email, phone, plan_idx, area_idx, status_str = row
            customer = Customer(
                full_name=full_name,
                email=email,
                phone=phone,
                pppoe_username=pppoe_user,
                pppoe_password="demo1234",
                status=CustomerStatus(status_str),
                plan_id=plan_objs[plan_idx].id,
                router_id=router.id,
                area_id=area_objs[area_idx].id,
                owner_id=owner_id,
                billing_due_day=15,
            )
            db.add(customer)
            customer_objs.append(customer)
        await db.flush()

        # --- Invoices & Payments for current month ---
        now = datetime.now(timezone.utc)
        current_month_start = date(now.year, now.month, 1)
        due = date(now.year, now.month, 15)

        for idx, customer in enumerate(customer_objs):
            inv_status_str = _INVOICE_STATUSES[idx]
            inv_status = InvoiceStatus(inv_status_str)
            plan = plan_objs[_CUSTOMERS[idx][4]]
            amount = plan.monthly_price

            paid_at = None
            if inv_status == InvoiceStatus.paid:
                # Paid sometime between the 1st and 14th
                pay_day = random.randint(1, 14)
                paid_at = datetime(now.year, now.month, pay_day, 10, 0, 0, tzinfo=timezone.utc)

            invoice = Invoice(
                customer_id=customer.id,
                plan_id=plan.id,
                amount=amount,
                due_date=due,
                status=inv_status,
                issued_at=datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc),
                paid_at=paid_at,
                owner_id=owner_id,
            )
            db.add(invoice)
            await db.flush()

            # Create payment record for paid invoices
            if inv_status == InvoiceStatus.paid and paid_at is not None:
                payment = Payment(
                    invoice_id=invoice.id,
                    amount=amount,
                    method=random.choice(_PAYMENT_METHODS),
                    reference_number=f"DEMO-{uuid.uuid4().hex[:8].upper()}",
                    received_by=owner_id,
                    received_at=paid_at,
                    owner_id=owner_id,
                )
                db.add(payment)

        # --- App Settings (billing config + dismiss onboarding) ---
        demo_settings = [
            ("billing_default_due_day", "15"),
            ("billing_grace_days", "7"),
            ("billing_send_invoice_email", "true"),
            ("billing_send_invoice_sms", "true"),
            ("smtp_host", "mail.sample-isp.net"),
            ("smtp_port", "587"),
            ("smtp_from", "billing@sample-isp.net"),
            ("smtp_from_name", "Sample ISP Billing"),
            ("sms_provider", "semaphore"),
            ("sms_sender_name", "SampleISP"),
            ("company_name", "Sample ISP"),
            ("onboarding_dismissed", "true"),
        ]
        for key, value in demo_settings:
            setting = AppSetting(key=key, value=value, owner_id=owner_id)
            db.add(setting)

        await db.commit()
        logger.info("Demo data seeded successfully (15 customers, 4 plans, 1 router, 2 areas)")
