import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.plan import Plan

API = settings.API_V1_PREFIX


@pytest_asyncio.fixture
async def test_plan(db_session: AsyncSession) -> Plan:
    plan = Plan(
        name="Test Plan 10Mbps",
        download_mbps=10,
        upload_mbps=5,
        monthly_price=999.00,
        is_active=True,
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


@pytest.mark.asyncio
async def test_create_customer(client, auth_headers, test_plan):
    response = await client.post(
        f"{API}/customers/",
        json=customer_payload(str(test_plan.id)),
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Juan Cruz"
    assert data["status"] == "active"
    assert data["pppoe_username"] == "juan"
    assert "pppoe_password" not in data  # should not expose password


@pytest.mark.asyncio
async def test_list_customers_paginated(client, auth_headers, test_plan):
    for i in range(5):
        await client.post(
            f"{API}/customers/",
            json=customer_payload(str(test_plan.id), suffix=str(i)),
            headers=auth_headers,
        )
    response = await client.get(f"{API}/customers/?page=1&page_size=3", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 5
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_search_customers(client, auth_headers, test_plan):
    await client.post(
        f"{API}/customers/",
        json=customer_payload(str(test_plan.id), suffix="_search"),
        headers=auth_headers,
    )
    response = await client.get(f"{API}/customers/?search=juan_search", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_get_customer(client, auth_headers, test_plan):
    create = await client.post(
        f"{API}/customers/",
        json=customer_payload(str(test_plan.id), suffix="_get"),
        headers=auth_headers,
    )
    customer_id = create.json()["id"]

    response = await client.get(f"{API}/customers/{customer_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Juan Cruz_get"


@pytest.mark.asyncio
async def test_update_customer(client, auth_headers, test_plan):
    create = await client.post(
        f"{API}/customers/",
        json=customer_payload(str(test_plan.id), suffix="_upd"),
        headers=auth_headers,
    )
    customer_id = create.json()["id"]

    response = await client.put(
        f"{API}/customers/{customer_id}",
        json={"full_name": "Updated Name"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_customer_soft(client, auth_headers, test_plan):
    create = await client.post(
        f"{API}/customers/",
        json=customer_payload(str(test_plan.id), suffix="_del"),
        headers=auth_headers,
    )
    customer_id = create.json()["id"]

    response = await client.delete(f"{API}/customers/{customer_id}", headers=auth_headers)
    assert response.status_code == 204

    get_resp = await client.get(f"{API}/customers/{customer_id}", headers=auth_headers)
    assert get_resp.json()["status"] == "terminated"


@pytest.mark.asyncio
async def test_customer_not_found(client, auth_headers):
    response = await client.get(
        f"{API}/customers/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404
