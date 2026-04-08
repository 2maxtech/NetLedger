# Onboarding Wizard Design

## Overview

Replace the current "jump between 6 pages" onboarding with a single-page guided wizard at `/onboarding`. 4 steps, every step skippable. Reuses existing API endpoints — no new backend needed.

## Route & Redirect Logic

- After login, if `onboarding.completed < onboarding.total && !onboarding.dismissed`, redirect to `/onboarding`
- X button in top-right exits wizard → dashboard (existing onboarding banner remains)
- Completing Step 4 marks onboarding dismissed and redirects to `/dashboard`

## Step 1: Connect Your Router (skippable)

### SaaS mode
- Fields: Router name (text)
- "Connect via VPN" button creates router with placeholder URL, then calls `POST /vpn/{id}/setup`
- Inline 3 substeps:
  1. Copy MikroTik script (code block + copy button)
  2. Paste public key (text input)
  3. Verify connection — calls `POST /vpn/{id}/activate`, shows green checkmark on success

### Self-hosted / On-premise mode
- Fields: Router name, URL (e.g. `http://192.168.88.1`), Username, Password
- "Test Connection" button calls `POST /routers/` then `GET /routers/{id}/status`
- Green checkmark when router identity received

### Skip
- "I'll set this up later" link → advances to Step 2
- Router step is optional; Steps 2-4 adapt based on whether a router exists

## Step 2: Import Customers (skippable)

### If router connected in Step 1
- Auto-calls `GET /routers/{id}/import-preview` to fetch PPPoE secrets + profiles
- Shows preview table: username, profile name, status (enabled/disabled)
- Per-profile price input (number field, pre-filled ₱0)
- "Import All" button calls `POST /routers/{id}/import` with plan_prices

### If router skipped
- "Create a Plan" mini-form: name, download Mbps, upload Mbps, monthly price
- "Add a Customer" mini-form: full name, PPPoE username, PPPoE password, select plan
- Both use existing `POST /plans/` and `POST /customers/` endpoints

### Skip
- "I'll do this later" → Step 3

## Step 3: Billing Settings (skippable)

Single settings card with pre-filled defaults:
- Default due day: 15
- Days after due to throttle: 3
- Days after due to disconnect: 5

"Save" calls `POST /settings/billing` with the values.

### Skip
- "Use defaults" → saves defaults and advances to Step 4

## Step 4: You're Ready

Summary card showing what was configured:
- Router: [name] connected / Not configured
- Customers: [X] imported / None yet
- Plans: [X] plans / None yet
- Billing: Due day [X], throttle [X] days, disconnect [X] days

"Go to Dashboard" button → calls `POST /onboarding/dismiss` → redirects to `/dashboard`

## Technical Details

### Frontend
- New file: `frontend/src/pages/Onboarding.vue` — single component with stepper
- New route: `/onboarding` as child of `/dashboard` layout (inherits auth guard)
- Modify: `frontend/src/router/index.ts` — add route
- Modify: login redirect logic — check onboarding status after login, redirect if needed

### Backend
- No new endpoints — all existing:
  - `POST /routers/` — create router
  - `POST /vpn/{id}/setup` — generate VPN script
  - `POST /vpn/{id}/activate` — activate VPN
  - `GET /routers/{id}/status` — test connection
  - `GET /routers/{id}/import-preview` — preview MT customers
  - `POST /routers/{id}/import` — import customers
  - `POST /plans/` — create plan
  - `POST /customers/` — create customer
  - `POST /settings/billing` — save billing config
  - `GET /onboarding/status` — check progress
  - `POST /onboarding/dismiss` — mark complete

### Styling
- Match existing app dark/light theme via Tailwind classes
- Step indicator bar at top (1 · 2 · 3 · 4) with active/completed states
- Cards for each step content area
- Consistent with existing modal/form styling

### What stays unchanged
- All existing pages (Routers, Customers, Plans, Settings) work as before
- Dashboard onboarding checklist banner stays for users who exit early
- `/setup` page for self-hosted initial server config is untouched
