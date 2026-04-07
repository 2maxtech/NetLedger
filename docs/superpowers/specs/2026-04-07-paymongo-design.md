# PayMongo Integration — Design Spec

**Date:** 2026-04-07
**Goal:** Enable ISP customers to pay invoices online via GCash, Maya, or Card through PayMongo Checkout.

## Overview

Each tenant (ISP operator) signs up for their own PayMongo account and configures API keys in NetLedger. Customer payments go directly to the tenant's PayMongo account — NetLedger never touches the money.

## Payment Methods

- GCash
- Maya (PayMaya)
- Visa / Mastercard (credit + debit)

## Payment Flow

1. Invoice generated → SMS/email notification includes unique payment link
2. Customer clicks link → public payment page shows invoice summary
3. Customer clicks "Pay Now" → backend creates PayMongo Checkout Session
4. Customer redirected to PayMongo-hosted checkout (selects GCash/Maya/Card)
5. Payment completes → PayMongo sends webhook to backend
6. Backend verifies webhook signature → records payment → marks invoice paid
7. If customer was throttled/disconnected, auto-reconnect triggers
8. Customer sees success page

## Payment Link (Public)

- URL format: `{base_url}/pay/{payment_token}`
- `payment_token` is a unique UUID generated per invoice
- Page shows: tenant logo/company name, customer name, plan, amount, fee breakdown, total
- "Pay Now" button creates checkout session
- After payment: success page with confirmation
- Link becomes inactive when invoice is paid or voided
- No login required

## Portal Integration

- Customer portal dashboard: "Pay Now" button on unpaid invoices
- Same backend flow — creates checkout session, redirects to PayMongo
- Returns to portal after payment

## PayMongo API

- **API version:** Use Checkout Sessions API (v1)
- **Base URL:** `https://api.paymongo.com/v1`
- **Auth:** Basic auth with secret key (base64 encoded)
- **Checkout Session:** POST /checkout_sessions
  - `line_items`: invoice amount + optional convenience fee
  - `payment_method_types`: ["gcash", "paymaya", "card"]
  - `success_url`: redirect after payment
  - `cancel_url`: redirect on cancel
  - `reference_number`: invoice ID for reconciliation
  - `description`: "Invoice for {plan_name} - {customer_name}"
- **Webhook:** POST from PayMongo when payment succeeds
  - Verify signature using webhook signing secret
  - Event type: `checkout_session.payment.paid`
  - Extract checkout session ID, match to invoice

## Fee Handling

- Configurable per tenant: `paymongo_fee_mode` ("absorb" or "pass_to_customer")
- Default: "pass_to_customer"
- GCash/Maya fee: ~2.5% + ₱15 (we calculate this, not hardcoded — read from setting)
- Card fee: ~3.5% + ₱15
- If pass_to_customer: add fee to checkout amount, display breakdown on payment page
- If absorb: checkout amount = invoice amount, ISP receives less after PayMongo cut
- `convenience_fee` stored on Payment record for bookkeeping

## Settings UI (Tenant)

- New "Payments" tab in Settings (between Billing and SMTP)
- Fields:
  - PayMongo Secret Key (password field, masked)
  - PayMongo Public Key (text field)
  - Webhook Signing Secret (password field, masked)
  - Fee Mode: radio — "Customer pays convenience fee" / "We absorb the fee"
  - Fee percentage: number input (default 2.5)
  - Fee flat amount: number input (default 15)
- "Test Connection" button → calls PayMongo API to verify keys are valid
- Help text: "Sign up at paymongo.com to get your API keys"

## Database Changes

### Invoice model
- Add `payment_token: UUID | None` — unique token for public payment link, generated on invoice creation

### Payment model
- Add `paymongo_checkout_id: str | None` — PayMongo checkout session ID
- Add `convenience_fee: Decimal | None` — fee charged on top of invoice amount

### App Settings (per tenant)
- `paymongo_secret_key`
- `paymongo_public_key`
- `paymongo_webhook_secret`
- `paymongo_fee_mode` ("absorb" | "pass_to_customer")
- `paymongo_fee_percent` (default "2.5")
- `paymongo_fee_flat` (default "15")

## Webhook Endpoint

- `POST /api/v1/webhooks/paymongo` — public (no auth), verified by signature
- PayMongo signs webhooks with HMAC-SHA256
- Verify: compute HMAC of raw body with webhook secret, compare to `Paymongo-Signature` header
- Process `checkout_session.payment.paid` event:
  1. Extract checkout session ID
  2. Find Payment record by `paymongo_checkout_id`
  3. If already processed (idempotent check), return 200
  4. Record payment via existing `billing_service.record_payment()`
  5. This handles auto-reconnect, status updates, audit logging
  6. Return 200

## API Endpoints

### Public
- `GET /pay/{payment_token}` — returns invoice details for payment page (no auth)
- `POST /pay/{payment_token}/checkout` — creates PayMongo checkout session, returns redirect URL
- `POST /api/v1/webhooks/paymongo` — webhook receiver
- `GET /pay/{payment_token}/success` — success page after payment
- `GET /pay/{payment_token}/cancel` — cancel/return page

### Admin (authenticated)
- `GET /api/v1/settings/payments` — get PayMongo config
- `PUT /api/v1/settings/payments` — save PayMongo config
- `POST /api/v1/settings/payments/test` — test PayMongo connection

## Frontend Pages

### Payment Page (public, new route)
- `/pay/:token` — Vue page, no app layout (standalone like portal login)
- Fetches invoice details from `GET /pay/{token}`
- Shows: ISP branding, invoice summary, fee breakdown, total, "Pay Now" button
- On click: calls `POST /pay/{token}/checkout`, redirects to PayMongo URL
- Success/cancel pages: simple status with "Return to Portal" link

### Settings → Payments Tab
- API key fields, fee mode toggle, test connection button
- Only shown when PayMongo keys are not empty: payment link info

### Portal Dashboard
- "Pay Now" button on unpaid invoices (only if tenant has PayMongo configured)
- Same checkout flow

## Visibility Rules

- If tenant has NOT configured PayMongo keys:
  - No payment links in SMS/email
  - No Pay Now buttons in portal
  - Settings → Payments tab still accessible (to configure)
- If configured:
  - Payment links included in invoice notifications
  - Pay Now buttons appear in portal

## Non-Goals

- Partial payments (full invoice only)
- Refunds through NetLedger (use PayMongo dashboard)
- Payment history sync from PayMongo (we track our own)
- Recurring/auto-debit payments (future)
- BillEase, GrabPay, or other payment methods (future)
