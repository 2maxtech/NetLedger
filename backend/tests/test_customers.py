"""E2E tests for customer endpoints — verifies full MikroTik sync chain.

Every customer lifecycle operation (create, disconnect, reconnect, throttle,
change-plan, delete) is tested to ensure MikroTik API calls are made with
correct arguments. MikroTik I/O is mocked at the get_client_for_customer
boundary so the rest of the stack (DB, auth, routing) runs for real.
"""
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.plan import Plan
from app.models.router import Router

API = settings.API_V1_PREFIX

# All modules that import get_client_for_customer — patch them all
_GCFC_PATHS = [
    "app.api.admin.customers.get_client_for_customer",
    "app.services.nat_redirect.get_client_for_customer",
]

# ---------------------------------------------------------------------------
# Mock MikroTik client
# ---------------------------------------------------------------------------

def _mock_mt_client():
    """Return an AsyncMock that behaves like MikroTikClient."""
    mt = AsyncMock()
    mt.create_secret.return_value = "*NEW_SECRET"
    mt.ensure_profile.return_value = "Test Plan 10Mbps"
    mt.enable_secret.return_value = None
    mt.disable_secret.return_value = None
    mt.delete_secret.return_value = None
    mt.update_secret.return_value = None
    mt.kick_session.return_value = True
    mt.get_secret.return_value = {".id": "*NEW_SECRET", "name": "juan"}
    mt.get_active_sessions.return_value = []
    mt.remove_nat_redirect.return_value = None
    mt.add_nat_redirect.return_value = "*NAT1"
    mt.get_nat_redirects.return_value = []
    return mt


@contextmanager
def mock_mikrotik(mt=None):
    """Patch get_client_for_customer everywhere it's imported."""
    if mt is None:
        mt = _mock_mt_client()
    mock_return = AsyncMock(return_value=(mt, "router-id"))
    patches = [patch(p, mock_return) for p in _GCFC_PATHS]
    for p in patches:
        p.start()
    try:
        yield mt
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_router(db_session: AsyncSession, admin_user) -> Router:
    """Create an active router so get_client_for_customer can resolve it."""
    router = Router(
        name="Test Router",
        url="https://192.168.88.1",
        username="admin",
        password="secret",
        is_active=True,
        owner_id=admin_user.id,
    )
    db_session.add(router)
    await db_session.commit()
    await db_session.refresh(router)
    return router


@pytest_asyncio.fixture
async def test_plan(db_session: AsyncSession, admin_user) -> Plan:
    plan = Plan(
        name="Test Plan 10Mbps",
        download_mbps=10,
        upload_mbps=5,
        monthly_price=999.00,
        is_active=True,
        owner_id=admin_user.id,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest_asyncio.fixture
async def second_plan(db_session: AsyncSession, admin_user) -> Plan:
    plan = Plan(
        name="Premium 50Mbps",
        download_mbps=50,
        upload_mbps=25,
        monthly_price=1999.00,
        is_active=True,
        owner_id=admin_user.id,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


def customer_payload(plan_id: str, suffix: str = "") -> dict:
    return {
        "full_name": f"Juan Cruz{suffix}",
        "email": f"juan{suffix}@example.com",
        "phone": "09171234567",
        "address": "Manila, Philippines",
        "pppoe_username": f"juan{suffix}",
        "pppoe_password": "secret123",
        "plan_id": plan_id,
    }


# ---------------------------------------------------------------------------
# Helper: create a customer with mocked MT and return (response_data, mock)
# ---------------------------------------------------------------------------

async def create_customer_with_mt(client, auth_headers, plan_id, suffix=""):
    """POST /customers/ with MikroTik mocked. Returns (data, mt_mock, status)."""
    with mock_mikrotik() as mt:
        resp = await client.post(
            f"{API}/customers/",
            json=customer_payload(str(plan_id), suffix),
            headers=auth_headers,
        )
    return resp.json(), mt, resp.status_code


# ===========================================================================
# CREATE
# ===========================================================================

@pytest.mark.asyncio
async def test_create_customer_syncs_to_mikrotik(client, auth_headers, test_plan, test_router):
    """Creating a customer must create a PPP secret on MikroTik."""
    data, mt, status = await create_customer_with_mt(client, auth_headers, test_plan.id)

    assert status == 201
    assert data["full_name"] == "Juan Cruz"
    assert data["status"] == "active"
    assert data["pppoe_username"] == "juan"
    assert "pppoe_password" not in data  # password never exposed

    # MikroTik sync must have happened
    assert data["mikrotik_secret_id"] == "*NEW_SECRET"

    # Verify ensure_profile was called with correct plan bandwidth
    mt.ensure_profile.assert_awaited_once()
    profile_args = mt.ensure_profile.call_args
    assert profile_args[0][0] == "Test Plan 10Mbps"  # profile name = plan name
    assert profile_args[0][1] == "5M/10M"             # upload/download

    # Verify create_secret was called with correct credentials
    mt.create_secret.assert_awaited_once()
    secret_args = mt.create_secret.call_args
    assert secret_args[1]["name"] == "juan"
    assert secret_args[1]["password"] == "secret123"
    assert secret_args[1]["profile"] == "Test Plan 10Mbps"


@pytest.mark.asyncio
async def test_create_customer_with_mac_syncs_caller_id(client, auth_headers, test_plan, test_router):
    """MAC address must be passed as caller-id to MikroTik."""
    payload = customer_payload(str(test_plan.id), "_mac")
    payload["mac_address"] = "AA:BB:CC:DD:EE:FF"

    with mock_mikrotik() as mt:
        resp = await client.post(
            f"{API}/customers/",
            json=payload,
            headers=auth_headers,
        )

    assert resp.status_code == 201
    mt.create_secret.assert_awaited_once()
    assert mt.create_secret.call_args[1]["caller_id"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_create_customer_still_saved_when_mikrotik_down(client, auth_headers, test_plan, test_router):
    """If MikroTik is unreachable, customer is still created (but no secret_id)."""
    mock_return = AsyncMock(return_value=(None, None))
    patches = [patch(p, mock_return) for p in _GCFC_PATHS]
    for p in patches:
        p.start()
    try:
        resp = await client.post(
            f"{API}/customers/",
            json=customer_payload(str(test_plan.id), "_nomt"),
            headers=auth_headers,
        )
    finally:
        for p in patches:
            p.stop()

    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "Juan Cruz_nomt"
    assert data["mikrotik_secret_id"] is None


# ===========================================================================
# DISCONNECT
# ===========================================================================

@pytest.mark.asyncio
async def test_disconnect_disables_secret_on_mikrotik(client, auth_headers, test_plan, test_router):
    """Disconnect must disable the PPP secret on MikroTik."""
    data, _, _ = await create_customer_with_mt(client, auth_headers, test_plan.id, "_disc")
    customer_id = data["id"]

    with mock_mikrotik() as mt:
        resp = await client.post(
            f"{API}/customers/{customer_id}/disconnect",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"
    mt.disable_secret.assert_awaited_once_with("*NEW_SECRET")


# ===========================================================================
# RECONNECT
# ===========================================================================

@pytest.mark.asyncio
async def test_reconnect_enables_secret_on_mikrotik(client, auth_headers, test_plan, test_router):
    """Reconnect must re-enable the PPP secret and restore the plan profile."""
    data, _, _ = await create_customer_with_mt(client, auth_headers, test_plan.id, "_recon")
    customer_id = data["id"]

    # Disconnect first
    with mock_mikrotik():
        await client.post(f"{API}/customers/{customer_id}/disconnect", headers=auth_headers)

    # Reconnect
    with mock_mikrotik() as mt:
        resp = await client.post(
            f"{API}/customers/{customer_id}/reconnect",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "reconnected"
    mt.enable_secret.assert_awaited_once_with("*NEW_SECRET")

    # Plan profile must be restored
    mt.ensure_profile.assert_awaited_once()
    profile_args = mt.ensure_profile.call_args
    assert profile_args[0][0] == "Test Plan 10Mbps"
    assert profile_args[0][1] == "5M/10M"


@pytest.mark.asyncio
async def test_reconnect_recreates_secret_if_missing(client, auth_headers, test_plan, test_router):
    """If the PPP secret was deleted from MikroTik, reconnect must recreate it."""
    data, _, _ = await create_customer_with_mt(client, auth_headers, test_plan.id, "_recreate")
    customer_id = data["id"]

    # Disconnect
    with mock_mikrotik():
        await client.post(f"{API}/customers/{customer_id}/disconnect", headers=auth_headers)

    # Reconnect — but the secret was deleted from MikroTik
    mt = _mock_mt_client()
    mt.get_secret.return_value = None  # secret no longer exists on MT
    mt.create_secret.return_value = "*RECREATED"

    with mock_mikrotik(mt):
        resp = await client.post(
            f"{API}/customers/{customer_id}/reconnect",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    mt.create_secret.assert_awaited_once()
    secret_args = mt.create_secret.call_args
    assert secret_args[1]["name"] == "juan_recreate"
    assert secret_args[1]["password"] == "secret123"


# ===========================================================================
# THROTTLE
# ===========================================================================

@pytest.mark.asyncio
async def test_throttle_changes_profile_on_mikrotik(client, auth_headers, test_plan, test_router):
    """Throttle must switch the customer to a throttle profile on MikroTik."""
    data, _, _ = await create_customer_with_mt(client, auth_headers, test_plan.id, "_thr")
    customer_id = data["id"]

    mt = _mock_mt_client()
    mt.ensure_profile.return_value = "1M-throttle"

    with mock_mikrotik(mt):
        resp = await client.post(
            f"{API}/customers/{customer_id}/throttle",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "throttled"

    # Must have called ensure_profile with throttle rate
    mt.ensure_profile.assert_awaited_once()

    # Must have updated the secret to use the throttle profile
    mt.update_secret.assert_awaited_once()
    update_args = mt.update_secret.call_args
    assert update_args[0][0] == "*NEW_SECRET"


# ===========================================================================
# CHANGE PLAN
# ===========================================================================

@pytest.mark.asyncio
async def test_change_plan_updates_mikrotik_profile(client, auth_headers, test_plan, second_plan, test_router):
    """Changing a customer's plan must update the MikroTik profile and secret."""
    data, _, _ = await create_customer_with_mt(client, auth_headers, test_plan.id, "_chplan")
    customer_id = data["id"]

    mt = _mock_mt_client()
    mt.ensure_profile.return_value = "Premium 50Mbps"

    with mock_mikrotik(mt):
        resp = await client.post(
            f"{API}/customers/{customer_id}/change-plan",
            json={"plan_id": str(second_plan.id)},
            headers=auth_headers,
        )

    assert resp.status_code == 200

    # Must have called ensure_profile with new plan's bandwidth
    mt.ensure_profile.assert_awaited_once()
    profile_args = mt.ensure_profile.call_args
    assert profile_args[0][0] == "Premium 50Mbps"
    assert profile_args[0][1] == "25M/50M"  # upload/download

    # Must have updated secret to use the new profile
    mt.update_secret.assert_awaited_once()
    assert mt.update_secret.call_args[0][1] == {"profile": "Premium 50Mbps"}


# ===========================================================================
# DELETE
# ===========================================================================

@pytest.mark.asyncio
async def test_delete_removes_secret_from_mikrotik(client, auth_headers, test_plan, test_router):
    """Deleting a customer must kick their session and remove the PPP secret."""
    data, _, _ = await create_customer_with_mt(client, auth_headers, test_plan.id, "_del")
    customer_id = data["id"]

    with mock_mikrotik() as mt:
        resp = await client.post(
            f"{API}/customers/{customer_id}/delete",
            json={"password": "admin123"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    mt.kick_session.assert_awaited_once_with("juan_del")
    mt.delete_secret.assert_awaited_once_with("*NEW_SECRET")


# ===========================================================================
# LIST / SEARCH / GET / UPDATE (non-MT operations still need to work)
# ===========================================================================

@pytest.mark.asyncio
async def test_list_customers_paginated(client, auth_headers, test_plan, test_router):
    for i in range(5):
        await create_customer_with_mt(client, auth_headers, test_plan.id, f"_list{i}")

    response = await client.get(f"{API}/customers/?page=1&page_size=3", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 5
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_search_customers(client, auth_headers, test_plan, test_router):
    await create_customer_with_mt(client, auth_headers, test_plan.id, "_search")

    response = await client.get(f"{API}/customers/?search=juan_search", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_get_customer(client, auth_headers, test_plan, test_router):
    data, _, _ = await create_customer_with_mt(client, auth_headers, test_plan.id, "_get")
    customer_id = data["id"]

    response = await client.get(f"{API}/customers/{customer_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Juan Cruz_get"


@pytest.mark.asyncio
async def test_update_customer(client, auth_headers, test_plan, test_router):
    data, _, _ = await create_customer_with_mt(client, auth_headers, test_plan.id, "_upd")
    customer_id = data["id"]

    response = await client.put(
        f"{API}/customers/{customer_id}",
        json={"full_name": "Updated Name"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_customer_not_found(client, auth_headers):
    response = await client.get(
        f"{API}/customers/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404
