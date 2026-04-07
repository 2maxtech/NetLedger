# NetLedger Polish Batch — Design Spec

**Date:** 2026-04-07
**Goal:** Polish the app for PH ISP Facebook group launch — 9 features to improve first impressions and retention.

## 1. Demo Mode (Shared Read-Only)

**How it works:**
- A pre-seeded demo tenant exists in the database with realistic Filipino ISP data
- Landing page gets a "Try Demo" button that logs in as a demo user (read-only role)
- Demo user can browse all pages but cannot create/edit/delete anything
- Backend enforces read-only: demo user's POST/PUT/DELETE requests return 403
- Demo data: 1 router, 4 plans, 15 customers (mix of active/suspended/disconnected), invoices, payments, 2 areas

**Implementation:**
- New `is_demo` flag on User model
- Backend middleware: if `current_user.is_demo`, reject all mutating requests with "Demo mode — sign up for full access"
- Seed script to create demo tenant with realistic data
- Landing page: "Try Demo" button → POST /auth/demo-login → returns JWT → redirect to dashboard
- Demo banner at top of app: "You're in demo mode — [Sign Up] for full access"

## 2. HTML Email Templates

**Design:**
- Jinja2 HTML template with tenant branding (logo URL, company name, primary color)
- Single base template used by all email types (invoice, reminder, overdue, welcome)
- Header: tenant logo + company name
- Body: dynamic content per email type
- Footer: company name, "Powered by NetLedger" subtle text
- Responsive (works on mobile email clients)
- Inline CSS (email client compatibility)

**Template variables:** Same as existing notification templates ({customer_name}, {amount}, {plan_name}, {due_date}, {portal_url}) plus {company_name}, {logo_url}, {primary_color}

## 3. Onboarding Checklist (Dashboard Card)

**Checklist items:**
1. Add a router (check: routers count > 0)
2. Create a plan (check: plans count > 0)
3. Add customers (check: customers count > 0)
4. Configure billing (check: billing settings exist)
5. Set up notifications (check: SMTP or SMS configured)

**Behavior:**
- Shows as the first card on dashboard when any item is incomplete
- Each item shows check/unchecked with link to the relevant page
- Progress bar (e.g., "3/5 complete")
- "Dismiss" button to hide permanently (stored in app_settings)
- Backend endpoint: GET /api/v1/onboarding/status → returns completion state of each item

## 4. Mobile-Responsive Admin (Slide-Over Sidebar)

**Changes:**
- Sidebar hidden on mobile (< 768px), replaced with hamburger icon in header
- Hamburger tap opens sidebar as overlay with dark backdrop
- Tap backdrop or menu item to close
- Tables get horizontal scroll wrapper on mobile
- Stat cards stack properly (already using grid-cols responsive)
- Modal dialogs: full-width on mobile
- Touch-friendly: larger tap targets on buttons/links (min 44px)

## 5. Bulk Actions

**Customer List:**
- Checkbox column on each row + "Select All" header checkbox
- Floating action bar appears when 1+ selected: "X selected — [Generate Invoices] [Send Reminder] [Change Status]"
- Bulk generate invoices: creates invoices for selected customers
- Bulk send reminder: sends SMS/email to selected
- Bulk change status: dropdown to set active/suspended/disconnected

**Invoice List:**
- Same checkbox pattern
- Actions: [Mark as Paid] [Send Notification]
- Bulk mark paid: sets status to paid with today's date
- Bulk send notification: sends invoice email/SMS to each

## 6. CSV Export

**Pages with export button:**
- Customer list → customers.csv (name, email, phone, pppoe_username, plan, status, area, created_at)
- Invoice list → invoices.csv (customer_name, amount, status, due_date, paid_date, created_at)
- Payments → payments.csv (customer_name, invoice_id, amount, method, date)
- Active sessions → sessions.csv (username, ip, mac, uptime, router, bytes_in, bytes_out)

**Implementation:**
- Backend: GET endpoints with `?format=csv` query param, returns Content-Disposition: attachment
- Frontend: "Export CSV" button in page header, triggers download

## 7. Empty States with CTAs

**Pattern for all list pages:**
- When data is empty, show: icon/illustration + descriptive text + primary action button
- Examples:
  - Customers: people icon + "No customers yet" + [Import from MikroTik] [Add Customer]
  - Routers: server icon + "Connect your first router" + [Add Router]
  - Invoices: receipt icon + "No invoices generated" + [Generate Invoices]
  - Plans: layers icon + "Create your first plan" + [Add Plan]
  - Areas: map-pin icon + "Organize customers by area" + [Create Area]

**Use inline SVG icons** — no external dependencies. Keep it simple, not overly illustrated.

## 8. PWA Manifest

**Files:**
- manifest.json: app name, short_name, icons (192, 512), theme_color (#e8700a), background_color (#1a1a2e), display: standalone
- Icons: generate from existing logo-2.png (192x192, 512x512)
- Link in index.html: `<link rel="manifest" href="/manifest.json">`
- Meta tags: theme-color, apple-mobile-web-app-capable

**No service worker for offline** — just the manifest for "Add to Home Screen" capability. Keep it simple.

## 9. Loading Skeletons

**Replace spinners on:**
- Dashboard (stat cards, chart, router cards, payments list)
- Customer list (table rows)
- Invoice list (table rows)
- Customer detail (info card, tabs)
- All other list pages

**Skeleton pattern:**
- Animated pulse (already used in portal: `animate-pulse`)
- Match the shape of the actual content (rectangles for text, circles for avatars, bars for stats)
- Show for the same duration as current spinners (until data loads)

## Non-Goals

- No offline support (PWA is just for home screen install)
- No push notifications (future)
- No real-time WebSocket updates (future)
- Demo mode is read-only only — no temporary sandboxes
