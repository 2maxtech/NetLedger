import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class MikroTikError(Exception):
    """Base MikroTik API error."""

    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class MikroTikAuthError(MikroTikError):
    """Raised on HTTP 401 Unauthorized."""


class MikroTikConnectionError(MikroTikError):
    """Raised when the router is unreachable (connection refused / timeout)."""


class MikroTikClient:
    """MikroTik RouterOS v7 REST API client.

    All requests go to https://<host>/rest/ using HTTP Basic Auth.
    SSL verification is disabled because RouterOS ships with a self-signed cert.
    """

    def __init__(
        self,
        url: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.url = (url or getattr(settings, "MIKROTIK_URL", "https://192.168.88.1")).rstrip("/")
        self.user = user or getattr(settings, "MIKROTIK_USER", "admin")
        self.password = password or getattr(settings, "MIKROTIK_PASSWORD", "")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a lazily-initialised httpx.AsyncClient with Basic Auth."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=(self.user, self.password),
                verify=False,
                timeout=30.0,
            )
        return self._client

    def _alt_url(self) -> str | None:
        """Return the URL with the alternate protocol, or None if already tried."""
        if self.url.startswith("https://"):
            return "http://" + self.url[8:]
        if self.url.startswith("http://"):
            return "https://" + self.url[7:]
        return None

    async def _request(
        self,
        method: str,
        path: str,
        json: Any = None,
    ) -> httpx.Response:
        """Perform an authenticated REST request, mapping HTTP errors to exceptions.

        On connection failure, automatically retries with the alternate protocol
        (http ↔ https) and switches permanently if the fallback succeeds.
        """
        url = f"{self.url}/rest/{path.lstrip('/')}"
        client = await self._get_client()
        try:
            response = await client.request(method, url, json=json)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            # Try the other protocol before giving up
            alt = self._alt_url()
            if alt:
                alt_full = f"{alt}/rest/{path.lstrip('/')}"
                try:
                    response = await client.request(method, alt_full, json=json)
                    # Fallback worked — switch permanently
                    logger.info("Switched MikroTik URL from %s to %s", self.url, alt)
                    self.url = alt
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass  # Both failed, raise the original error below
                else:
                    # We got a response from fallback, skip to status checks
                    return self._check_response(response)
            if isinstance(exc, httpx.ConnectError):
                raise MikroTikConnectionError(f"Connection refused to {self.url}: {exc}") from exc
            raise MikroTikConnectionError(f"Request timed out to {self.url}: {exc}") from exc

        return self._check_response(response)

    def _check_response(self, response: httpx.Response) -> httpx.Response:
        if response.status_code == 401:
            raise MikroTikAuthError("Authentication failed (401)", status_code=401)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise MikroTikError(
                f"API error {response.status_code}: {detail}",
                status_code=response.status_code,
            )
        return response

    # --- System ---

    async def get_identity(self) -> str:
        """Return the router's identity (hostname)."""
        resp = await self._request("GET", "system/identity")
        data = resp.json()
        name = data.get("name", "")
        logger.debug("MikroTik identity: %s", name)
        return name

    async def get_resources(self) -> dict:
        """Return system resource info (uptime, memory, CPU, etc.)."""
        resp = await self._request("GET", "system/resource")
        return resp.json()

    # --- PPP Secrets ---

    async def get_secrets(self) -> list[dict]:
        """Return all PPP secrets."""
        resp = await self._request("GET", "ppp/secret")
        return resp.json()

    async def get_secret(self, secret_id: str) -> dict | None:
        """Return a single PPP secret by .id, or None if not found."""
        try:
            resp = await self._request("GET", f"ppp/secret/{secret_id}")
            return resp.json()
        except MikroTikError as exc:
            if exc.status_code == 404:
                return None
            raise

    async def create_secret(
        self,
        name: str,
        password: str,
        profile: str = "default",
        caller_id: str | None = None,
    ) -> str:
        """Create a PPP secret and return its .id."""
        payload: dict[str, Any] = {
            "name": name,
            "password": password,
            "profile": profile,
            "service": "pppoe",
        }
        if caller_id is not None:
            payload["caller-id"] = caller_id

        resp = await self._request("PUT", "ppp/secret", json=payload)
        data = resp.json()
        secret_id = data.get(".id", "")
        logger.info("Created PPP secret '%s' with id %s", name, secret_id)
        return secret_id

    async def update_secret(self, secret_id: str, fields: dict) -> None:
        """Update fields on an existing PPP secret."""
        await self._request("PATCH", f"ppp/secret/{secret_id}", json=fields)
        logger.info("Updated PPP secret %s: %s", secret_id, fields)

    async def enable_secret(self, secret_id: str) -> None:
        """Re-enable a PPP secret (disabled=no)."""
        await self._request("PATCH", f"ppp/secret/{secret_id}", json={"disabled": "no"})
        logger.info("Enabled PPP secret %s", secret_id)

    async def disable_secret(self, secret_id: str) -> None:
        """Disable a PPP secret and kill any active session."""
        # Get the secret name to find the active session
        try:
            secret = await self.get_secret(secret_id)
            if secret:
                username = secret.get("name", "")
                # Kill active session if any
                sessions = await self.get_active_sessions()
                for s in sessions:
                    if s.get("name") == username:
                        sid = s.get(".id", "")
                        if sid:
                            await self._request("DELETE", f"ppp/active/{sid}")
                            logger.info("Killed active session for %s", username)
        except Exception as e:
            logger.warning("Failed to kill active session for secret %s: %s", secret_id, e)
        await self._request("PATCH", f"ppp/secret/{secret_id}", json={"disabled": "yes"})
        logger.info("Disabled PPP secret %s", secret_id)

    async def delete_secret(self, secret_id: str) -> None:
        """Delete a PPP secret."""
        await self._request("DELETE", f"ppp/secret/{secret_id}")
        logger.info("Deleted PPP secret %s", secret_id)

    # --- PPP Profiles (bandwidth via rate-limit) ---

    async def get_profiles(self) -> list[dict]:
        """Return all PPP profiles."""
        resp = await self._request("GET", "ppp/profile")
        return resp.json()

    async def ensure_profile(self, name: str, rate_limit: str) -> str:
        """Ensure a PPP profile exists with the given rate-limit. Returns the profile name.
        rate_limit format: 'upload/download' e.g. '5M/10M' (MikroTik order: rx/tx from server perspective).
        """
        profiles = await self.get_profiles()
        for p in profiles:
            if p.get("name") == name:
                # Update rate-limit if different
                if p.get("rate-limit", "") != rate_limit:
                    await self._request("PATCH", f"ppp/profile/{p['.id']}", json={"rate-limit": rate_limit})
                    logger.info("Updated profile '%s' rate-limit to %s", name, rate_limit)
                return name

        # Create new profile — only set name and rate-limit, let MikroTik use defaults
        # for local/remote address to avoid pool conflicts
        payload = {
            "name": name,
            "rate-limit": rate_limit,
        }
        await self._request("PUT", "ppp/profile", json=payload)
        logger.info("Created profile '%s' with rate-limit %s", name, rate_limit)
        return name

    # --- Simple Queues ---

    async def get_queues(self) -> list[dict]:
        """Return all simple queues."""
        resp = await self._request("GET", "queue/simple")
        return resp.json()

    async def set_queue(self, name: str, target: str, max_limit: str) -> str:
        """Create a simple queue and return its .id.

        Args:
            name: queue name (e.g. subscriber username)
            target: IP address or subnet (e.g. "192.168.1.10/32")
            max_limit: "download/upload" in RouterOS format (e.g. "10M/5M")
        """
        payload = {
            "name": name,
            "target": target,
            "max-limit": max_limit,
        }
        resp = await self._request("PUT", "queue/simple", json=payload)
        data = resp.json()
        queue_id = data.get(".id", "")
        logger.info("Created simple queue '%s' with id %s", name, queue_id)
        return queue_id

    async def update_queue(self, queue_id: str, max_limit: str) -> None:
        """Update the max-limit on an existing simple queue."""
        await self._request("PATCH", f"queue/simple/{queue_id}", json={"max-limit": max_limit})
        logger.info("Updated simple queue %s max-limit to %s", queue_id, max_limit)

    async def remove_queue(self, queue_id: str) -> None:
        """Delete a simple queue."""
        await self._request("DELETE", f"queue/simple/{queue_id}")
        logger.info("Deleted simple queue %s", queue_id)

    # --- Active PPP Sessions ---

    async def get_active_sessions(self) -> list[dict]:
        """Return currently active PPPoE/PPP sessions."""
        resp = await self._request("GET", "ppp/active")
        return resp.json()


# --- Client Factory + Cache ---

_client_cache: dict[str, MikroTikClient] = {}


def get_mikrotik_client(
    router_id: str | None = None,
    url: str | None = None,
    user: str | None = None,
    password: str | None = None,
) -> MikroTikClient:
    """Get or create a MikroTikClient. Cached by router_id."""
    cache_key = router_id or "default"

    if cache_key in _client_cache:
        return _client_cache[cache_key]

    # Auto-prepend http:// if no protocol
    if url and not url.startswith(("http://", "https://")):
        url = "http://" + url
    client = MikroTikClient(url=url, user=user, password=password)
    _client_cache[cache_key] = client
    return client


def invalidate_client(router_id: str) -> None:
    """Remove a cached client (call when router credentials change)."""
    _client_cache.pop(router_id, None)
    _client_cache.pop(str(router_id), None)


async def get_customer_router(db, customer):
    """Resolve the router for a customer: direct → area → first active."""
    from sqlalchemy import select
    from app.models.router import Router

    # 1. Direct assignment
    if customer.router_id:
        result = await db.execute(select(Router).where(Router.id == customer.router_id))
        router = result.scalar_one_or_none()
        if router and router.is_active:
            return router

    # 2. Area's default router
    if hasattr(customer, 'area') and customer.area and customer.area.router_id:
        result = await db.execute(select(Router).where(Router.id == customer.area.router_id))
        router = result.scalar_one_or_none()
        if router and router.is_active:
            return router

    # 3. System default (first active router)
    result = await db.execute(
        select(Router).where(Router.is_active == True).order_by(Router.created_at).limit(1)
    )
    return result.scalar_one_or_none()


async def get_client_for_customer(db, customer) -> tuple[MikroTikClient | None, str | None]:
    """Resolve the customer's router and return (client, router_id)."""
    router = await get_customer_router(db, customer)
    if not router:
        logger.warning("No router found for customer %s", customer.id)
        return None, None

    client = get_mikrotik_client(
        router_id=str(router.id),
        url=router.url,
        user=router.username,
        password=router.password,
    )
    return client, str(router.id)


# Legacy singleton for backward compatibility (uses env vars)
mikrotik = get_mikrotik_client()
