# 2maXnetBill — Gateway + accel-ppp Integration Design

## Overview

This spec covers deploying and integrating the ISP Gateway with the existing 2maXnetBill backend. The Gateway runs accel-ppp (PPPoE server), FreeRADIUS (authentication), and a lightweight Gateway Agent (FastAPI) that the main backend calls to manage PPPoE sessions.

A test client LXC is included to validate the full PPPoE flow end-to-end.

## Infrastructure

### Network Topology

```
vmbr1 tag=40 (192.168.40.0/24) — management/app network
  ├── 192.168.40.40  App Server (LXC 108, existing)
  └── 192.168.40.41  ISP Gateway eth0 (management + Gateway Agent API)

"LAN" bridge (isolated, no physical ports) — simulated customer network
  ├── ISP Gateway eth1 (accel-ppp listens for PPPoE, no IP assigned)
  └── Test Client eth0 (PPPoE client, no static IP — gets IP via PPPoE)

PPPoE tunnel pool: 10.0.0.0/24
  ├── 10.0.0.1  ISP Gateway (PPP local address)
  └── 10.0.0.2-254  Customer PPP addresses
```

### LXC Specifications

**ISP Gateway (LXC 111)**
- OS: Debian 12 (bookworm) — accel-ppp has stable packages for bookworm
- RAM: 2048 MB
- Disk: 10 GB
- Cores: 2
- Features: nesting=1, keyctl=1
- Privileged: yes (required for accel-ppp kernel interfaces)
- net0: vmbr1, tag=40, ip=192.168.40.41/24, gw=192.168.40.1
- net1: LAN bridge, no IP (raw L2 for PPPoE)

**Test Client (LXC 112)**
- OS: Debian 12 (bookworm)
- RAM: 512 MB
- Disk: 4 GB
- Cores: 1
- Features: nesting=1
- Privileged: yes (pppd needs /dev/ppp)
- net0: LAN bridge, no IP (PPPoE client)
- net1: vmbr1, tag=40, ip=192.168.40.42/24 (management access via SSH)

### Proxmox Host Preparation

Load kernel modules required by accel-ppp on the Proxmox host:

```
modprobe pppoe
modprobe ppp_generic
modprobe ppp_async
```

Persist via `/etc/modules-load.d/accel-ppp.conf`.

## Software Components

### 1. accel-ppp (PPPoE Server)

Runs on the ISP Gateway, listens on eth1 (LAN bridge) for PPPoE discovery.

**Config highlights (`/etc/accel-ppp.conf`):**
- PPPoE interface: eth1
- Authentication: RADIUS (FreeRADIUS on localhost)
- IP pool: 10.0.0.2-10.0.0.254, local address 10.0.0.1
- DNS: 8.8.8.8, 8.8.4.4 (pushed to clients)
- Session timeout: none (always-on)
- Idle timeout: none
- RADIUS accounting interval: 30 seconds
- Traffic shaping: via RADIUS attributes (rate-limit)
- Logging: syslog + `/var/log/accel-ppp/accel-ppp.log`
- CLI: enabled on localhost:2001 for session management

### 2. FreeRADIUS 3

Runs on the ISP Gateway, authenticates PPPoE users and handles accounting.

**Authentication (authorize + authenticate):**
- Uses `rlm_sql` (PostgreSQL driver) to query the App Server's database directly
- SQL query: SELECT pppoe_username, pppoe_password FROM customers WHERE pppoe_username = '%{User-Name}' AND status = 'active'
- Returns RADIUS attributes: Framed-IP-Address (from pool), bandwidth attributes

**Accounting:**
- Interim-Update every 30 seconds from accel-ppp
- Writes to `pppoe_sessions` and `session_traffic` tables via SQL
- On session start: INSERT into pppoe_sessions
- On interim update: UPDATE bytes_in/bytes_out, INSERT into session_traffic
- On session stop: UPDATE ended_at, disconnect_reason

**CoA (Change of Authorization):**
- FreeRADIUS acts as CoA client to accel-ppp
- Used for disconnect (Disconnect-Request) and throttle (CoA with new bandwidth)
- accel-ppp CoA port: 3799

**SQL connection:**
- Server: 192.168.40.40 (App Server PostgreSQL)
- Port: 5432 (exposed by Docker)
- Database: netbill
- User: netbill / netbill
- Read-only for auth queries, write for accounting

**Bandwidth RADIUS attributes:**
- `WISPr-Bandwidth-Max-Down` (bits per second)
- `WISPr-Bandwidth-Max-Up` (bits per second)
- Derived from customer's plan: download_mbps * 1000000, upload_mbps * 1000000

### 3. Gateway Agent (FastAPI)

Lightweight API running on the ISP Gateway (port 8443). The main backend calls this to manage PPPoE sessions.

**Endpoints:**

```
POST /agent/pppoe/disconnect     — Kill a customer's PPPoE session
  Body: { "customer_id": "uuid", "pppoe_username": "string" }
  Action: Send RADIUS Disconnect-Request to accel-ppp
  
POST /agent/pppoe/reconnect      — Re-enable customer for PPPoE auth
  Body: { "customer_id": "uuid", "pppoe_username": "string" }
  Action: No active action needed — customer status already updated in DB,
          FreeRADIUS will allow next auth attempt
  
POST /agent/pppoe/throttle       — Reduce bandwidth for active session
  Body: { "customer_id": "uuid", "pppoe_username": "string",
          "download_mbps": 1, "upload_kbps": 512 }
  Action: Send RADIUS CoA to accel-ppp with new bandwidth attributes

GET  /agent/pppoe/sessions       — List all active PPPoE sessions
  Action: Query accel-ppp CLI (telnet localhost:2001)
  Returns: [ { "session_id", "username", "ip", "mac", "uptime",
               "bytes_in", "bytes_out", "rate_in", "rate_out" } ]

GET  /agent/system/stats         — System health
  Returns: { "cpu_percent", "memory_percent", "disk_percent", "uptime" }
```

**Security:**
- API key authentication (shared secret in config)
- Listens only on eth0 (192.168.40.41:8443)
- HTTPS with self-signed cert (mTLS can be added later)

**Implementation:**
- Communicates with accel-ppp via:
  - Telnet CLI (port 2001) for session queries
  - `radclient` command for CoA/Disconnect packets
- Minimal dependencies: FastAPI, uvicorn, psutil

### 4. Backend Gateway Service

New module in the existing backend (`backend/app/services/gateway.py`) that calls the Gateway Agent API.

**Functions:**
- `disconnect_customer(customer_id, pppoe_username)` — POST to Gateway Agent
- `reconnect_customer(customer_id, pppoe_username)` — POST to Gateway Agent  
- `throttle_customer(customer_id, pppoe_username, down_mbps, up_kbps)` — POST to Gateway Agent
- `get_active_sessions()` — GET from Gateway Agent
- Retry with exponential backoff if Gateway Agent unreachable
- All calls logged

**New API endpoints in backend:**
```
POST /api/v1/customers/{id}/disconnect   — Manual disconnect
POST /api/v1/customers/{id}/reconnect    — Manual reconnect
POST /api/v1/customers/{id}/throttle     — Manual throttle
GET  /api/v1/pppoe/sessions              — All active sessions
GET  /api/v1/pppoe/sessions/{id}         — Session detail
DELETE /api/v1/pppoe/sessions/{id}       — Kill session
```

## Data Flow

### PPPoE Authentication
```
Customer Router → PPPoE Discovery → accel-ppp (eth1)
                                        │
                                   RADIUS Access-Request
                                        │
                                        ▼
                                   FreeRADIUS
                                        │
                                   SQL query to App DB (192.168.40.40:5432)
                                   SELECT where pppoe_username AND status='active'
                                        │
                                        ▼
                                   Access-Accept + IP + Bandwidth attrs
                                        │
                                        ▼
                                   accel-ppp creates PPP session
                                   applies tc shaping
                                        │
                                        ▼
                                   Customer is online at 10.0.0.x
```

### Disconnect Flow
```
Admin clicks "Disconnect" in UI
        │
        ▼
Backend: POST /api/v1/customers/{id}/disconnect
        │
        ├── Update customer.status = 'suspended' in DB
        ├── POST http://192.168.40.41:8443/agent/pppoe/disconnect
        │       │
        │       ▼
        │   Gateway Agent: radclient → Disconnect-Request → accel-ppp
        │       │
        │       ▼
        │   accel-ppp terminates PPPoE session
        │
        ├── Log to disconnect_logs table
        └── Send notification (future: SMS/email)
        
Next auth attempt: FreeRADIUS checks status='suspended' → Access-Reject
```

### Throttle Flow
```
System or Admin triggers throttle
        │
        ▼
Backend: POST /api/v1/customers/{id}/throttle
        │
        ├── POST http://192.168.40.41:8443/agent/pppoe/throttle
        │       │
        │       ▼
        │   Gateway Agent: radclient → CoA-Request with new bandwidth → accel-ppp
        │       │
        │       ▼
        │   accel-ppp updates tc rules for active session
        │
        └── Log to disconnect_logs (action=throttle)
```

### RADIUS Accounting
```
accel-ppp → Accounting-Request (every 30s) → FreeRADIUS
                                                  │
                                           SQL INSERT/UPDATE
                                                  │
                                                  ▼
                                           pppoe_sessions (bytes_in/out)
                                           session_traffic (per-sample)
```

## FreeRADIUS SQL Schema Mapping

FreeRADIUS `rlm_sql` needs to map to our existing tables. We use custom SQL queries instead of the default FreeRADIUS schema.

**authorize query (check credentials):**
```sql
SELECT pppoe_password AS 'Cleartext-Password'
FROM customers
WHERE pppoe_username = '%{User-Name}'
  AND status NOT IN ('disconnected', 'terminated')
```

**Status-based auth behavior:**
- `active` → Access-Accept, full plan speed
- `suspended` → Access-Accept, throttled speed (1 Mbps / 512 Kbps)
- `disconnected` → Access-Reject
- `terminated` → Access-Reject

This allows the graduated disconnect flow: suspended customers stay online at reduced speed (throttle), while disconnected customers are fully cut off.

**group reply query (return attributes):**
```sql
SELECT 
  'WISPr-Bandwidth-Max-Down' AS attribute,
  CASE 
    WHEN c.status = 'suspended' THEN '1000000'  -- 1 Mbps throttle
    ELSE (p.download_mbps * 1000000)::text
  END AS value,
  ':=' AS op
FROM customers c
JOIN plans p ON c.plan_id = p.id
WHERE c.pppoe_username = '%{User-Name}'

UNION ALL

SELECT 
  'WISPr-Bandwidth-Max-Up',
  CASE 
    WHEN c.status = 'suspended' THEN '512000'  -- 512 Kbps throttle
    ELSE (p.upload_mbps * 1000000)::text
  END,
  ':='
FROM customers c
JOIN plans p ON c.plan_id = p.id
WHERE c.pppoe_username = '%{User-Name}'

UNION ALL

SELECT 'Framed-Pool', 'main', ':='
```

**accounting start query:**
```sql
INSERT INTO pppoe_sessions (id, customer_id, session_id, ip_address, mac_address, started_at, bytes_in, bytes_out, created_at)
SELECT gen_random_uuid(), c.id, '%{Acct-Session-Id}', '%{Framed-IP-Address}', '%{Calling-Station-Id}', NOW(), 0, 0, NOW()
FROM customers c WHERE c.pppoe_username = '%{User-Name}'
```

**accounting interim query:**
```sql
UPDATE pppoe_sessions 
SET bytes_in = '%{Acct-Input-Octets}'::bigint, 
    bytes_out = '%{Acct-Output-Octets}'::bigint
WHERE session_id = '%{Acct-Session-Id}' AND ended_at IS NULL;

INSERT INTO session_traffic (id, session_id, bytes_in, bytes_out, packets_in, packets_out, sampled_at, created_at)
SELECT gen_random_uuid(), ps.id, '%{Acct-Input-Octets}'::bigint, '%{Acct-Output-Octets}'::bigint,
       '%{Acct-Input-Packets}'::bigint, '%{Acct-Output-Packets}'::bigint, NOW(), NOW()
FROM pppoe_sessions ps WHERE ps.session_id = '%{Acct-Session-Id}' AND ps.ended_at IS NULL
```

**accounting stop query:**
```sql
UPDATE pppoe_sessions 
SET bytes_in = '%{Acct-Input-Octets}'::bigint,
    bytes_out = '%{Acct-Output-Octets}'::bigint,
    ended_at = NOW(),
    disconnect_reason = '%{Acct-Terminate-Cause}'
WHERE session_id = '%{Acct-Session-Id}' AND ended_at IS NULL
```

## PostgreSQL Access

FreeRADIUS on the Gateway (192.168.40.41) needs to connect to PostgreSQL on the App Server (192.168.40.40:5432). Currently PostgreSQL is inside Docker.

**Required change:** Update `docker-compose.yml` to bind PostgreSQL to `0.0.0.0:5432` (already done — it's exposed). Add `pg_hba.conf` entry to allow the Gateway IP:

```
host netbill netbill 192.168.40.41/32 md5
```

This is configured via Docker environment variable or a custom pg_hba.conf mount.

## Testing Plan

### End-to-End Test Sequence

1. **PPPoE Connect:** Test client dials PPPoE → accel-ppp → FreeRADIUS → auth against DB → session established, IP assigned from pool
2. **Verify Session:** Gateway Agent `/agent/pppoe/sessions` returns the active session
3. **Bandwidth Check:** Test client runs speed test (iperf3 against gateway) — should match plan speed
4. **Throttle:** Backend calls throttle → CoA → speed drops to 1 Mbps
5. **Disconnect:** Backend calls disconnect → session killed → test client goes offline
6. **Reconnect:** Change customer status back to active → test client redials → back online at full speed
7. **Auth Reject:** Set customer status to 'disconnected' → test client dials → auth rejected

## Implementation Order

1. **Proxmox setup** — Create vmbr2 (if needed for future), create Gateway LXC, create Test Client LXC
2. **Gateway OS setup** — Install accel-ppp, FreeRADIUS, Python, configure kernel modules
3. **FreeRADIUS config** — SQL module pointing to App DB, custom queries, CoA config
4. **accel-ppp config** — PPPoE on eth1, RADIUS auth, IP pool, traffic shaping
5. **Gateway Agent** — FastAPI app with disconnect/reconnect/throttle/sessions endpoints
6. **Backend integration** — Gateway service, new API endpoints, customer action endpoints
7. **PostgreSQL access** — pg_hba.conf for Gateway IP
8. **Test Client setup** — Install pppoe client, configure credentials
9. **End-to-end testing** — Full flow validation
