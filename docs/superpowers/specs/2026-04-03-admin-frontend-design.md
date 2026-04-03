# 2maXnetBill — Admin Dashboard Frontend Design

## Overview

React 18 SPA serving as the admin dashboard for 2maXnetBill. Built with TypeScript, Ant Design, and ECharts. Served as static files from the backend (or nginx) — no Node.js runtime needed on the appliance. All 9 admin pages included.

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Framework | React 18 + TypeScript | UI components + type safety |
| UI Library | Ant Design 5 | Layout, tables, forms, modals, notifications |
| Charts | Apache ECharts (echarts-for-react) | Traffic graphs, usage charts, revenue reports |
| Routing | React Router 6 | SPA navigation |
| State | React Query (TanStack Query) | Server state, caching, auto-refresh |
| HTTP Client | Axios | API calls with interceptors for JWT |
| Build | Vite | Fast dev server + production build |
| Icons | @ant-design/icons | Consistent icon set |

## Theme

| Token | Value | Usage |
|---|---|---|
| Primary color | `#0d9488` (Teal) | Buttons, links, active states, accents |
| Sidebar background | `#0f172a` (Dark Slate) | Sidebar / navigation |
| Sidebar text | `#94a3b8` | Inactive sidebar items |
| Sidebar active | `#0d9488` | Active menu item background |
| Content background | `#f5f5f5` | Page background |
| Card background | `#ffffff` | Cards, tables, content areas |
| Success | `#10b981` | Online, active, paid states |
| Warning | `#f59e0b` | Overdue, suspended states |
| Error | `#ef4444` | Disconnected, failed, terminated states |
| Info | `#0d9488` | Same as primary |

Ant Design 5 theme customization via `ConfigProvider` with `token` prop.

## Layout

**Collapsible sidebar (Ant Design `Layout.Sider`):**
- Default state: collapsed (64px, icon-only)
- Expanded state: 220px with labels
- Toggle via hamburger icon in top header
- Dark Slate (#0f172a) background
- Logo: "2M" when collapsed, "2maXnetBill" when expanded

**Top header bar:**
- Breadcrumb navigation
- Right side: user dropdown (profile, logout)

**Content area:**
- Light gray background (#f5f5f5)
- Content in white cards with border-radius

## Sidebar Navigation Structure

```
Dashboard         (DashboardOutlined)
Customers         (TeamOutlined)
Plans             (AppstoreOutlined)
PPPoE Sessions    (WifiOutlined)
─── Billing ───
  Invoices        (FileTextOutlined)
  Payments        (DollarOutlined)
─── System ───
  Staff Users     (UserOutlined)
  System Status   (DesktopOutlined)
  Logs            (FileSearchOutlined)
```

Group headers ("Billing", "System") shown only when sidebar is expanded.

## Pages

### 1. Login Page (`/login`)

Full-screen centered card. No sidebar.

- Fields: username, password
- "Sign In" button
- Error message on invalid credentials
- On success: store JWT tokens in localStorage, redirect to `/`
- Auto-redirect to `/` if already authenticated

### 2. Dashboard (`/`)

**Stat cards row (4 cards):**
- Online Customers (count, green if > 0)
- Total Customers (count)
- Monthly Revenue (₱ amount)
- Overdue Invoices (count, red if > 0)

**Traffic chart (ECharts):**
- Placeholder for now — will show real-time traffic when WebSocket is implemented
- Area chart showing bandwidth over time

**Recent Activity feed:**
- Last 10 disconnect/reconnect/throttle actions from disconnect_logs
- Table with: time, customer name, action, performed by

**System Health (mini cards):**
- CPU, RAM, Disk usage from Gateway Agent `/agent/system/stats`
- Progress bars with color thresholds (green < 60%, yellow < 80%, red >= 80%)

### 3. Customers (`/customers`)

**List view:**
- Ant Design `Table` with server-side pagination
- Columns: Name, Email, PPPoE Username, Plan, Status, Created
- Status column: colored tag (green=active, yellow=suspended, red=disconnected, gray=terminated)
- Search bar (filters by name, email, pppoe_username)
- Status filter dropdown
- "Add Customer" button → modal form

**Customer Detail (`/customers/:id`):**
- Header: customer name, status tag, plan name
- Action buttons: Disconnect / Reconnect / Throttle (based on current status)
- Tabs:
  - **Overview**: customer info, plan details, PPPoE credentials (password masked)
  - **Sessions**: PPPoE session history table (from pppoe_sessions)
  - **Usage**: bandwidth chart (placeholder — from bandwidth_usage when implemented)
  - **Invoices**: customer's invoices (from future billing API)
  - **Activity**: disconnect/reconnect/throttle log

**Create/Edit Customer Modal:**
- Fields: full_name, email, phone, address, pppoe_username, pppoe_password, plan (dropdown)

### 4. Plans (`/plans`)

- Ant Design `Table`
- Columns: Name, Download (Mbps), Upload (Mbps), Monthly Price (₱), Status, Actions
- "Add Plan" button → modal form
- Inline edit via modal
- Soft delete (deactivate) with confirmation

### 5. PPPoE Sessions (`/pppoe`)

- Ant Design `Table` with auto-refresh every 10 seconds (React Query `refetchInterval`)
- Data source: `GET /api/v1/pppoe/sessions` (live from Gateway Agent)
- Columns: Interface, Username, IP Address, MAC, State, Uptime, Rate Limit
- Action: "Kill Session" button with confirmation modal
- Status indicator: green dot for active sessions

### 6. Invoices (`/billing/invoices`)

- Ant Design `Table` with server-side pagination
- Columns: Invoice #, Customer, Amount (₱), Due Date, Status, Issued Date
- Status tags: pending (blue), paid (green), overdue (red), void (gray)
- Filter by status
- Note: Billing API endpoints don't exist yet — this page will show "No billing endpoints configured" until the billing API is built. Structure the page so it's ready to connect.

### 7. Payments (`/billing/payments`)

- Ant Design `Table`
- Columns: Payment #, Customer, Invoice #, Amount (₱), Method, Reference, Received By, Date
- "Record Payment" button → modal form
- Same note as Invoices — ready to connect when billing API exists.

### 8. Staff Users (`/system/users`)

- Ant Design `Table`
- Columns: Username, Email, Role (tag), Active (switch), Created
- "Add User" button → modal form
- Edit via modal
- Deactivate with confirmation (cannot deactivate self)
- Role column: colored tags (admin=teal, billing=amber, technician=blue-gray)

### 9. System Status (`/system/status`)

- Gateway health cards: CPU, RAM, Disk (from Gateway Agent `/agent/system/stats`)
- Auto-refresh every 5 seconds
- Progress bars with percentage
- If Gateway unreachable: show error card

### 10. Logs (`/system/logs`)

- Placeholder page with "Coming soon" message
- Will show system and auth logs when log API is built

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts          # Axios instance with JWT interceptor
│   │   ├── auth.ts            # Login, refresh, me
│   │   ├── customers.ts       # Customer CRUD + actions
│   │   ├── plans.ts           # Plan CRUD
│   │   ├── pppoe.ts           # Sessions
│   │   ├── users.ts           # Staff user CRUD
│   │   └── gateway.ts         # System stats
│   ├── components/
│   │   ├── Layout/
│   │   │   ├── AppLayout.tsx   # Sidebar + header + content shell
│   │   │   └── SideMenu.tsx    # Navigation menu
│   │   ├── StatusTag.tsx       # Colored status tags
│   │   └── StatCard.tsx        # Dashboard stat card
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx
│   │   ├── customers/
│   │   │   ├── CustomerList.tsx
│   │   │   └── CustomerDetail.tsx
│   │   ├── Plans.tsx
│   │   ├── PPPoESessions.tsx
│   │   ├── billing/
│   │   │   ├── Invoices.tsx
│   │   │   └── Payments.tsx
│   │   ├── system/
│   │   │   ├── Users.tsx
│   │   │   ├── SystemStatus.tsx
│   │   │   └── Logs.tsx
│   ├── hooks/
│   │   └── useAuth.ts         # Auth state, login, logout, token refresh
│   ├── routes.tsx             # Route definitions with auth guard
│   ├── theme.ts               # Ant Design theme tokens
│   ├── App.tsx
│   ├── main.tsx
│   └── vite-env.d.ts
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

## API Integration

**Authentication flow:**
1. Login → store `access_token` + `refresh_token` in localStorage
2. Axios interceptor adds `Authorization: Bearer <token>` to all requests
3. On 401 response: attempt token refresh, retry original request
4. On refresh failure: redirect to `/login`

**React Query patterns:**
- `useQuery` for data fetching with automatic caching
- `useMutation` for create/update/delete with cache invalidation
- PPPoE sessions: `refetchInterval: 10000` (10s auto-refresh)
- System stats: `refetchInterval: 5000` (5s auto-refresh)

## Docker / Deployment

**Development:**
- `frontend/` runs on Vite dev server (port 3000)
- Proxies API calls to backend (port 8000)

**Production:**
- `npm run build` → static files in `frontend/dist/`
- Served by the backend via FastAPI `StaticFiles` mount, or nginx
- No Node.js runtime needed on the appliance

**Dockerfile:**
```
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

## Scope Notes

- **Billing pages (Invoices, Payments):** UI structure built but no working API — shows empty state. Ready to connect when billing endpoints are implemented.
- **Logs page:** Placeholder only.
- **Dashboard traffic chart:** Static placeholder — real-time WebSocket data is a future feature.
- **Customer portal:** Separate sub-project, not included here.
