"""NAT redirect management for overdue customer browser notification.

Creates/removes MikroTik firewall NAT dstnat rules to redirect overdue
customers' HTTP traffic to a payment notification page.
"""

import logging
import socket
import uuid
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.app_setting import AppSetting
from app.models.customer import Customer
from app.services.mikrotik import get_client_for_customer

logger = logging.getLogger(__name__)

COMMENT_PREFIX = "netledger-redirect-"

# Cache resolved server IP (only changes on restart)
_resolved_server_ip: str | None = None


def _resolve_server_ip() -> str:
    """Resolve the server IP from BASE_URL. Cached after first call."""
    global _resolved_server_ip
    if _resolved_server_ip:
        return _resolved_server_ip

    parsed = urlparse(settings.BASE_URL)
    host = parsed.hostname or "localhost"

    # If it's already an IP, use it directly
    try:
        socket.inet_aton(host)
        _resolved_server_ip = host
        return host
    except socket.error:
        pass

    # Resolve hostname to IP
    try:
        ip = socket.gethostbyname(host)
        _resolved_server_ip = ip
        logger.info("Resolved server IP for NAT redirect: %s → %s", host, ip)
        return ip
    except socket.gaierror:
        logger.warning("Failed to resolve %s for NAT redirect, using as-is", host)
        _resolved_server_ip = host
        return host


def _make_comment(customer_id: uuid.UUID) -> str:
    """Build the NAT rule comment for a customer."""
    return f"{COMMENT_PREFIX}{customer_id}"


async def _is_redirect_enabled(db: AsyncSession, owner_id: uuid.UUID) -> tuple[bool, str]:
    """Check if NAT redirect is enabled for a tenant. Returns (enabled, portal_slug)."""
    keys = ["nat_redirect_enabled", "portal_slug"]
    result = await db.execute(
        select(AppSetting).where(
            AppSetting.key.in_(keys),
            AppSetting.owner_id == owner_id,
        )
    )
    s = {row.key: row.value for row in result.scalars().all()}
    enabled = s.get("nat_redirect_enabled") == "true"
    slug = s.get("portal_slug", "")
    return enabled, slug


async def add_redirect_for_customer(db: AsyncSession, customer: Customer) -> bool:
    """Add a NAT redirect rule for a throttled/overdue customer.

    Returns True if redirect was created, False if skipped or failed.
    """
    enabled, slug = await _is_redirect_enabled(db, customer.owner_id)

    if not enabled:
        return False

    if not slug:
        logger.warning("NAT redirect: no portal_slug for tenant %s", customer.owner_id)
        return False

    redirect_ip = _resolve_server_ip()

    try:
        client, _ = await get_client_for_customer(db, customer)
        if not client:
            logger.warning("NAT redirect: no MikroTik client for customer %s", customer.id)
            return False

        # Get customer's current PPPoE IP
        ip = await client.get_active_session_ip(customer.pppoe_username)
        if not ip:
            logger.info("NAT redirect: customer %s has no active session, skipping", customer.pppoe_username)
            return False

        comment = _make_comment(customer.id)

        # Remove any existing redirect first (idempotent)
        await client.remove_nat_redirect(comment)

        # Create new redirect rule
        await client.add_nat_redirect(
            src_address=ip,
            to_address=redirect_ip,
            to_port=80,
            comment=comment,
        )
        logger.info("NAT redirect added for %s (%s) → %s", customer.pppoe_username, ip, redirect_ip)
        return True

    except Exception as e:
        logger.error("NAT redirect failed for customer %s: %s", customer.id, e)
        return False


async def remove_redirect_for_customer(db: AsyncSession, customer: Customer) -> bool:
    """Remove NAT redirect rules for a customer.

    Returns True if any rules were removed, False otherwise.
    """
    try:
        client, _ = await get_client_for_customer(db, customer)
        if not client:
            return False

        comment = _make_comment(customer.id)
        removed = await client.remove_nat_redirect(comment)
        if removed > 0:
            logger.info("NAT redirect removed for %s (%d rules)", customer.pppoe_username, removed)
        return removed > 0

    except Exception as e:
        logger.error("NAT redirect removal failed for customer %s: %s", customer.id, e)
        return False


async def check_redirect_for_customer(db: AsyncSession, customer: Customer) -> dict | None:
    """Check if a NAT redirect rule exists for a customer.

    Returns the rule dict if found, None otherwise.
    """
    try:
        client, _ = await get_client_for_customer(db, customer)
        if not client:
            return None

        comment = _make_comment(customer.id)
        rules = await client.get_nat_redirects(comment)
        for rule in rules:
            if rule.get("comment") == comment:
                return {
                    "id": rule.get(".id"),
                    "src_address": rule.get("src-address"),
                    "to_address": rule.get("to-addresses"),
                    "to_port": rule.get("to-ports"),
                    "comment": rule.get("comment"),
                    "disabled": rule.get("disabled", "false"),
                }
        return None

    except Exception as e:
        logger.error("NAT redirect check failed for customer %s: %s", customer.id, e)
        return None
