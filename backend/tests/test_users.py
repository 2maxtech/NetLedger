import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole

API = settings.API_V1_PREFIX


@pytest_asyncio.fixture
async def billing_user(db_session: AsyncSession) -> User:
    user = User(
        username="billing_user",
        email="billing@test.com",
        password_hash=hash_password("billing123"),
        role=UserRole.billing,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def billing_headers(billing_user: User) -> dict:
    token = create_access_token(str(billing_user.id), billing_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_users(client, auth_headers, admin_user):
    response = await client.get(f"{API}/system/users/", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_create_user(client, auth_headers):
    response = await client.post(
        f"{API}/system/users/",
        json={
            "username": "newuser",
            "email": "new@test.com",
            "password": "newpass123",
            "role": "billing",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["role"] == "billing"


@pytest.mark.asyncio
async def test_create_user_duplicate(client, auth_headers, admin_user):
    response = await client.post(
        f"{API}/system/users/",
        json={
            "username": "admin",
            "email": "another@test.com",
            "password": "pass",
            "role": "billing",
        },
        headers=auth_headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_user(client, auth_headers):
    create = await client.post(
        f"{API}/system/users/",
        json={"username": "toupdate", "email": "up@test.com", "password": "pass", "role": "technician"},
        headers=auth_headers,
    )
    user_id = create.json()["id"]

    response = await client.put(
        f"{API}/system/users/{user_id}", json={"role": "billing"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "billing"


@pytest.mark.asyncio
async def test_delete_user(client, auth_headers):
    create = await client.post(
        f"{API}/system/users/",
        json={"username": "todelete", "email": "del@test.com", "password": "pass", "role": "technician"},
        headers=auth_headers,
    )
    user_id = create.json()["id"]

    response = await client.delete(f"{API}/system/users/{user_id}", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_cannot_delete_self(client, auth_headers, admin_user):
    response = await client.delete(
        f"{API}/system/users/{admin_user.id}", headers=auth_headers
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_users(client, billing_headers):
    response = await client.get(f"{API}/system/users/", headers=billing_headers)
    assert response.status_code == 403
