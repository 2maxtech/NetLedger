# 2maXnetBill — Phase 1 Design Specification

## Overview

2maXnetBill is an all-in-one ISP management platform that combines PPPoE server management (via accel-ppp), full customer billing, and network infrastructure control into a single web-based application. The long-term vision is to package this as an installable OS appliance — a custom Debian-based distribution that turns any server into a complete ISP management system.

Phase 1 delivers the core: **PPPoE management + billing + graduated disconnect + customer portal**.

## Architecture

### Deployment: Two Containers on Proxmox

```
┌──────────────────────────────────────────────────────────┐
│                  Proxmox Host                             │
│                                                           │
│  ┌─────────────────────────────────┐  ┌───────────────┐  │
│  │  LXC/VM: 2maXnetBill App       │  │ LXC/VM: ISP   │  │
│  │                                 │  │ Gateway        │  │
│  │  ┌──────────┐ ┌──────────────┐ │  │               │  │
│  │  │  React   │ │   FastAPI    │ │  │ - accel-ppp   │  │
│  │  │ Frontend │►│   Backend    │─┼──┤ - FreeRADIUS  │  │
│  │  │          │ │              │ │  │ - nftables    │  │
│  │  │ - Admin  │ │ - REST API   │ │  │ - NAT         │  │
│  │  │ - Portal │ │ - Auth (JWT) │ │  │               │  │
│  │  └──────────┘ └──────┬───────┘ │  │ eth0: WAN     │  │
│  │                      │         │  │ eth1: LAN     │  │
│  │  ┌──────────┐ ┌──────┴───────┐ │  └───────────────┘  │
│  │  │  Redis   │ │  PostgreSQL  │ │                      │
│  │  └──────────┘ └──────────────┘ │                      │
│  │  ┌──────────────────────────┐  │                      │
│  │  │  Celery Workers          │  │                      │
│  │  │  - Invoice generation    │  │                      │
│  │  │  - Reminders (SMS/email) │  │                      │
│  │  │  - Disconnect/reconnect  │  │                      │
│  │  └──────────────────────────┘  │                      │
│  └─────────────────────────────────┘                     │
└──────────────────────────────────────────────────────────┘
```

- **App Server (LXC/VM):** Runs the web application, database, Redis, and Celery workers. Accessible by staff and customers via browser.
- **ISP Gateway (VM):** Runs accel-ppp, FreeRADIUS, and the Gateway Agent. Needs direct access to WAN (leased line) and LAN (customer-facing) interfaces.
- Communication between app and gateway is over Proxmox internal network via HTTPS with mutual TLS.

### Network Topology

```
[Internet / Leased Line]
        |
        | WAN (e.g., eth0)
        |
  ┌─────────────────────────┐
  │   ISP Gateway VM         │
  │                          │
  │   eth0 = WAN (uplink)    │
  │   eth1 = LAN (customers) │
  │                          │
  │   accel-ppp listens on   │
  │   eth1 for PPPoE         │
  │                          │
  │   Linux handles:         │
  │   - NAT (WAN <-> LAN)   │
  │   - Routing              │
  │   - Firewall (nftables)  │
  └─────────┬────────────────┘
            |
            | eth1 (LAN)
            |
     ┌──────┴──────┐
     │   Switch     │ (managed switch for VLANs)
     └──┬───┬───┬──┘
        |   |   |
       C1  C2  C3  ... (Customer routers — PPPoE clients)
```

### PPPoE Authentication Flow

1. Customer router sends PPPoE discovery on the LAN.
2. accel-ppp responds and establishes PPPoE session.
3. Customer router sends username + password.
4. accel-ppp forwards to FreeRADIUS.
5. FreeRADIUS queries the app's PostgreSQL database directly via its `rlm_sql` module for credentials and plan info.
6. RADIUS responds: allow/deny, assigned IP from pool, bandwidth attributes (download/upload speed).
7. accel-ppp establishes session, applies traffic shaping via Linux tc.
8. Customer is online.

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React 18 + TypeScript | Admin dashboard + customer portal |
| UI Library | Ant Design | Components, tables, forms, charts |
| Charts | Apache ECharts (via echarts-for-react) | Live traffic, usage graphs |
| Backend | Python 3.12 + FastAPI | REST API + WebSocket |
| ORM | SQLAlchemy 2.0 + Alembic | Database models + migrations |
| Database | PostgreSQL 16 | Primary data store |
| Cache/Queue | Redis 7 | Celery broker + session cache + WebSocket pub/sub |
| Task Queue | Celery | Background jobs (billing, notifications, sync) |
| PPPoE Server | accel-ppp | Customer PPPoE sessions |
| RADIUS | FreeRADIUS 3 | PPPoE auth + accounting |
| Firewall | nftables | Firewall rules, NAT |
| Traffic Shaping | Linux tc / HTB | Per-customer bandwidth limits |
| DNS | dnsmasq | DNS forwarder for customers |
| SMS | Twilio or Semaphore (PH) | SMS notifications |
| Email | SMTP (any provider) | Email notifications |
| PDF | WeasyPrint | Invoice PDF generation |
| Gateway Agent | Python + FastAPI (lightweight) | Runs on ISP gateway, executes network commands |
| Containerization | Docker + Docker Compose | Development + deployment |

## Project Structure

```
2maXnetBill/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin/          # Admin endpoints
│   │   │   │   ├── customers.py
│   │   │   │   ├── plans.py
│   │   │   │   ├── billing.py
│   │   │   │   ├── pppoe.py
│   │   │   │   ├── network.py
│   │   │   │   ├── system.py
│   │   │   │   └── users.py
│   │   │   ├── portal/         # Customer portal endpoints
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── invoices.py
│   │   │   │   └── usage.py
│   │   │   └── auth.py
│   │   ├── models/             # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── customer.py
│   │   │   ├── plan.py
│   │   │   ├── invoice.py
│   │   │   ├── payment.py
│   │   │   ├── pppoe_session.py
│   │   │   ├── notification.py
│   │   │   ├── disconnect_log.py
│   │   │   ├── session_traffic.py
│   │   │   ├── bandwidth_usage.py
│   │   │   └── customer_activity.py
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic
│   │   │   ├── billing.py
│   │   │   ├── gateway.py      # Communicates with Gateway Agent
│   │   │   ├── notification.py
│   │   │   └── radius.py
│   │   ├── tasks/              # Celery background tasks
│   │   │   ├── billing_tasks.py
│   │   │   ├── notification_tasks.py
│   │   │   └── sync_tasks.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py     # JWT, password hashing
│   │   │   ├── database.py
│   │   │   └── dependencies.py
│   │   ├── websocket/
│   │   │   ├── traffic.py
│   │   │   ├── sessions.py
│   │   │   └── system_stats.py
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── admin/
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── Customers.tsx
│   │   │   │   ├── CustomerDetail.tsx
│   │   │   │   ├── Plans.tsx
│   │   │   │   ├── Invoices.tsx
│   │   │   │   ├── Payments.tsx
│   │   │   │   ├── PPPoESessions.tsx
│   │   │   │   ├── SystemStatus.tsx
│   │   │   │   └── Users.tsx
│   │   │   └── layouts/
│   │   ├── portal/
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── Invoices.tsx
│   │   │   │   └── Usage.tsx
│   │   │   └── layouts/
│   │   ├── components/         # Shared components
│   │   │   ├── TrafficGraph.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   └── InvoicePDF.tsx
│   │   ├── api/                # API client (axios)
│   │   ├── hooks/              # Custom React hooks
│   │   ├── stores/             # State management
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── Dockerfile
├── gateway-agent/
│   ├── agent/
│   │   ├── api/
│   │   │   ├── pppoe.py
│   │   │   ├── firewall.py
│   │   │   ├── network.py
│   │   │   ├── shaper.py
│   │   │   ├── dns.py
│   │   │   └── system.py
│   │   ├── services/
│   │   │   ├── accel_ppp.py
│   │   │   ├── freeradius.py
│   │   │   ├── nftables.py
│   │   │   ├── traffic_control.py
│   │   │   └── dnsmasq.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   └── main.py
│   ├── requirements.txt
│   └── install.sh              # Gateway setup script
├── docker-compose.yml
├── docker-compose.dev.yml
└── docs/
```

## Data Models

### User (Staff)

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| username | String | Unique |
| email | String | Unique |
| password_hash | String | bcrypt |
| role | Enum | admin, billing, technician |
| is_active | Boolean | Soft disable |
| created_at | DateTime | |

### Customer

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| full_name | String | |
| email | String | For notifications + portal login |
| phone | String | For SMS notifications |
| address | String | Service address |
| pppoe_username | String | Unique — used for PPPoE auth |
| pppoe_password | String | Stored encrypted |
| status | Enum | active, suspended, disconnected, terminated |
| plan_id | FK → Plan | Current service plan |
| created_at | DateTime | |

### Plan

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | String | e.g., "Basic 10Mbps", "Premium 50Mbps" |
| download_mbps | Integer | Download speed limit |
| upload_mbps | Integer | Upload speed limit |
| monthly_price | Decimal | Monthly billing amount |
| description | String | |
| is_active | Boolean | Can new customers subscribe |
| created_at | DateTime | |

### Invoice

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| customer_id | FK → Customer | |
| plan_id | FK → Plan | Plan at time of invoice |
| amount | Decimal | Total amount due |
| due_date | Date | Payment deadline |
| status | Enum | pending, paid, overdue, void |
| paid_at | DateTime | Nullable |
| issued_at | DateTime | When invoice was generated |
| created_at | DateTime | |

### Payment

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| invoice_id | FK → Invoice | |
| amount | Decimal | Can be partial |
| method | Enum | cash, bank, online |
| reference_number | String | Nullable — bank ref, receipt # |
| received_by | FK → User | Staff who recorded it (nullable for online) |
| received_at | DateTime | |
| created_at | DateTime | |

### PPPoESession

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| customer_id | FK → Customer | |
| session_id | String | accel-ppp session identifier |
| ip_address | String | Assigned IP |
| mac_address | String | Customer router MAC |
| started_at | DateTime | |
| ended_at | DateTime | Nullable (null = active) |
| bytes_in | BigInteger | Total bytes downloaded |
| bytes_out | BigInteger | Total bytes uploaded |
| disconnect_reason | String | Nullable |

### SessionTraffic

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| session_id | FK → PPPoESession | |
| bytes_in | BigInteger | Cumulative at sample time |
| bytes_out | BigInteger | Cumulative at sample time |
| packets_in | BigInteger | |
| packets_out | BigInteger | |
| sampled_at | DateTime | RADIUS accounting timestamp |

### BandwidthUsage

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| customer_id | FK → Customer | |
| date | Date | One row per customer per day |
| total_bytes_in | BigInteger | Aggregated daily download |
| total_bytes_out | BigInteger | Aggregated daily upload |
| peak_download_mbps | Decimal | Peak speed that day |
| peak_upload_mbps | Decimal | Peak speed that day |
| created_at | DateTime | |

### CustomerActivity

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| customer_id | FK → Customer | |
| event_type | Enum | login, logout, auth_fail, ip_change, plan_change, throttled, disconnected |
| details | JSON | Flexible extra data |
| ip_address | String | |
| created_at | DateTime | |

### Notification

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| customer_id | FK → Customer | |
| type | Enum | sms, email |
| subject | String | |
| message | Text | |
| status | Enum | pending, sent, failed |
| sent_at | DateTime | Nullable |
| created_at | DateTime | |

### DisconnectLog

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| customer_id | FK → Customer | |
| action | Enum | throttle, disconnect, reconnect |
| reason | Enum | non_payment, manual, expired |
| performed_by | FK → User | Nullable (null = system/auto) |
| performed_at | DateTime | |
| created_at | DateTime | |

## Billing & Disconnect Flow

### Invoice Lifecycle

```
Generate (auto, 1st of month)
    → Pending
        → Paid (before due date)
        → Overdue (past due date)
            → Paid (late)
            → Void (manual cancel)
```

### Graduated Disconnect Timeline (all days configurable by admin)

| Day | Action | Notification |
|---|---|---|
| 0 | Invoice generated | Invoice email + SMS |
| 10 | Reminder | "Bill due in 5 days" — SMS + email |
| 15 | Due date — status becomes OVERDUE | "Bill is overdue, pay within 5 days" — SMS + email |
| 18 | Throttle — bandwidth reduced to 1 Mbps | "Service slowed, pay to restore" — SMS + email |
| 20 | Disconnect — PPPoE session killed, RADIUS rejects auth | "Service disconnected" — SMS + email |
| 50 | Termination — staff reviews, account terminated | Manual process |

### Disconnect Mechanism

1. App marks customer status as "suspended" in database.
2. App calls Gateway Agent: `POST /agent/pppoe/disconnect` with customer ID.
3. Gateway Agent instructs FreeRADIUS to send RADIUS Disconnect-Request (CoA) to accel-ppp.
4. accel-ppp terminates the active PPPoE session.
5. FreeRADIUS is updated to reject future auth attempts for this customer.
6. App logs action to DisconnectLog.
7. App sends notification to customer.

### Reconnect Flow

1. Staff records payment (or customer pays online in future).
2. Invoice marked as paid.
3. App checks for remaining overdue invoices.
   - If none: trigger reconnect.
   - If remaining: stay suspended.
4. Reconnect: update customer status to "active", update RADIUS to allow auth.
5. Customer router auto-redials PPPoE, accel-ppp authenticates, session established.
6. Full speed restored via RADIUS bandwidth attributes.
7. Log and notify.

### Throttle Mechanism

1. App sends request to Gateway Agent: `POST /agent/pppoe/throttle`.
2. Gateway Agent sends RADIUS CoA (Change of Authorization) to accel-ppp with reduced bandwidth attributes (e.g., 1 Mbps down / 512 Kbps up).
3. accel-ppp applies new tc rules to the active session.
4. Customer stays online but at reduced speed.
5. On payment: another CoA restores original plan speed.

## API Design

### Admin API (`/api/v1/`)

```
/auth/
  POST   /login                    Staff login → JWT
  POST   /logout
  POST   /refresh                  Refresh JWT token
  GET    /me                       Current user info

/customers/
  GET    /                         List (paginated, filterable)
  POST   /                         Create customer
  GET    /{id}                     Detail
  PUT    /{id}                     Update
  DELETE /{id}                     Soft delete
  GET    /{id}/sessions            PPPoE session history
  GET    /{id}/usage               Bandwidth usage
  GET    /{id}/activity            Activity log
  GET    /{id}/invoices            Customer invoices
  POST   /{id}/disconnect          Manual disconnect
  POST   /{id}/reconnect           Manual reconnect
  POST   /{id}/throttle            Manual throttle

/plans/
  GET    /                         List plans
  POST   /                         Create plan
  GET    /{id}                     Plan detail
  PUT    /{id}                     Update plan
  DELETE /{id}                     Deactivate plan

/billing/
  GET    /invoices                 All invoices (filterable)
  POST   /invoices/generate        Bulk generate monthly invoices
  GET    /invoices/{id}            Invoice detail
  PUT    /invoices/{id}            Update (void, adjust)
  POST   /payments                 Record a payment
  GET    /payments                 Payment history
  GET    /reports                  Revenue reports

/pppoe/
  GET    /sessions                 All active PPPoE sessions
  GET    /sessions/{id}            Session detail + live stats
  DELETE /sessions/{id}            Kill session

/system/
  GET    /status                   CPU, RAM, disk, uptime
  GET    /users                    Staff user management
  POST   /users                    Create staff user
  PUT    /users/{id}               Update staff user
  DELETE /users/{id}               Deactivate staff user

/logs/
  GET    /system                   Syslog
  GET    /auth                     Auth attempts
```

### Customer Portal API (`/api/v1/portal/`)

```
/auth/
  POST   /login                    Customer login → JWT
  GET    /me                       Customer info

/dashboard                         Account overview
/invoices                          My invoices
/invoices/{id}/pdf                 Download invoice PDF
/usage                             My bandwidth usage
/session                           My current session
/activity                          My activity log
```

### WebSocket Endpoints (`/api/v1/ws/`)

```
/live-traffic                      Real-time traffic graphs
/sessions                          PPPoE session updates
/system-stats                      CPU/RAM/disk live
/alerts                            System alerts push
```

### Gateway Agent API (runs on ISP gateway)

```
POST /agent/pppoe/disconnect       Send RADIUS CoA disconnect
POST /agent/pppoe/reconnect        Re-enable in RADIUS
POST /agent/pppoe/throttle         Send CoA with new bandwidth
GET  /agent/pppoe/sessions         Query accel-ppp active sessions

POST /agent/firewall/apply         Apply nftables ruleset
GET  /agent/firewall/states        Active connection table

POST /agent/network/interface      Configure interface
POST /agent/network/route          Add/remove route

POST /agent/dhcp/apply             Regenerate dnsmasq config + reload
POST /agent/dns/apply              Regenerate DNS config + reload

POST /agent/shaper/apply           Apply tc rules
GET  /agent/shaper/stats           Current shaper stats

GET  /agent/system/stats           CPU, RAM, disk, temps
GET  /agent/system/traffic         Interface traffic counters
POST /agent/system/reboot
POST /agent/system/shutdown
```

### App ↔ Gateway Security

- HTTPS with mutual TLS (both sides verify certificates).
- Shared API key as additional auth layer.
- Gateway Agent only accepts connections from the app server IP.
- All commands logged and auditable.
- If Gateway Agent is unreachable, the app queues commands in Celery and retries with exponential backoff. Admin is alerted via dashboard notification.

## Real-Time Data Flow

```
Customer Router ──PPPoE──► accel-ppp
                                │
                    RADIUS accounting (every 30s)
                                │
                                ▼
                          FreeRADIUS
                                │
                    Writes to DB / forwards to Gateway Agent
                                │
                                ▼
                        Gateway Agent
                                │
                    Pushes via WebSocket
                                │
                                ▼
                      App Server (FastAPI)
                                │
                    Pushes via WebSocket
                                │
                                ▼
                      Admin Browser Dashboard
                      (live graphs update)
```

## Admin Dashboard Pages

1. **Dashboard (Home)** — system health (CPU, RAM, disk, WAN bandwidth), online customer count, revenue overview, recent activity feed.
2. **Customers** — table with search/filter, click into detail page with profile, sessions, usage charts, invoices, activity, manual actions.
3. **Plans** — CRUD for service plans with subscriber counts.
4. **Billing > Invoices** — invoice list, filter by status, bulk generate, bulk reminders.
5. **Billing > Payments** — record payments, payment history.
6. **Billing > Reports** — monthly revenue, by plan, collection rate.
7. **PPPoE Sessions** — live active sessions, kick sessions, session history.
8. **System Status** — live system health, interface traffic.
9. **Staff Users** — manage admin/billing/technician accounts.
10. **Logs** — system log, auth log.

## Customer Portal Pages

1. **Overview** — account status (online/offline), current plan, session info, outstanding balance.
2. **Invoices** — invoice history, download PDF.
3. **Usage** — bandwidth charts (daily/weekly/monthly), current session stats.

## Role-Based Access Control

| Feature | Admin | Billing Staff | Technician |
|---|---|---|---|
| Dashboard | Full | Billing metrics only | Network metrics only |
| Customers | Full CRUD | View + billing actions | View + network actions |
| Billing | Full | Full | View only |
| PPPoE Sessions | Full | View only | Full |
| System | Full | No access | No access |
| Staff Users | Full | No access | No access |

## Full Feature Scope (All Phases)

For reference, the complete feature set across all phases:

### Phase 1 (This spec)
- Staff authentication with roles (admin, billing, technician)
- Customer CRUD with PPPoE credentials
- Plan management (speed tiers, pricing)
- Invoice generation (auto-monthly)
- Payment recording
- Graduated disconnect (reminders → throttle → disconnect)
- Notifications (SMS + email)
- Customer self-service portal
- Admin dashboard with system health
- Live traffic monitoring (WebSocket)
- Invoice PDF generation
- Gateway Agent (accel-ppp, FreeRADIUS, basic NAT, traffic shaping, DNS, system stats)

### Phase 2 — Network Management
- Interface configuration (WAN, LAN, VLAN, bridge, bonding)
- Routing (static routes, policy routing, gateway groups)
- NAT management (SNAT, DNAT, port forwarding, 1:1 NAT)
- DHCP server management (config, leases, static mappings)
- DNS management (forwarder, overrides, blocklists)
- IP pool management from UI
- ARP table viewer
- Multi-WAN load balancing and failover

### Phase 3 — Security / UTM
- Suricata IDS/IPS integration
- DNS-based filtering (malware, ads, custom blocklists)
- Web filtering (category-based)
- GeoIP blocking
- Captive portal

### Phase 4 — VPN + Advanced
- WireGuard tunnels
- OpenVPN server/client
- IPsec tunnels
- Captive portal enhancements
- Multi-WAN advanced features
- Backup/restore
- Certificate management (Let's Encrypt)
- DDNS, SNMP, NTP configuration
- Web-based terminal

### Phase 5 — OS Packaging
- Custom Debian 12 base ISO
- First-boot setup wizard
- Auto-start all services
- System update mechanism
- ISO builder for distribution
