# NetLedger Feature Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. 19 features in 6 phases.

**Goal:** Bring NetLedger to production-ready state with all competitor features — vouchers, payments, hotspot, tickets, IPAM, map, audit logs, and more.

**Architecture:** All new models in one Alembic migration. Backend-first (models → schemas → APIs → services), then frontend (API clients → pages → sidebar/routes → dashboard).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, httpx, Celery, React 18, TypeScript, Ant Design 5, Leaflet.js

---

## Phase 1: All New Backend Models + Single Migration

**Create all models and one migration covering everything.**

### Files to Create:

**`backend/app/models/expense.py`**
```python
import enum, uuid
from decimal import Decimal
from datetime import date
from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class ExpenseCategory(str, enum.Enum):
    electricity = "electricity"
    internet = "internet"
    salary = "salary"
    equipment = "equipment"
    maintenance = "maintenance"
    rent = "rent"
    other = "other"

class Expense(BaseModel):
    __tablename__ = "expenses"
    category: Mapped[ExpenseCategory] = mapped_column(Enum(ExpenseCategory), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
```

**`backend/app/models/app_setting.py`**
```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class AppSetting(BaseModel):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
```

**`backend/app/models/voucher.py`**
```python
import enum, uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class VoucherStatus(str, enum.Enum):
    unused = "unused"
    active = "active"
    expired = "expired"
    revoked = "revoked"

class Voucher(BaseModel):
    __tablename__ = "vouchers"
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VoucherStatus] = mapped_column(Enum(VoucherStatus), default=VoucherStatus.unused, nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plan = relationship("Plan", lazy="selectin")
    customer = relationship("Customer", lazy="selectin")
```

**`backend/app/models/ticket.py`**
```python
import enum, uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class TicketStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"

class TicketPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"

class Ticket(BaseModel):
    __tablename__ = "tickets"
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.open, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(Enum(TicketPriority), default=TicketPriority.medium, nullable=False)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer = relationship("Customer", lazy="selectin")
    messages = relationship("TicketMessage", back_populates="ticket", lazy="selectin", order_by="TicketMessage.created_at")

class TicketMessage(BaseModel):
    __tablename__ = "ticket_messages"
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "staff" or "customer"
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ticket = relationship("Ticket", back_populates="messages")
```

**`backend/app/models/ip_pool.py`**
```python
import uuid
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class IPPool(BaseModel):
    __tablename__ = "ip_pools"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    router_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("routers.id"), nullable=False)
    range_start: Mapped[str] = mapped_column(String(15), nullable=False)
    range_end: Mapped[str] = mapped_column(String(15), nullable=False)
    subnet: Mapped[str] = mapped_column(String(18), nullable=False)
    router = relationship("Router", lazy="selectin")
```

**`backend/app/models/audit_log.py`**
```python
import uuid
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
```

### Modify: `backend/app/models/plan.py`
Add data cap / FUP fields:
```python
    data_cap_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fup_download_mbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fup_upload_mbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

### Modify: `backend/app/models/customer.py`
Add lat/lng:
```python
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
```

### Modify: `backend/app/models/payment.py`
Add gcash/maya to PaymentMethod enum:
```python
class PaymentMethod(str, enum.Enum):
    cash = "cash"
    bank = "bank"
    online = "online"
    gcash = "gcash"
    maya = "maya"
```

### Modify: `backend/app/models/router.py`
Add maintenance fields to Router:
```python
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    maintenance_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Modify: `backend/app/models/__init__.py`
Register all new models.

### Create: `backend/alembic/versions/005_feature_pack.py`
Single migration creating all new tables and adding new columns to existing tables.

**Commit:** `git commit -m "feat: all new models + migration for 19-feature pack"`

---

## Phase 2: All Backend Schemas

Create Pydantic schemas for all new models.

### Files to Create:
- `backend/app/schemas/expense.py` — ExpenseCreate, ExpenseUpdate, ExpenseResponse, ExpenseSummary
- `backend/app/schemas/voucher.py` — VoucherGenerate, VoucherRedeem, VoucherResponse
- `backend/app/schemas/ticket.py` — TicketCreate, TicketUpdate, TicketResponse, TicketMessageCreate, TicketMessageResponse

### Files to Modify:
- `backend/app/schemas/plan.py` — add data_cap_gb, fup_download_mbps, fup_upload_mbps
- `backend/app/schemas/customer.py` — add latitude, longitude
- `backend/app/schemas/router.py` — add maintenance_mode, maintenance_message to RouterResponse/RouterUpdate

**Commit:** `git commit -m "feat: schemas for expenses, vouchers, tickets, plan FUP, customer geo"`

---

## Phase 3: All Backend API Routes + Services

### Files to Create:
- `backend/app/api/admin/expenses.py` — CRUD + summary
- `backend/app/api/admin/settings.py` — SMTP config, SMS config, payment gateways
- `backend/app/api/admin/vouchers.py` — generate, list, redeem, revoke
- `backend/app/api/admin/tickets.py` — CRUD + messages
- `backend/app/api/admin/ipam.py` — IP pool CRUD + usage
- `backend/app/api/admin/audit.py` — log query
- `backend/app/api/webhooks.py` — GCash/Maya webhook handlers
- `backend/app/services/sms.py` — SMS provider abstraction (Semaphore)
- `backend/app/services/payment_gateway.py` — GCash/Maya payment intent

### Files to Modify:
- `backend/app/api/admin/network.py` — scan endpoint, multi-router dashboard, hotspot endpoints
- `backend/app/api/admin/customers.py` — change-plan endpoint
- `backend/app/api/portal.py` — voucher redeem, tickets, pay online
- `backend/app/services/mikrotik.py` — hotspot methods
- `backend/app/services/notification.py` — read SMTP from DB, add SMS sending
- `backend/app/celery_app.py` — add data cap check task
- `backend/app/main.py` — register all new routers

**Commit per group:** expenses, settings, vouchers, tickets, IPAM, audit, network scan, hotspot, payments, SMS, plan change

---

## Phase 4: All Frontend API Clients

### Files to Create:
- `frontend/src/api/routers.ts` — Router + Area API (already defined in plan)
- `frontend/src/api/vouchers.ts` — Voucher API
- `frontend/src/api/tickets.ts` — Ticket API
- `frontend/src/api/expenses.ts` — Expense API
- `frontend/src/api/settings.ts` — Settings API
- `frontend/src/api/ipam.ts` — IPAM API
- `frontend/src/api/audit.ts` — Audit log API

### Files to Modify:
- `frontend/src/api/network.ts` — multi-router dashboard types, scan API, hotspot API

**Commit:** `git commit -m "feat: all frontend API clients for feature pack"`

---

## Phase 5: All Frontend Pages

### Files to Create:
- `frontend/src/pages/Routers.tsx` — Router management with scan
- `frontend/src/pages/Areas.tsx` — Area management
- `frontend/src/pages/Vouchers.tsx` — Voucher generate/list/redeem
- `frontend/src/pages/Expenses.tsx` — Expense tracking
- `frontend/src/pages/Tickets.tsx` — Ticket list
- `frontend/src/pages/TicketDetail.tsx` — Ticket conversation
- `frontend/src/pages/Hotspot.tsx` — Hotspot users + sessions
- `frontend/src/pages/IPAM.tsx` — IP pool management
- `frontend/src/pages/Map.tsx` — Customer map (Leaflet)
- `frontend/src/pages/Settings.tsx` — SMTP, SMS, payment gateway config
- `frontend/src/pages/AuditLogs.tsx` — Audit log viewer
- `frontend/src/pages/portal/PortalTickets.tsx` — Customer tickets
- `frontend/src/pages/portal/PortalTicketDetail.tsx` — Customer ticket conversation

**Commit per batch:** 3-4 pages per commit

---

## Phase 6: Wire Everything Together

### Files to Modify:
- `frontend/src/components/Layout/SideMenu.tsx` — all new menu items
- `frontend/src/pages/Dashboard.tsx` — multi-router cards, expenses, net profit, customizable widgets
- `frontend/src/pages/ActiveUsers.tsx` — router filter
- `frontend/src/pages/billing/Invoices.tsx` — print button
- `frontend/src/pages/portal/PortalInvoices.tsx` — print + pay online
- `frontend/src/pages/portal/PortalDashboard.tsx` — redeem voucher, submit ticket
- Customer create form — password generator + area/router dropdowns
- Route definitions — all new page routes

**Commit:** `git commit -m "feat: wire all features — sidebar, routes, dashboard, portal"`
