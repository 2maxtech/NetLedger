# NetLedger On-Premise (Self-Hosted) — Design Spec

**Date:** 2026-04-06
**Status:** Draft

## Goal

Ship a self-hosted version of NetLedger that ISP operators can install on their own server. Same UI and features as SaaS, minus multi-tenancy and VPN tunnel. Two delivery options: Docker Compose bundle (DIY) and one-liner install script (turnkey).

## Decisions

| Question | Answer |
|----------|--------|
| Deployment options | A) Docker Compose + B) Install script |
| Licensing | Free tier + paid feature unlock (details TBD) |
| Tenancy | Single-tenant only |
| VPN tunnel | Not needed — direct LAN access to routers |
| Updates | Built-in update checker, dashboard notification |
| Initial setup | Web-based setup wizard (like WordPress) |

## Architecture

### Deployment Mode Flag

A single environment variable controls behavior:

```
DEPLOYMENT_MODE=onpremise   # or "saas" (default)
```

Backend reads this in `app/core/config.py`. Frontend reads `VITE_DEPLOYMENT_MODE` at build time (baked into the bundle via Vite env).

### What Changes by Mode

| Feature | SaaS | On-Premise |
|---------|------|------------|
| Landing page | Yes | No (redirect to login or setup wizard) |
| Registration + email verification | Yes | No |
| Multi-tenant (owner_id scoping) | Yes | Single owner auto-assigned |
| Super admin impersonation | Yes | No (no super admin role) |
| VPN onboarding wizard | Yes | No |
| VPN button on router cards | Yes | No |
| Customer portal slug | `/portal/:slug/login` | `/portal/login` (single tenant) |
| Setup wizard | No | Yes (first-time only) |
| Update checker | No | Yes (dashboard banner) |
| Tenant switcher in sidebar | Yes | No |

### What Stays the Same

Everything else: dashboard, customers, plans, invoices, payments, billing enforcement, hotspot, vouchers, LibreQoS, settings, customer portal, MikroTik integration, Celery tasks, areas, tickets, audit logs.

## Backend Changes

### 1. Config (`app/core/config.py`)

Add to Settings:
```python
DEPLOYMENT_MODE: str = "saas"         # "saas" or "onpremise"
APP_VERSION: str = "1.0.0"           # Current version, read from VERSION file
UPDATE_CHECK_URL: str = "https://netl.2max.tech/api/v1/releases/latest"
```

### 2. Tenant Resolution (`app/core/tenant.py`)

In on-premise mode, `get_tenant_id()` always returns the single admin's user ID. No `X-Tenant-Id` header needed.

```python
async def get_tenant_id(...) -> str:
    if settings.DEPLOYMENT_MODE == "onpremise":
        return str(current_user.id)
    # existing SaaS logic...
```

### 3. Setup Wizard API (`app/api/setup.py` — new file)

Only active when `DEPLOYMENT_MODE=onpremise`.

**Endpoints:**

- `GET /api/v1/setup/status` — public, returns `{"configured": bool}`. Checks if any admin user exists.
- `POST /api/v1/setup/initialize` — public (only when unconfigured), accepts:
  ```json
  {
    "company_name": "My ISP",
    "admin_username": "admin",
    "admin_email": "admin@myisp.com",
    "admin_password": "securepass",
    "router_name": "Main Router",        // optional
    "router_url": "http://192.168.88.1", // optional
    "router_username": "admin",           // optional
    "router_password": ""                 // optional
  }
  ```
  Creates admin user (role=admin, is_active=True, no email verification), optionally creates first router. Returns JWT tokens so the wizard can redirect to dashboard.

**Guard:** Every request to `/api/v1/setup/initialize` checks if an admin already exists. If yes, returns 403.

### 4. Update Checker (`app/services/update_checker.py` — new file)

Celery Beat task (runs once daily, on-premise only):
- Fetches `UPDATE_CHECK_URL` → `{"version": "1.2.0", "release_notes": "...", "download_url": "..."}`
- Compares with current `APP_VERSION`
- If newer, stores in `app_settings` table: `update_available_version`, `update_release_notes`, `update_download_url`

Dashboard API endpoint:
- `GET /api/v1/system/update-check` — returns latest update info (or null if up to date)

### 5. Auth Changes (`app/api/auth.py`)

- `POST /auth/register` — disabled in on-premise mode (return 404)
- `POST /auth/login` — works unchanged
- `GET /auth/verify` — disabled in on-premise mode

### 6. Router Endpoints

- VPN endpoints (`/api/v1/vpn/*`) — return 404 in on-premise mode
- Router CRUD — unchanged (direct LAN IP instead of tunnel IP)

### 7. Portal Simplification

In on-premise mode, customer portal doesn't need tenant slug:
- `/portal/login` → works directly (single tenant)
- Backend portal auth resolves the single admin as owner

### 8. Version File

Add `VERSION` file at repo root containing the current version string (e.g., `1.0.0`). Backend reads this at startup. Docker image includes it.

## Frontend Changes

### 1. Environment Variable

```
VITE_DEPLOYMENT_MODE=onpremise  # in .env for on-premise builds
```

Exposed via a composable:
```typescript
// src/composables/useDeploymentMode.ts
export const isOnPremise = import.meta.env.VITE_DEPLOYMENT_MODE === 'onpremise'
export const isSaaS = !isOnPremise
```

### 2. Setup Wizard Page (`src/pages/Setup.vue` — new)

Three-step wizard (only shown when app is unconfigured):

1. **Company Info** — company name (used for branding)
2. **Admin Account** — username, email, password
3. **Connect Router** (optional, can skip) — router name, IP/URL, username, password, test connection button

On submit → calls `POST /api/v1/setup/initialize` → stores JWT → redirects to `/dashboard`.

### 3. Router Changes

```typescript
// src/router/index.ts
{
  path: '/',
  component: () => isOnPremise
    ? import('../pages/Login.vue')       // on-premise: straight to login
    : import('../pages/Landing.vue'),    // SaaS: landing page
},
{
  path: '/setup',
  component: () => import('../pages/Setup.vue'),  // new
},
```

Route guard: if on-premise and unconfigured → redirect to `/setup`.

### 4. Conditional UI Elements

Hide in on-premise mode:
- VPN button on router cards (`Routers.vue`)
- Registration link on login page
- Tenant slug in portal URLs
- Super admin menu items

Show in on-premise mode:
- Update available banner on dashboard

### 5. Portal Route

On-premise portal uses a simplified route:
```
/portal/login       → PortalLogin.vue (no slug)
/portal/            → PortalDashboard.vue
/portal/invoices    → PortalInvoices.vue
...
```

## Deployment Artifacts

### 1. `docker-compose.onpremise.yml`

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${DB_USER:-netledger}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME:-netledger}
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  backend:
    image: ghcr.io/2maxtech/netledger-backend:latest
    depends_on: [db, redis]
    environment:
      DEPLOYMENT_MODE: onpremise
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-netledger}:${DB_PASSWORD}@db:5432/${DB_NAME:-netledger}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    volumes:
      - uploads:/app/uploads
    restart: unless-stopped

  frontend:
    image: ghcr.io/2maxtech/netledger-frontend:onpremise
    depends_on: [backend]
    ports:
      - "${HTTP_PORT:-80}:80"
    restart: unless-stopped

  celery-worker:
    image: ghcr.io/2maxtech/netledger-backend:latest
    command: celery -A app.celery_app worker --loglevel=info --concurrency=2
    depends_on: [db, redis]
    environment:
      DEPLOYMENT_MODE: onpremise
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-netledger}:${DB_PASSWORD}@db:5432/${DB_NAME:-netledger}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    restart: unless-stopped

  celery-beat:
    image: ghcr.io/2maxtech/netledger-backend:latest
    command: celery -A app.celery_app beat --loglevel=info -s /tmp/celerybeat-schedule
    depends_on: [db, redis]
    environment:
      DEPLOYMENT_MODE: onpremise
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-netledger}:${DB_PASSWORD}@db:5432/${DB_NAME:-netledger}
      REDIS_URL: redis://redis:6379/0
    restart: unless-stopped

volumes:
  pgdata:
  uploads:
```

Key differences from SaaS:
- No Caddy (ISP manages their own reverse proxy/SSL)
- No WireGuard service
- Uses published Docker images from GHCR (not local builds)
- Environment variables from `.env` file
- `restart: unless-stopped` for production reliability

### 2. `.env.onpremise.example`

```env
# NetLedger On-Premise Configuration
# Copy this to .env and fill in your values

# Database (auto-generated by install script)
DB_USER=netledger
DB_PASSWORD=CHANGE_ME
DB_NAME=netledger

# Security (auto-generated by install script)
SECRET_KEY=CHANGE_ME

# HTTP port (default 80, put behind reverse proxy for SSL)
HTTP_PORT=80

# SMTP (optional — for email notifications)
# SMTP_HOST=
# SMTP_PORT=587
# SMTP_USER=
# SMTP_PASSWORD=
# SMTP_FROM=noreply@yourisp.com
```

### 3. `install.sh`

```bash
#!/bin/bash
# NetLedger On-Premise Installer
# Usage: curl -fsSL https://get.netledger.io/install.sh | bash
```

The script will:
1. Check OS (Ubuntu 22+/Debian 12+)
2. Install Docker + Docker Compose if not present
3. Create `/opt/netledger/` directory
4. Download `docker-compose.onpremise.yml` and `.env.onpremise.example`
5. Generate random `DB_PASSWORD` and `SECRET_KEY`
6. Write `.env` with generated values
7. Run `docker compose up -d`
8. Print: "NetLedger is ready! Open http://<server-ip> in your browser to complete setup."

### 4. Docker Image Build

Two frontend image variants:
- `netledger-frontend:latest` — SaaS build (`VITE_DEPLOYMENT_MODE=saas`)
- `netledger-frontend:onpremise` — On-premise build (`VITE_DEPLOYMENT_MODE=onpremise`)

Backend image is the same for both — mode is controlled by env var at runtime.

### 5. GitHub Actions (future)

CI/CD to build and push images to GHCR on tagged releases. Not part of initial implementation — we'll build and push manually first.

## Update Flow

1. Celery Beat runs `check_for_updates` task daily (on-premise only)
2. Task fetches `https://netl.2max.tech/api/v1/releases/latest`
3. If newer version available, stores in `app_settings`
4. Dashboard component checks `/api/v1/system/update-check` on load
5. If update available, shows banner: "NetLedger v1.2.0 is available. [View release notes] [How to update]"
6. "How to update" links to docs with instructions:
   ```bash
   cd /opt/netledger
   docker compose pull
   docker compose up -d
   ```

## SaaS Release Endpoint

Add to the SaaS backend (separate from on-premise):

`GET /api/v1/releases/latest` — public, returns:
```json
{
  "version": "1.2.0",
  "release_notes": "Bug fixes and performance improvements",
  "release_date": "2026-04-15",
  "download_url": "https://github.com/2maxtech/NetLedger/releases/tag/v1.2.0"
}
```

This is a simple endpoint on the SaaS instance that on-premise installations check against.

## File Structure (New/Modified)

```
New files:
  VERSION                                    # "1.0.0"
  docker-compose.onpremise.yml              # On-premise Docker stack
  .env.onpremise.example                    # Config template
  scripts/install-onpremise.sh              # Install script
  backend/app/api/setup.py                  # Setup wizard API
  backend/app/services/update_checker.py    # Update check Celery task
  frontend/src/pages/Setup.vue              # Setup wizard UI
  frontend/src/composables/useDeploymentMode.ts  # Mode helper

Modified files:
  backend/app/core/config.py               # Add DEPLOYMENT_MODE, APP_VERSION
  backend/app/core/tenant.py               # Single-tenant shortcut
  backend/app/api/auth.py                  # Disable register in on-premise
  backend/app/main.py                      # Mount setup router conditionally
  frontend/src/router/index.ts             # Setup route, conditional landing
  frontend/src/pages/Routers.vue           # Hide VPN button
  frontend/src/pages/Login.vue             # Hide register link
  frontend/src/pages/Dashboard.vue         # Update banner
  frontend/src/components/layout/Sidebar.vue  # Hide SaaS-only items
  frontend/src/api/client.ts               # (if portal slug changes needed)
```

## Out of Scope (For Now)

- License key validation (will design separately)
- Auto-update mechanism (manual `docker compose pull` for now)
- GitHub Actions CI/CD for image publishing
- On-premise customer portal without slug (keep slug but auto-resolve for single tenant)
