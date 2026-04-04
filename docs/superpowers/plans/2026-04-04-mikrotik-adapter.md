# MikroTik Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Kerio Control integration with MikroTik RouterOS v7 REST API for PPPoE subscriber management, bandwidth control, and session monitoring.

**Architecture:** A `MikroTikClient` class uses `httpx` with HTTP basic auth to talk to RouterOS v7 REST endpoints (`/rest/ppp/secret`, `/rest/queue/simple`, `/rest/ppp/active`). Billing and customer APIs call this client instead of the removed Kerio client. An Alembic migration renames `kerio_user_id` to `mikrotik_secret_id` and adds `mikrotik_queue_id`.

**Tech Stack:** Python 3.12, FastAPI, httpx, SQLAlchemy 2.0 async, Alembic, PostgreSQL, React 18 + TypeScript + Ant Design

---

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| Create | `backend/app/services/mikrotik.py` | MikroTik REST API client |
| Create | `backend/app/api/admin/network.py` | Network API routes (replaces kerio.py) |
| Create | `backend/alembic/versions/003_kerio_to_mikrotik.py` | DB migration |
| Create | `backend/tests/test_mikrotik.py` | Unit tests for MikroTik client |
| Create | `frontend/src/api/network.ts` | Network API client (replaces kerio.ts) |
| Modify | `backend/app/core/config.py` | Replace Kerio config with MikroTik config |
| Modify | `backend/app/models/customer.py` | Rename kerio_user_id → mikrotik_secret_id, add mikrotik_queue_id |
| Modify | `backend/app/schemas/customer.py` | Update schema fields |
| Modify | `backend/app/services/billing.py` | Replace Kerio calls with MikroTik calls |
| Modify | `backend/app/api/admin/customers.py` | Replace Kerio calls with MikroTik calls |
| Modify | `backend/app/main.py` | Swap kerio router for network router |
| Modify | `backend/tests/test_billing.py` | Fix skip_gateway → skip_network |
| Modify | `docker-compose.yml` | Replace Kerio env vars with MikroTik env vars |
| Delete | `backend/app/services/kerio.py` | Removed |
| Delete | `backend/app/api/admin/kerio.py` | Removed |
| Delete | `frontend/src/api/kerio.ts` | Removed |
| Modify | `frontend/src/pages/ActiveUsers.tsx` | Use network API, PPPoE session columns |

---

### Task 1: MikroTik Client — Core HTTP Transport

**Files:**
- Create: `backend/app/services/mikrotik.py`
- Create: `backend/tests/test_mikrotik.py`

- [ ] **Step 1: Write test for MikroTik client GET request**

```python
# backend/tests/test_mikrotik.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.mikrotik import MikroTikClient, MikroTikError, MikroTikAuthError, MikroTikConnectionError


@pytest.fixture
def mt():
    return MikroTikClient(url="https://192.168.40.50", user="admin", password="test123")


@pytest.mark.asyncio
async def test_get_identity(mt):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"name": "MikroTik-CHR"}
    mock_response.raise_for_status = MagicMock()

    with patch.object(mt, '_request', new_callable=AsyncMock, return_value=mock_response):
        identity = await mt.get_identity()
        assert identity == "MikroTik-CHR"


@pytest.mark.asyncio
async def test_auth_error(mt):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch.object(mt, '_get_client') as mock_get:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_get.return_value = mock_client

        with pytest.raises(MikroTikAuthError):
            await mt._request("GET", "/rest/system/identity")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_mikrotik.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.mikrotik'`

- [ ] **Step 3: Implement MikroTik client core**

```python
# backend/app/services/mikrotik.py
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
    """Authentication failed."""
    pass


class MikroTikConnectionError(MikroTikError):
    """Connection to MikroTik failed."""
    pass


class MikroTikClient:
    """MikroTik RouterOS v7 REST API client."""

    def __init__(self, url: str | None = None, user: str | None = None, password: str | None = None):
        self.url = (url or settings.MIKROTIK_URL).rstrip("/")
        self.user = user or settings.MIKROTIK_USER
        self.password = password or settings.MIKROTIK_PASSWORD
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                verify=False,
                timeout=15.0,
                auth=(self.user, self.password),
            )
        return self._client

    async def _request(self, method: str, path: str, json: dict | None = None) -> httpx.Response:
        """Make an HTTP request to the RouterOS REST API."""
        client = await self._get_client()
        url = f"{self.url}{path}"

        try:
            response = await client.request(method, url, json=json)
        except httpx.ConnectError as e:
            raise MikroTikConnectionError(f"Cannot connect to MikroTik at {self.url}: {e}")
        except httpx.TimeoutException as e:
            raise MikroTikConnectionError(f"MikroTik request timed out: {e}")

        if response.status_code == 401:
            raise MikroTikAuthError("MikroTik authentication failed — check credentials")

        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("detail", body.get("message", response.text))
            except Exception:
                detail = response.text
            raise MikroTikError(f"MikroTik API error: {detail}", response.status_code)

        return response

    # --- System ---

    async def get_identity(self) -> str:
        """Get router identity name."""
        resp = await self._request("GET", "/rest/system/identity")
        return resp.json().get("name", "unknown")

    async def get_resources(self) -> dict:
        """Get system resource info (uptime, CPU, memory)."""
        resp = await self._request("GET", "/rest/system/resource")
        return resp.json()

    # --- PPPoE Secrets ---

    async def get_secrets(self) -> list[dict]:
        """List all PPPoE secrets."""
        resp = await self._request("GET", "/rest/ppp/secret")
        return resp.json()

    async def get_secret(self, secret_id: str) -> dict | None:
        """Get a specific PPPoE secret by its .id."""
        try:
            resp = await self._request("GET", f"/rest/ppp/secret/{secret_id}")
            return resp.json()
        except MikroTikError:
            return None

    async def create_secret(
        self, name: str, password: str, profile: str = "default", caller_id: str | None = None
    ) -> str:
        """Create a PPPoE secret. Returns the MikroTik .id."""
        body: dict[str, Any] = {
            "name": name,
            "password": password,
            "service": "pppoe",
            "profile": profile,
        }
        if caller_id:
            body["caller-id"] = caller_id

        resp = await self._request("PUT", "/rest/ppp/secret", json=body)
        data = resp.json()
        secret_id = data.get(".id")
        if not secret_id:
            raise MikroTikError("Secret created but .id not returned")
        logger.info(f"MikroTik PPPoE secret created: {name} → {secret_id}")
        return secret_id

    async def update_secret(self, secret_id: str, fields: dict) -> None:
        """Update a PPPoE secret's fields."""
        await self._request("PATCH", f"/rest/ppp/secret/{secret_id}", json=fields)
        logger.info(f"MikroTik secret {secret_id} updated: {fields}")

    async def enable_secret(self, secret_id: str) -> None:
        """Enable a PPPoE secret (reconnect)."""
        await self._request("PATCH", f"/rest/ppp/secret/{secret_id}", json={"disabled": "no"})
        logger.info(f"MikroTik secret {secret_id} enabled")

    async def disable_secret(self, secret_id: str) -> None:
        """Disable a PPPoE secret (disconnect)."""
        await self._request("PATCH", f"/rest/ppp/secret/{secret_id}", json={"disabled": "yes"})
        logger.info(f"MikroTik secret {secret_id} disabled")

    async def delete_secret(self, secret_id: str) -> None:
        """Delete a PPPoE secret."""
        await self._request("DELETE", f"/rest/ppp/secret/{secret_id}")
        logger.info(f"MikroTik secret {secret_id} deleted")

    # --- Simple Queues ---

    async def get_queues(self) -> list[dict]:
        """List all simple queues."""
        resp = await self._request("GET", "/rest/queue/simple")
        return resp.json()

    async def set_queue(self, name: str, target: str, max_limit: str) -> str:
        """Create a simple queue. Returns the MikroTik .id.
        max_limit format: '10M/5M' (download/upload)
        target: '<pppoe-username>' for PPPoE subscribers
        """
        body = {
            "name": name,
            "target": target,
            "max-limit": max_limit,
        }
        resp = await self._request("PUT", "/rest/queue/simple", json=body)
        data = resp.json()
        queue_id = data.get(".id")
        if not queue_id:
            raise MikroTikError("Queue created but .id not returned")
        logger.info(f"MikroTik queue created: {name} → {queue_id}")
        return queue_id

    async def update_queue(self, queue_id: str, max_limit: str) -> None:
        """Update a simple queue's bandwidth limit."""
        await self._request("PATCH", f"/rest/queue/simple/{queue_id}", json={"max-limit": max_limit})
        logger.info(f"MikroTik queue {queue_id} updated: {max_limit}")

    async def remove_queue(self, queue_id: str) -> None:
        """Delete a simple queue."""
        await self._request("DELETE", f"/rest/queue/simple/{queue_id}")
        logger.info(f"MikroTik queue {queue_id} removed")

    # --- Active Sessions ---

    async def get_active_sessions(self) -> list[dict]:
        """Get active PPPoE sessions."""
        resp = await self._request("GET", "/rest/ppp/active")
        return resp.json()


# Singleton instance
mikrotik = MikroTikClient()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_mikrotik.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/mikrotik.py backend/tests/test_mikrotik.py
git commit -m "feat: add MikroTik RouterOS v7 REST API client"
```

---

### Task 2: Config — Replace Kerio with MikroTik Settings

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update config.py — remove Kerio settings, add MikroTik**

Replace these lines in `backend/app/core/config.py`:

```python
    # Kerio Control
    KERIO_URL: str = "https://192.168.10.1:4081"
    KERIO_ADMIN_USER: str = "admin"
    KERIO_ADMIN_PASSWORD: str = ""
    KERIO_DOMAIN_ID: str = "local"
```

With:

```python
    # MikroTik RouterOS
    MIKROTIK_URL: str = "https://192.168.40.50"
    MIKROTIK_USER: str = "admin"
    MIKROTIK_PASSWORD: str = ""
```

- [ ] **Step 2: Update docker-compose.yml — replace Kerio env vars**

In the `backend` and `celery-worker` services, replace:

```yaml
      KERIO_URL: https://192.168.10.1
      KERIO_ADMIN_USER: admin
      KERIO_ADMIN_PASSWORD: SeafoodCity12#
      KERIO_DOMAIN_ID: local
```

With:

```yaml
      MIKROTIK_URL: https://192.168.40.50
      MIKROTIK_USER: admin
      MIKROTIK_PASSWORD: ""
```

Remove `KERIO_*` from `celery-beat` if present.

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/config.py docker-compose.yml
git commit -m "feat: replace Kerio config with MikroTik settings"
```

---

### Task 3: Database Migration — Rename kerio_user_id, Add mikrotik_queue_id

**Files:**
- Create: `backend/alembic/versions/003_kerio_to_mikrotik.py`
- Modify: `backend/app/models/customer.py`
- Modify: `backend/app/schemas/customer.py`

- [ ] **Step 1: Create Alembic migration**

```python
# backend/alembic/versions/003_kerio_to_mikrotik.py
"""rename kerio_user_id to mikrotik_secret_id, add mikrotik_queue_id

Revision ID: 003_mikrotik
Revises: 002_kerio
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = '003_mikrotik'
down_revision = '002_kerio'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('customers', 'kerio_user_id', new_column_name='mikrotik_secret_id')
    op.add_column('customers', sa.Column('mikrotik_queue_id', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'mikrotik_queue_id')
    op.alter_column('customers', 'mikrotik_secret_id', new_column_name='kerio_user_id')
```

- [ ] **Step 2: Update Customer model**

In `backend/app/models/customer.py`, replace:

```python
    kerio_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

With:

```python
    mikrotik_secret_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mikrotik_queue_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

- [ ] **Step 3: Update Customer schemas**

In `backend/app/schemas/customer.py`, replace all `kerio_user_id` with `mikrotik_secret_id` and add `mikrotik_queue_id`:

```python
class CustomerCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    address: str | None = None
    pppoe_username: str
    pppoe_password: str
    plan_id: uuid.UUID
    mikrotik_secret_id: str | None = None
    mikrotik_queue_id: str | None = None
    mac_address: str | None = None


class CustomerUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    pppoe_username: str | None = None
    pppoe_password: str | None = None
    plan_id: uuid.UUID | None = None
    status: CustomerStatus | None = None
    mikrotik_secret_id: str | None = None
    mikrotik_queue_id: str | None = None
    mac_address: str | None = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    phone: str
    address: str | None
    pppoe_username: str
    status: CustomerStatus
    plan_id: uuid.UUID
    plan: PlanResponse | None = None
    created_at: datetime
    mikrotik_secret_id: str | None = None
    mikrotik_queue_id: str | None = None
    mac_address: str | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/003_kerio_to_mikrotik.py backend/app/models/customer.py backend/app/schemas/customer.py
git commit -m "feat: migrate customer model from Kerio to MikroTik fields"
```

---

### Task 4: Remove Kerio Code

**Files:**
- Delete: `backend/app/services/kerio.py`
- Delete: `backend/app/api/admin/kerio.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Delete Kerio files**

```bash
rm backend/app/services/kerio.py
rm backend/app/api/admin/kerio.py
```

- [ ] **Step 2: Update main.py — swap kerio router for network router**

In `backend/app/main.py`, replace:

```python
from app.api.admin.kerio import router as kerio_router
```

With:

```python
from app.api.admin.network import router as network_router
```

And replace:

```python
app.include_router(kerio_router, prefix=settings.API_V1_PREFIX)
```

With:

```python
app.include_router(network_router, prefix=settings.API_V1_PREFIX)
```

- [ ] **Step 3: Create network API routes**

```python
# backend/app/api/admin/network.py
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.mikrotik import mikrotik

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/active-sessions")
async def get_active_sessions(current_user: User = Depends(get_current_user)):
    """Get active PPPoE sessions from MikroTik."""
    try:
        sessions = await mikrotik.get_active_sessions()
        return {"sessions": sessions, "total": len(sessions)}
    except Exception as e:
        return {"sessions": [], "total": 0, "error": str(e)}


@router.get("/status")
async def get_network_status(current_user: User = Depends(get_current_user)):
    """Check MikroTik connectivity."""
    try:
        identity = await mikrotik.get_identity()
        resources = await mikrotik.get_resources()
        return {
            "connected": True,
            "identity": identity,
            "uptime": resources.get("uptime", ""),
            "cpu_load": resources.get("cpu-load", ""),
            "free_memory": resources.get("free-memory", ""),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.get("/subscribers")
async def get_subscribers(current_user: User = Depends(get_current_user)):
    """List PPPoE secrets from MikroTik."""
    try:
        secrets = await mikrotik.get_secrets()
        return {"subscribers": secrets, "total": len(secrets)}
    except Exception as e:
        return {"subscribers": [], "total": 0, "error": str(e)}
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: replace Kerio API routes with MikroTik network routes"
```

---

### Task 5: Wire Billing to MikroTik

**Files:**
- Modify: `backend/app/services/billing.py`
- Modify: `backend/tests/test_billing.py`

- [ ] **Step 1: Update billing.py — replace all Kerio references**

In `backend/app/services/billing.py`:

**a)** In `record_payment`, replace `skip_kerio` with `skip_network` and swap Kerio calls:

Replace the parameter:
```python
    skip_kerio: bool = False,
```
With:
```python
    skip_network: bool = False,
```

Replace the reconnect block (lines ~142-151):
```python
                if not skip_kerio:
                    if customer.kerio_user_id:
                        from app.services.kerio import kerio
                        try:
                            await kerio.login()
                            await kerio.enable_user(customer.kerio_user_id)
                        except Exception as e:
                            logger.error(f"Kerio enable failed for {customer.id}: {e}")
                    else:
                        logger.warning(f"Customer {customer.id} has no kerio_user_id, skipping")
```

With:
```python
                if not skip_network:
                    if customer.mikrotik_secret_id:
                        from app.services.mikrotik import mikrotik
                        try:
                            await mikrotik.enable_secret(customer.mikrotik_secret_id)
                            if customer.mikrotik_queue_id and customer.plan:
                                max_limit = f"{customer.plan.download_mbps}M/{customer.plan.upload_mbps}M"
                                await mikrotik.update_queue(customer.mikrotik_queue_id, max_limit)
                        except Exception as e:
                            logger.error(f"MikroTik enable failed for {customer.id}: {e}")
                    else:
                        logger.warning(f"Customer {customer.id} has no mikrotik_secret_id, skipping")
```

**b)** In `process_graduated_disconnect`, replace `skip_kerio` with `skip_network`.

Replace the parameter:
```python
async def process_graduated_disconnect(db: AsyncSession, skip_kerio: bool = False) -> dict:
```
With:
```python
async def process_graduated_disconnect(db: AsyncSession, skip_network: bool = False) -> dict:
```

Replace the throttle block (lines ~209-218):
```python
                if not skip_kerio:
                    if customer.kerio_user_id:
                        from app.services.kerio import kerio
                        try:
                            await kerio.login()
                            await kerio.disable_user(customer.kerio_user_id)
                        except Exception as e:
                            logger.error(f"Kerio throttle/disable failed for {customer.id}: {e}")
                    else:
                        logger.warning(f"Customer {customer.id} has no kerio_user_id, skipping")
```

With:
```python
                if not skip_network:
                    if customer.mikrotik_queue_id:
                        from app.services.mikrotik import mikrotik
                        try:
                            throttle_limit = f"{settings.THROTTLE_DOWNLOAD_MBPS}M/{settings.THROTTLE_UPLOAD_KBPS}k"
                            await mikrotik.update_queue(customer.mikrotik_queue_id, throttle_limit)
                        except Exception as e:
                            logger.error(f"MikroTik throttle failed for {customer.id}: {e}")
                    else:
                        logger.warning(f"Customer {customer.id} has no mikrotik_queue_id, skipping")
```

Replace the disconnect block (lines ~235-244) similarly:
```python
                if not skip_network:
                    if customer.mikrotik_secret_id:
                        from app.services.mikrotik import mikrotik
                        try:
                            await mikrotik.disable_secret(customer.mikrotik_secret_id)
                        except Exception as e:
                            logger.error(f"MikroTik disconnect failed for {customer.id}: {e}")
                    else:
                        logger.warning(f"Customer {customer.id} has no mikrotik_secret_id, skipping")
```

- [ ] **Step 2: Fix tests — rename skip_gateway to skip_network**

In `backend/tests/test_billing.py`, replace all 4 occurrences of `skip_gateway=True` with `skip_network=True`:

Line 170: `skip_gateway=True` → `skip_network=True`
Line 222: `skip_gateway=True` → `skip_network=True`
Line 247: `skip_gateway=True` → `skip_network=True`
Line 272: `skip_gateway=True` → `skip_network=True`

- [ ] **Step 3: Run billing tests**

Run: `cd backend && python -m pytest tests/test_billing.py -v`
Expected: All 14 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/billing.py backend/tests/test_billing.py
git commit -m "feat: wire billing engine to MikroTik adapter"
```

---

### Task 6: Wire Customer API to MikroTik

**Files:**
- Modify: `backend/app/api/admin/customers.py`

- [ ] **Step 1: Replace all Kerio references in customers.py**

Replace the import:
```python
from app.services.kerio import kerio
```
With:
```python
from app.services.mikrotik import mikrotik
```

**a)** Update `create_customer` to auto-provision MikroTik:

Replace:
```python
@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    customer = Customer(**body.model_dump())
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return customer
```

With:
```python
@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    customer = Customer(**body.model_dump())
    db.add(customer)
    await db.flush()
    await db.refresh(customer)

    # Auto-provision PPPoE secret + queue on MikroTik
    try:
        secret_id = await mikrotik.create_secret(
            name=customer.pppoe_username,
            password=customer.pppoe_password,
            caller_id=customer.mac_address,
        )
        customer.mikrotik_secret_id = secret_id

        plan = customer.plan
        if plan:
            max_limit = f"{plan.download_mbps}M/{plan.upload_mbps}M"
            queue_id = await mikrotik.set_queue(
                name=customer.pppoe_username,
                target=f"<pppoe-{customer.pppoe_username}>",
                max_limit=max_limit,
            )
            customer.mikrotik_queue_id = queue_id

        await db.flush()
        await db.refresh(customer)
    except Exception as e:
        logger.warning(f"MikroTik provisioning failed for {customer.id}: {e}")

    return customer
```

**b)** Update `disconnect_customer` — replace Kerio calls:

Replace all references to `kerio_user_id` and `kerio` with:
```python
    response = {"detail": "No MikroTik secret linked"}
    if customer.mikrotik_secret_id:
        try:
            await mikrotik.disable_secret(customer.mikrotik_secret_id)
            response = {"detail": "PPPoE secret disabled"}
        except Exception as e:
            response = {"detail": f"MikroTik error: {e}"}
    logger.info(f"Customer {customer.id} status changed to disconnected")
```

**c)** Update `reconnect_customer`:

```python
    response = {"detail": "No MikroTik secret linked"}
    if customer.mikrotik_secret_id:
        try:
            await mikrotik.enable_secret(customer.mikrotik_secret_id)
            if customer.mikrotik_queue_id and customer.plan:
                max_limit = f"{customer.plan.download_mbps}M/{customer.plan.upload_mbps}M"
                await mikrotik.update_queue(customer.mikrotik_queue_id, max_limit)
            response = {"detail": "PPPoE secret enabled"}
        except Exception as e:
            response = {"detail": f"MikroTik error: {e}"}
    logger.info(f"Customer {customer.id} status changed to active")
```

**d)** Update `throttle_customer`:

```python
    response = {"detail": "No MikroTik queue linked"}
    if customer.mikrotik_queue_id:
        try:
            from app.core.config import settings
            throttle_limit = f"{settings.THROTTLE_DOWNLOAD_MBPS}M/{settings.THROTTLE_UPLOAD_KBPS}k"
            await mikrotik.update_queue(customer.mikrotik_queue_id, throttle_limit)
            response = {"detail": f"Queue throttled to {throttle_limit}"}
        except Exception as e:
            response = {"detail": f"MikroTik error: {e}"}
    logger.info(f"Customer {customer.id} status changed to suspended")
```

- [ ] **Step 2: Run customer tests**

Run: `cd backend && python -m pytest tests/test_customers.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/admin/customers.py
git commit -m "feat: wire customer API to MikroTik for provisioning and lifecycle"
```

---

### Task 7: Frontend — Replace Kerio API with Network API

**Files:**
- Create: `frontend/src/api/network.ts`
- Delete: `frontend/src/api/kerio.ts`
- Modify: `frontend/src/pages/ActiveUsers.tsx`

- [ ] **Step 1: Create network.ts API client**

```typescript
// frontend/src/api/network.ts
import client from './client';

export interface PppoeSession {
  '.id': string;
  name: string;
  service: string;
  'caller-id': string;
  address: string;
  uptime: string;
  encoding: string;
}

export interface NetworkStatus {
  connected: boolean;
  identity?: string;
  uptime?: string;
  cpu_load?: string;
  free_memory?: string;
  error?: string;
}

export const getActiveSessions = () =>
  client.get<{ sessions: PppoeSession[]; total: number }>('/network/active-sessions');

export const getNetworkStatus = () =>
  client.get<NetworkStatus>('/network/status');

export const getSubscribers = () =>
  client.get<{ subscribers: any[]; total: number }>('/network/subscribers');
```

- [ ] **Step 2: Delete kerio.ts**

```bash
rm frontend/src/api/kerio.ts
```

- [ ] **Step 3: Rewrite ActiveUsers.tsx for PPPoE sessions**

```typescript
// frontend/src/pages/ActiveUsers.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Table, Card, Typography, Button, Tag, Space, Badge, Statistic, Row, Col } from 'antd';
import { ReloadOutlined, WifiOutlined, UserOutlined, LaptopOutlined } from '@ant-design/icons';
import { getActiveSessions, getNetworkStatus } from '../api/network';
import type { PppoeSession } from '../api/network';

const ActiveUsers = () => {
  const queryClient = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ['network-status'],
    queryFn: () => getNetworkStatus().then((r) => r.data),
    refetchInterval: 30000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['active-sessions'],
    queryFn: () => getActiveSessions().then((r) => r.data),
    refetchInterval: 15000,
  });

  const sessions = data?.sessions || [];

  const columns = [
    {
      title: 'Username',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <span style={{ fontWeight: 500 }}>{name}</span>,
    },
    {
      title: 'IP Address',
      dataIndex: 'address',
      key: 'address',
      width: 140,
      render: (ip: string) => ip || '-',
    },
    {
      title: 'Caller ID',
      key: 'caller-id',
      width: 160,
      render: (_: unknown, r: PppoeSession) => (
        <code style={{ fontSize: 12 }}>{r['caller-id'] || '-'}</code>
      ),
    },
    {
      title: 'Service',
      dataIndex: 'service',
      key: 'service',
      width: 100,
      render: (s: string) => <Tag>{s || 'pppoe'}</Tag>,
    },
    {
      title: 'Uptime',
      dataIndex: 'uptime',
      key: 'uptime',
      width: 120,
    },
    {
      title: 'Status',
      key: 'status',
      width: 100,
      render: () => <Badge status="success" text="Online" />,
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <WifiOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          Active Users
        </Typography.Title>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['active-sessions'] });
            queryClient.invalidateQueries({ queryKey: ['network-status'] });
          }}
        >
          Refresh
        </Button>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="MikroTik"
              valueRender={() => (
                <Space direction="vertical" size={0}>
                  <Tag color={status?.connected ? 'green' : 'red'}>
                    {status?.connected ? 'Connected' : 'Disconnected'}
                  </Tag>
                  {status?.identity && (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {status.identity}
                    </Typography.Text>
                  )}
                </Space>
              )}
              prefix={<LaptopOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="PPPoE Sessions"
              value={sessions.length}
              prefix={<UserOutlined style={{ color: '#e8700a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Router Uptime"
              valueRender={() => (
                <Typography.Text>{status?.uptime || '-'}</Typography.Text>
              )}
              prefix={<WifiOutlined style={{ color: '#f9a825' }} />}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          {sessions.length} active PPPoE session(s) — auto-refreshes every 15s
        </Typography.Text>
        <Table
          columns={columns}
          dataSource={sessions}
          rowKey=".id"
          loading={isLoading}
          pagination={false}
          size="middle"
        />
      </Card>
    </div>
  );
};

export default ActiveUsers;
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: replace Kerio frontend with MikroTik PPPoE session UI"
```

---

### Task 8: Cleanup and Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Grep for any remaining Kerio references**

Run: `grep -r "kerio\|Kerio\|KERIO" backend/app/ frontend/src/ docker-compose.yml --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yml" -l`
Expected: No files found (clean removal)

- [ ] **Step 2: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit any cleanup**

```bash
git add -A
git commit -m "chore: remove all remaining Kerio references"
```
