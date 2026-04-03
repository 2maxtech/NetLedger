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
