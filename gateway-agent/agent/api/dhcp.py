from fastapi import APIRouter, Depends

from agent.core.security import verify_api_key
from agent.services import dhcp, dns

router = APIRouter(prefix="/agent/dhcp", tags=["dhcp"], dependencies=[Depends(verify_api_key)])


@router.get("/config")
async def get_dhcp_config():
    return {"config": await dhcp.get_config()}


@router.post("/apply")
async def apply_dhcp_config(body: dict):
    return {"result": await dhcp.apply_config(body["config"])}


@router.get("/leases")
async def get_leases():
    return await dhcp.get_leases()


@router.post("/static-lease")
async def add_static_lease(body: dict):
    return {"result": await dhcp.add_static_lease(
        body["mac"], body["ip"], body.get("hostname", "")
    )}


# DNS endpoints
@router.get("/dns/config")
async def get_dns_config():
    return {"config": await dns.get_dns_config()}


@router.post("/dns/apply")
async def apply_dns_config(body: dict):
    return {"result": await dns.apply_dns_config(body["config"])}


@router.post("/dns/entry")
async def add_dns_entry(body: dict):
    return {"result": await dns.add_dns_entry(body["domain"], body["ip"])}


@router.get("/dns/upstream")
async def get_upstream_dns():
    return await dns.get_upstream_dns()
