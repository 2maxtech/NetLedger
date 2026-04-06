import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.tenant import get_tenant_id
from app.models.customer import Customer, CustomerStatus
from app.models.plan import Plan
from app.models.router import Router
from app.models.user import User
from app.schemas.router import RouterCreate, RouterResponse, RouterStatusResponse, RouterUpdate
from app.services.mikrotik import get_mikrotik_client, invalidate_client

router = APIRouter(prefix="/routers", tags=["routers"])


@router.get("/", response_model=list[RouterResponse])
async def list_routers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.owner_id == tid).order_by(Router.created_at))
    return result.scalars().all()


@router.post("/", response_model=RouterResponse, status_code=status.HTTP_201_CREATED)
async def create_router(
    body: RouterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    data = body.model_dump()
    # Auto-prepend http:// if no protocol specified
    if data.get("url") and not data["url"].startswith(("http://", "https://")):
        data["url"] = "http://" + data["url"]
    r = Router(**data)
    r.owner_id = uuid.UUID(tenant_id)
    db.add(r)
    await db.flush()
    await db.refresh(r)
    return r


@router.get("/{router_id}", response_model=RouterResponse)
async def get_router(
    router_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")
    return r


@router.put("/{router_id}", response_model=RouterResponse)
async def update_router(
    router_id: uuid.UUID,
    body: RouterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")

    update_data = body.model_dump(exclude_unset=True)
    if "url" in update_data and update_data["url"] and not update_data["url"].startswith(("http://", "https://")):
        update_data["url"] = "http://" + update_data["url"]
    for field, value in update_data.items():
        setattr(r, field, value)

    invalidate_client(str(router_id))
    await db.flush()
    await db.refresh(r)
    return r


@router.delete("/{router_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_router(
    router_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")
    r.is_active = False
    invalidate_client(str(router_id))
    await db.flush()


@router.get("/{router_id}/status", response_model=RouterStatusResponse)
async def get_router_status(
    router_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")

    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    try:
        identity = await client.get_identity()
        resources = await client.get_resources()
        sessions = await client.get_active_sessions()
        # Fetch interface traffic
        interfaces = []
        try:
            iface_resp = await client._request("GET", "interface")
            for iface in iface_resp.json():
                if iface.get("type") in ("ether", "bridge", "vlan", "pppoe-in"):
                    interfaces.append({
                        "name": iface.get("name", ""),
                        "type": iface.get("type", ""),
                        "running": iface.get("running") == "true",
                        "tx_bytes": int(iface.get("tx-byte", 0)),
                        "rx_bytes": int(iface.get("rx-byte", 0)),
                    })
        except Exception:
            pass
        return RouterStatusResponse(
            id=r.id,
            name=r.name,
            connected=True,
            identity=identity,
            uptime=resources.get("uptime", ""),
            cpu_load=resources.get("cpu-load", "0"),
            free_memory=int(resources.get("free-memory", 0)),
            total_memory=int(resources.get("total-memory", 0)),
            active_sessions=len(sessions),
            version=resources.get("version", ""),
            interfaces=interfaces,
        )
    except Exception as e:
        error_msg = str(e)
        if "timed out" in error_msg.lower() or "connection refused" in error_msg.lower():
            error_msg = (
                f"Cannot reach router at {r.url}. "
                "Make sure NetLedger can access the router. "
                "If behind NAT, port-forward port 443 or run NetLedger on the same LAN."
            )
        return RouterStatusResponse(id=r.id, name=r.name, connected=False, error=error_msg)


def _to_mbps(s: str) -> int:
    s = s.strip().lower()
    if s.endswith("m"):
        return int(float(s[:-1]))
    elif s.endswith("k"):
        return max(1, int(float(s[:-1]) / 1000))
    return max(1, int(float(s)) // 1_000_000) if s.replace(".", "").isdigit() else 1


async def _fetch_mt_data(r: Router):
    """Fetch profiles and secrets from MikroTik, with error handling."""
    client = get_mikrotik_client(str(r.id), r.url, r.username, r.password)
    try:
        mt_profiles = await client.get_profiles()
        mt_secrets = await client.get_secrets()
        return mt_profiles, mt_secrets
    except Exception as e:
        error_msg = str(e)
        if "timed out" in error_msg.lower() or "connection refused" in error_msg.lower():
            error_msg = (
                f"Cannot reach router at {r.url}. "
                "Make sure NetLedger can access the router's IP/hostname. "
                "If your router is behind NAT, you need to port-forward the REST API (port 443) "
                "or run NetLedger on the same local network."
            )
        raise HTTPException(status_code=502, detail=error_msg)


@router.post("/{router_id}/import/preview")
async def import_preview(
    router_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Preview import: returns profiles with speeds and customer count, no data saved."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")

    mt_profiles, mt_secrets = await _fetch_mt_data(r)

    # Build profile info
    profile_info: dict[str, str] = {}
    for p in mt_profiles:
        profile_info[p["name"]] = p.get("rate-limit", "")

    # Existing data
    existing_result = await db.execute(select(Customer).where(Customer.owner_id == tid))
    existing_customers = existing_result.scalars().all()
    existing_usernames = {c.pppoe_username for c in existing_customers}
    existing_secret_ids = {c.mikrotik_secret_id for c in existing_customers if c.mikrotik_secret_id}

    plans_result = await db.execute(select(Plan).where(Plan.owner_id == tid))
    existing_plans = {p.name: p for p in plans_result.scalars().all()}

    # Which profiles are used by secrets
    used_profiles = {s.get("profile", "default") for s in mt_secrets if s.get("name")}

    # Count new customers
    new_customers = 0
    for secret in mt_secrets:
        username = secret.get("name", "")
        secret_id = secret.get(".id", "")
        if not username:
            continue
        if username not in existing_usernames and secret_id not in existing_secret_ids:
            new_customers += 1

    # Build plan list for pricing
    plans = []
    for pname in sorted(used_profiles):
        rate = profile_info.get(pname, "")
        if rate:
            parts = rate.split("/")
            if len(parts) == 2:
                download = _to_mbps(parts[1])
                upload = _to_mbps(parts[0])
            else:
                download, upload = 10, 5
        else:
            download, upload = 10, 5

        # Count customers on this profile
        count = sum(1 for s in mt_secrets if s.get("profile", "default") == pname and s.get("name"))
        existing = pname in existing_plans
        existing_price = float(existing_plans[pname].monthly_price) if existing else 0

        plans.append({
            "name": pname,
            "download_mbps": download,
            "upload_mbps": upload,
            "rate_limit": rate or "none",
            "customer_count": count,
            "already_exists": existing,
            "current_price": existing_price,
        })

    return {
        "plans": plans,
        "total_secrets": len(mt_secrets),
        "new_customers": new_customers,
        "existing_customers": len(mt_secrets) - new_customers,
    }


from pydantic import BaseModel


class ImportRequest(BaseModel):
    plan_prices: dict[str, float] = {}


@router.post("/{router_id}/import")
async def import_from_router(
    router_id: uuid.UUID,
    body: ImportRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Import PPPoE secrets and profiles from a specific router into NetLedger."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")

    plan_prices = (body.plan_prices if body else None) or {}
    mt_profiles, mt_secrets = await _fetch_mt_data(r)

    # Build profile → rate-limit map
    profile_info: dict[str, str] = {}
    for p in mt_profiles:
        profile_info[p["name"]] = p.get("rate-limit", "")

    # Get existing data
    existing_result = await db.execute(select(Customer).where(Customer.owner_id == tid))
    existing_customers = existing_result.scalars().all()
    existing_usernames = {c.pppoe_username for c in existing_customers}
    existing_secret_ids = {c.mikrotik_secret_id for c in existing_customers if c.mikrotik_secret_id}

    plans_result = await db.execute(select(Plan).where(Plan.owner_id == tid))
    existing_plans_list = plans_result.scalars().all()
    existing_plans = {p.name: p for p in existing_plans_list}

    plans_created = 0
    plans_updated = 0
    customers_created = 0
    customers_skipped = 0

    used_profiles = {s.get("profile", "default") for s in mt_secrets if s.get("name")}

    plan_map: dict[str, Plan] = {}
    for pname in used_profiles:
        price = Decimal(str(plan_prices.get(pname, 0)))
        if pname in existing_plans:
            plan_map[pname] = existing_plans[pname]
            # Update price if a new price was provided and it's different
            if pname in plan_prices and existing_plans[pname].monthly_price != price:
                existing_plans[pname].monthly_price = price
                plans_updated += 1
            continue
        rate = profile_info.get(pname, "")
        if rate:
            parts = rate.split("/")
            if len(parts) == 2:
                download = _to_mbps(parts[1])
                upload = _to_mbps(parts[0])
            else:
                download, upload = 10, 5
        else:
            download, upload = 10, 5
        plan = Plan(
            name=pname,
            download_mbps=download,
            upload_mbps=upload,
            monthly_price=price,
            is_active=True,
            description=f"Imported from MikroTik" + (" (no rate-limit set)" if not rate else ""),
            owner_id=tid,
        )
        db.add(plan)
        await db.flush()
        await db.refresh(plan)
        plan_map[pname] = plan
        existing_plans[pname] = plan
        plans_created += 1

    for secret in mt_secrets:
        secret_id = secret.get(".id", "")
        username = secret.get("name", "")
        if not username:
            continue
        if username in existing_usernames or secret_id in existing_secret_ids:
            customers_skipped += 1
            continue
        profile = secret.get("profile", "default")
        plan = plan_map.get(profile)
        if not plan:
            plan = next((p for p in existing_plans.values() if p.is_active), None)
        if not plan:
            customers_skipped += 1
            continue
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
            router_id=router_id,
            owner_id=tid,
        )
        db.add(customer)
        existing_usernames.add(username)
        customers_created += 1

    await db.flush()
    return {
        "plans_created": plans_created,
        "plans_updated": plans_updated,
        "customers_created": customers_created,
        "customers_skipped": customers_skipped,
        "total_secrets": len(mt_secrets),
    }
