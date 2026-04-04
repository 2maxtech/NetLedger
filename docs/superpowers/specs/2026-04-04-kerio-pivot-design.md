# Kerio Control Integration + UI Overhaul — Design Spec

## Overview

Pivot 2maXnetBill from accel-ppp/FreeRADIUS to Kerio Control for subscriber management. Remove gateway-agent, clean up Proxmox LXCs, build Kerio adapter, rewire billing, and overhaul the UI with 2mX branding.

## Architecture

```
2maXnetBill (192.168.40.40)          Kerio Control (192.168.10.1:4081)
├── Customer CRUD              →     Create/disable local user
├── Plan assignment            →     Set bandwidth rule per user
├── MAC binding                →     autoLogin.macAddresses per user
├── Graduated disconnect       →     Disable user
├── Payment → reconnect        →     Re-enable user
├── Dashboard                  ←     ActiveHosts (who's online)
├── Customer portal                  (no change)
└── Billing engine                   (no change)
```

## What Gets Removed

### Infrastructure
- LXC 111 (isp-gateway): accel-ppp + FreeRADIUS + Gateway Agent
- LXC 112 (test-client): PPPoE test client

### Code
- `gateway-agent/` directory (entire thing)
- `backend/app/services/gateway.py`
- `backend/app/api/admin/network.py` (Phase 2 gateway proxy)
- `backend/app/api/admin/security.py` (Phase 3 gateway proxy)
- `backend/app/api/websocket.py` (relied on gateway for sessions/traffic)
- `frontend/src/api/gateway.ts`
- `frontend/src/api/network.ts`
- `frontend/src/api/security.ts`
- `frontend/src/pages/network/` (Firewall, Interfaces, DhcpDns)
- `frontend/src/pages/security/` (Suricata, ContentFilter)
- Sidebar menu groups: Network, Security
- Routes for removed pages

### Config
- `GATEWAY_AGENT_URL`, `GATEWAY_API_KEY` from config and docker-compose.yml
- `extra_hosts: gateway:192.168.40.41` from docker-compose.yml
- `psutil` from backend requirements (was for WebSocket system stats)
- nginx `/agent/` proxy block
- nginx `/api/v1/ws/` WebSocket proxy block

## What Gets Added

### Kerio Adapter (`backend/app/services/kerio.py`)

JSON-RPC client with cookie-based session management:

```python
class KerioClient:
    async login()
    async create_user(username, password, full_name, mac) -> str  # returns kerio user ID
    async update_user(kerio_id, fields)
    async disable_user(kerio_id)
    async enable_user(kerio_id)
    async delete_user(kerio_id)
    async set_mac_binding(kerio_id, mac_addresses: list)
    async get_active_hosts() -> list
    async get_users(domain_id="local") -> list
    async get_user(kerio_id) -> dict
    async get_traffic_policy() -> list
    async add_bandwidth_rule(user_id, down_kbps, up_kbps)
```

Key details:
- Uses `httpx.AsyncClient` with cookie jar for session persistence
- Session expires quickly — re-login on 401/session-expired errors
- Local domain users (not AD) — `domainId: "local"`
- MAC binding via `autoLogin.macAddresses` field on user object
- Bandwidth via `BandwidthManagement` rules per user

### Config (`backend/app/core/config.py`)

Replace gateway settings with:
```python
KERIO_URL: str = "https://192.168.10.1:4081"
KERIO_ADMIN_USER: str = "admin"
KERIO_ADMIN_PASSWORD: str = ""
KERIO_DOMAIN_ID: str = "local"
```

### Database Changes

- Add `kerio_user_id: str | None` to Customer model (Alembic migration)
- Add `mac_address: str | None` to Customer model (for MAC binding)

### API Changes

- `backend/app/api/admin/network.py` — rewritten: `GET /network/active-hosts`, `GET /network/kerio-status`
- PPPoE endpoints in `backend/app/api/admin/pppoe.py` — rewritten to show Kerio active hosts instead
- Customer create/update — also syncs to Kerio

### Billing Integration

- `record_payment` auto-reconnect → `kerio.enable_user()`
- `process_graduated_disconnect` throttle → `kerio.add_bandwidth_rule(user_id, 1000, 512)` (1Mbps/512kbps)
- `process_graduated_disconnect` disconnect → `kerio.disable_user()`
- Customer create → `kerio.create_user()` + `kerio.set_mac_binding()`

### Frontend Changes

**Removed pages:** Firewall, Interfaces, DhcpDns, Suricata, ContentFilter, PPPoESessions
**Replaced with:** Active Users page (Kerio active hosts with user/MAC/IP/traffic)

**Sidebar restructure:**
- Dashboard
- Customers (list, detail)
- Billing (Invoices, Payments)
- Active Users (replaces PPPoE Sessions — shows Kerio connected hosts)
- System (Users, Status, Logs)

**No more Network/Security groups** — Kerio handles those via its own admin at https://192.168.10.1:4081

## UI Overhaul

### Branding
- 2mX logo extracted from `ChatGPT Image Apr 3, 2026, 09_35_56 PM.png` (dark bg version)
- Logo in sidebar header (collapsed = "2mX" text, expanded = full logo)
- Logo on admin login page (centered, above login card)
- Logo on customer portal login page
- Logo on invoice PDF (replaces text "2maXnet")
- Favicon updated

### Visual Improvements
- **Login page:** Dark gradient background (#0f172a → #1e293b), glass-effect card, 2mX logo with subtle glow
- **Sidebar:** Gradient background instead of flat dark slate, active item with cyan left border + subtle glow
- **Dashboard:** Gradient stat cards with icons, better typography, welcome banner with logo
- **Tables:** Alternating row colors, better hover states
- **Cards:** Subtle shadow, rounded corners, consistent padding
- **Color palette refinement:** Primary stays teal (#0d9488), add cyan accent (#06b6d4) from logo glow for highlights/active states
- **Overall:** More whitespace, larger headings, consistent spacing

## What Stays the Same
- Billing engine (invoices, payments, graduated disconnect logic)
- Customer portal (all 4 pages)
- Invoice PDF (updated logo only)
- Email notifications
- Celery tasks (call kerio adapter instead of gateway)
- Database (PostgreSQL + Redis)
- Docker Compose (minus gateway references)
- All billing tests (mock the adapter)
