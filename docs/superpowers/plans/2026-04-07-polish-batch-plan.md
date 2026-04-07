# NetLedger Polish Batch — Implementation Plan

**Spec:** docs/superpowers/specs/2026-04-07-polish-batch-design.md
**Approach:** Group into parallel streams by dependency. Backend-first where frontend depends on new APIs.

---

## Stream 1: Quick Wins (no backend changes)

### Task 1: PWA Manifest
**Files:** `frontend/public/manifest.json`, `frontend/index.html`
- Create `manifest.json` with name "NetLedger", icons (192, 512), theme_color #e8700a, background_color #1a1a2e, display standalone, start_url /
- Generate 512x512 icon from existing logo-2.png (use the same file, it scales)
- Add `<link rel="manifest">` and meta tags to index.html
- Test: "Add to Home Screen" on Chrome mobile

### Task 2: Loading Skeletons
**Files:** `frontend/src/components/SkeletonTable.vue` (new), `frontend/src/components/SkeletonCard.vue` (new), update Dashboard.vue, CustomerList.vue, Invoices.vue, Plans.vue, Payments.vue, ActiveUsers.vue, Routers.vue, Areas.vue, Tickets.vue
- Create reusable SkeletonTable component (accepts cols/rows count, renders animate-pulse rows)
- Create reusable SkeletonCard component (for dashboard stat cards)
- Replace all `<div class="animate-spin">` loading states with skeleton components
- Use existing pattern from PortalDashboard.vue as reference

### Task 3: Empty States
**Files:** `frontend/src/components/EmptyState.vue` (new), update all list pages
- Create reusable EmptyState component: props for icon (SVG name), title, description, action label, action route
- Inline SVG icons: people, server, receipt, layers, map-pin, ticket, wifi
- Replace all `<td colspan>No X found</td>` with EmptyState component
- Each page passes relevant CTA (e.g., Customers → "Import from MikroTik" + "Add Customer")

### Task 4: Mobile Responsive Sidebar
**Files:** `frontend/src/components/layout/AppLayout.vue`, `frontend/src/components/layout/Sidebar.vue`
- Add `isMobile` reactive ref (window.innerWidth < 768, listen to resize)
- Mobile: hide sidebar, show hamburger icon in header
- Hamburger click: slide sidebar in from left as overlay (absolute/fixed positioning, z-50)
- Dark backdrop behind sidebar (click to close)
- Close sidebar on route change
- Add `overflow-x-auto` wrapper to all table containers (scan all pages)
- Test on Chrome DevTools mobile viewport

---

## Stream 2: Backend APIs + Frontend

### Task 5: CSV Export — Backend
**Files:** `backend/app/api/admin/customers.py`, `backend/app/api/admin/billing.py`, `backend/app/api/admin/payments.py`, `backend/app/api/admin/sessions.py`
- Add `format` query param to existing list endpoints
- When `format=csv`: build CSV with Python's `csv` module + `io.StringIO`
- Return `StreamingResponse` with `Content-Disposition: attachment; filename="customers.csv"`
- Fields per export:
  - Customers: name, email, phone, pppoe_username, plan_name, status, area_name, created_at
  - Invoices: customer_name, amount, status, due_date, paid_date, created_at
  - Payments: customer_name, amount, method, date
  - Active Sessions: username, ip, mac, uptime, router_name, bytes_in, bytes_out

### Task 6: CSV Export — Frontend
**Files:** `frontend/src/pages/customers/CustomerList.vue`, `frontend/src/pages/Invoices.vue`, `frontend/src/pages/Payments.vue`, `frontend/src/pages/ActiveUsers.vue`
- Add "Export CSV" button in page header (next to search/filter)
- On click: window.open or anchor download to the API endpoint with `?format=csv` + auth token
- Use current filter params (status, search) so export matches what's on screen

### Task 7: Bulk Actions — Backend
**Files:** `backend/app/api/admin/customers.py`, `backend/app/api/admin/billing.py`
- POST `/customers/bulk/generate-invoices` — body: `{ customer_ids: [...] }`, generates invoices for each
- POST `/customers/bulk/send-reminder` — body: `{ customer_ids: [...] }`, sends SMS/email reminder
- POST `/customers/bulk/change-status` — body: `{ customer_ids: [...], status: "suspended" }`
- POST `/billing/invoices/bulk/mark-paid` — body: `{ invoice_ids: [...] }`
- POST `/billing/invoices/bulk/send-notification` — body: `{ invoice_ids: [...] }`
- Each endpoint validates tenant ownership, returns `{ success: N, failed: N, errors: [...] }`

### Task 8: Bulk Actions — Frontend
**Files:** `frontend/src/pages/customers/CustomerList.vue`, `frontend/src/pages/Invoices.vue`
- Add checkbox column (first col) with header "Select All" checkbox
- Track `selectedIds` ref (Set)
- Floating action bar: fixed bottom bar appears when selectedIds.size > 0
- Bar shows: "X selected" + action buttons
- Each action: confirm dialog → call bulk API → refresh list → clear selection
- Customer list actions: Generate Invoices, Send Reminder, Change Status (dropdown)
- Invoice list actions: Mark as Paid, Send Notification

### Task 9: Onboarding Checklist — Backend
**Files:** `backend/app/api/admin/onboarding.py` (new)
- GET `/onboarding/status` — returns:
  ```json
  {
    "has_router": true/false,
    "has_plan": true/false,
    "has_customer": true/false,
    "has_billing_config": true/false,
    "has_notifications": true/false,
    "dismissed": true/false,
    "completed": 3,
    "total": 5
  }
  ```
- POST `/onboarding/dismiss` — sets dismissed flag in app_settings
- Queries: simple count checks (SELECT COUNT(*) > 0 FROM routers WHERE owner_id=...)

### Task 10: Onboarding Checklist — Frontend
**Files:** `frontend/src/pages/Dashboard.vue`
- New OnboardingCard component at top of dashboard
- Fetches GET /onboarding/status on mount
- Shows only if not dismissed AND not all complete
- Each item: checkbox icon + label + link to page (e.g., "Add a router" → /routers)
- Progress bar with "3/5 complete"
- Dismiss button (X) → POST /onboarding/dismiss
- Smooth transition when dismissing

### Task 11: Demo Mode — Backend
**Files:** `backend/app/api/auth.py`, `backend/app/core/demo.py` (new), `backend/app/scripts/seed_demo.py` (new)
- Add `is_demo` boolean field to User model (default False)
- POST `/auth/demo-login` (public) — returns JWT for the demo user
- Demo guard middleware: if user.is_demo and method in (POST, PUT, DELETE, PATCH), return 403 "Demo mode — sign up for full access" (except /auth/ endpoints)
- Seed script: creates demo tenant with:
  - Company: "Sample ISP" 
  - 1 router (simulated, no real MikroTik connection)
  - 4 plans: 5Mbps ₱599, 10Mbps ₱799, 20Mbps ₱1,299, 50Mbps ₱1,999
  - 15 customers with Filipino names, mix of statuses
  - Invoices for current month (paid, pending, overdue)
  - Payments for paid invoices
  - 2 areas: "Brgy. San Isidro", "Brgy. Maligaya"
- Run seed on startup if demo user doesn't exist

### Task 12: Demo Mode — Frontend
**Files:** `frontend/src/pages/Landing.vue`, `frontend/src/components/layout/AppLayout.vue`
- Landing page: "Try Demo" button next to "Join the Beta"
- On click: POST /auth/demo-login → store token → redirect to /dashboard
- Demo banner: fixed top bar (orange/yellow) "You're exploring the demo — [Sign Up Free] to manage your ISP"
- Banner shown when user.is_demo (check from JWT or user endpoint)
- All mutating actions show toast "Demo mode — sign up for full access" on 403

### Task 13: HTML Email Templates — Backend
**Files:** `backend/app/templates/email_base.html` (new), `backend/app/services/notification.py`, `backend/app/services/billing.py`
- Create Jinja2 HTML base template:
  - Header: logo (from branding URL or default), company name, colored accent bar
  - Body: slot for content
  - Footer: company name, "Powered by NetLedger", unsubscribe placeholder
  - All CSS inline (email compatibility)
  - Responsive (max-width 600px, mobile-friendly)
- Create content templates: invoice_email.html, reminder_email.html, overdue_email.html
- Update notification.py send_email_tenant() to render HTML template with tenant branding
- Fetch branding settings (logo_url, company_name, primary_color) and pass to template
- Keep plain text as fallback (multipart/alternative)

---

## Execution Order

**Phase 1 — Quick wins (parallel, no dependencies):**
Tasks 1, 2, 3, 4 — PWA, Skeletons, Empty States, Mobile

**Phase 2 — Backend APIs (parallel):**
Tasks 5, 7, 9, 11, 13 — CSV backend, Bulk backend, Onboarding backend, Demo backend, HTML emails

**Phase 3 — Frontend integration (depends on Phase 2):**
Tasks 6, 8, 10, 12 — CSV frontend, Bulk frontend, Onboarding frontend, Demo frontend

**Phase 4 — Deploy + test:**
- Push all changes
- Deploy to Hetzner
- Test demo mode end-to-end
- Test mobile on real phone
- Verify emails render correctly

---

## Estimated Task Breakdown

| Task | Effort | Dependencies |
|------|--------|-------------|
| 1. PWA Manifest | Small | None |
| 2. Loading Skeletons | Medium | None |
| 3. Empty States | Medium | None |
| 4. Mobile Sidebar | Medium | None |
| 5. CSV Export Backend | Small | None |
| 6. CSV Export Frontend | Small | Task 5 |
| 7. Bulk Actions Backend | Medium | None |
| 8. Bulk Actions Frontend | Medium | Task 7 |
| 9. Onboarding Backend | Small | None |
| 10. Onboarding Frontend | Small | Task 9 |
| 11. Demo Mode Backend | Medium | None |
| 12. Demo Mode Frontend | Small | Task 11 |
| 13. HTML Email Templates | Medium | None |
