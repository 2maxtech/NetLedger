# 2maXnetBill — project notes for Claude

## What this is

Multi-tenant SaaS ISP billing + network management app. FastAPI backend, Vue 3 + Tailwind frontend, Postgres, Redis, Celery (worker + beat), Caddy reverse proxy. Integrates with MikroTik RouterOS via REST for PPPoE secret management, profile changes, simple queue control, and NAT redirects for payment-notice pages. Also does PayMongo for PH payments, WireGuard VPN onboarding, and an on-premise install variant.

Target customer: small-to-medium Philippine ISPs / WISPs running MikroTik. Keep PH context in mind for pricing formats, peso amounts, provincial addresses, PPPoE-heavy setups.

## Deploy

Source of truth is GitHub. The live VPS pulls from main and rebuilds:

```bash
ssh root@157.180.72.253
cd 2maXnetBill
git pull
docker compose up -d --build backend celery-worker   # or any service that changed
```

- Domain: `https://netl.2max.tech` (Caddy reverse proxy on the same host)
- Deploy is the user's call — **never `docker compose pull`/rebuild on the VPS without being asked**. Always commit + push to GitHub; let the user trigger the deploy.
- If `docker compose up` recreates `db` or `redis` as a side effect, the data volume (`pgdata`, `uploads`) persists — so no data loss, but **all services that depend on those will also recreate**, which can expose env drift (see below).

## Secrets live outside git

`.env` (on the VPS, `.gitignore`d) + `docker-compose.override.yml` (also `.gitignore`d) hold real credentials. The committed `docker-compose.yml` now requires `DB_PASSWORD` via `${DB_PASSWORD:?...}` so a fresh rebuild fails fast instead of silently running with a wrong default.

If you're setting up a new deploy, copy `.env.production.example` to `.env` on the host and fill it in. The existing VPS already has its `.env`/override in place — don't regenerate or rotate without deliberate intent (altering the Postgres user password breaks the running deploy).

Known leftover secrets still hardcoded in the committed `docker-compose.yml` (tech debt, not my job to fix unless the user asks):
- `SECRET_KEY: dev-secret-key-not-for-production` — JWT signing key; rotating will log every user out.
- `MIKROTIK_URL` / `MIKROTIK_USER` / `MIKROTIK_PASSWORD` — defaults pointing at the lab CHR; real tenants override via the UI.

## Proxmox lab

- Host: `192.168.88.99` (root, SSH key auth works from the user's laptop)
- **VM 111 `mikrotik-chr` (IP 192.168.40.30) is LIVE — bar23me's paying customers authenticate against it.** Read-only only. Never create/disable queues, kick sessions, or disable secrets against it. For live testing of throttle/disconnect flows, ask the user to clone VM 111 or spin up a fresh CHR with no uplink.
- CT 104 `pppoe-test-client` (IP 192.168.40.50) is a lab PPPoE client used for throttle verification.

## MikroTik integration gotchas

- Per-user **simple queues** shadow PPP profile rate-limits. The app now disables/re-enables matching queues on throttle/disconnect/reconnect (see `mikrotik.py::disable_user_queues` / `enable_user_queues`). Without this, changing a secret's profile to "throttle" has no observable effect for customers whose MT admin pre-configured per-user queues.
- PPP profile rate-limit changes only take effect on **new** sessions — every throttle/disconnect path must also call `kick_session` to force reconnect.
- `/ppp/secret` with `disabled=yes` + `kick_session` is the disconnect primitive. For throttle it's `ensure_profile` → `update_secret(profile=throttle)` → `disable_user_queues` → `kick_session`.

## Testing

- Unit tests: `cd backend && python -m pytest tests/test_mikrotik.py --no-header --noconftest -q` (the full conftest pulls in weasyprint, which needs GTK on Windows — use docker for the E2E suite).
- E2E suite: lives in `backend/tests/test_customers.py`, `backend/e2e/...` — runs in docker.
- There's a pre-existing failing unit test `test_disable_secret_sends_correct_patch` (expects a single `_request` call but `disable_secret` now also kicks sessions). Unrelated to any recent change; low priority.
- Live-router verification: `test_throttle_queue.sh` at repo root. Requires a non-live MT target (see Proxmox lab note above).

## Style / process preferences

- Commits include `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- Always push to GitHub after committing. Do not deploy to the VPS unprompted.
- Per-user CLAUDE.md at `~/.claude/CLAUDE.md` sets the tone — anticipate downstream effects, debug thoroughly, no slash-command proliferation.
