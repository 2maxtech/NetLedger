import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0)
HEADERS = {"X-API-Key": settings.GATEWAY_API_KEY}


async def _request(method: str, path: str, json: dict | None = None) -> dict:
    url = f"{settings.GATEWAY_AGENT_URL}{path}"
    async with httpx.AsyncClient(timeout=TIMEOUT, verify=False) as client:
        response = await client.request(method, url, headers=HEADERS, json=json)
        response.raise_for_status()
        return response.json()


async def get_active_sessions() -> list[dict]:
    return await _request("GET", "/agent/pppoe/sessions")


async def disconnect_customer(customer_id: str, pppoe_username: str) -> dict:
    return await _request("POST", "/agent/pppoe/disconnect", json={
        "customer_id": customer_id,
        "pppoe_username": pppoe_username,
    })


async def reconnect_customer(customer_id: str, pppoe_username: str) -> dict:
    return await _request("POST", "/agent/pppoe/reconnect", json={
        "customer_id": customer_id,
        "pppoe_username": pppoe_username,
    })


async def throttle_customer(customer_id: str, pppoe_username: str, download_mbps: int, upload_kbps: int) -> dict:
    return await _request("POST", "/agent/pppoe/throttle", json={
        "customer_id": customer_id,
        "pppoe_username": pppoe_username,
        "download_mbps": download_mbps,
        "upload_kbps": upload_kbps,
    })


# --- Firewall ---
async def get_firewall_ruleset() -> dict:
    return await _request("GET", "/agent/firewall/ruleset")

async def get_firewall_tables() -> list:
    return await _request("GET", "/agent/firewall/tables")

async def add_firewall_rule(table: str, chain: str, rule: str, family: str = "inet") -> dict:
    return await _request("POST", "/agent/firewall/rule", json={"table": table, "chain": chain, "rule": rule, "family": family})

async def delete_firewall_rule(table: str, chain: str, handle: int, family: str = "inet") -> dict:
    return await _request("DELETE", "/agent/firewall/rule", json={"table": table, "chain": chain, "handle": handle, "family": family})

async def flush_firewall_chain(table: str, chain: str, family: str = "inet") -> dict:
    return await _request("POST", "/agent/firewall/flush", json={"table": table, "chain": chain, "family": family})


# --- Network ---
async def get_interfaces() -> list:
    return await _request("GET", "/agent/network/interfaces")

async def get_routes() -> list:
    return await _request("GET", "/agent/network/routes")

async def add_route(destination: str, gw: str, interface: str | None = None) -> dict:
    return await _request("POST", "/agent/network/route", json={"destination": destination, "gateway": gw, "interface": interface})

async def delete_route(destination: str) -> dict:
    return await _request("DELETE", "/agent/network/route", json={"destination": destination})

async def get_nat_rules() -> dict:
    return await _request("GET", "/agent/network/nat")

async def add_nat_masquerade(out_interface: str) -> dict:
    return await _request("POST", "/agent/network/nat/masquerade", json={"out_interface": out_interface})

async def add_port_forward(protocol: str, dport: int, dest_ip: str, dest_port: int, in_interface: str | None = None) -> dict:
    return await _request("POST", "/agent/network/nat/port-forward", json={"protocol": protocol, "dport": dport, "dest_ip": dest_ip, "dest_port": dest_port, "in_interface": in_interface})


# --- DHCP ---
async def get_dhcp_leases() -> list:
    return await _request("GET", "/agent/dhcp/leases")

async def get_dhcp_config() -> dict:
    return await _request("GET", "/agent/dhcp/config")

async def apply_dhcp_config(config: str) -> dict:
    return await _request("POST", "/agent/dhcp/apply", json={"config": config})


# --- DNS ---
async def get_dns_config() -> dict:
    return await _request("GET", "/agent/dhcp/dns/config")

async def add_dns_entry(domain: str, ip: str) -> dict:
    return await _request("POST", "/agent/dhcp/dns/entry", json={"domain": domain, "ip": ip})

async def get_upstream_dns() -> list:
    return await _request("GET", "/agent/dhcp/dns/upstream")


# --- Suricata IDS/IPS ---
async def get_suricata_status() -> dict:
    return await _request("GET", "/agent/security/suricata/status")

async def get_suricata_stats() -> dict:
    return await _request("GET", "/agent/security/suricata/stats")

async def get_suricata_alerts(limit: int = 50) -> list:
    return await _request("GET", f"/agent/security/suricata/alerts?limit={limit}")

async def get_suricata_rules() -> list:
    return await _request("GET", "/agent/security/suricata/rules")

async def suricata_reload() -> dict:
    return await _request("POST", "/agent/security/suricata/reload")

async def suricata_start() -> dict:
    return await _request("POST", "/agent/security/suricata/start")

async def suricata_stop() -> dict:
    return await _request("POST", "/agent/security/suricata/stop")

# --- DNS Filtering ---
async def get_blocked_domains() -> list:
    return await _request("GET", "/agent/security/dns-filter/domains")

async def add_blocked_domain(domain: str) -> dict:
    return await _request("POST", "/agent/security/dns-filter/domain", json={"domain": domain})

async def remove_blocked_domain(domain: str) -> dict:
    return await _request("DELETE", "/agent/security/dns-filter/domain", json={"domain": domain})

async def apply_dns_blocklist(domains: list) -> dict:
    return await _request("POST", "/agent/security/dns-filter/apply", json={"domains": domains})

# --- GeoIP ---
async def get_blocked_countries() -> list:
    return await _request("GET", "/agent/security/geoip/countries")

async def apply_geoip_block(country_codes: list) -> dict:
    return await _request("POST", "/agent/security/geoip/apply", json={"country_codes": country_codes})
