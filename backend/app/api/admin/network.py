import ipaddress
import logging
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.tenant import get_tenant_id
from app.models.customer import Customer, CustomerStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.user import User
from app.services.mikrotik import get_mikrotik_client, mikrotik
from app.utils.csv_export import make_csv_response

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
    tenant_id: str = Depends(get_tenant_id),
):
    """Aggregated dashboard stats — MikroTik live data + billing summary."""
    tid = uuid.UUID(tenant_id)
    today = date.today()
    this_month_start = today.replace(day=1)
    month_start_dt = datetime(this_month_start.year, this_month_start.month, 1, tzinfo=timezone.utc)

    # --- DB Stats (parallel queries) ---
    customers_by_status = await db.execute(
        select(Customer.status, func.count(Customer.id))
        .where(Customer.owner_id == tid)
        .group_by(Customer.status)
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
        .where(Customer.status == CustomerStatus.active, Customer.owner_id == tid)
    )
    mrr = float(mrr_result.scalar() or 0)

    # Revenue this month
    billed_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            and_(
                Invoice.owner_id == tid,
                Invoice.issued_at >= month_start_dt,
                Invoice.status != InvoiceStatus.void,
            )
        )
    )
    billed_this_month = float(billed_result.scalar() or 0)

    collected_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            and_(
                Payment.owner_id == tid,
                Payment.received_at >= month_start_dt,
            )
        )
    )
    collected_this_month = float(collected_result.scalar() or 0)

    # Overdue
    overdue_result = await db.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.amount), 0)).where(
            and_(
                Invoice.owner_id == tid,
                Invoice.status == InvoiceStatus.overdue,
            )
        )
    )
    overdue_row = overdue_result.one()
    overdue_count = overdue_row[0]
    overdue_amount = float(overdue_row[1])

    # Recent payments (last 5) with customer name
    recent_payments_result = await db.execute(
        select(Payment)
        .where(Payment.owner_id == tid)
        .order_by(Payment.received_at.desc())
        .limit(5)
    )
    recent_payments = []
    for p in recent_payments_result.scalars().all():
        customer_name = None
        if p.invoice and p.invoice.customer:
            customer_name = p.invoice.customer.full_name
        recent_payments.append({
            "id": str(p.id),
            "amount": str(p.amount),
            "method": p.method.value,
            "received_at": p.received_at.isoformat() if p.received_at else None,
            "customer_name": customer_name,
        })

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
                and_(Payment.owner_id == tid, Payment.received_at >= m_start, Payment.received_at < m_end)
            )
        )
        revenue_trend.append({
            "month": f"{y}-{m:02d}",
            "collected": float(month_collected.scalar() or 0),
        })

    # --- MikroTik Live Stats (from tenant's first router) ---
    from app.models.router import Router
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
    router_result = await db.execute(select(Router).where(Router.owner_id == tid, Router.is_active == True).limit(1))
    tenant_router = router_result.scalar_one_or_none()
    if tenant_router:
        mt_client = get_mikrotik_client(str(tenant_router.id), tenant_router.url, tenant_router.username, tenant_router.password)
        try:
            identity = await mt_client.get_identity()
            resources = await mt_client.get_resources()
            all_sessions = await mt_client.get_active_sessions()
            # Filter to only this tenant's customers
            cust_result = await db.execute(select(Customer.pppoe_username).where(Customer.owner_id == tid))
            my_usernames = {row[0] for row in cust_result.all()}
            sessions = [s for s in all_sessions if s.get("name") in my_usernames]

            interfaces_resp = await mt_client._request("GET", "interface")
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
async def get_active_sessions(
    format: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get active PPPoE sessions from tenant's routers, filtered to tenant's customers only."""
    from app.models.router import Router
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.owner_id == tid, Router.is_active == True))
    routers = result.scalars().all()
    if not routers:
        if format == "csv":
            return make_csv_response([], "active_sessions.csv")
        return {"sessions": [], "total": 0}

    # Get tenant's customer usernames for filtering
    cust_result = await db.execute(select(Customer.pppoe_username).where(Customer.owner_id == tid))
    tenant_usernames = {row[0] for row in cust_result.all()}

    all_sessions = []
    for r in routers:
        try:
            client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
            sessions = await client.get_active_sessions()
            # Only include sessions belonging to this tenant's customers
            for s in sessions:
                if s.get("name") in tenant_usernames:
                    s["_router_name"] = r.name if hasattr(r, "name") else str(r.id)
                    all_sessions.append(s)
        except Exception:
            pass

    if format == "csv":
        rows = [
            {
                "username": s.get("name", ""),
                "ip_address": s.get("address", ""),
                "mac_address": s.get("caller-id", ""),
                "uptime": s.get("uptime", ""),
                "router_name": s.get("_router_name", ""),
                "bytes_in": s.get("bytes-in", "0"),
                "bytes_out": s.get("bytes-out", "0"),
            }
            for s in all_sessions
        ]
        return make_csv_response(rows, "active_sessions.csv")

    return {"sessions": all_sessions, "total": len(all_sessions)}


@router.get("/status")
async def get_network_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Check MikroTik connectivity for tenant's first router."""
    from app.models.router import Router
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.owner_id == tid, Router.is_active == True).limit(1))
    r = result.scalar_one_or_none()
    if not r:
        return {"connected": False, "error": "No router configured"}
    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    try:
        identity = await client.get_identity()
        resources = await client.get_resources()
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
async def get_subscribers(current_user: User = Depends(get_current_user), tenant_id: str = Depends(get_tenant_id)):
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
    tenant_id: str = Depends(get_tenant_id),
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

    tid = uuid.UUID(tenant_id)

    # Get existing customers to skip duplicates
    existing_result = await db.execute(select(Customer).where(Customer.owner_id == tid))
    existing_customers = existing_result.scalars().all()
    existing_usernames = {c.pppoe_username for c in existing_customers}
    existing_secret_ids = {c.mikrotik_secret_id for c in existing_customers if c.mikrotik_secret_id}

    # Get existing plans to avoid duplicates
    existing_plans_result = await db.execute(select(Plan).where(Plan.owner_id == tid))
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
            owner_id=tid,
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
            owner_id=tid,
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


@router.post("/scan")
async def scan_network(
    body: dict,
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Scan a subnet for MikroTik devices."""
    import asyncio
    subnet = body.get("subnet", "192.168.40.0/24")
    username = body.get("username", "admin")
    password = body.get("password", "")

    # Parse subnet to get IP range
    network = ipaddress.IPv4Network(subnet, strict=False)
    hosts = list(network.hosts())

    found = []

    async def check_host(ip):
        ip_str = str(ip)
        try:
            async with httpx.AsyncClient(verify=False, timeout=2.0, auth=(username, password)) as client:
                resp = await client.get(f"http://{ip_str}/rest/system/identity")
                if resp.status_code == 200:
                    data = resp.json()
                    # Try to get version too
                    try:
                        res_resp = await client.get(f"http://{ip_str}/rest/system/resource")
                        version = res_resp.json().get("version", "") if res_resp.status_code == 200 else ""
                    except Exception:
                        version = ""
                    return {"ip": ip_str, "identity": data.get("name", ""), "version": version, "auth_ok": True}
                elif resp.status_code == 401:
                    return {"ip": ip_str, "identity": "", "version": "", "auth_ok": False}
        except Exception:
            pass
        return None

    # Scan in batches of 20
    for i in range(0, len(hosts), 20):
        batch = hosts[i:i+20]
        results = await asyncio.gather(*[check_host(ip) for ip in batch])
        found.extend([r for r in results if r is not None])

    return {"found": found, "scanned": len(hosts), "subnet": subnet}


@router.get("/hotspot/profiles")
async def get_hotspot_profiles(
    router_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    from app.models.router import Router
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if not r:
        return {"profiles": [], "error": "Router not found"}
    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    try:
        resp = await client._request("GET", "ip/hotspot/user/profile")
        return {"profiles": resp.json()}
    except Exception as e:
        return {"profiles": [], "error": str(e)}


@router.post("/hotspot/profiles")
async def create_hotspot_profile(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    from app.models.router import Router
    tid = uuid.UUID(tenant_id)
    router_id = body.get("router_id")
    if not router_id:
        raise HTTPException(status_code=400, detail="router_id required")
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")
    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    payload = {"name": body["name"]}
    if body.get("rate_limit"):
        payload["rate-limit"] = body["rate_limit"]
    if body.get("session_timeout"):
        payload["session-timeout"] = body["session_timeout"]
    if body.get("shared_users"):
        payload["shared-users"] = str(body["shared_users"])
    if body.get("address_pool"):
        payload["address-pool"] = body["address_pool"]
    resp = await client._request("PUT", "ip/hotspot/user/profile", json=payload)
    return resp.json()


@router.patch("/hotspot/profiles/{profile_id}")
async def update_hotspot_profile(
    profile_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    from app.models.router import Router
    tid = uuid.UUID(tenant_id)
    router_id = body.get("router_id")
    if not router_id:
        raise HTTPException(status_code=400, detail="router_id required")
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")
    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    payload = {}
    if "name" in body:
        payload["name"] = body["name"]
    if "rate_limit" in body:
        payload["rate-limit"] = body["rate_limit"]
    if "session_timeout" in body:
        payload["session-timeout"] = body["session_timeout"]
    if "shared_users" in body:
        payload["shared-users"] = str(body["shared_users"])
    if "address_pool" in body:
        payload["address-pool"] = body["address_pool"]
    resp = await client._request("PATCH", f"ip/hotspot/user/profile/{profile_id}", json=payload)
    return resp.json()


@router.delete("/hotspot/profiles/{profile_id}")
async def delete_hotspot_profile(
    profile_id: str,
    router_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    from app.models.router import Router
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found")
    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    await client._request("DELETE", f"ip/hotspot/user/profile/{profile_id}")
    return {"status": "deleted"}


@router.get("/hotspot/users")
async def get_hotspot_users(
    router_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    from app.models.router import Router
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if not r:
        return {"users": [], "error": "Router not found"}
    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    try:
        resp = await client._request("GET", "ip/hotspot/user")
        return {"users": resp.json(), "total": len(resp.json())}
    except Exception as e:
        return {"users": [], "total": 0, "error": str(e)}


@router.get("/hotspot/sessions")
async def get_hotspot_sessions(
    router_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    from app.models.router import Router
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if not r:
        return {"sessions": [], "error": "Router not found"}
    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    try:
        resp = await client._request("GET", "ip/hotspot/active")
        return {"sessions": resp.json(), "total": len(resp.json())}
    except Exception as e:
        return {"sessions": [], "total": 0, "error": str(e)}
