from fastapi import APIRouter, Depends, Query

from app.core.dependencies import require_role
from app.models.user import UserRole
from app.services import gateway

router = APIRouter(prefix="/security", tags=["security"])
admin_only = Depends(require_role(UserRole.admin))


# --- Suricata ---
@router.get("/suricata/status", dependencies=[admin_only])
async def suricata_status():
    return await gateway.get_suricata_status()

@router.get("/suricata/stats", dependencies=[admin_only])
async def suricata_stats():
    return await gateway.get_suricata_stats()

@router.get("/suricata/alerts", dependencies=[admin_only])
async def suricata_alerts(limit: int = Query(50)):
    return await gateway.get_suricata_alerts(limit)

@router.get("/suricata/rules", dependencies=[admin_only])
async def suricata_rules():
    return await gateway.get_suricata_rules()

@router.post("/suricata/reload", dependencies=[admin_only])
async def suricata_reload():
    return await gateway.suricata_reload()

@router.post("/suricata/start", dependencies=[admin_only])
async def suricata_start():
    return await gateway.suricata_start()

@router.post("/suricata/stop", dependencies=[admin_only])
async def suricata_stop():
    return await gateway.suricata_stop()

# --- DNS Filtering ---
@router.get("/dns-filter/domains", dependencies=[admin_only])
async def get_blocked_domains():
    return await gateway.get_blocked_domains()

@router.post("/dns-filter/domain", dependencies=[admin_only])
async def add_blocked_domain(body: dict):
    return await gateway.add_blocked_domain(body["domain"])

@router.delete("/dns-filter/domain", dependencies=[admin_only])
async def remove_blocked_domain(body: dict):
    return await gateway.remove_blocked_domain(body["domain"])

@router.post("/dns-filter/apply", dependencies=[admin_only])
async def apply_dns_blocklist(body: dict):
    return await gateway.apply_dns_blocklist(body["domains"])

# --- GeoIP ---
@router.get("/geoip/countries", dependencies=[admin_only])
async def get_blocked_countries():
    return await gateway.get_blocked_countries()

@router.post("/geoip/apply", dependencies=[admin_only])
async def apply_geoip_block(body: dict):
    return await gateway.apply_geoip_block(body["country_codes"])
