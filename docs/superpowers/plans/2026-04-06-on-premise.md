# NetLedger On-Premise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add self-hosted on-premise deployment mode to NetLedger — same UI, single-tenant, no VPN, web setup wizard, update checker.

**Architecture:** A `DEPLOYMENT_MODE` env var (saas|onpremise) controls behavior. Backend conditionally skips multi-tenancy, VPN, and registration. Frontend uses `VITE_DEPLOYMENT_MODE` to hide SaaS-only UI. New setup wizard API + page handles first-time configuration. Docker Compose + install script for deployment.

**Tech Stack:** FastAPI, SQLAlchemy, Celery, Vue 3, Vite, Docker Compose, Bash

---

### Task 1: Backend — Config & Deployment Mode Flag

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `VERSION`

- [ ] **Step 1: Add DEPLOYMENT_MODE and APP_VERSION to Settings**

In `backend/app/core/config.py`, add these fields to the `Settings` class after `ALGORITHM`:

```python
# Deployment mode
DEPLOYMENT_MODE: str = "saas"  # "saas" or "onpremise"
APP_VERSION: str = "1.0.0"
UPDATE_CHECK_URL: str = "https://netl.2max.tech/api/v1/releases/latest"
```

- [ ] **Step 2: Create VERSION file at repo root**

Create `VERSION` at the repo root with content:
```
1.0.0
```

- [ ] **Step 3: Commit**

```bash
git add VERSION backend/app/core/config.py
git commit -m "feat: add DEPLOYMENT_MODE config and VERSION file"
```

---

### Task 2: Backend — Single-Tenant Resolution

**Files:**
- Modify: `backend/app/core/tenant.py`

- [ ] **Step 1: Update get_tenant_id for on-premise mode**

Replace the entire `backend/app/core/tenant.py` with:

```python
from fastapi import Depends, Header
from typing import Optional
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User, UserRole


async def get_tenant_id(
    current_user: User = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None),
) -> str:
    """Resolve effective tenant ID.

    On-premise: always returns the current user's ID (single tenant).
    SaaS:
      - Regular admin: returns their own user ID
      - Super admin without header: returns their own ID
      - Super admin with X-Tenant-Id header: returns the impersonated tenant's ID
    """
    if settings.DEPLOYMENT_MODE == "onpremise":
        return str(current_user.id)
    if current_user.role == UserRole.super_admin and x_tenant_id:
        return x_tenant_id
    return str(current_user.id)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/tenant.py
git commit -m "feat: single-tenant resolution for on-premise mode"
```

---

### Task 3: Backend — Setup Wizard API

**Files:**
- Create: `backend/app/api/setup.py`
- Create: `backend/app/schemas/setup.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create setup schema**

Create `backend/app/schemas/setup.py`:

```python
from pydantic import BaseModel


class SetupRequest(BaseModel):
    company_name: str
    admin_username: str
    admin_email: str
    admin_password: str
    router_name: str | None = None
    router_url: str | None = None
    router_username: str = "admin"
    router_password: str = ""


class SetupStatusResponse(BaseModel):
    configured: bool
    deployment_mode: str
```

- [ ] **Step 2: Create setup API**

Create `backend/app/api/setup.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.router import Router
from app.models.user import User, UserRole
from app.schemas.setup import SetupRequest, SetupStatusResponse

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusResponse)
async def setup_status(db: AsyncSession = Depends(get_db)):
    """Check if the app has been configured (public endpoint)."""
    result = await db.execute(select(func.count()).select_from(User).where(User.role == UserRole.admin))
    admin_count = result.scalar() or 0
    return SetupStatusResponse(
        configured=admin_count > 0,
        deployment_mode=settings.DEPLOYMENT_MODE,
    )


@router.post("/initialize")
async def initialize(body: SetupRequest, db: AsyncSession = Depends(get_db)):
    """First-time setup: create admin user and optionally first router.
    Only works when no admin user exists yet."""
    if settings.DEPLOYMENT_MODE != "onpremise":
        raise HTTPException(status_code=404, detail="Not found")

    # Check if already configured
    result = await db.execute(select(func.count()).select_from(User).where(User.role == UserRole.admin))
    if (result.scalar() or 0) > 0:
        raise HTTPException(status_code=403, detail="Application is already configured")

    # Check uniqueness
    existing = await db.execute(
        select(User).where((User.username == body.admin_username) | (User.email == body.admin_email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    # Create admin user
    user = User(
        username=body.admin_username,
        email=body.admin_email,
        password_hash=hash_password(body.admin_password),
        full_name=body.company_name,
        company_name=body.company_name,
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Optionally create first router
    router_created = False
    if body.router_name and body.router_url:
        url = body.router_url
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        r = Router(
            name=body.router_name,
            url=url,
            username=body.router_username,
            password=body.router_password,
            owner_id=user.id,
        )
        db.add(r)
        await db.flush()
        router_created = True

    # Generate tokens
    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": str(user.id),
        "router_created": router_created,
        "message": "Setup complete! Welcome to NetLedger.",
    }
```

- [ ] **Step 3: Mount setup router in main.py**

In `backend/app/main.py`, add the import after the existing imports:

```python
from app.api.setup import router as setup_router
```

Add the router include after the existing includes (before the uploads mount):

```python
app.include_router(setup_router, prefix=settings.API_V1_PREFIX)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/setup.py backend/app/api/setup.py backend/app/main.py
git commit -m "feat: setup wizard API for on-premise first-time configuration"
```

---

### Task 4: Backend — Disable SaaS-Only Endpoints in On-Premise

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Guard registration endpoint**

In `backend/app/api/auth.py`, add at the top of the `register` function (after the function signature line):

```python
    if settings.DEPLOYMENT_MODE == "onpremise":
        raise HTTPException(status_code=404, detail="Not found")
```

Add the import at the top of the file (it's already imported as `app_settings` but we need the raw settings):

```python
from app.core.config import settings as app_config
```

Actually, `settings` is already imported as `app_settings` on line 17. Update the guard to use that:

```python
    if app_settings.DEPLOYMENT_MODE == "onpremise":
        raise HTTPException(status_code=404, detail="Not found")
```

Add the same guard to the `verify_email` function.

- [ ] **Step 2: Conditionally skip VPN router in main.py**

In `backend/app/main.py`, wrap the VPN router include:

Change:
```python
app.include_router(vpn_router, prefix=settings.API_V1_PREFIX)
```

To:
```python
if settings.DEPLOYMENT_MODE != "onpremise":
    app.include_router(vpn_router, prefix=settings.API_V1_PREFIX)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/auth.py backend/app/main.py
git commit -m "feat: disable registration and VPN endpoints in on-premise mode"
```

---

### Task 5: Backend — Update Checker Service

**Files:**
- Create: `backend/app/services/update_checker.py`
- Create: `backend/app/tasks/update_checker.py`
- Modify: `backend/app/celery_app.py`
- Create: `backend/app/api/admin/system.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create update checker service**

Create `backend/app/services/update_checker.py`:

```python
import logging
import httpx
from packaging.version import Version

from app.core.config import settings

logger = logging.getLogger(__name__)


async def check_for_updates() -> dict | None:
    """Check if a newer version of NetLedger is available.
    Returns update info dict or None if up to date."""
    if settings.DEPLOYMENT_MODE != "onpremise":
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(settings.UPDATE_CHECK_URL)
            if resp.status_code != 200:
                return None
            data = resp.json()
            latest = data.get("version", "")
            if not latest:
                return None
            if Version(latest) > Version(settings.APP_VERSION):
                return {
                    "version": latest,
                    "release_notes": data.get("release_notes", ""),
                    "release_date": data.get("release_date", ""),
                    "download_url": data.get("download_url", ""),
                }
    except Exception as e:
        logger.warning(f"Update check failed: {e}")
    return None
```

- [ ] **Step 2: Create Celery task**

Create `backend/app/tasks/update_checker.py`:

```python
import asyncio
from app.celery_app import celery
from app.core.database import async_session_factory
from app.models.app_setting import AppSetting
from app.services.update_checker import check_for_updates
from sqlalchemy import select
import json


@celery.task(name="app.tasks.update_checker.check_updates_task")
def check_updates_task():
    """Daily task to check for NetLedger updates (on-premise only)."""
    asyncio.get_event_loop().run_until_complete(_check_updates())


async def _check_updates():
    update_info = await check_for_updates()
    async with async_session_factory() as session:
        # Clear old update info
        result = await session.execute(
            select(AppSetting).where(
                AppSetting.key == "update_available",
                AppSetting.owner_id.is_(None),
            )
        )
        existing = result.scalar_one_or_none()

        if update_info:
            value = json.dumps(update_info)
            if existing:
                existing.value = value
            else:
                session.add(AppSetting(key="update_available", value=value, owner_id=None))
        else:
            if existing:
                await session.delete(existing)

        await session.commit()
```

- [ ] **Step 3: Add beat schedule for update checker**

In `backend/app/celery_app.py`, add to the `include` list:

```python
include=["app.tasks.billing", "app.tasks.update_checker"],
```

Add to `beat_schedule` dict:

```python
    "check-for-updates": {
        "task": "app.tasks.update_checker.check_updates_task",
        "schedule": crontab(hour="3", minute="30"),
    },
```

- [ ] **Step 4: Create system API endpoint**

Create `backend/app/api/admin/system.py`:

```python
import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.app_setting import AppSetting
from app.models.user import User

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/update-check")
async def check_update(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get available update info (on-premise only)."""
    if settings.DEPLOYMENT_MODE != "onpremise":
        return {"update_available": False}

    result = await db.execute(
        select(AppSetting).where(
            AppSetting.key == "update_available",
            AppSetting.owner_id.is_(None),
        )
    )
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        info = json.loads(setting.value)
        return {"update_available": True, **info}
    return {"update_available": False}


@router.get("/version")
async def get_version():
    """Get current app version and deployment mode (public)."""
    return {
        "version": settings.APP_VERSION,
        "deployment_mode": settings.DEPLOYMENT_MODE,
    }
```

- [ ] **Step 5: Mount system router in main.py**

In `backend/app/main.py`, add import:

```python
from app.api.admin.system import router as system_router
```

Add include:

```python
app.include_router(system_router, prefix=settings.API_V1_PREFIX)
```

- [ ] **Step 6: Add httpx and packaging to dependencies**

Check if `httpx` and `packaging` are already in `backend/requirements.txt`. If not, add them.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/update_checker.py backend/app/tasks/update_checker.py backend/app/celery_app.py backend/app/api/admin/system.py backend/app/main.py
git commit -m "feat: update checker service with daily Celery task and API endpoint"
```

---

### Task 6: Backend — Release Endpoint (SaaS side)

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add releases endpoint to main.py**

Add a simple public endpoint directly in `backend/app/main.py` (before the health check):

```python
@app.get(f"{settings.API_V1_PREFIX}/releases/latest")
async def latest_release():
    """Public endpoint for on-premise installations to check for updates."""
    return {
        "version": settings.APP_VERSION,
        "release_notes": "Latest release of NetLedger",
        "release_date": "2026-04-06",
        "download_url": "https://github.com/2maxtech/NetLedger/releases/latest",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: public releases/latest endpoint for on-premise update checking"
```

---

### Task 7: Frontend — Deployment Mode Composable

**Files:**
- Create: `frontend/src/composables/useDeploymentMode.ts`
- Create: `frontend/src/api/setup.ts`

- [ ] **Step 1: Create deployment mode composable**

Create `frontend/src/composables/useDeploymentMode.ts`:

```typescript
export const isOnPremise = import.meta.env.VITE_DEPLOYMENT_MODE === 'onpremise'
export const isSaaS = !isOnPremise
```

- [ ] **Step 2: Create setup API client**

Create `frontend/src/api/setup.ts`:

```typescript
import api from './client'
import axios from 'axios'

export interface SetupStatus {
  configured: boolean
  deployment_mode: string
}

export interface SetupRequest {
  company_name: string
  admin_username: string
  admin_email: string
  admin_password: string
  router_name?: string
  router_url?: string
  router_username?: string
  router_password?: string
}

export interface SetupResponse {
  access_token: string
  refresh_token: string
  user_id: string
  router_created: boolean
  message: string
}

export interface UpdateInfo {
  update_available: boolean
  version?: string
  release_notes?: string
  release_date?: string
  download_url?: string
}

// Setup status is public (no auth needed)
export function getSetupStatus() {
  return axios.get<SetupStatus>('/api/v1/setup/status')
}

export function initializeSetup(data: SetupRequest) {
  return axios.post<SetupResponse>('/api/v1/setup/initialize', data)
}

export function checkForUpdate() {
  return api.get<UpdateInfo>('/system/update-check')
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useDeploymentMode.ts frontend/src/api/setup.ts
git commit -m "feat: deployment mode composable and setup API client"
```

---

### Task 8: Frontend — Setup Wizard Page

**Files:**
- Create: `frontend/src/pages/Setup.vue`

- [ ] **Step 1: Create setup wizard page**

Create `frontend/src/pages/Setup.vue`:

```vue
<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { initializeSetup } from '../api/setup'
import axios from 'axios'

const router = useRouter()
const step = ref(1)
const loading = ref(false)
const error = ref('')
const testResult = ref<'success' | 'error' | ''>('')
const testMessage = ref('')

const form = reactive({
  company_name: '',
  admin_username: '',
  admin_email: '',
  admin_password: '',
  admin_password_confirm: '',
  router_name: '',
  router_url: '',
  router_username: 'admin',
  router_password: '',
})

function nextStep() {
  error.value = ''
  if (step.value === 1) {
    if (!form.company_name.trim()) { error.value = 'Company name is required'; return }
    step.value = 2
  } else if (step.value === 2) {
    if (!form.admin_username.trim()) { error.value = 'Username is required'; return }
    if (!form.admin_email.trim()) { error.value = 'Email is required'; return }
    if (!form.admin_password || form.admin_password.length < 6) { error.value = 'Password must be at least 6 characters'; return }
    if (form.admin_password !== form.admin_password_confirm) { error.value = 'Passwords do not match'; return }
    step.value = 3
  }
}

function prevStep() {
  error.value = ''
  if (step.value > 1) step.value--
}

async function testConnection() {
  testResult.value = ''
  testMessage.value = ''
  if (!form.router_url.trim()) { testMessage.value = 'Enter a router URL first'; testResult.value = 'error'; return }
  loading.value = true
  try {
    // We don't have auth yet, so test by pinging the setup endpoint with router info
    // For now, just validate URL format
    const url = form.router_url.startsWith('http') ? form.router_url : `http://${form.router_url}`
    testResult.value = 'success'
    testMessage.value = `Router URL looks valid: ${url}`
  } catch {
    testResult.value = 'error'
    testMessage.value = 'Could not validate router URL'
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await initializeSetup({
      company_name: form.company_name,
      admin_username: form.admin_username,
      admin_email: form.admin_email,
      admin_password: form.admin_password,
      router_name: form.router_name || undefined,
      router_url: form.router_url || undefined,
      router_username: form.router_username || undefined,
      router_password: form.router_password || undefined,
    })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    router.push('/dashboard')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Setup failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-[#1a1a2e] to-sidebar px-4">
    <div class="absolute inset-0 opacity-5">
      <div class="absolute inset-0" style="background-image: radial-gradient(circle at 25% 25%, white 1px, transparent 1px); background-size: 50px 50px;" />
    </div>

    <div class="relative w-full max-w-lg">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-white/10 backdrop-blur-sm mb-4">
          <img src="/logo-2.png" alt="NetLedger" class="w-16 h-16 object-contain" />
        </div>
        <h1 class="text-3xl font-bold text-white tracking-tight">NetLedger Setup</h1>
        <p class="text-gray-400 mt-1 text-sm">Let's get your ISP billing system ready</p>
      </div>

      <!-- Progress steps -->
      <div class="flex items-center justify-center gap-2 mb-6">
        <div v-for="s in 3" :key="s" class="flex items-center gap-2">
          <div
            :class="[
              'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors',
              s <= step ? 'bg-primary text-white' : 'bg-white/10 text-gray-400'
            ]"
          >{{ s }}</div>
          <div v-if="s < 3" :class="['w-8 h-0.5', s < step ? 'bg-primary' : 'bg-white/10']" />
        </div>
      </div>

      <!-- Card -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-8">
        <!-- Error -->
        <div v-if="error" class="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {{ error }}
        </div>

        <!-- Step 1: Company -->
        <div v-if="step === 1">
          <h2 class="text-lg font-semibold text-gray-900 mb-1">Company Information</h2>
          <p class="text-sm text-gray-500 mb-6">This will be used for branding your ISP portal.</p>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Company / ISP Name</label>
            <input
              v-model="form.company_name"
              type="text"
              placeholder="e.g. MyISP Internet Services"
              class="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              @keyup.enter="nextStep"
            />
          </div>
        </div>

        <!-- Step 2: Admin Account -->
        <div v-if="step === 2">
          <h2 class="text-lg font-semibold text-gray-900 mb-1">Admin Account</h2>
          <p class="text-sm text-gray-500 mb-6">Create your administrator login.</p>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Username</label>
              <input v-model="form.admin_username" type="text" placeholder="admin" class="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
              <input v-model="form.admin_email" type="email" placeholder="admin@myisp.com" class="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
              <input v-model="form.admin_password" type="password" placeholder="Min. 6 characters" class="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Confirm Password</label>
              <input v-model="form.admin_password_confirm" type="password" placeholder="Re-enter password" class="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" @keyup.enter="nextStep" />
            </div>
          </div>
        </div>

        <!-- Step 3: Router (optional) -->
        <div v-if="step === 3">
          <h2 class="text-lg font-semibold text-gray-900 mb-1">Connect Your Router</h2>
          <p class="text-sm text-gray-500 mb-6">Optional — you can add routers later from the Routers page.</p>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Router Name</label>
              <input v-model="form.router_name" type="text" placeholder="e.g. Main Router" class="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Router IP / URL</label>
              <input v-model="form.router_url" type="text" placeholder="e.g. 192.168.88.1" class="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Username</label>
                <input v-model="form.router_username" type="text" placeholder="admin" class="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
                <input v-model="form.router_password" type="password" placeholder="Router password" class="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
              </div>
            </div>
            <!-- Test connection -->
            <div v-if="testResult" :class="['rounded-lg px-4 py-3 text-sm', testResult === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-700']">
              {{ testMessage }}
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-between mt-8">
          <button
            v-if="step > 1"
            @click="prevStep"
            class="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
          >Back</button>
          <div v-else />

          <div class="flex gap-3">
            <button
              v-if="step === 3"
              @click="handleSubmit"
              :disabled="loading"
              class="px-6 py-2.5 rounded-lg bg-primary text-white font-medium text-sm hover:bg-primary-hover disabled:opacity-60 transition-colors"
            >
              {{ loading ? 'Setting up...' : (form.router_name ? 'Complete Setup' : 'Skip & Finish') }}
            </button>
            <button
              v-else
              @click="nextStep"
              class="px-6 py-2.5 rounded-lg bg-primary text-white font-medium text-sm hover:bg-primary-hover transition-colors"
            >Next</button>
          </div>
        </div>
      </div>

      <p class="text-center text-gray-500 text-xs mt-6">
        &copy; {{ new Date().getFullYear() }} NetLedger &mdash; 2max Tech
      </p>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Setup.vue
git commit -m "feat: setup wizard page for on-premise first-time configuration"
```

---

### Task 9: Frontend — Routing & Guards

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Update router for on-premise mode**

In `frontend/src/router/index.ts`, add import at top:

```typescript
import { isOnPremise } from '../composables/useDeploymentMode'
```

Change the root route from:
```typescript
{
  path: '/',
  component: () => import('../pages/Landing.vue'),
},
```
To:
```typescript
{
  path: '/',
  component: () => isOnPremise ? import('../pages/Login.vue') : import('../pages/Landing.vue'),
},
```

Add setup route after the `/self-hosted` route:
```typescript
{
  path: '/setup',
  component: () => import('../pages/Setup.vue'),
},
```

Update the `publicPaths` in the `beforeEach` guard:
```typescript
const publicPaths = ['/', '/login', '/register', '/self-hosted', '/setup']
```

Add a setup redirect check inside `beforeEach`, after the `publicPaths` definition:

```typescript
// On-premise: redirect to setup if unconfigured
if (isOnPremise && !localStorage.getItem('setup_done') && to.path !== '/setup') {
  try {
    const resp = await fetch('/api/v1/setup/status')
    const data = await resp.json()
    if (!data.configured) return '/setup'
    localStorage.setItem('setup_done', '1')
  } catch {
    // If setup check fails, allow navigation
  }
}
```

Note: The `beforeEach` callback needs to become `async`:
```typescript
router.beforeEach(async (to) => {
```

- [ ] **Step 2: Hide register route in on-premise mode**

Wrap the register route:
```typescript
...(isOnPremise ? [] : [{
  path: '/register',
  component: () => import('../pages/Register.vue'),
}]),
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.ts
git commit -m "feat: on-premise routing — setup redirect, hide registration"
```

---

### Task 10: Frontend — Conditional UI (Login, Routers, Sidebar, Dashboard)

**Files:**
- Modify: `frontend/src/pages/Login.vue`
- Modify: `frontend/src/pages/Routers.vue`
- Modify: `frontend/src/components/layout/Sidebar.vue`
- Modify: `frontend/src/pages/Dashboard.vue`

- [ ] **Step 1: Hide register link on Login page**

In `frontend/src/pages/Login.vue`, add import:
```typescript
import { isSaaS } from '../composables/useDeploymentMode'
```

Wrap the register link (around line 177) with `v-if="isSaaS"`:
```html
<p v-if="isSaaS" class="text-center text-sm text-gray-400 mt-5">
  Don't have an account?
  <router-link to="/register" class="text-primary font-medium hover:underline">Register</router-link>
</p>
```

- [ ] **Step 2: Hide VPN button on Routers page**

In `frontend/src/pages/Routers.vue`, add import:
```typescript
import { isSaaS } from '../composables/useDeploymentMode'
```

Find the VPN setup button in the template (the button that calls `startVpnSetup`) and wrap it with `v-if="isSaaS"`.

- [ ] **Step 3: Hide super admin menu in Sidebar for on-premise**

In `frontend/src/components/layout/Sidebar.vue`, add import:
```typescript
import { isOnPremise } from '../../composables/useDeploymentMode'
```

Update `showAdminMenu` to always show ISP menu in on-premise mode:
```typescript
const showAdminMenu = computed(() => isOnPremise || (!isSuperAdmin.value || isImpersonating.value))
```

Also import `isSuperAdmin` isn't needed in on-premise — the existing computed already handles it since there's no super_admin role.

- [ ] **Step 4: Add update banner to Dashboard**

In `frontend/src/pages/Dashboard.vue`, add imports:
```typescript
import { isOnPremise } from '../composables/useDeploymentMode'
import { checkForUpdate, type UpdateInfo } from '../api/setup'
```

Add state:
```typescript
const updateInfo = ref<UpdateInfo | null>(null)
```

Add to `onMounted`:
```typescript
if (isOnPremise) {
  try {
    const { data } = await checkForUpdate()
    if (data.update_available) updateInfo.value = data
  } catch { /* ignore */ }
}
```

Add banner in template, at the very top of the main content (before the stats row):
```html
<!-- Update available banner -->
<div v-if="updateInfo" class="mb-4 flex items-center justify-between rounded-lg bg-blue-50 border border-blue-200 px-4 py-3">
  <div class="flex items-center gap-2 text-sm text-blue-700">
    <svg class="w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 8.25H7.5a2.25 2.25 0 00-2.25 2.25v9a2.25 2.25 0 002.25 2.25h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25H15M9 12l3 3m0 0l3-3m-3 3V2.25" />
    </svg>
    <span><strong>NetLedger v{{ updateInfo.version }}</strong> is available.</span>
    <span v-if="updateInfo.release_notes" class="text-blue-500">{{ updateInfo.release_notes }}</span>
  </div>
  <a
    v-if="updateInfo.download_url"
    :href="updateInfo.download_url"
    target="_blank"
    class="text-sm font-medium text-blue-600 hover:text-blue-800"
  >View Release</a>
</div>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Login.vue frontend/src/pages/Routers.vue frontend/src/components/layout/Sidebar.vue frontend/src/pages/Dashboard.vue
git commit -m "feat: hide SaaS-only UI elements in on-premise mode, add update banner"
```

---

### Task 11: Deployment Artifacts — Docker Compose, Env Template, Install Script

**Files:**
- Create: `docker-compose.onpremise.yml`
- Create: `.env.onpremise.example`
- Create: `scripts/install-onpremise.sh`

- [ ] **Step 1: Create on-premise Docker Compose file**

Create `docker-compose.onpremise.yml`:

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
    build:
      context: ./backend
      dockerfile: Dockerfile
    depends_on:
      - db
      - redis
    environment:
      DEPLOYMENT_MODE: onpremise
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-netledger}:${DB_PASSWORD}@db:5432/${DB_NAME:-netledger}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      BASE_URL: ${BASE_URL:-http://localhost}
    volumes:
      - uploads:/app/uploads
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_DEPLOYMENT_MODE: onpremise
    ports:
      - "${HTTP_PORT:-80}:80"
    depends_on:
      - backend
    restart: unless-stopped

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.celery_app worker --loglevel=info --concurrency=2
    depends_on:
      - db
      - redis
    environment:
      DEPLOYMENT_MODE: onpremise
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-netledger}:${DB_PASSWORD}@db:5432/${DB_NAME:-netledger}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    restart: unless-stopped

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.celery_app beat --loglevel=info -s /tmp/celerybeat-schedule
    depends_on:
      - db
      - redis
    environment:
      DEPLOYMENT_MODE: onpremise
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-netledger}:${DB_PASSWORD}@db:5432/${DB_NAME:-netledger}
      REDIS_URL: redis://redis:6379/0
    restart: unless-stopped

volumes:
  pgdata:
  uploads:
```

- [ ] **Step 2: Create env template**

Create `.env.onpremise.example`:

```env
# NetLedger On-Premise Configuration
# Copy to .env and fill in your values (install script does this automatically)

# Database
DB_USER=netledger
DB_PASSWORD=CHANGE_ME
DB_NAME=netledger

# Security — generate with: openssl rand -hex 32
SECRET_KEY=CHANGE_ME

# HTTP port (default 80). Use a reverse proxy (nginx/caddy) for SSL.
HTTP_PORT=80

# Base URL for email links (e.g., https://billing.myisp.com)
BASE_URL=http://localhost

# SMTP (optional — needed for email notifications)
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=
# SMTP_PASSWORD=
# SMTP_FROM=noreply@myisp.com
```

- [ ] **Step 3: Create install script**

Create `scripts/install-onpremise.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# NetLedger On-Premise Installer
# Usage: bash install-onpremise.sh

INSTALL_DIR="/opt/netledger"
REPO_URL="https://github.com/2maxtech/NetLedger.git"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║    NetLedger On-Premise Installer      ║"
echo "  ║    ISP Billing Made Simple             ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# Check running as root
if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run as root (sudo bash install-onpremise.sh)"
  exit 1
fi

# Check OS
if [ -f /etc/os-release ]; then
  . /etc/os-release
  echo "Detected OS: $PRETTY_NAME"
else
  echo "Warning: Could not detect OS"
fi

# Install Docker if not present
if ! command -v docker &> /dev/null; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | bash
  systemctl enable docker
  systemctl start docker
  echo "Docker installed."
else
  echo "Docker already installed: $(docker --version)"
fi

# Install Docker Compose plugin if not present
if ! docker compose version &> /dev/null; then
  echo "Installing Docker Compose plugin..."
  apt-get update -qq && apt-get install -y -qq docker-compose-plugin
  echo "Docker Compose installed."
else
  echo "Docker Compose already installed: $(docker compose version)"
fi

# Create install directory
echo "Creating $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Clone or pull repo
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating existing installation..."
  git pull --ff-only
else
  echo "Downloading NetLedger..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Generate .env if not exists
if [ ! -f "$INSTALL_DIR/.env" ]; then
  echo "Generating configuration..."
  DB_PASS=$(openssl rand -hex 16)
  SECRET=$(openssl rand -hex 32)

  cp "$INSTALL_DIR/.env.onpremise.example" "$INSTALL_DIR/.env"
  sed -i "s/DB_PASSWORD=CHANGE_ME/DB_PASSWORD=$DB_PASS/" "$INSTALL_DIR/.env"
  sed -i "s/SECRET_KEY=CHANGE_ME/SECRET_KEY=$SECRET/" "$INSTALL_DIR/.env"

  echo "Generated .env with secure random passwords."
else
  echo "Existing .env found, keeping it."
fi

# Build and start
echo ""
echo "Building and starting NetLedger..."
docker compose -f docker-compose.onpremise.yml up -d --build

# Wait for backend to be ready
echo "Waiting for services to start..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:${HTTP_PORT:-80}/health > /dev/null 2>&1; then
    break
  fi
  sleep 2
done

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║    NetLedger is ready!                 ║"
echo "  ╠═══════════════════════════════════════╣"
echo "  ║                                       ║"
echo "  ║  Open in your browser:                ║"
echo "  ║  http://$SERVER_IP                    ║"
echo "  ║                                       ║"
echo "  ║  Complete the setup wizard to create   ║"
echo "  ║  your admin account.                   ║"
echo "  ║                                       ║"
echo "  ║  Config: $INSTALL_DIR/.env            ║"
echo "  ║                                       ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""
echo "To update later: cd $INSTALL_DIR && git pull && docker compose -f docker-compose.onpremise.yml up -d --build"
echo ""
```

- [ ] **Step 4: Make install script executable**

```bash
chmod +x scripts/install-onpremise.sh
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.onpremise.yml .env.onpremise.example scripts/install-onpremise.sh
git commit -m "feat: on-premise deployment artifacts — Docker Compose, env template, install script"
```

---

### Task 12: Frontend Dockerfile — Support Build Args

**Files:**
- Modify: `frontend/Dockerfile`

- [ ] **Step 1: Check current Dockerfile and add VITE_DEPLOYMENT_MODE build arg**

In `frontend/Dockerfile`, add a build arg so the on-premise compose file can set it at build time:

After the `FROM node:... AS build` line (or wherever the build stage starts), add:
```dockerfile
ARG VITE_DEPLOYMENT_MODE=saas
ENV VITE_DEPLOYMENT_MODE=$VITE_DEPLOYMENT_MODE
```

This ensures the SaaS build (default, no arg) stays as-is, while the on-premise compose passes `VITE_DEPLOYMENT_MODE=onpremise`.

- [ ] **Step 2: Commit**

```bash
git add frontend/Dockerfile
git commit -m "feat: support VITE_DEPLOYMENT_MODE build arg in frontend Dockerfile"
```

---

### Task 13: Portal Simplification for On-Premise

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add simplified portal routes for on-premise**

In `frontend/src/router/index.ts`, add on-premise portal routes (without slug) alongside the existing ones:

```typescript
...(isOnPremise ? [
  {
    path: '/portal/login',
    component: () => import('../pages/portal/PortalLogin.vue'),
    props: { defaultSlug: '_default' },
  },
  {
    path: '/portal',
    component: () => import('../components/layout/PortalLayout.vue'),
    children: [
      { path: '', component: () => import('../pages/portal/PortalDashboard.vue') },
      { path: 'invoices', component: () => import('../pages/portal/PortalInvoices.vue') },
      { path: 'usage', component: () => import('../pages/portal/PortalUsage.vue') },
      { path: 'tickets', component: () => import('../pages/portal/PortalTickets.vue') },
      { path: 'tickets/:id', component: () => import('../pages/portal/PortalTicketDetail.vue') },
    ],
  },
] : []),
```

- [ ] **Step 2: Update portal API client redirect for on-premise**

In `frontend/src/api/client.ts`, add import:
```typescript
import { isOnPremise } from '../composables/useDeploymentMode'
```

Update the 401 handler in `portalApi` interceptor:
```typescript
if (error.response?.status === 401) {
  localStorage.removeItem('portal_token')
  localStorage.removeItem('portal_customer')
  localStorage.removeItem('portal_slug')
  if (isOnPremise) {
    window.location.href = '/portal/login'
  } else {
    const slug = localStorage.getItem('portal_slug')
    window.location.href = slug ? `/portal/${slug}/login` : '/'
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/api/client.ts
git commit -m "feat: simplified portal routes for on-premise (no tenant slug)"
```

---

### Summary

| Task | Description | Est. |
|------|-------------|------|
| 1 | Config + VERSION file | 2 min |
| 2 | Single-tenant resolution | 2 min |
| 3 | Setup wizard API | 5 min |
| 4 | Disable SaaS endpoints | 3 min |
| 5 | Update checker service | 5 min |
| 6 | Release endpoint (SaaS) | 2 min |
| 7 | Frontend composable + API | 2 min |
| 8 | Setup wizard page | 5 min |
| 9 | Routing & guards | 5 min |
| 10 | Conditional UI elements | 5 min |
| 11 | Deployment artifacts | 5 min |
| 12 | Frontend Dockerfile build arg | 2 min |
| 13 | Portal simplification | 3 min |

**Total: 13 tasks, ~46 minutes**

Dependencies:
- Tasks 1-6 (backend) are independent of Tasks 7-10, 12-13 (frontend)
- Task 7 must complete before Tasks 8-10, 13
- Task 11 is fully independent
