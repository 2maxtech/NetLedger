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

    async def ensure_profile(
        self,
        name: str,
        rate_limit: str,
        local_address: str | None = None,
        remote_address: str | None = None,
        dns_server: str | None = None,
        parent_queue: str | None = None,
    ) -> str:
        """Ensure a PPP profile exists with the given settings. Returns the profile name."""
        profiles = await self.get_profiles()
        for p in profiles:
            if p.get("name") == name:
                # Update fields if different
                updates = {}
                if p.get("rate-limit", "") != rate_limit:
                    updates["rate-limit"] = rate_limit
                if local_address is not None and p.get("local-address", "") != local_address:
                    updates["local-address"] = local_address
                if remote_address is not None and p.get("remote-address", "") != remote_address:
                    updates["remote-address"] = remote_address
                if dns_server is not None and p.get("dns-server", "") != dns_server:
                    updates["dns-server"] = dns_server
                if parent_queue is not None and p.get("parent-queue", "") != parent_queue:
                    updates["parent-queue"] = parent_queue
                if p.get("only-one") != "yes":
                    updates["only-one"] = "yes"
                if updates:
                    await self._request("PATCH", f"ppp/profile/{p['.id']}", json=updates)
                    logger.info("Updated profile '%s': %s", name, updates)
                return name

        # Create new profile
        payload = {"name": name, "rate-limit": rate_limit, "only-one": "yes"}
        if local_address:
            payload["local-address"] = local_address
        if remote_address:
            payload["remote-address"] = remote_address
        if dns_server:
            payload["dns-server"] = dns_server
        if parent_queue:
            payload["parent-queue"] = parent_queue
        await self._request("PUT", "ppp/profile", json=payload)
        logger.info("Created profile '%s' with %s", name, payload)
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

    async def find_user_queues(self, username: str) -> list[dict]:
        """Return simple queues that shadow a PPPoE user's bandwidth.

        Matches by queue name == username, or target referencing the
        auto-named PPPoE interface ``<pppoe-{username}>``.
        """
        queues = await self.get_queues()
        interface_marker = f"<pppoe-{username}>"
        result: list[dict] = []
        for q in queues:
            if q.get("name") == username:
                result.append(q)
                continue
            target = q.get("target", "") or ""
            if interface_marker in target:
                result.append(q)
        return result

    async def disable_user_queues(self, username: str) -> int:
        """Disable simple queues shadowing this PPPoE user. Returns count affected.

        Existing per-user simple queues enforce bandwidth at the IP/interface
        layer, shadowing the PPP profile's rate-limit. Disabling them lets the
        profile (e.g. throttle) take effect after the session reconnects.
        """
        queues = await self.find_user_queues(username)
        count = 0
        for q in queues:
            if q.get("disabled") == "true":
                continue
            await self._request(
                "PATCH",
                f"queue/simple/{q['.id']}",
                json={"disabled": "yes"},
            )
            logger.info(
                "Disabled simple queue %s (%s) shadowing %s",
                q.get(".id"), q.get("name"), username,
            )
            count += 1
        return count

    async def enable_user_queues(self, username: str) -> int:
        """Re-enable simple queues shadowing this PPPoE user. Returns count affected."""
        queues = await self.find_user_queues(username)
        count = 0
        for q in queues:
            if q.get("disabled") != "true":
                continue
            await self._request(
                "PATCH",
                f"queue/simple/{q['.id']}",
                json={"disabled": "no"},
            )
            logger.info(
                "Enabled simple queue %s (%s) for %s",
                q.get(".id"), q.get("name"), username,
            )
            count += 1
        return count

    # --- Active PPP Sessions ---

    async def get_active_sessions(self) -> list[dict]:
        """Return currently active PPPoE/PPP sessions."""
        resp = await self._request("GET", "ppp/active")
        return resp.json()

    async def get_active_session_ip(self, username: str) -> str | None:
        """Return the current IP address of an active PPPoE session, or None."""
        sessions = await self.get_active_sessions()
        for s in sessions:
            if s.get("name") == username:
                return s.get("address")
        return None

    async def kick_session(self, username: str) -> bool:
        """Remove active PPP session by username, forcing reconnect with new profile."""
        sessions = await self.get_active_sessions()
        for s in sessions:
            if s.get("name") == username:
                await self._request("DELETE", f"ppp/active/{s['.id']}")
                logger.info("Kicked active session for '%s'", username)
                return True
        return False

    # --- Firewall NAT (redirect rules) ---

    NAT_COMMENT_PREFIX = "netledger-redirect-"

    async def add_nat_redirect(
        self,
        src_address: str,
        to_address: str,
        to_port: int = 80,
        comment: str = "",
    ) -> str:
        """Create a dstnat rule that redirects HTTP traffic from src_address to a notification server.

        Returns the .id of the created rule.
        """
        payload = {
            "chain": "dstnat",
            "action": "dst-nat",
            "src-address": src_address,
            "protocol": "tcp",
            "dst-port": "80",
            "to-addresses": to_address,
            "to-ports": str(to_port),
            "comment": comment,
        }
        resp = await self._request("PUT", "ip/firewall/nat", json=payload)
        data = resp.json()
        rule_id = data.get(".id", "")
        logger.info("Created NAT redirect %s → %s:%s (id=%s)", src_address, to_address, to_port, rule_id)
        return rule_id

    async def remove_nat_redirect(self, comment: str) -> int:
        """Remove NAT redirect rules matching the exact comment. Returns count removed."""
        rules = await self._request("GET", "ip/firewall/nat")
        removed = 0
        for rule in rules.json():
            if rule.get("comment") == comment:
                await self._request("DELETE", f"ip/firewall/nat/{rule['.id']}")
                logger.info("Removed NAT redirect rule %s (%s)", rule[".id"], comment)
                removed += 1
        return removed

    async def remove_nat_redirects_by_prefix(self, prefix: str) -> int:
        """Remove all NAT redirect rules whose comment starts with prefix. Returns count removed."""
        rules = await self._request("GET", "ip/firewall/nat")
        removed = 0
        for rule in rules.json():
            if (rule.get("comment") or "").startswith(prefix):
                await self._request("DELETE", f"ip/firewall/nat/{rule['.id']}")
                logger.info("Removed NAT redirect rule %s (%s)", rule[".id"], rule.get("comment"))
                removed += 1
        return removed

    async def get_nat_redirects(self, prefix: str | None = None) -> list[dict]:
        """List NAT redirect rules, optionally filtered by comment prefix."""
        rules = await self._request("GET", "ip/firewall/nat")
        result = []
        for rule in rules.json():
            comment = rule.get("comment", "")
            if prefix is None or comment.startswith(prefix):
                result.append(rule)
        return result


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

    # 3. Tenant default (first active router for the same owner)
    result = await db.execute(
        select(Router).where(Router.is_active == True, Router.owner_id == customer.owner_id).order_by(Router.created_at).limit(1)
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
