# NetLedger Feature Pack — Design Spec

## Overview

Bundle of features to bring NetLedger to production-ready state for PH ISP market. Covers: multi-router frontend completion, network scanner, SMTP settings UI, invoice printing, expense tracking, PPPoE password generator, and customizable dashboard.

---

## Feature 1: Multi-Router Frontend (Tasks 7-8 completion)

### Routers Page (`/routers`)

Table with columns: Name, URL, Location, Status badge (green/red), Sessions count, Actions.

Actions per row:
- **Edit** — modal with name, url, username, password, location fields
- **Test Connection** — calls `GET /routers/{id}/status`, shows result toast
- **Import Subscribers** — calls `POST /routers/{id}/import`, shows result count
- **Delete** — Popconfirm → soft-delete (set is_active=false)

"Add Router" button opens same modal for creation.

### Areas Page (`/areas`)

Table: Name, Description, Router (dropdown name), Customer count, Actions (Edit, Delete).

Modal form: name, description, router_id (Select populated from routers list).

### Sidebar Updates

Add after Active Users, before System group:
- Routers (CloudServerOutlined icon)
- Areas (EnvironmentOutlined icon)

### Route Registration

Lazy-load Routers and Areas pages in the router config, matching existing pattern.

### Dashboard — Per-Router Health Cards

Replace single MikroTik card with a row of cards, one per router. Each shows: name, status badge, CPU gauge, memory gauge, active sessions, interface traffic table.

Header subtitle: "{X}/{Y} routers online".

### Active Users — Router Filter

Add Select dropdown above table to filter sessions by router. Pass `?router_id=` to API.

### Network API Type Update

`DashboardData.mikrotik` becomes:
```typescript
{
  total_sessions: number;
  routers: Array<{ id, name, location, connected, identity, uptime, cpu_load, free_memory, total_memory, active_sessions, version, interfaces[] }>;
}
```

---

## Feature 2: MikroTik Network Scanner

### Backend: `POST /api/v1/network/scan`

Scans the local subnet for MikroTik devices using:
1. **Port scan** — try connecting to port 80 (www/REST API) on each IP in a given subnet range
2. For each responding IP, attempt `GET /rest/system/identity` with default credentials (admin/"") and configurable credentials
3. Return list of discovered devices with IP, identity name, version, and whether auth succeeded

Request body:
```json
{
  "subnet": "192.168.40.0/24",
  "username": "admin",
  "password": ""
}
```

Response:
```json
{
  "found": [
    {"ip": "192.168.40.30", "identity": "NetLedger-MT", "version": "7.18.2", "auth_ok": true},
    {"ip": "192.168.40.31", "identity": "MT-Tower2", "version": "7.16.1", "auth_ok": false}
  ],
  "scanned": 254,
  "duration_seconds": 12.3
}
```

Uses `asyncio.gather` with `httpx` to scan in parallel (batch of 20 concurrent). Timeout 2s per IP.

### Frontend

On the Routers page, add "Scan Network" button. Opens a modal:
- Input: subnet (default from MIKROTIK_URL's subnet), username, password
- Click "Scan" → shows spinner → shows results table
- Each found router has an "Add" button that pre-fills the Add Router modal

---

## Feature 3: SMTP Settings in UI

### Database: `settings` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| key | String(100), unique | e.g. "smtp_host", "smtp_port" |
| value | Text | encrypted for passwords |
| created_at | DateTime | |

Settings stored as key-value pairs. Keys:
- `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `smtp_from_name`

### Backend

- `GET /api/v1/settings/smtp` — returns current SMTP config (password masked)
- `PUT /api/v1/settings/smtp` — save SMTP config
- `POST /api/v1/settings/smtp/test` — send a test email to a given address

The notification service reads SMTP settings from DB instead of env vars. Falls back to env vars if DB settings not configured.

### Frontend: Settings Page (`/settings`)

Under System menu. Tabs or sections:
- **Email (SMTP)** — host, port, username, password, from email, from name, "Send Test Email" button
- Future tabs: General, Billing defaults, etc.

### Model

```python
class AppSetting(BaseModel):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
```

---

## Feature 4: Invoice Printing

### Approach: Browser Print (`window.print()`)

No server-side printer detection needed. Add a "Print" button on:
- Invoice detail/list page — per invoice
- Invoice PDF download already exists — add a print-friendly view

### Implementation

Add a `PrintInvoice` component that:
1. Fetches invoice data
2. Renders a print-optimized HTML layout (hidden on screen, shown on print)
3. Calls `window.print()`

Or simpler: the existing PDF download already works. Add a "Print" button next to "Download PDF" that:
1. Downloads the PDF into a hidden iframe
2. Calls `iframe.contentWindow.print()`

Simplest approach: just add a Print button that opens the PDF in a new tab — the browser's PDF viewer has a built-in print button.

### Frontend Changes

- `Invoices.tsx`: Add PrinterOutlined button in the actions column, links to `/api/v1/billing/invoices/{id}/pdf` in a new tab
- `PortalInvoices.tsx`: Same for customer portal

---

## Feature 5: Expense Tracking

### Database: `expenses` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| category | Enum | electricity, internet, salary, equipment, maintenance, rent, other |
| description | String(255) | |
| amount | Numeric(10,2) | |
| date | Date | when expense occurred |
| receipt_number | String(100), nullable | |
| recorded_by | UUID (FK → users), nullable | |
| created_at | DateTime | |

### Backend

- `POST /api/v1/expenses/` — create expense
- `GET /api/v1/expenses/` — list with date range filter, category filter, pagination
- `PUT /api/v1/expenses/{id}` — update
- `DELETE /api/v1/expenses/{id}` — delete
- `GET /api/v1/expenses/summary` — totals by category for date range

### Frontend: Expenses Page (`/expenses`)

Under Billing menu group:
- Table: date, category (colored tag), description, amount, receipt #, actions
- "Add Expense" button → modal with form
- Summary cards at top: total expenses this month, by category breakdown
- Date range filter

### Dashboard Integration

Add to dashboard:
- "Expenses This Month" stat card
- "Net Profit" = collected revenue - expenses
- Revenue vs Expenses in the trend chart

### Sidebar

Add "Expenses" under Billing group (after Payments).

---

## Feature 6: PPPoE Password Generator

### Frontend Only

On the Customer create/edit form, add a "Generate" button next to the PPPoE password field.

Clicking it generates a random password:
- 8 characters
- Mix of lowercase, uppercase, digits
- No ambiguous characters (0/O, 1/l/I)
- Sets the password field value

Implementation: a simple utility function, no backend needed.

```typescript
function generatePassword(length = 8): string {
  const chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789';
  return Array.from({ length }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
}
```

Add a Button with KeyOutlined icon next to the password Input in the customer form.

---

## Feature 7: Customizable Dashboard

### Approach: Widget Preferences Stored in localStorage

No backend needed for v1. The admin can show/hide dashboard widgets.

Available widgets:
1. Subscriber counts (always shown)
2. Revenue stats (always shown)
3. Router health cards
4. Revenue trend chart
5. Recent payments
6. Overdue accounts
7. Expense summary

### Implementation

- Add a "Customize" button (SettingOutlined) on dashboard header
- Opens a drawer/modal with checkbox list of widgets
- Preferences saved to `localStorage('dashboard_widgets')`
- Dashboard reads preferences and conditionally renders widgets
- Default: all widgets visible

---

## Feature 8: Prepaid Voucher System

Critical for PH market — Mikhmon and PHPMixBill's main selling point.

### Database: `vouchers` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| code | String(20), unique | e.g. "NL-A3K9-X7M2" |
| plan_id | UUID (FK → plans) | Which plan this voucher grants |
| duration_days | Integer | How long access lasts (1, 7, 30, etc.) |
| status | Enum | unused, active, expired, revoked |
| customer_id | UUID (FK → customers), nullable | Set when redeemed |
| activated_at | DateTime, nullable | When redeemed |
| expires_at | DateTime, nullable | activated_at + duration_days |
| batch_id | String(50), nullable | Group vouchers by generation batch |
| created_at | DateTime | |

### Backend

- `POST /api/v1/vouchers/generate` — generate batch of vouchers (count, plan_id, duration_days). Returns codes.
- `GET /api/v1/vouchers/` — list with status filter, batch filter, pagination
- `POST /api/v1/vouchers/redeem` — redeem a code (customer_id + code). Creates/extends customer access.
- `DELETE /api/v1/vouchers/{id}` — revoke unused voucher
- `GET /api/v1/vouchers/batches` — list generation batches with counts

Voucher code format: `NL-XXXX-XXXX` (alphanumeric, uppercase, no ambiguous chars).

### Frontend: Vouchers Page (`/vouchers`)

Under Billing menu:
- Table: code, plan name, duration, status (tag), customer (if redeemed), created/activated dates
- "Generate Vouchers" button → modal: plan dropdown, duration, count (1-500)
- Batch filter dropdown
- "Print Vouchers" — generates a printable card layout for selected vouchers
- "Redeem" button → modal with code input + customer selector

### Customer Portal

- "Redeem Voucher" section on portal dashboard
- Input voucher code → extends access

---

## Feature 9: GCash/Maya Payment Integration

### Approach: Payment Gateway Abstraction

Support GCash and Maya (PayMaya) via their respective APIs. Both use similar webhook patterns.

### Database: `payment_gateways` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| name | String(50) | "gcash", "maya" |
| is_active | Boolean | |
| api_key | String(255) | |
| api_secret | String(255) | |
| webhook_secret | String(255) | |
| mode | Enum | sandbox, production |
| created_at | DateTime | |

### Backend

- `GET /api/v1/settings/payment-gateways` — list configured gateways
- `PUT /api/v1/settings/payment-gateways/{name}` — configure gateway credentials
- `POST /api/v1/portal/pay` — create payment intent (customer selects invoice + gateway)
- `POST /api/v1/webhooks/gcash` — GCash payment confirmation webhook
- `POST /api/v1/webhooks/maya` — Maya payment confirmation webhook

On webhook confirmation → auto-record payment → auto-reconnect if applicable.

### Frontend

- Settings page: Payment Gateways tab — configure GCash/Maya API keys
- Customer portal: "Pay Now" button on invoice → select GCash or Maya → redirect to payment page → webhook confirms → invoice marked paid
- Admin invoices: show payment method badge (cash/bank/gcash/maya)

### PaymentMethod Enum Update

Add `gcash` and `maya` to the existing `PaymentMethod` enum in the Payment model.

---

## Feature 10: MikroTik Hotspot User Management

### Scope

Manage MikroTik hotspot users (separate from PPPoE). Used for WiFi voucher/captive portal systems.

### MikroTik REST Endpoints

- `GET /rest/ip/hotspot/user` — list hotspot users
- `PUT /rest/ip/hotspot/user` — create user
- `PATCH /rest/ip/hotspot/user/{id}` — update (enable/disable)
- `DELETE /rest/ip/hotspot/user/{id}` — delete
- `GET /rest/ip/hotspot/active` — active hotspot sessions
- `GET /rest/ip/hotspot/host` — connected hosts

### Backend

Add methods to `MikroTikClient`:
- `get_hotspot_users()`, `create_hotspot_user()`, `enable/disable_hotspot_user()`, `delete_hotspot_user()`
- `get_hotspot_sessions()`

API routes:
- `GET /api/v1/network/hotspot/users` — list hotspot users on a router
- `POST /api/v1/network/hotspot/users` — create hotspot user
- `GET /api/v1/network/hotspot/sessions` — active hotspot sessions

### Frontend: Hotspot Page (`/hotspot`)

New sidebar item under Active Users:
- Table: username, password, profile, time-limit, status, actions
- "Add User" button → quick create for walk-in customers
- Active sessions tab
- Ties into voucher system (voucher can generate hotspot user instead of PPPoE)

---

## Feature 11: Data Cap / Fair Use Policy (FUP)

### Approach

Track per-customer data usage. When usage exceeds a cap, auto-throttle to reduced speed.

### Database: `data_caps` fields on Plan model

Add to Plan:
- `data_cap_gb: Integer, nullable` — monthly data cap in GB (null = unlimited)
- `fup_download_mbps: Integer, nullable` — throttled speed after cap hit
- `fup_upload_mbps: Integer, nullable` — throttled speed after cap hit

### MikroTik Accounting

MikroTik PPPoE tracks per-session bytes. We can:
1. Poll `GET /rest/ppp/active` and sum bytes for each user
2. Or use MikroTik's accounting feature (`/ip/accounting`)

Celery task runs hourly: fetch active session traffic → update `bandwidth_usage` table → check cap → auto-throttle by switching profile.

### Backend

- `GET /api/v1/customers/{id}/usage` — current month usage
- Celery task: `check_data_caps` — runs hourly, throttles customers over cap
- Auto-restore speed at month start

### Frontend

- Customer detail page: usage bar showing GB used / cap
- Plan form: data cap field, FUP speed fields
- Dashboard: top bandwidth consumers widget

---

## Feature 12: Ticket/Support System

### Database: `tickets` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| customer_id | UUID (FK → customers) | |
| subject | String(200) | |
| status | Enum | open, in_progress, resolved, closed |
| priority | Enum | low, medium, high, urgent |
| assigned_to | UUID (FK → users), nullable | staff member |
| created_at | DateTime | |
| resolved_at | DateTime, nullable | |

### `ticket_messages` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| ticket_id | UUID (FK → tickets) | |
| sender_type | Enum | staff, customer |
| sender_id | UUID | user or customer ID |
| message | Text | |
| created_at | DateTime | |

### Backend

- `POST /api/v1/tickets/` — create ticket
- `GET /api/v1/tickets/` — list with status/priority/assigned filter
- `GET /api/v1/tickets/{id}` — ticket with messages
- `PUT /api/v1/tickets/{id}` — update status/priority/assigned
- `POST /api/v1/tickets/{id}/messages` — add message
- Portal: `POST /api/v1/portal/tickets` — customer creates ticket
- Portal: `GET /api/v1/portal/tickets` — customer views their tickets

### Frontend

**Admin: Tickets Page** (`/tickets`):
- Table: ID, customer name, subject, status tag, priority tag, assigned to, created date
- Click row → ticket detail with message thread (chat-like UI)
- Reply input at bottom
- Status/priority/assignment dropdowns in header

**Customer Portal: Support section**:
- "Submit Ticket" button
- List of their tickets with status
- Click → view messages + reply

---

## Feature 13: SMS Notifications

### Approach: Pluggable SMS Provider

Support popular PH SMS APIs: Semaphore, Globe Labs, or generic HTTP.

### Database: SMS Settings in `app_settings`

Keys: `sms_provider` (semaphore/globe/custom), `sms_api_key`, `sms_sender_name`

### Backend

- `POST /api/v1/settings/sms` — configure SMS provider
- `POST /api/v1/settings/sms/test` — send test SMS
- Notification service: when creating a notification with type=sms, send via configured provider
- Auto-send SMS on: invoice due reminder, overdue notice, service disconnection, payment confirmation

### Celery Task

Existing `process_pending_notifications` task already handles notifications. Add SMS sending alongside email:
```python
if notification.type == NotificationType.sms:
    await send_sms(notification.customer.phone, notification.message)
```

### Frontend

Settings page: SMS tab — provider dropdown, API key, sender name, test button.

---

## Feature 14: Plan Upgrade/Downgrade with Instant Speed Change

### Backend

`POST /api/v1/customers/{id}/change-plan`:
- Body: `{"plan_id": "new-plan-uuid"}`
- Updates customer's plan_id
- Creates prorated invoice (credit remaining days of old plan, charge new plan)
- Immediately updates MikroTik: ensure new profile, update secret's profile
- Subscriber gets new speed on next PPPoE reconnect (or immediately if we disconnect/reconnect them)

### Frontend

Customer detail page: "Change Plan" button → modal with plan selector → shows proration calculation → confirm.

---

## Feature 15: IP Address Management (IPAM)

### Database: `ip_pools` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| name | String(100) | e.g. "Pool-Brgy1" |
| router_id | UUID (FK → routers) | |
| range_start | String(15) | e.g. "192.168.50.2" |
| range_end | String(15) | e.g. "192.168.50.254" |
| subnet | String(18) | e.g. "192.168.50.0/24" |
| created_at | DateTime | |

### Backend

- `GET /api/v1/ipam/pools` — list pools with usage stats
- `POST /api/v1/ipam/pools` — create pool
- `GET /api/v1/ipam/pools/{id}/usage` — which IPs are assigned/free
- Sync with MikroTik IP pools on router

### Frontend: IPAM Page (`/ipam`)

Visual IP grid showing used (green) / free (gray) / reserved (yellow) addresses per pool.

---

## Feature 16: Customer Map View

### Approach

Use customer address + area to plot on a map. Leaflet.js (free, no API key needed).

### Frontend: Map Page (`/map`)

- Leaflet map centered on operator's area
- Pins for each customer (color by status: green=active, yellow=suspended, red=disconnected)
- Click pin → customer quick info popup
- Area polygons overlay (optional)
- Router location pins with different icon

### Customer Model Addition

Add `latitude: Float, nullable` and `longitude: Float, nullable` to Customer model. Set manually or via geocoding.

---

## Feature 17: Audit/Activity Logs

### Database: `audit_logs` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id | UUID (FK → users), nullable | who did it |
| action | String(50) | e.g. "customer.create", "payment.record" |
| entity_type | String(50) | e.g. "customer", "invoice" |
| entity_id | UUID, nullable | |
| details | JSON | changed fields, old/new values |
| ip_address | String(45), nullable | |
| created_at | DateTime | |

### Backend

Middleware or decorator that auto-logs: customer CRUD, payment recording, plan changes, router changes, login/logout.

- `GET /api/v1/audit-logs/` — list with entity/user/date filters

### Frontend

System > Audit Logs page — table with filters. Already have a Logs page, enhance it.

---

## Feature 18: Bulk SMS/Email

### Backend

- `POST /api/v1/notifications/bulk` — send message to filtered customer set
- Body: `{"type": "sms|email", "subject": "...", "message": "...", "filters": {"status": "active", "area_id": "..."}}`

### Frontend

New "Send Notification" button on Customers page toolbar. Opens modal:
- Filter: status, area, plan
- Message type: SMS or Email
- Template selector or free text
- Preview count: "Will send to 45 customers"
- Send button

---

## Feature 19: Scheduled Maintenance Mode

### Backend

- `POST /api/v1/maintenance/start` — enable maintenance mode for a router or globally
- `POST /api/v1/maintenance/end` — disable
- During maintenance: suppress disconnect alerts, show banner to customers
- Optional: notify customers before maintenance via SMS/email

### Database

Add to Router model: `maintenance_mode: Boolean, default False`, `maintenance_message: Text, nullable`

### Frontend

- Router detail: "Enable Maintenance" toggle
- Customer portal: shows maintenance banner when their router is in maintenance
- Dashboard: maintenance badge on router cards

---

## What Stays the Same

- Core billing engine logic (enhanced but not replaced)
- Database (PostgreSQL + Redis)
- Docker Compose architecture
- Auth system (enhanced with audit logging)

## Complete File Summary

### New Backend Files
| File | Purpose |
|------|---------|
| `backend/app/models/router.py` | Already exists (Router, Area) |
| `backend/app/models/expense.py` | Expense model |
| `backend/app/models/app_setting.py` | AppSetting key-value model |
| `backend/app/models/voucher.py` | Voucher model |
| `backend/app/models/payment_gateway.py` | Payment gateway config model |
| `backend/app/models/ticket.py` | Ticket + TicketMessage models |
| `backend/app/models/ip_pool.py` | IP pool model |
| `backend/app/models/audit_log.py` | Audit log model |
| `backend/app/schemas/expense.py` | Expense schemas |
| `backend/app/schemas/voucher.py` | Voucher schemas |
| `backend/app/schemas/ticket.py` | Ticket schemas |
| `backend/app/api/admin/expenses.py` | Expense CRUD API |
| `backend/app/api/admin/settings.py` | Settings API (SMTP, SMS, payment gateways) |
| `backend/app/api/admin/vouchers.py` | Voucher generate/redeem API |
| `backend/app/api/admin/tickets.py` | Ticket CRUD + messages API |
| `backend/app/api/admin/ipam.py` | IP pool management API |
| `backend/app/api/admin/audit.py` | Audit log query API |
| `backend/app/api/webhooks.py` | GCash/Maya webhook handlers |
| `backend/app/services/sms.py` | SMS provider abstraction |
| `backend/app/services/payment_gateway.py` | GCash/Maya payment intent creation |
| `backend/alembic/versions/005_feature_pack.py` | All new tables migration |

### New Frontend Files
| File | Purpose |
|------|---------|
| `frontend/src/api/routers.ts` | Router + Area API |
| `frontend/src/api/vouchers.ts` | Voucher API |
| `frontend/src/api/tickets.ts` | Ticket API |
| `frontend/src/api/expenses.ts` | Expense API |
| `frontend/src/pages/Routers.tsx` | Router management |
| `frontend/src/pages/Areas.tsx` | Area management |
| `frontend/src/pages/Vouchers.tsx` | Voucher management |
| `frontend/src/pages/Expenses.tsx` | Expense tracking |
| `frontend/src/pages/Tickets.tsx` | Ticket management |
| `frontend/src/pages/TicketDetail.tsx` | Ticket conversation |
| `frontend/src/pages/Hotspot.tsx` | Hotspot user management |
| `frontend/src/pages/IPAM.tsx` | IP address management |
| `frontend/src/pages/Map.tsx` | Customer map view |
| `frontend/src/pages/Settings.tsx` | SMTP, SMS, payment gateway config |
| `frontend/src/pages/AuditLogs.tsx` | Audit log viewer |
| `frontend/src/pages/portal/PortalTickets.tsx` | Customer portal tickets |
| `frontend/src/pages/portal/PortalTicketDetail.tsx` | Portal ticket conversation |

### Modified Files
| File | Change |
|------|--------|
| `frontend/src/components/Layout/SideMenu.tsx` | All new menu items |
| `frontend/src/pages/Dashboard.tsx` | Multi-router, expenses, net profit, customizable widgets |
| `frontend/src/pages/ActiveUsers.tsx` | Router filter |
| `frontend/src/api/network.ts` | Multi-router types, scan API |
| `frontend/src/pages/billing/Invoices.tsx` | Print button |
| `frontend/src/pages/portal/PortalInvoices.tsx` | Print + pay online button |
| `frontend/src/pages/portal/PortalDashboard.tsx` | Redeem voucher, submit ticket |
| `backend/app/api/admin/network.py` | Scan endpoint, multi-router dashboard |
| `backend/app/api/admin/customers.py` | Change plan endpoint |
| `backend/app/models/__init__.py` | Register all new models |
| `backend/app/models/plan.py` | Data cap / FUP fields |
| `backend/app/models/customer.py` | lat/lng fields |
| `backend/app/models/payment.py` | Add gcash/maya to PaymentMethod |
| `backend/app/main.py` | Register all new routers |
| `backend/app/services/notification.py` | Read SMTP from DB, add SMS |
| `backend/app/services/mikrotik.py` | Hotspot methods |
| `backend/app/celery_app.py` | Add data cap check task |
| Route definitions | All new page routes |

- Billing engine logic
- Customer portal (all pages)
- Celery tasks
- Auth system
- All existing API endpoints

## File Summary

### New Files
| File | Purpose |
|------|---------|
| `frontend/src/api/routers.ts` | Router + Area API client |
| `frontend/src/pages/Routers.tsx` | Router management page |
| `frontend/src/pages/Areas.tsx` | Area management page |
| `frontend/src/pages/Expenses.tsx` | Expense tracking page |
| `frontend/src/pages/Settings.tsx` | SMTP settings page |
| `backend/app/models/expense.py` | Expense model |
| `backend/app/models/app_setting.py` | AppSetting model |
| `backend/app/schemas/expense.py` | Expense schemas |
| `backend/app/api/admin/expenses.py` | Expense CRUD API |
| `backend/app/api/admin/settings.py` | Settings API |
| `backend/alembic/versions/005_expenses_settings.py` | Migration |

### Modified Files
| File | Change |
|------|--------|
| `frontend/src/components/Layout/SideMenu.tsx` | Add Routers, Areas, Expenses, Settings |
| `frontend/src/pages/Dashboard.tsx` | Multi-router cards, expense stat, net profit, customizable widgets |
| `frontend/src/pages/ActiveUsers.tsx` | Router filter dropdown |
| `frontend/src/api/network.ts` | Multi-router dashboard types |
| `frontend/src/pages/billing/Invoices.tsx` | Print button |
| `frontend/src/pages/portal/PortalInvoices.tsx` | Print button |
| `backend/app/api/admin/network.py` | Scan endpoint, multi-router dashboard |
| `backend/app/models/__init__.py` | Register new models |
| `backend/app/main.py` | Register new routers |
| `backend/app/services/notification.py` | Read SMTP from DB |
| Route definitions file | Add new page routes |
