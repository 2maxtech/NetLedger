# MikroTik Adapter — Design Spec

## Overview

Replace the Kerio Control integration with MikroTik RouterOS v7 REST API. NetLedger manages PPPoE subscribers (secrets), bandwidth (simple queues), and monitors active sessions through MikroTik's `/rest/` API. Kerio code is fully removed.

## Architecture

```
NetLedger (192.168.40.40)              MikroTik CHR (192.168.40.50)
├── Customer CRUD              →     Create/disable PPPoE secret
├── Plan assignment            →     Simple queue with max-limit
├── MAC binding                →     caller-id on PPPoE secret
├── Graduated disconnect       →     Disable secret / throttle queue
├── Payment → reconnect        →     Re-enable secret + restore queue
├── Active Users page          ←     GET /rest/ppp/active
├── Customer portal                   (no change)
└── Billing engine                    (no change)
```

## What Gets Removed

### Code
- `backend/app/services/kerio.py`
- `backend/app/api/admin/kerio.py`
- Kerio router registration in `backend/app/main.py`
- All `from app.services.kerio import kerio` imports in billing.py, customers.py

### Config
- `KERIO_URL`, `KERIO_ADMIN_USER`, `KERIO_ADMIN_PASSWORD`, `KERIO_DOMAIN_ID` from config.py
- `KERIO_*` env vars from docker-compose.yml

### Database
- Rename column `kerio_user_id` → `mikrotik_secret_id` (Alembic migration)

## What Gets Added

### Config (`backend/app/core/config.py`)

```python
MIKROTIK_URL: str = "https://192.168.40.50"
MIKROTIK_USER: str = "admin"
MIKROTIK_PASSWORD: str = ""
```

### MikroTik Client (`backend/app/services/mikrotik.py`)

REST API client using `httpx.AsyncClient` with HTTP basic auth. RouterOS v7 REST API is at `https://<host>/rest/`.

#### Authentication
No session management needed — every request sends HTTP basic auth credentials. SSL verification disabled (self-signed cert on CHR).

#### Methods

```python
class MikroTikClient:
    # PPPoE Secrets
    async def get_secrets() -> list[dict]
    async def get_secret(secret_id: str) -> dict | None
    async def create_secret(name: str, password: str, profile: str, caller_id: str | None) -> str
    async def update_secret(secret_id: str, fields: dict) -> None
    async def enable_secret(secret_id: str) -> None
    async def disable_secret(secret_id: str) -> None
    async def delete_secret(secret_id: str) -> None

    # Simple Queues
    async def get_queues() -> list[dict]
    async def set_queue(name: str, target: str, max_limit: str) -> str
    async def update_queue(queue_id: str, max_limit: str) -> None
    async def remove_queue(queue_id: str) -> None

    # Active Sessions
    async def get_active_sessions() -> list[dict]

    # System
    async def get_identity() -> str
    async def get_resources() -> dict
```

#### REST API Mapping

| Method | HTTP | Endpoint | Body/Params |
|--------|------|----------|-------------|
| `create_secret` | `PUT` | `/rest/ppp/secret` | `{"name": "user1", "password": "pass", "profile": "10M", "caller-id": "AA:BB:CC:DD:EE:FF"}` |
| `enable_secret` | `PATCH` | `/rest/ppp/secret/{id}` | `{"disabled": "no"}` |
| `disable_secret` | `PATCH` | `/rest/ppp/secret/{id}` | `{"disabled": "yes"}` |
| `delete_secret` | `DELETE` | `/rest/ppp/secret/{id}` | — |
| `get_secrets` | `GET` | `/rest/ppp/secret` | — |
| `set_queue` | `PUT` | `/rest/queue/simple` | `{"name": "user1", "target": "<pppoe-user1>", "max-limit": "10M/5M"}` |
| `update_queue` | `PATCH` | `/rest/queue/simple/{id}` | `{"max-limit": "1M/512k"}` |
| `remove_queue` | `DELETE` | `/rest/queue/simple/{id}` | — |
| `get_queues` | `GET` | `/rest/queue/simple` | — |
| `get_active_sessions` | `GET` | `/rest/ppp/active` | — |
| `get_identity` | `GET` | `/rest/system/identity` | — |
| `get_resources` | `GET` | `/rest/system/resource` | — |

#### Error Handling
- HTTP 401 → `MikroTikAuthError`
- HTTP 400 with body → parse RouterOS error message
- Connection refused / timeout → `MikroTikConnectionError`
- All errors inherit from `MikroTikError`

#### Queue Target Convention
MikroTik PPPoE assigns dynamic IPs. Simple queues target the PPPoE interface name: `<pppoe-{username}>`. This matches the interface created when the subscriber connects.

#### Profile Strategy
PPPoE profiles on MikroTik define the IP pool and can set rate limits. However, we use **simple queues** for bandwidth control (more flexible, per-subscriber granularity). Profiles are only used for IP pool assignment. A single profile `default` with the PPPoE IP pool is sufficient. Bandwidth is fully managed by NetLedger via queue CRUD.

### API Routes (`backend/app/api/admin/network.py`)

Replaces `kerio.py`:

```python
router = APIRouter(prefix="/network", tags=["network"])

GET  /network/active-sessions   # PPPoE active connections
GET  /network/status             # MikroTik connectivity + identity
GET  /network/subscribers        # List PPPoE secrets
```

### Billing Integration Changes (`backend/app/services/billing.py`)

Replace all Kerio calls:

| Billing Event | Old (Kerio) | New (MikroTik) |
|--------------|-------------|----------------|
| Payment auto-reconnect | `kerio.enable_user(kerio_user_id)` | `mikrotik.enable_secret(mikrotik_secret_id)` + restore queue |
| Throttle (overdue) | `kerio.disable_user(kerio_user_id)` | `mikrotik.update_queue(queue_id, "1M/512k")` |
| Disconnect (overdue) | `kerio.disable_user(kerio_user_id)` | `mikrotik.disable_secret(mikrotik_secret_id)` |

Rename `skip_kerio` parameter to `skip_network` throughout.

**Throttle improvement:** With MikroTik, throttle actually throttles (reduces queue bandwidth) instead of fully disabling like Kerio did. This is a better user experience — subscriber stays connected but at reduced speed.

### Customer API Changes (`backend/app/api/admin/customers.py`)

- Replace all `kerio` imports with `mikrotik`
- `disconnect_customer`: calls `mikrotik.disable_secret()`
- `reconnect_customer`: calls `mikrotik.enable_secret()` + restore queue
- `throttle_customer`: calls `mikrotik.update_queue()` with throttle speeds
- `create_customer`: calls `mikrotik.create_secret()` + `mikrotik.set_queue()`, stores `mikrotik_secret_id`
- References to `kerio_user_id` → `mikrotik_secret_id`

### Customer Model Changes

```python
# Remove
kerio_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

# Add
mikrotik_secret_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
mikrotik_queue_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

`mac_address` stays — used as `caller-id` in PPPoE secret.

### Database Migration

Alembic migration:
- Rename `kerio_user_id` → `mikrotik_secret_id`
- Add `mikrotik_queue_id` column

### Docker Compose Changes

Replace Kerio env vars:
```yaml
MIKROTIK_URL: https://192.168.40.50
MIKROTIK_USER: admin
MIKROTIK_PASSWORD: ""
```

### Frontend API Changes

- `frontend/src/api/kerio.ts` → rename to `frontend/src/api/network.ts`
- Update endpoints from `/kerio/*` to `/network/*`
- Update `ActiveUsers.tsx` to call `/network/active-sessions`
- Update types: `ActiveHost` → `PppoeSession` with fields: `name`, `service`, `caller-id`, `address`, `uptime`, `encoding`

## What Stays the Same

- Billing engine logic (invoices, payments, graduated disconnect flow)
- Customer portal (all 4 pages)
- Invoice PDF generation
- Email notifications
- Celery task schedule (same tasks, just calls mikrotik instead of kerio)
- Database (PostgreSQL + Redis)
- Auth system
- All existing tests (mock the adapter)

## Testing Strategy

- Unit tests mock `MikroTikClient` methods
- Integration test against CHR VM (manual, when VM is ready)
- Billing tests use `skip_network=True` (renamed from `skip_kerio`)
