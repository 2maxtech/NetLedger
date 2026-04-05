import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.tenant import get_tenant_id
from app.models.router import Router
from app.models.user import User

router = APIRouter(prefix="/vpn", tags=["vpn"])

WG_API_URL = "http://192.168.40.40:9999"


class VpnActivateRequest(BaseModel):
    public_key: str
    client_lan: str = ""


async def _wg_api(method: str, path: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        if method == "GET":
            r = await client.get(f"{WG_API_URL}{path}")
        else:
            r = await client.post(f"{WG_API_URL}{path}", json=json)
        return r.json()


@router.post("/{router_id}/setup")
async def vpn_setup(
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

    try:
        info = await _wg_api("GET", "/info")
        ip_data = await _wg_api("GET", "/next-ip")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"VPN service unavailable: {e}")

    tunnel_ip = r.wg_tunnel_ip or ip_data["tunnel_ip"]
    server_key = info["server_public_key"]
    endpoint = info["endpoint"]

    if not r.wg_tunnel_ip:
        r.wg_tunnel_ip = tunnel_ip
        await db.flush()

    script = (
        f'/interface/wireguard/add name=wg-netledger listen-port=13231\n'
        f'/interface/wireguard/peers/add interface=wg-netledger '
        f'public-key="{server_key}" '
        f'endpoint-address={endpoint.split(":")[0]} '
        f'endpoint-port={endpoint.split(":")[1]} '
        f'allowed-address=10.10.10.0/24 '
        f'persistent-keepalive=25\n'
        f'/ip/address/add address={tunnel_ip}/24 interface=wg-netledger'
    )

    return {
        "tunnel_ip": tunnel_ip,
        "server_public_key": server_key,
        "endpoint": endpoint,
        "script": script,
        "instructions": [
            "1. Open your MikroTik terminal (Winbox Terminal tab or SSH)",
            "2. Paste the script below and press Enter",
            "3. Run:  /interface/wireguard/print",
            "4. Copy the Public Key shown and paste it back here",
        ],
    }


@router.post("/{router_id}/activate")
async def vpn_activate(
    router_id: uuid.UUID,
    body: VpnActivateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(Router).where(Router.id == router_id, Router.owner_id == tid))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Router not found")

    if not r.wg_tunnel_ip:
        raise HTTPException(status_code=400, detail="Run VPN setup first")

    try:
        resp = await _wg_api("POST", "/add-peer", {
            "public_key": body.public_key,
            "tunnel_ip": r.wg_tunnel_ip,
            "client_lan": body.client_lan,
        })
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"VPN service error: {e}")

    if not resp.get("ok"):
        raise HTTPException(status_code=500, detail=resp.get("message", "Failed to add peer"))

    r.wg_peer_public_key = body.public_key
    r.url = f"http://{r.wg_tunnel_ip}"
    await db.flush()

    from app.services.mikrotik import invalidate_client
    invalidate_client(str(router_id))

    return {
        "status": "activated",
        "tunnel_ip": r.wg_tunnel_ip,
        "router_url": r.url,
        "message": "VPN tunnel activated. Router URL updated to tunnel IP.",
    }


@router.get("/{router_id}/vpn-status")
async def vpn_status(
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

    if not r.wg_peer_public_key:
        return {"status": "not_configured", "tunnel_ip": r.wg_tunnel_ip}

    try:
        peer = await _wg_api("GET", f"/status/{r.wg_peer_public_key}")
    except Exception:
        return {"status": "service_unavailable"}

    if peer.get("error"):
        return {"status": "peer_not_found", "tunnel_ip": r.wg_tunnel_ip}

    connected = peer.get("latest_handshake", 0) > 0
    return {
        "status": "connected" if connected else "waiting",
        "tunnel_ip": r.wg_tunnel_ip,
        "endpoint": peer.get("endpoint"),
        "latest_handshake": peer.get("latest_handshake"),
        "rx_bytes": peer.get("rx_bytes", 0),
        "tx_bytes": peer.get("tx_bytes", 0),
    }
