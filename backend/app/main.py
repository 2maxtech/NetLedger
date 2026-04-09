import os
import app.models  # noqa: F401 — ensures all models are registered in SQLAlchemy mapper
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.admin.customers import router as customers_router
from app.api.admin.plans import router as plans_router
from app.api.admin.billing import router as billing_router
from app.api.admin.network import router as network_router
from app.api.portal import router as portal_router
from app.api.admin.users import router as users_router, org_router as organizations_router
from app.api.auth import router as auth_router
from app.api.admin.routers import router as routers_router
from app.api.admin.areas import router as areas_router
from app.api.admin.expenses import router as expenses_router
from app.api.admin.settings import router as settings_router
from app.api.admin.vouchers import router as vouchers_router
from app.api.admin.tickets import router as tickets_router
from app.api.admin.ipam import router as ipam_router
from app.api.admin.audit import router as audit_router
from app.api.admin.vpn import router as vpn_router
from app.api.admin.libreqos import router as libreqos_router
from app.api.admin.onboarding import router as onboarding_router
from app.api.admin.support import router as support_router
from app.api.admin.system import router as system_router
from app.api.setup import router as setup_router
from app.api.payment import router as payment_router
from app.api.chat import router as chat_router
from app.api.notice import router as notice_router
from app.core.config import settings

from app.core.demo_guard import DemoGuardMiddleware
from app.core.rate_limit import RateLimitMiddleware

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_PREFIX}/openapi.json")


@app.on_event("startup")
async def create_tables():
    """Auto-create database tables on startup if they don't exist."""
    from app.core.database import engine
    from app.models.base import Base
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Auto-add permissions column if missing (existing installs)
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions JSONB DEFAULT '[]'"
        ))

    # Seed demo tenant (skips if already present)
    from app.scripts.seed_demo import seed_demo_data
    await seed_demo_data()

# Build allowed origins based on deployment mode
_allowed_origins = ["https://netl.2max.tech", "http://localhost", "http://localhost:5173"]
if settings.DEPLOYMENT_MODE == "onpremise":
    _allowed_origins = ["*"]  # On-premise: admin controls their own network

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware, rate_limit=10, window=60)  # 10 attempts per minute on auth
app.add_middleware(DemoGuardMiddleware)  # Block mutating requests for demo users

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(plans_router, prefix=settings.API_V1_PREFIX)
app.include_router(customers_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
app.include_router(billing_router, prefix=settings.API_V1_PREFIX)
app.include_router(network_router, prefix=settings.API_V1_PREFIX)
app.include_router(routers_router, prefix=settings.API_V1_PREFIX)
app.include_router(areas_router, prefix=settings.API_V1_PREFIX)
app.include_router(portal_router, prefix=settings.API_V1_PREFIX)
app.include_router(expenses_router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_router, prefix=settings.API_V1_PREFIX)
app.include_router(vouchers_router, prefix=settings.API_V1_PREFIX)
app.include_router(tickets_router, prefix=settings.API_V1_PREFIX)
app.include_router(ipam_router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_router, prefix=settings.API_V1_PREFIX)
app.include_router(organizations_router, prefix=settings.API_V1_PREFIX)
if settings.DEPLOYMENT_MODE != "onpremise":
    app.include_router(vpn_router, prefix=settings.API_V1_PREFIX)
app.include_router(libreqos_router, prefix=settings.API_V1_PREFIX)
app.include_router(setup_router, prefix=settings.API_V1_PREFIX)
app.include_router(onboarding_router, prefix=settings.API_V1_PREFIX)
app.include_router(support_router, prefix=settings.API_V1_PREFIX)
app.include_router(system_router, prefix=settings.API_V1_PREFIX)
app.include_router(payment_router, prefix=settings.API_V1_PREFIX)
app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
app.include_router(notice_router, prefix=settings.API_V1_PREFIX)


# Serve uploaded files
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/api/v1/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get(f"{settings.API_V1_PREFIX}/releases/latest")
async def latest_release():
    """Public endpoint for on-premise installations to check for updates."""
    return {
        "version": settings.APP_VERSION,
        "release_notes": "Latest release of NetLedger",
        "release_date": "2026-04-06",
        "download_url": "https://github.com/2maxtech/NetLedger/releases/latest",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring services (UptimeRobot, etc.)."""
    from app.core.database import engine
    from datetime import datetime, timezone

    health = {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Check database connectivity
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["database"] = "ok"
    except Exception:
        health["database"] = "error"
        health["status"] = "degraded"

    # Check Redis connectivity
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        health["redis"] = "ok"
    except Exception:
        health["redis"] = "error"
        health["status"] = "degraded"

    return health
