import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.customer import Customer, CustomerStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.user import User
from app.services.mikrotik import mikrotik

logger = logging.getLogger(__name__)


def _parse_rate(rate_str: str) -> tuple[int, int]:
    """Parse MikroTik rate-limit 'upload/download' into (download_mbps, upload_mbps).
    Handles formats like '5M/10M', '512k/1M', '10000000/5000000'.
    """
    if not rate_str or "/" not in rate_str:
        return 0, 0

    upload_str, download_str = rate_str.split("/", 1)

    def to_mbps(s: str) -> int:
        s = s.strip().lower()
        if s.endswith("m"):
            return int(float(s[:-1]))
        elif s.endswith("k"):
            return max(1, int(float(s[:-1]) / 1000))
        else:
            return max(1, int(float(s)) // 1_000_000) if s.isdigit() else 0

    return to_mbps(download_str), to_mbps(upload_str)

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregated dashboard stats — MikroTik live data + billing summary."""
    today = date.today()
    this_month_start = today.replace(day=1)
    month_start_dt = datetime(this_month_start.year, this_month_start.month, 1, tzinfo=timezone.utc)

    # --- DB Stats (parallel queries) ---
    customers_by_status = await db.execute(
        select(Customer.status, func.count(Customer.id)).group_by(Customer.status)
    )
    status_counts = {row[0].value: row[1] for row in customers_by_status}

    total_customers = sum(status_counts.values())
    active = status_counts.get("active", 0)
    suspended = status_counts.get("suspended", 0)
    disconnected = status_counts.get("disconnected", 0)

    # MRR = sum of monthly_price for all active customers with plans
    mrr_result = await db.execute(
        select(func.coalesce(func.sum(Plan.monthly_price), 0))
        .join(Customer, Customer.plan_id == Plan.id)
        .where(Customer.status == CustomerStatus.active)
    )
    mrr = float(mrr_result.scalar() or 0)

    # Revenue this month
    billed_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            and_(
                Invoice.issued_at >= month_start_dt,
                Invoice.status != InvoiceStatus.void,
            )
        )
    )
    billed_this_month = float(billed_result.scalar() or 0)

    collected_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.received_at >= month_start_dt,
        )
    )
    collected_this_month = float(collected_result.scalar() or 0)

    # Overdue
    overdue_result = await db.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.status == InvoiceStatus.overdue
        )
    )
    overdue_row = overdue_result.one()
    overdue_count = overdue_row[0]
    overdue_amount = float(overdue_row[1])

    # Recent payments (last 5)
    recent_payments_result = await db.execute(
        select(Payment)
        .order_by(Payment.received_at.desc())
        .limit(5)
    )
    recent_payments = [
        {
            "id": str(p.id),
            "amount": str(p.amount),
            "method": p.method.value,
            "received_at": p.received_at.isoformat() if p.received_at else None,
        }
        for p in recent_payments_result.scalars().all()
    ]

    # Revenue last 6 months
    revenue_trend = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        m_start = datetime(y, m, 1, tzinfo=timezone.utc)
        if m == 12:
            m_end = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
        else:
            m_end = datetime(y, m + 1, 1, tzinfo=timezone.utc)

        month_collected = await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                and_(Payment.received_at >= m_start, Payment.received_at < m_end)
            )
        )
        revenue_trend.append({
            "month": f"{y}-{m:02d}",
            "collected": float(month_collected.scalar() or 0),
        })

    # --- MikroTik Live Stats ---
    mt_stats = {
        "connected": False,
        "identity": "",
        "uptime": "",
        "cpu_load": "",
        "free_memory": 0,
        "total_memory": 0,
        "active_sessions": 0,
        "interfaces": [],
    }
    try:
        identity = await mikrotik.get_identity()
        resources = await mikrotik.get_resources()
        sessions = await mikrotik.get_active_sessions()

        # Interface traffic
        interfaces_resp = await mikrotik._request("GET", "interface")
        interfaces = []
        for iface in interfaces_resp.json():
            if iface.get("type") in ("ether", "pppoe-in"):
                interfaces.append({
                    "name": iface.get("name", ""),
                    "type": iface.get("type", ""),
                    "running": iface.get("running", "false") == "true",
                    "rx_bytes": int(iface.get("rx-byte", 0)),
                    "tx_bytes": int(iface.get("tx-byte", 0)),
                })

        mt_stats = {
            "connected": True,
            "identity": identity,
            "uptime": resources.get("uptime", ""),
            "cpu_load": resources.get("cpu-load", "0"),
            "free_memory": int(resources.get("free-memory", 0)),
            "total_memory": int(resources.get("total-memory", 0)),
            "active_sessions": len(sessions),
            "interfaces": interfaces,
            "version": resources.get("version", ""),
        }
    except Exception as e:
        mt_stats["error"] = str(e)

    return {
        "subscribers": {
            "total": total_customers,
            "active": active,
            "suspended": suspended,
            "disconnected": disconnected,
        },
        "billing": {
            "mrr": mrr,
            "billed_this_month": billed_this_month,
            "collected_this_month": collected_this_month,
            "collection_rate": round(collected_this_month / billed_this_month * 100, 1) if billed_this_month > 0 else 0,
            "overdue_count": overdue_count,
            "overdue_amount": overdue_amount,
        },
        "recent_payments": recent_payments,
        "revenue_trend": revenue_trend,
        "mikrotik": mt_stats,
    }


@router.get("/active-sessions")
async def get_active_sessions(current_user: User = Depends(get_current_user)):
    """Get active PPPoE sessions from MikroTik."""
    try:
        sessions = await mikrotik.get_active_sessions()
        return {"sessions": sessions, "total": len(sessions)}
    except Exception as e:
        return {"sessions": [], "total": 0, "error": str(e)}


@router.get("/status")
async def get_network_status(current_user: User = Depends(get_current_user)):
    """Check MikroTik connectivity."""
    try:
        identity = await mikrotik.get_identity()
        resources = await mikrotik.get_resources()
        return {
            "connected": True,
            "identity": identity,
            "uptime": resources.get("uptime", ""),
            "cpu_load": resources.get("cpu-load", ""),
            "free_memory": resources.get("free-memory", ""),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.get("/subscribers")
async def get_subscribers(current_user: User = Depends(get_current_user)):
    """List PPPoE secrets from MikroTik."""
    try:
        secrets = await mikrotik.get_secrets()
        return {"subscribers": secrets, "total": len(secrets)}
    except Exception as e:
        return {"subscribers": [], "total": 0, "error": str(e)}


@router.post("/import")
async def import_from_mikrotik(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Import existing PPPoE secrets and profiles from MikroTik into NetLedger.

    - Creates Plans from MikroTik profiles that have rate-limits
    - Creates Customers from PPPoE secrets not already in NetLedger
    - Skips secrets that match an existing customer's pppoe_username or mikrotik_secret_id
    """
    try:
        mt_profiles = await mikrotik.get_profiles()
        mt_secrets = await mikrotik.get_secrets()
    except Exception as e:
        return {"error": f"Failed to connect to MikroTik: {e}"}

    # Build profile → rate-limit map
    profile_rates: dict[str, str] = {}
    for p in mt_profiles:
        if p.get("rate-limit"):
            profile_rates[p["name"]] = p["rate-limit"]

    # Get existing customers to skip duplicates
    existing_result = await db.execute(select(Customer))
    existing_customers = existing_result.scalars().all()
    existing_usernames = {c.pppoe_username for c in existing_customers}
    existing_secret_ids = {c.mikrotik_secret_id for c in existing_customers if c.mikrotik_secret_id}

    # Get existing plans to avoid duplicates
    existing_plans_result = await db.execute(select(Plan))
    existing_plans = existing_plans_result.scalars().all()
    existing_plan_names = {p.name for p in existing_plans}

    # Create plans from profiles with rate-limits
    profile_to_plan: dict[str, Plan] = {}
    plans_created = 0

    for profile_name, rate_limit in profile_rates.items():
        download_mbps, upload_mbps = _parse_rate(rate_limit)
        if download_mbps == 0 and upload_mbps == 0:
            continue

        plan_name = f"{profile_name}"
        if plan_name in existing_plan_names:
            # Map to existing plan with same name
            plan = next((p for p in existing_plans if p.name == plan_name), None)
            if plan:
                profile_to_plan[profile_name] = plan
            continue

        plan = Plan(
            name=plan_name,
            download_mbps=download_mbps,
            upload_mbps=upload_mbps,
            monthly_price=Decimal("0.00"),  # Admin sets pricing later
            description=f"Imported from MikroTik profile '{profile_name}'",
            is_active=True,
        )
        db.add(plan)
        await db.flush()
        await db.refresh(plan)
        profile_to_plan[profile_name] = plan
        existing_plan_names.add(plan_name)
        plans_created += 1

    # Also map profiles without rate-limits to the default plan if one exists
    # Secrets on 'default' profile get no plan assignment (admin handles later)

    # Create customers from secrets
    customers_created = 0
    customers_skipped = 0

    for secret in mt_secrets:
        secret_id = secret.get(".id", "")
        username = secret.get("name", "")

        if not username:
            continue

        # Skip if already exists
        if username in existing_usernames or secret_id in existing_secret_ids:
            customers_skipped += 1
            continue

        profile_name = secret.get("profile", "default")
        plan = profile_to_plan.get(profile_name)

        # If no plan mapped, try matching by speed pattern in profile name
        if not plan and profile_name != "default":
            # Try to find existing plan with matching speeds
            download_mbps, upload_mbps = _parse_rate(profile_rates.get(profile_name, ""))
            for ep in existing_plans:
                if ep.download_mbps == download_mbps and ep.upload_mbps == upload_mbps:
                    plan = ep
                    break

        if not plan:
            # Use first active plan as fallback, or skip
            fallback = next((p for p in existing_plans if p.is_active), None)
            if not fallback and profile_to_plan:
                fallback = next(iter(profile_to_plan.values()))
            if not fallback:
                logger.warning(f"Skipping secret '{username}' — no plan available")
                customers_skipped += 1
                continue
            plan = fallback

        customer = Customer(
            full_name=username.replace(".", " ").replace("_", " ").title(),
            email=f"{username}@imported.local",
            phone="0000000000",
            pppoe_username=username,
            pppoe_password=secret.get("password", "imported"),
            status=CustomerStatus.disconnected if secret.get("disabled") == "true" else CustomerStatus.active,
            plan_id=plan.id,
            mikrotik_secret_id=secret_id,
            mac_address=secret.get("caller-id") or None,
        )
        db.add(customer)
        existing_usernames.add(username)
        customers_created += 1

    await db.flush()

    return {
        "plans_created": plans_created,
        "customers_created": customers_created,
        "customers_skipped": customers_skipped,
        "total_secrets_on_mikrotik": len(mt_secrets),
        "profiles_with_rates": len(profile_rates),
    }
