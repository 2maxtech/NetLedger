# Billing Implementation Design

## Overview

Implements the billing engine for 2maXnetBill: automated invoice generation, payment recording with auto-reconnect, and graduated disconnect enforcement via Celery background tasks. This builds on the existing models (Invoice, Payment, Notification, DisconnectLog) and config settings already in place.

## Architecture

### New Docker Services

Celery worker and Beat run as **separate containers** using the same backend image with different entrypoints. Redis (already running) serves as both broker and result backend.

```
docker-compose.yml:
  celery-worker  — celery -A app.celery_app worker
  celery-beat    — celery -A app.celery_app beat -s /tmp/celerybeat-schedule
```

Both containers share the same `DATABASE_URL`, `REDIS_URL`, and `GATEWAY_*` env vars as backend. No new images needed.

> **ISO note:** When packaged as a Debian appliance, these become systemd services instead of Docker containers. The Celery app code stays identical.

### New Files

```
backend/
  app/
    celery_app.py              # Celery app + Beat schedule config
    tasks/
      __init__.py
      billing.py               # Invoice generation, overdue check, disconnect enforcement
    services/
      billing.py               # Core billing logic (used by API + tasks)
    api/admin/
      billing.py               # Billing REST endpoints
frontend/
  src/
    api/billing.ts             # Axios client for billing endpoints
```

## Billing Service (`app/services/billing.py`)

Pure business logic — no HTTP or Celery awareness. Called by both API endpoints and tasks.

### `generate_invoice(db, customer, billing_period: date) -> Invoice`
- Creates invoice for customer's current plan at `plan.monthly_price`
- Sets `due_date` = billing_period.replace(day=BILLING_DUE_DAY)
- Sets `issued_at` = now, `status` = pending
- **Idempotent:** skips if invoice already exists for that customer + billing_period month
- Returns the created or existing invoice

### `generate_monthly_invoices(db) -> dict`
- Queries all customers where `status` in (active, suspended) and `plan_id` is not null
- Calls `generate_invoice()` for each with current month as billing_period
- Returns `{generated: N, skipped: N, errors: [...]}`

### `record_payment(db, invoice_id, amount, method, reference, received_by) -> Payment`
- Creates Payment record linked to invoice
- Calculates total paid = sum of all payments for this invoice
- If total_paid >= invoice.amount: mark invoice as `paid`, set `paid_at`
- **Auto-reconnect logic:** if customer status is suspended or disconnected AND no remaining overdue invoices:
  1. Call gateway service reconnect
  2. Set customer status = active
  3. Log reconnect in DisconnectLog (reason=non_payment, performed_by=null for auto)
- Returns the payment

### `check_overdue_invoices(db) -> int`
- Queries invoices where `status` = pending AND `due_date` < today
- Sets `status` = overdue for each
- Returns count of newly overdue invoices

### `process_graduated_disconnect(db, gateway_service) -> dict`
- Queries all overdue invoices with related customers
- For each, calculates `days_overdue = (today - due_date).days`
- Applies actions based on config thresholds:

| Condition | Action | Customer Status |
|-----------|--------|----------------|
| days_overdue >= BILLING_THROTTLE_DAYS_AFTER_DUE (3) AND customer.status == active | Throttle via Gateway Agent CoA | suspended |
| days_overdue >= BILLING_DISCONNECT_DAYS_AFTER_DUE (5) AND customer.status == suspended | Disconnect via Gateway Agent | disconnected |
| days_overdue >= BILLING_TERMINATE_DAYS_AFTER_DUE (35) | Flag for manual termination review | disconnected (flagged) |

- Each action:
  - Calls Gateway Agent (throttle or disconnect)
  - Updates customer.status
  - Creates DisconnectLog entry (performed_by=null for automated)
  - Creates Notification record (SMS + email)
- **Idempotent:** skips customers already at the correct enforcement level
- Returns `{throttled: N, disconnected: N, flagged: N, errors: [...]}`

### `send_billing_reminders(db) -> int`
- Queries pending invoices where `due_date - today == BILLING_REMINDER_DAYS_BEFORE_DUE`
- Creates Notification record for each (SMS + email)
- Returns count of reminders queued

### `get_revenue_summary(db, start_date, end_date) -> dict`
- Aggregates: total_billed, total_collected, total_outstanding, collection_rate
- Grouped by month if range > 1 month

## Celery Configuration (`app/celery_app.py`)

```python
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery = Celery("netbill", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery.conf.beat_schedule = {
    "generate-monthly-invoices": {
        "task": "app.tasks.billing.generate_monthly_invoices_task",
        "schedule": crontab(day_of_month=str(settings.BILLING_GENERATE_DAY), hour="2", minute="0"),
    },
    "check-overdue-invoices": {
        "task": "app.tasks.billing.check_overdue_invoices_task",
        "schedule": crontab(hour="6", minute="0"),
    },
    "process-graduated-disconnect": {
        "task": "app.tasks.billing.process_graduated_disconnect_task",
        "schedule": crontab(hour="7", minute="0"),
    },
    "send-billing-reminders": {
        "task": "app.tasks.billing.send_billing_reminders_task",
        "schedule": crontab(hour="9", minute="0"),
    },
}

celery.conf.timezone = "Asia/Manila"
```

## Celery Tasks (`app/tasks/billing.py`)

Thin wrappers that create a DB session, call the billing service, and log results.

| Task | Schedule | Service Method |
|------|----------|---------------|
| `generate_monthly_invoices_task` | 1st of month, 2:00 AM | `billing.generate_monthly_invoices()` |
| `check_overdue_invoices_task` | Daily, 6:00 AM | `billing.check_overdue_invoices()` |
| `process_graduated_disconnect_task` | Daily, 7:00 AM | `billing.process_graduated_disconnect()` |
| `send_billing_reminders_task` | Daily, 9:00 AM | `billing.send_billing_reminders()` |

### DB Session in Tasks

Tasks use synchronous SQLAlchemy sessions (not async) since Celery workers run in a sync context:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", "+psycopg2"))
```

This requires adding `psycopg2-binary` to requirements.txt.

## Billing API Endpoints (`app/api/admin/billing.py`)

All endpoints require JWT auth. Roles: admin + billing have full access, technician has read-only.

### Invoices

| Method | Path | Description | Query Params |
|--------|------|-------------|-------------|
| GET | `/billing/invoices` | List invoices | `customer_id`, `status`, `from_date`, `to_date`, `page`, `size` |
| GET | `/billing/invoices/{id}` | Invoice detail with payments | - |
| POST | `/billing/invoices/generate` | Generate invoices | Body: `{customer_id?: uuid}` (null = all active) |
| PUT | `/billing/invoices/{id}` | Update invoice (void/adjust) | Body: `{status?: str, amount?: decimal}` |

### Payments

| Method | Path | Description | Query Params |
|--------|------|-------------|-------------|
| GET | `/billing/payments` | List payments | `customer_id`, `from_date`, `to_date`, `page`, `size` |
| POST | `/billing/payments` | Record payment | Body: `{invoice_id, amount, method, reference_number?}` |

### Reports

| Method | Path | Description | Query Params |
|--------|------|-------------|-------------|
| GET | `/billing/reports/summary` | Revenue summary | `from_date`, `to_date` |

## Frontend Changes

### `src/api/billing.ts`

Axios client module with functions:
- `getInvoices(params)`, `getInvoice(id)`, `generateInvoices(customerId?)`, `updateInvoice(id, data)`
- `getPayments(params)`, `recordPayment(data)`
- `getRevenueSummary(params)`

### `src/pages/billing/Invoices.tsx` (update existing shell)

- Table with columns: customer, amount, due_date, status (StatusTag), issued_at, actions
- Filters: status dropdown, customer search, date range picker
- "Generate Invoices" button (POST /billing/invoices/generate) — generates for all active customers
- Row action: "Void" for admin/billing role
- Uses React Query with auto-refresh

### `src/pages/billing/Payments.tsx` (update existing shell)

- Table with columns: customer, invoice, amount, method, reference, received_by, received_at
- "Record Payment" button opens modal:
  - Invoice selector (searchable dropdown, shows customer + amount + due date)
  - Amount input (pre-filled with remaining balance)
  - Method selector (cash/bank/online)
  - Reference number (optional)
- Filters: customer search, date range, method

## Docker Compose Changes

```yaml
  celery-worker:
    build:
      context: ./backend
    command: celery -A app.celery_app worker --loglevel=info --concurrency=2
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis
    extra_hosts:
      - "gateway:192.168.40.41"
    environment:
      DATABASE_URL: postgresql+asyncpg://netbill:netbill@db:5432/netbill
      REDIS_URL: redis://redis:6379/0

  celery-beat:
    build:
      context: ./backend
    command: celery -A app.celery_app beat --loglevel=info -s /tmp/celerybeat-schedule
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis
    environment:
      DATABASE_URL: postgresql+asyncpg://netbill:netbill@db:5432/netbill
      REDIS_URL: redis://redis:6379/0
```

## Dependencies to Add

- `psycopg2-binary==2.9.10` — Sync PostgreSQL driver for Celery tasks

## Testing Strategy

- Unit tests for billing service functions (generate_invoice, record_payment, check_overdue, process_graduated_disconnect)
- Test idempotency: calling generate_invoice twice for same period creates only one invoice
- Test auto-reconnect: payment on last overdue invoice triggers reconnect
- Test graduated disconnect: correct thresholds trigger correct actions
- Mock Gateway Agent calls in tests
